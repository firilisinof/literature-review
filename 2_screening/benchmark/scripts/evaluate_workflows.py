"""Compare four fixed groups of LLM and decision-model screening workflows."""

import argparse
import hashlib
import json
from pathlib import Path

from compare_results import NAMES, benchmark_labels, prediction_maps, score_predictions
from historical_screening import historical_binary_choices, historical_runs
from merge_results import collect_predictions
from run_screening import FOLDER
from screening_api import JSON

GROUPS = {
    "closed-weight-llms": (
        "Closed-weight LLMs",
        ("historical-openai", "historical-anthropic", "historical-gemini"),
    ),
    "open-weight-llms": ("Open-weight LLMs", ("qwen", "llama", "gemma")),
    "closed-weight-decisions": ("Closed-weight decision models", ("jev", "decisions")),
    "open-weight-decisions": ("Open-weight decision models", ("kev-9b", "pplx-flash")),
}


def workflow_metrics(
    labels: dict[str, dict[str, str]],
    predictions: dict[str, dict[str, str]],
    models: tuple[str, ...],
    minimum_votes: int,
) -> dict[str, JSON]:
    """Route records to humans at a fixed vote threshold, then reuse human labels."""
    if not models or len(set(models)) != len(models):
        raise ValueError(f"Models {models}: expected a nonempty set of distinct models")
    if not 1 <= minimum_votes <= len(models):
        raise ValueError(f"Threshold {minimum_votes}: expected 1 to {len(models)}")
    for model in models:
        votes = predictions[model]
        if set(votes) != set(labels) or set(votes.values()) - {"include", "exclude"}:
            raise ValueError(
                f"{model}: expected one binary vote for every labeled record"
            )
    routes = {
        rid: (
            "include"
            if sum(predictions[model][rid] == "include" for model in models)
            >= minimum_votes
            else "exclude"
        )
        for rid in labels
    }
    metrics = score_predictions(labels, routes)
    excluded = len(labels) - metrics["retained"]
    return {
        "models": list(models),
        "model_count": len(models),
        "minimum_include_votes": minimum_votes,
        "records_for_human_review": metrics["retained"],
        "records_automatically_excluded": excluded,
        "human_workload_reduction": 1 - metrics["retained_fraction"],
        "known_inclusions_retained": metrics["true_inclusions"],
        "known_inclusions_missed": metrics["false_exclusions"],
        "recall": metrics["recall"],
        "recall_wilson_95": metrics["recall_wilson_95"],
        "inclusion_precision": metrics["precision"],
        "exclusion_precision": (
            metrics["true_exclusions"] / excluded if excluded else None
        ),
        "true_exclusions": metrics["true_exclusions"],
        "human_exclusions_to_review": metrics["false_inclusions"],
        "human_disagreements": metrics["human_disagreements"],
        "missed_record_ids": metrics["false_exclusion_ids"],
    }


