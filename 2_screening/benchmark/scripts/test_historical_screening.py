"""Offline regression checks for importing historical screening decisions."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from compare_results import (
    benchmark_labels,
    historical_baseline,
    historical_model_metrics,
)
from historical_screening import (
    HistoricalRun,
    extract_original_choice,
    historical_runs,
    raw_historical_records,
    verify_historical_choices,
)
from run_screening import FOLDER
from screening_api import decision_from


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


if __name__ == "__main__":
    unittest.main()
