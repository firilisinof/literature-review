"""Score the complete benchmark and historical baseline without making requests."""

import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from merge_results import collect_predictions
from run_screening import FOLDER
from screening_api import JSON, MODELS

NAMES = {
    "jev": "Jev 1.14.0",
    "decisions": "OpenAI Decisions",
    "kev-4b": "Kev-4B",
    "kev-9b": "Kev-9B",
    "qwen": "Qwen3-8B",
}


def wilson_interval(successes: int, total: int) -> list[float]:
    """Calculate a two-sided 95% Wilson interval, e.g. wilson_interval(60, 62)."""
    rate, z = successes / total, 1.959963984540054
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = (
        z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / denominator
    )
    return [center - radius, center + radius]


def score_predictions(
    labels: dict[str, dict[str, str]], votes: dict[str, str]
) -> dict[str, JSON]:
    """Withhold metrics for incomplete runs, e.g. score_predictions(labels, votes)."""
    result: dict[str, JSON] = {
        "valid": len(votes),
        "errors": len(labels) - len(votes),
        "coverage": len(votes) / len(labels),
        "complete": set(votes) == set(labels),
    }
    if not result["complete"]:
        return result
    result.update(confusion_metrics(labels, votes))
    return result


def confusion_metrics(
    labels: dict[str, dict[str, str]], votes: dict[str, str]
) -> dict[str, JSON]:
    """Score complete binary predictions, e.g. confusion_metrics(labels, votes)."""
    counts = Counter((labels[rid]["label"], vote) for rid, vote in votes.items())
    tp, fn = counts["include", "include"], counts["include", "exclude"]
    fp, tn = counts["exclude", "include"], counts["exclude", "exclude"]
    result: dict[str, JSON] = {
        "true_inclusions": tp,
        "false_exclusions": fn,
        "false_inclusions": fp,
        "true_exclusions": tn,
    }
    result.update(recall=tp / (tp + fn), recall_wilson_95=wilson_interval(tp, tp + fn))
    result.update(precision=tp / (tp + fp) if tp + fp else None, retained=tp + fp)
    result.update(
        retained_fraction=(tp + fp) / len(labels), human_disagreements=fp + fn
    )
    result["false_exclusion_ids"] = false_exclusion_ids(labels, votes)
    return result


def false_exclusion_ids(
    labels: dict[str, dict[str, str]], votes: dict[str, str]
) -> list[str]:
    """Identify missed human inclusions, e.g. false_exclusion_ids(labels, votes)."""
    return [
        rid
        for rid in labels
        if labels[rid]["label"] == "include" and votes[rid] == "exclude"
    ]