def evaluate_workflows(predictions_path: Path) -> dict[str, JSON]:
    """Compare category members and unanimous inclusion without ranking on labels."""
    labels = benchmark_labels()
    predictions = prediction_maps(collect_predictions([predictions_path]))
    runs = historical_runs(FOLDER.parents[1], set(labels))
    predictions.update(
        {model: historical_binary_choices(run) for model, run in runs.items()}
    )
    workflows, groups = {}, {}
    for key, (title, models) in GROUPS.items():
        for model in models:
            workflows[f"single/{model}"] = workflow_metrics(
                labels, predictions, (model,), 1
            )
        combination = f"{key}/unanimous"
        workflows[combination] = workflow_metrics(
            labels, predictions, models, len(models)
        )
        groups[key] = {
            "title": title,
            "models": list(models),
            "workflow_keys": [*(f"single/{model}" for model in models), combination],
        }
    sources = {
        "benchmark.jsonl": hashlib.sha256(
            (FOLDER / "benchmark.jsonl").read_bytes()
        ).hexdigest(),
        "prompt.txt": hashlib.sha256((FOLDER / "prompt.txt").read_bytes()).hexdigest(),
        str(predictions_path): hashlib.sha256(
            predictions_path.read_bytes()
        ).hexdigest(),
    }
    for run in runs.values():
        sources.update(run.metadata["source_sha256"])
    return {
        "records": len(labels),
        "human_inclusions": sum(row["label"] == "include" for row in labels.values()),
        "model_names": {
            model: NAMES[model].removesuffix(" (historical)")
            for _, models in GROUPS.values()
            for model in models
        },
        "selection": {
            "rule": (
                "Fixed roster chosen by weight availability and model purpose before "
                "scoring the added models. No ranking or subset search on the human labels."
            ),
        },
        "groups": groups,
        "routing_rule": (
            "For each single model, review its included records. For each group "
            "combination, review only records every member includes. Automatically "
            "exclude other records. Historical doubt counts as include. No automatic inclusion."
        ),
        "human_decision_assumption": (
            "Reviewed records receive their existing human label. Workload measures records, "
            "not screening time, reviewer errors, or disagreement resolution."
        ),
        "interpretation": (
            "Descriptive results on 595 labeled records. The later cohort was selected "
            "by historical unanimous inclusion. Unlabeled search results and approved "
            "removals are outside these denominators. Closed-weight LLMs retain their original "
            "inputs. Two-model unanimity is less strict than three-model unanimity. "
            "Llama uses binary constrained decoding, while Qwen and Gemma use unconstrained "
            "greedy generation with strict response validation. "
            "Observed scores do not establish performance across the entire search or a new review."
        ),
        "metric_definitions": {
            "human_disagreements": (
                "False inclusions plus false exclusions: FP + FN. Compare model routing "
                "decisions with human labels before human review corrects extra inclusions."
            ),
            "inclusion_precision": (
                "True inclusions among records sent to humans: TP / (TP + FP)."
            ),
            "exclusion_precision": (
                "True exclusions among automatically excluded records: TN / (TN + FN). "
                "Also called negative predictive value."
            ),
            "undefined_precision": "Undefined when no records receive that label.",
        },
        "source_sha256": sources,
        "workflows": workflows,
    }


