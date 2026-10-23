"""Offline regression checks for screening and historical decision imports."""

import argparse
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from compare_results import (
    benchmark_labels,
    historical_baseline,
    historical_model_metrics,
    model_metrics,
)
from historical_screening import (
    HistoricalRun,
    extract_original_choice,
    historical_runs,
    raw_historical_records,
    verify_historical_choices,
)
from merge_results import check_coverage, collect_predictions
from run_screening import FOLDER, native_result, validate_saved, write_model
from screening_api import MODELS, NATIVE_REVISIONS, decision_from


class HistoricalScreeningTests(unittest.TestCase):
    """Use the committed evidence and isolated files, e.g. python -m unittest discover."""

    labels: ClassVar[dict[str, dict[str, str]]]
    runs: ClassVar[dict[str, HistoricalRun]]
    expected_ids: ClassVar[set[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.labels = benchmark_labels()
        cls.runs = historical_runs(FOLDER.parents[1], set(cls.labels))
        cls.expected_ids = set(cls.labels)

    def test_every_cached_choice_matches_its_raw_response(self) -> None:
        for run in self.runs.values():
            self.assertEqual(set(run.choices), self.expected_ids)
            self.assertEqual(len(run.choices), 595)
            self.assertTrue(run.metadata["source_sha256"])

    def test_gemini_doubt_counts_as_inclusion_without_changing_the_original(
        self,
    ) -> None:
        run = self.runs["historical-gemini"]
        metric = historical_model_metrics(run, self.labels)
        self.assertEqual(run.choices["2429"], "doubt")
        self.assertEqual(metric["doubt_inclusion_ids"], ["2429"])
        self.assertEqual(metric["valid"], 595)
        self.assertEqual(metric["technical_errors"], 0)
        self.assertTrue(metric["complete"])
        self.assertEqual(metric["retained"], 329)
        self.assertEqual(metric["recorded_choice_counts"]["doubt"], 1)

    def test_unanimous_baseline_also_counts_doubt_as_inclusion(self) -> None:
        labels = {"1": {"label": "include"}, "2": {"label": "exclude"}}
        runs = {
            "openai": HistoricalRun({"1": "include", "2": "include"}, {}),
            "anthropic": HistoricalRun({"1": "include", "2": "include"}, {}),
            "gemini": HistoricalRun({"1": "include", "2": "doubt"}, {}),
        }
        metric = historical_baseline(labels, runs)
        self.assertTrue(metric["complete"])
        self.assertEqual(metric["true_inclusions"], 1)
        self.assertEqual(metric["false_inclusions"], 1)

    def test_original_sonnet_parser_recovers_decisions_before_truncated_rationale(
        self,
    ) -> None:
        text = '```json\n{"decision":"include"}\n```\nAn unfinished explanation'
        self.assertEqual(extract_original_choice(text), ("include", "json"))
        incomplete = '```json\n{"decision":"exclude", "reason": ['
        self.assertEqual(
            extract_original_choice(incomplete), ("exclude", "decision_field_recovery")
        )
        run = self.runs["historical-anthropic"]
        self.assertEqual(run.metadata["truncated_responses"], 519)
        self.assertEqual(run.metadata["decision_field_recovery_ids"], ["3128"])

    def test_raw_cache_mismatch_is_rejected(self) -> None:
        path = FOLDER.parent / "results/openai-batch-001.jsonl"
        raw = raw_historical_records([path], {"1"})
        with self.assertRaisesRegex(ValueError, "expected gpt-5.4"):
            verify_historical_choices(
                "openai", "gpt-5.4-2026-03-05", raw, {"1": "exclude"}
            )

    def test_duplicate_and_missing_historical_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "responses.jsonl"
            path.write_text((json.dumps({"custom_id": "1"}) + "\n") * 2)
            with self.assertRaisesRegex(ValueError, "one historical response"):
                raw_historical_records([path], {"1"})
            with self.assertRaisesRegex(ValueError, "expected all 1 IDs"):
                raw_historical_records([], {"1"})

    def test_current_qwen_parser_still_rejects_truncated_responses(self) -> None:
        response = {
            "choices": [{"finish_reason": "length", "message": {"content": "include"}}]
        }
        with self.assertRaisesRegex(ValueError, "expected stop"):
            decision_from("qwen", response)


class FakeNativeModel:
    def __init__(self, response):
        self.response = response

    def predict(self, body):
        return self.response


class FailedNativeModel:
    def predict(self, body):
        raise RuntimeError("Synthetic inference failure")


class ScreeningTests(unittest.TestCase):
    """Validate the common path for HTTP and native model evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.labels = benchmark_labels()
        cls.prompt = (FOLDER / "prompt.txt").read_text().strip()
        cls.rows = collect_predictions([FOLDER / "results/predictions.jsonl"])
        cls.examples = {
            model: next(row for row in cls.rows if row["model"] == model)
            for model in MODELS
        }

    def test_all_saved_models_use_the_same_validated_predictions_file(self) -> None:
        self.assertEqual(len(self.rows), 4760)
        self.assertEqual(len(self.examples), 8)
        check_coverage(self.rows)

    def test_native_saved_settings_and_revisions_are_checked(self) -> None:
        for model in NATIVE_REVISIONS:
            original = self.examples[model]
            for field, value in (
                ("revision", "changed"),
                ("repository", "changed"),
                ("settings", {}),
            ):
                with self.subTest(model=model, field=field):
                    row = copy.deepcopy(original)
                    row[field] = value
                    with self.assertRaisesRegex(
                        ValueError, "incompatible saved model settings"
                    ):
                        validate_saved(row, self.labels[row["record_id"]], self.prompt)

    def test_mixed_backend_chunks_reject_duplicates(self) -> None:
        rows = [self.examples["jev"], self.examples["gemma"]]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "predictions.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.assertEqual(len(collect_predictions([path])), 2)
            with self.assertRaisesRegex(ValueError, "duplicate prediction"):
                collect_predictions([path, path])
            with self.assertRaisesRegex(ValueError, "expected 595 records"):
                check_coverage(rows)

    def test_incomplete_http_and_native_models_have_coverage_only(self) -> None:
        for model in ("jev", "gemma"):
            with self.subTest(model=model):
                metric = model_metrics([self.examples[model]], self.labels, model)
                self.assertFalse(metric["complete"])
                self.assertEqual(metric["missing_binary_decisions"], 594)
                self.assertNotIn("recall", metric)

    def test_native_runtime_and_failures_are_preserved(self) -> None:
        runtime = {"startup_seconds": 1.5}
        valid = native_result(
            "llama",
            {},
            FakeNativeModel({"finish_reason": "stop", "content": "Include"}),
            runtime,
        )
        self.assertEqual(valid["decision"], "include")
        self.assertEqual(valid["runtime"], runtime)
        for native in (
            FakeNativeModel({"finish_reason": "length", "content": "include"}),
            FailedNativeModel(),
        ):
            with self.subTest(native=type(native).__name__):
                failed = native_result("llama", {}, native, runtime)
                self.assertEqual(failed["status"], "error")
                self.assertIsNone(failed["decision"])
                self.assertIn("error", failed)
                self.assertGreaterEqual(failed["seconds"], 0)

    def test_common_runner_writes_native_evidence(self) -> None:
        runtime = {"startup_seconds": 1.5}
        native = FakeNativeModel({"finish_reason": "stop", "content": "exclude"})
        args = argparse.Namespace(
            execute=True, completed=None, limit=1, revision=None, url=None
        )
        output = io.StringIO()
        paper = self.labels[self.examples["gemma"]["record_id"]]
        with patch("run_screening.load_native_model", return_value=(native, runtime)):
            self.assertEqual(
                write_model(args, "gemma", [paper], self.prompt, "", output), (1, 0)
            )
        row = json.loads(output.getvalue())
        self.assertEqual(row["runtime"], runtime)
        self.assertEqual(row["revision"], NATIVE_REVISIONS["gemma"])
        self.assertEqual(row["decision"], "exclude")
        validate_saved(row, paper, self.prompt)

    def test_common_runner_previews_all_backends_and_skips_saved_records(self) -> None:
        command = [sys.executable, str(FOLDER / "scripts/run_screening.py")]
        preview = subprocess.run(
            [*command, "--dry-run", "--limit", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = [json.loads(line) for line in preview.stdout.splitlines()]
        self.assertEqual({row["model"] for row in rows}, set(MODELS))
        self.assertTrue(all(row["dry_run"] for row in rows))
        resumed = subprocess.run(
            [
                *command,
                "--dry-run",
                "--completed",
                str(FOLDER / "results/predictions.jsonl"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resumed.stdout, "")
        self.assertIn("Prepared 0 requests", resumed.stderr)
        smoke = subprocess.run(
            [*command, "--model", "gemma", "--dry-run", "--smoke-test"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            {json.loads(line)["record_id"] for line in smoke.stdout.splitlines()},
            {"synthetic-hpc", "synthetic-history"},
        )


if __name__ == "__main__":
    unittest.main()
