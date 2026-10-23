"""Score the complete benchmark and historical baseline without making requests."""

import argparse
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from historical_screening import (
    HISTORICAL_MODELS,
    HistoricalRun,
    historical_binary_choices,
    historical_runs,
)
from merge_results import collect_predictions
from run_extensions import MODELS as EXTENSION_MODELS
from run_screening import FOLDER
from screening_api import JSON, MODELS

NAMES = {
    "jev": "Jev 1.14.0",
    "decisions": "OpenAI Decisions",
    "kev-4b": "Kev-4B",
    "kev-9b": "Kev-9B",
    "qwen": "Qwen3-8B",
    **{key: title for key, (_, title, _) in HISTORICAL_MODELS.items()},
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
        "missing_binary_decisions": len(labels) - len(votes),
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


def historical_model_metrics(
    run: HistoricalRun, labels: dict[str, dict[str, str]]
) -> dict[str, JSON]:
    """Score historical choices with doubt included, e.g. historical_model_metrics(run, labels)."""
    votes = historical_binary_choices(run)
    result = score_predictions(labels, votes)
    result.update(run.metadata)
    result.update(
        attempted=len(run.choices), technical_errors=0, cost=None, request_seconds=None
    )
    result["choice_counts"] = dict(Counter(votes.values()))
    result["recorded_choice_counts"] = dict(Counter(run.choices.values()))
    result["doubt_inclusion_ids"] = [
        rid for rid, choice in run.choices.items() if choice == "doubt"
    ]
    return result


def historical_baseline(
    labels: dict[str, dict[str, str]], runs: dict[str, HistoricalRun]
) -> dict[str, JSON]:
    """Keep the original unanimous-include rule, e.g. historical_baseline(labels, runs)."""
    normalized = [historical_binary_choices(run) for run in runs.values()]
    choices = {rid: {votes[rid] for votes in normalized} for rid in labels}
    votes = {
        rid: ("include" if answers == {"include"} else "exclude")
        for rid, answers in choices.items()
    }
    result = score_predictions(labels, votes)
    result.update(
        invalid_ids=[rid for rid in labels if rid not in votes], technical_errors=0
    )
    return result


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
    rows: list[dict[str, JSON]],
    labels: dict[str, dict[str, str]],
    extension_rows: list[dict[str, JSON]] | None = None,
) -> dict[str, JSON]:
    """Compare current and verified historical choices, e.g. comparison_summary(rows, labels)."""
    runs = historical_runs(FOLDER.parents[1], set(labels))
    metrics = {model: model_metrics(rows, labels, model) for model in MODELS}
    metrics.update(
        {key: historical_model_metrics(run, labels) for key, run in runs.items()}
    )
    if extension_rows is not None:
        metrics.update(
            {key: model_metrics(extension_rows, labels, key) for key in EXTENSION_MODELS}
        )
    comparison = comparison_header(labels, metrics, runs)
    if extension_rows is not None:
        comparison["current_run_settings"]["models"].extend(EXTENSION_MODELS)
    if not all(metric["complete"] for metric in metrics.values()):
        return comparison
    predictions = prediction_maps(rows) | {
        key: historical_binary_choices(run) for key, run in runs.items()
    }
    if extension_rows is not None:
        predictions.update(
            {
                model: {
                    row["record_id"]: row["decision"]
                    for row in extension_rows
                    if row["model"] == model and row["status"] == "ok"
                }
                for model in EXTENSION_MODELS
            }
        )
    comparison.update(agreement_summary(predictions, labels))
    return comparison


def comparison_header(
    labels: dict[str, dict[str, str]],
    metrics: dict[str, dict[str, JSON]],
    runs: dict[str, HistoricalRun],
) -> dict[str, JSON]:
    """State which settings belong to the new runs, e.g. comparison_header(labels, metrics, runs)."""
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    return {
        "records": len(labels),
        "human_includes": 62,
        "human_excludes": 533,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "metrics": metrics,
        "historical_baseline": historical_baseline(labels, runs),
        "current_run_settings": {
            "models": list(MODELS),
            "concurrency_per_model": 1,
            "retries": 0,
        },
    }


def agreement_summary(
    predictions: dict[str, dict[str, str]], labels: dict[str, dict[str, str]]
) -> dict[str, JSON]:
    """Compare raters on exactly the same IDs, e.g. agreement_summary(votes, labels)."""
    comparison = pairwise_summary(predictions, labels)
    comparison["all_models_agree"] = sum(
        len({predictions[model][rid] for model in predictions}) == 1 for rid in labels
    )
    comparison["all_models_wrong_ids"] = [
        rid
        for rid in labels
        if all(predictions[model][rid] != labels[rid]["label"] for model in predictions)
    ]
    comparison["disagreements"] = disagreement_rows(predictions, labels)
    return comparison


def pairwise_summary(
    predictions: dict[str, dict[str, str]], labels: dict[str, dict[str, str]]
) -> dict[str, JSON]:
    """Compare decisions after historical doubt inclusion, e.g. pairwise_summary(votes, labels)."""
    return {
        "human_disagreements": {
            model: sum(votes[rid] != labels[rid]["label"] for rid in labels)
            for model, votes in predictions.items()
        },
        "pairwise_disagreements": {
            f"{a} / {b}": sum(
                predictions[a][rid] != predictions[b][rid] for rid in labels
            )
            for a, b in itertools.combinations(predictions, 2)
        },
        "pairwise_choice_policy": "Historical doubt is counted as include.",
    }


def disagreement_rows(
    predictions: dict[str, dict[str, str]], labels: dict[str, dict[str, str]]
) -> list[dict[str, JSON]]:
    """Retain human and model decisions for inspection, e.g. disagreement_rows(votes, labels)."""
    return [
        {
            "record_id": rid,
            "title": labels[rid]["title"],
            "human": labels[rid]["label"],
            "models": {model: predictions[model][rid] for model in predictions},
        }
        for rid in labels
        if any(predictions[model][rid] != labels[rid]["label"] for model in predictions)
    ]


def comparison_arguments() -> argparse.Namespace:
    """Select saved predictions, e.g. comparison_arguments() from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions", type=Path, default=FOLDER / "results/predictions.jsonl"
    )
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument(
        "--extensions",
        nargs="*",
        type=Path,
        default=[
            FOLDER / f"results/{model}-20261023.jsonl" for model in EXTENSION_MODELS
        ],
        help="Additional prediction chunks. Pass without paths for the original eight models.",
    )
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
    names = NAMES.copy()
    extension_rows = None
    if args.extensions:
        from compare_extensions import NAMES as EXTENSION_NAMES
        from compare_extensions import collect_predictions as collect_extensions

        extension_rows = collect_extensions(args.extensions)
        names.update(EXTENSION_NAMES)
    comparison = comparison_summary(rows, labels, extension_rows)
    if args.extensions:
        comparison["extensions_sha256"] = {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in args.extensions
        }
    save_comparison(comparison, args.predictions)
    if not args.no_plots:
        from plot_comparison import plot_comparison

        plot_comparison(comparison, names, FOLDER / "figures")
    print(json.dumps(comparison["metrics"], indent=2))


if __name__ == "__main__":
    main()