def plot_workflows(summary: dict[str, JSON], figures_folder: Path) -> None:
    """Render four groups on aligned workload and disagreement scales."""
    from plot_comparison import COLORS, configure_fonts

    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator, PercentFormatter
    from matplotlib.transforms import blended_transform_factory

    configure_fonts()
    rows, headings = [], []
    position = 0
    for group in summary["groups"].values():
        headings.append((position - 0.95, group["title"]))
        for key in group["workflow_keys"]:
            metric = summary["workflows"][key]
            label = (
                ("Both include" if metric["model_count"] == 2 else "All 3 include")
                if key.endswith("/unanimous")
                else summary["model_names"][metric["models"][0]]
            )
            rows.append((position, label, key, metric))
            position += 1
        position += 1.8
    figure, axes = plt.subplots(1, 2, figsize=(13, 11), sharey=True)
    figure.subplots_adjust(left=0.27, right=0.97, bottom=0.07, top=0.87, wspace=0.30)
    false_inclusion_color, false_exclusion_color = COLORS[5], COLORS[4]
    for axis, title in zip(
        axes, ("Human screening work saved", "Disagreements with humans")
    ):
        axis.set_title(title, loc="left", fontsize=16, weight=800, pad=30)
        axis.set_ylim(rows[-1][0] + 0.7, -1.55)
        axis.set_axisbelow(True)
        axis.grid(axis="x", color="#D5DCE1", linewidth=0.6)
        axis.spines[["left", "bottom"]].set_visible(False)
        axis.tick_params(axis="y", length=0, pad=12)
    heading_transform = blended_transform_factory(figure.transFigure, axes[0].transData)
    for row, title in headings:
        axes[0].text(
            0.035,
            row,
            title,
            transform=heading_transform,
            va="center",
            fontsize=14,
            weight=800,
            color="#243746",
        )
    for row, _, key, metric in rows:
        combined = key.endswith("/unanimous")
        weight = 800 if combined else 400
        if combined:
            for axis in axes:
                axis.axhspan(row - 0.4, row + 0.4, color="#EFF3F6", zorder=0)
        saved = metric["human_workload_reduction"] * 100
        axes[0].scatter(
            saved,
            row,
            color=COLORS[0],
            s=65 if combined else 35,
            marker="D" if combined else "o",
            edgecolor="white",
            linewidth=0.5,
            zorder=3,
        )
        axes[0].text(
            1.02,
            row,
            f"{saved:.1f}%",
            transform=axes[0].get_yaxis_transform(),
            va="center",
            fontsize=11,
            weight=weight,
            color="#333333",
        )
        false_inclusions = metric["human_exclusions_to_review"]
        false_exclusions = metric["known_inclusions_missed"]
        height = 0.5 if combined else 0.4
        axes[1].barh(
            row,
            false_inclusions,
            height=height,
            color=false_inclusion_color,
            zorder=2,
        )
        axes[1].barh(
            row,
            false_exclusions,
            left=false_inclusions,
            height=height,
            color=false_exclusion_color,
            zorder=2,
        )
        axes[1].annotate(
            f"{false_inclusions} + {false_exclusions}",
            (metric["human_disagreements"], row),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=11,
            weight=weight,
            color="#333333",
        )
    axes[0].set_yticks(
        [row for row, _, _, _ in rows], [label for _, label, _, _ in rows]
    )
    axes[0].tick_params(axis="y", labelsize=11)
    axes[1].tick_params(axis="y", labelleft=False)
    for tick, (_, _, key, _) in zip(axes[0].get_yticklabels(), rows):
        if key.endswith("/unanimous"):
            tick.set_weight(800)
    axes[0].set_xlim(0, 100)
    axes[0].set_xticks([0, 25, 50, 75, 100])
    axes[0].xaxis.set_major_formatter(PercentFormatter())
    axes[0].set_xlabel("Of 595 labeled records", fontsize=11, labelpad=10)
    maximum = max(m["human_disagreements"] for m in summary["workflows"].values())
    axes[1].set_xlim(0, max(10, maximum * 1.27))
    axes[1].xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    axes[1].set_xlabel(
        "False inclusions + false exclusions (records)", fontsize=11, labelpad=10
    )
    figure.suptitle(
        "Screening workflows",
        x=0.035,
        y=0.98,
        ha="left",
        fontsize=24,
        weight=800,
    )
    figure.legend(
        handles=[
            Patch(color=false_inclusion_color, label="False inclusions"),
            Patch(color=false_exclusion_color, label="False exclusions"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.98, 0.98),
        frameon=False,
        ncol=2,
        fontsize=11,
    )
    figures_folder.mkdir(parents=True, exist_ok=True)
    figure.savefig(figures_folder / "workflows.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    for obsolete in (
        "workflows-closed-weight-llms.png",
        "workflows-decision-models.png",
    ):
        (figures_folder / obsolete).unlink(missing_ok=True)


def main() -> None:
    """Write fourteen fixed workflows and their static comparison figure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions", type=Path, default=FOLDER / "results/predictions.jsonl"
    )
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    summary = evaluate_workflows(args.predictions)
    destination = args.predictions.parent / "workflows.json"
    destination.write_text(json.dumps(summary, indent=2) + "\n")
    if not args.no_plots:
        plot_workflows(summary, FOLDER / "figures")
    print(
        "Policy                           Review    Work saved    Disagreements    False inclusions    False exclusions"
    )
    for key, metric in summary["workflows"].items():
        print(
            f"{key:32} {metric['records_for_human_review']:>4}"
            f"    {metric['human_workload_reduction']:>8.1%}"
            f"    {metric['human_disagreements']:>13}"
            f"    {metric['human_exclusions_to_review']:>16}"
            f"    {metric['known_inclusions_missed']:>16}"
        )
    print(f"\nSaved {destination}")
    print(summary["interpretation"])


if __name__ == "__main__":
    main()