def historical_baseline(labels: dict[str, dict[str, str]]) -> dict[str, JSON]:
    """Apply unanimous inclusion with explicit invalid coverage, e.g. historical_baseline(labels)."""
    source = FOLDER.parents[1] / "artifacts/processed.csv"
    votes = historical_votes(source, set(labels))
    valid = {
        rid: ("include" if set(answers.values()) == {"include"} else "exclude")
        for rid, answers in votes.items()
        if len(answers) == 3 and set(answers.values()) <= {"include", "exclude"}
    }
    result = score_predictions(labels, valid)
    result.update(
        invalid_ids=[rid for rid in labels if rid not in valid],
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    return result


def historical_votes(source: Path, ids: set[str]) -> dict[str, dict[str, str]]:
    """Validate the original provider rows, e.g. historical_votes(source, ids)."""
    votes: dict[str, dict[str, str]] = {rid: {} for rid in ids}
    with source.open() as stream:
        for row in csv.DictReader(stream):
            rid, provider = row["paper_id"], row["provider"]
            if rid not in ids:
                continue
            if provider in votes[rid] or provider not in {
                "anthropic",
                "openai",
                "gemini",
            }:
                raise ValueError(
                    f"Historical {rid}/{provider}: expected three unique providers"
                )
            votes[rid][provider] = row["decision"]
    return votes


def model_metrics(
    rows: list[dict[str, JSON]], labels: dict[str, dict[str, str]], model: str
) -> dict[str, JSON]:
    """Add observed request times without estimating billing, e.g. model_metrics(rows, labels, 'jev')."""
    selected = [row for row in rows if row["model"] == model]
    votes = {
        row["record_id"]: row["decision"] for row in selected if row["status"] == "ok"
    }
    result = score_predictions(labels, votes)
    result.update(request_timings(selected))
    result.update(
        attempted=len(selected),
        technical_errors=sum(row["status"] == "error" for row in selected),
    )
    result["revisions"] = sorted(
        {row["revision"] for row in selected if row["revision"]}
    )
    return result


def request_timings(rows: list[dict[str, JSON]]) -> dict[str, JSON]:
    """Sum recorded latency across run dates, e.g. request_timings(rows)."""
    seconds = [row["seconds"] for row in rows]
    return {
        "request_seconds": sum(seconds),
        "cost": None,
        "mean_request_seconds": statistics.mean(seconds) if seconds else None,
        "median_request_seconds": statistics.median(seconds) if seconds else None,
    }


def prediction_maps(rows: list[dict[str, JSON]]) -> dict[str, dict[str, str]]:
    """Collect valid decisions for each model, e.g. prediction_maps(rows)."""
    return {
        model: {
            row["record_id"]: row["decision"]
            for row in rows
            if row["model"] == model and row["status"] == "ok"
        }
        for model in MODELS
    }


def comparison_summary(
    rows: list[dict[str, JSON]], labels: dict[str, dict[str, str]]
) -> dict[str, JSON]:
    """Summarize all 595 records, e.g. comparison_summary(rows, labels)."""
    metrics = {model: model_metrics(rows, labels, model) for model in MODELS}
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    comparison: dict[str, JSON] = {
        "records": len(labels),
        "human_includes": 62,
        "human_excludes": 533,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "metrics": metrics,
        "historical_baseline": historical_baseline(labels),
        "concurrency_per_model": 1,
        "retries": 0,
    }
    if not all(metric["complete"] for metric in metrics.values()):
        return comparison
    comparison.update(agreement_summary(prediction_maps(rows), labels))
    return comparison


def agreement_summary(
    predictions: dict[str, dict[str, str]], labels: dict[str, dict[str, str]]
) -> dict[str, JSON]:
    """Compare raters on exactly the same IDs, e.g. agreement_summary(votes, labels)."""
    comparison: dict[str, JSON] = {}
    comparison["pairwise_disagreements"] = {
        f"{a} / {b}": sum(predictions[a][rid] != predictions[b][rid] for rid in labels)
        for a, b in itertools.combinations(MODELS, 2)
    }
    comparison["all_five_agree"] = sum(
        len({predictions[model][rid] for model in MODELS}) == 1 for rid in labels
    )
    comparison["all_five_wrong_ids"] = [
        rid
        for rid in labels
        if all(predictions[model][rid] != labels[rid]["label"] for model in MODELS)
    ]
    comparison["disagreements"] = disagreement_rows(predictions, labels)
    return comparison


def disagreement_rows(
    predictions: dict[str, dict[str, str]], labels: dict[str, dict[str, str]]
) -> list[dict[str, JSON]]:
    """Retain human and model decisions for inspection, e.g. disagreement_rows(votes, labels)."""
    return [
        {
            "record_id": rid,
            "title": labels[rid]["title"],
            "human": labels[rid]["label"],
            "models": {model: predictions[model][rid] for model in MODELS},
        }
        for rid in labels
        if any(predictions[model][rid] != labels[rid]["label"] for model in MODELS)
    ]


def comparison_arguments() -> argparse.Namespace:
    """Select saved predictions, e.g. comparison_arguments() from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions", type=Path, default=FOLDER / "results/predictions.jsonl"
    )
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def benchmark_labels() -> dict[str, dict[str, str]]:
    """Require the reviewed label distribution, e.g. benchmark_labels()."""
    records = [
        json.loads(line)
        for line in (FOLDER / "benchmark.jsonl").read_text().splitlines()
    ]
    counts = Counter(row["label"] for row in records)
    if counts != {"include": 62, "exclude": 533}:
        raise ValueError(f"Human labels {counts}: expected 62 include and 533 exclude")
    return {row["record_id"]: row for row in records}


def save_comparison(comparison: dict[str, JSON], path: Path) -> None:
    """Keep input hashes with the score, e.g. save_comparison(summary, path)."""
    comparison["predictions_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    local_path = path.parent / "local-runs.json"
    if local_path.exists():
        comparison["local_runs_sha256"] = hashlib.sha256(
            local_path.read_bytes()
        ).hexdigest()
    (path.parent / "comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n"
    )
    if not all(metric["complete"] for metric in comparison["metrics"].values()):
        raise SystemExit(
            "Incomplete predictions: coverage saved to comparison.json, full comparison withheld"
        )


def main() -> None:
    """Validate before scoring, e.g. python compare_results.py --no-plots."""
    args = comparison_arguments()
    labels = benchmark_labels()
    rows = collect_predictions([args.predictions])
    comparison = comparison_summary(rows, labels)
    save_comparison(comparison, args.predictions)
    if not args.no_plots:
        from plot_comparison import plot_comparison

        plot_comparison(comparison, NAMES, FOLDER / "figures")
    print(json.dumps(comparison["metrics"], indent=2))


if __name__ == "__main__":
    main()
