"""Validate and score additional open-weight model runs without model requests."""

import argparse
import hashlib
import json
from pathlib import Path

from compare_results import benchmark_labels, request_timings, score_predictions
from run_extensions import MODELS, validate_saved
from run_screening import FOLDER, screening_records
from screening_api import JSON

NAMES = {
    "llama": "Llama-3.1-8B-Instruct",
    "gemma": "Gemma 4 12B",
    "pplx-flash": "Perplexity Decider Flash v1.2",
}


def collect_predictions(paths: list[Path]) -> list[dict[str, JSON]]:
    papers = {paper["record_id"]: paper for paper in screening_records()}
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    rows = []
    seen = set()
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            model, rid = row["model"], row["record_id"]
            if model not in MODELS or rid not in papers or (model, rid) in seen:
                raise ValueError(f"{path}: unknown or duplicate prediction {model}/{rid}")
            validate_saved(row, papers[rid], prompt)
            rows.append(row)
            seen.add((model, rid))
    return rows


def comparison_summary(paths: list[Path]) -> dict[str, JSON]:
    rows = collect_predictions(paths)
    labels = benchmark_labels()
    metrics = {}
    for model, (repository, revision) in MODELS.items():
        selected = [row for row in rows if row["model"] == model]
        votes = {row["record_id"]: row["decision"] for row in selected if row["status"] == "ok"}
        metrics[model] = {
            "name": NAMES[model], "repository": repository, "revision": revision,
            "attempted": len(selected),
            "technical_errors": sum(row["status"] == "error" for row in selected),
            **score_predictions(labels, votes),
            **request_timings(selected),
        }
    sources = [FOLDER / "benchmark.jsonl", FOLDER / "prompt.txt", *paths]
    return {
        "records": len(labels),
        "human_inclusions": sum(row["label"] == "include" for row in labels.values()),
        "models": metrics,
        "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
        "interpretation": "Descriptive results on the existing human-labeled collection. Incomplete models have coverage counts only, without accuracy metrics. Historical selection of the later cohort limits generalization to other records or reviews.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=FOLDER / "results/extensions-comparison.json")
    args = parser.parse_args()
    summary = comparison_summary(args.predictions)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    for model, metrics in summary["models"].items():
        print(f"{NAMES[model]}: {metrics['valid']}/{summary['records']} valid decisions, {metrics['technical_errors']} technical errors")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
