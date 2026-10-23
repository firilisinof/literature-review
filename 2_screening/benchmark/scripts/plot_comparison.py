"""Render the full benchmark with the established plot style."""

from itertools import combinations
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np
from numpy.typing import NDArray

from screening_api import JSON

COLORS = [
    "#0072B2",
    "#009E73",
    "#E69F00",
    "#CC79A7",
    "#D55E00",
    "#56B4E9",
    "#000000",
    "#F0E442",
    "#882255",
    "#44AA99",
    "#999999",
]
FIELDS = {
    "recall": "Recall",
    "false_exclusions": "False exclusions",
    "precision": "Inclusion precision",
    "retained_fraction": "Retained fraction",
}
METRIC_EXPLANATIONS = {
    "recall": (
        "Percentage of the 62 papers humans included that the model also included"
    ),
    "false_exclusions": (
        "Number of the 62 papers humans included that the model excluded"
    ),
    "precision": ("Percentage of papers the model included that humans also included"),
    "retained_fraction": "Percentage of all 595 papers that the model included",
}


def configure_fonts() -> None:
    """Require the project's plotting font, e.g. configure_fonts()."""
    # Refresh installed fonts so a newly installed font does not require a cache reset.
    for font_path in font_manager.findSystemFonts():
        if "robotocondensed" in Path(font_path).name.lower().replace("-", ""):
            font_manager.fontManager.addfont(font_path)
    font_manager.findfont("Roboto Condensed", fallback_to_default=False)
    plt.rcParams.update(
        {
            "font.family": "Roboto Condensed",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def metric_count(metric: dict[str, JSON], field: str) -> str:
    """Show denominators beside rates, e.g. metric_count(metric, 'recall')."""
    return {
        "recall": f"{metric['true_inclusions']}/62",
        "false_exclusions": str(metric["false_exclusions"]),
        "precision": f"{metric['true_inclusions']}/{metric['retained']}",
        "retained_fraction": f"{metric['retained']}/595",
    }[field]


def metric_panel_heading(axis: Axes, field: str) -> None:
    """Explain each denominator, e.g. metric_panel_heading(axis, 'recall')."""
    axis.set_title(FIELDS[field], loc="left", fontsize=16, weight=800, pad=28)
    axis.annotate(
        METRIC_EXPLANATIONS[field],
        xy=(0, 1),
        xycoords="axes fraction",
        xytext=(0, 9),
        textcoords="offset points",
        va="bottom",
        fontsize=12,
        fontstyle="italic",
        color="#444444",
        annotation_clip=False,
    )


def decorate_metric_axis(axis: Axes, field: str, titles: list[str]) -> None:
    """Keep scales comparable across models, e.g. decorate_metric_axis(axis, 'recall', names)."""
    counts = field == "false_exclusions"
    axis.set_yticks(range(len(titles)), titles)
    axis.set_ylim(len(titles) - 0.4, -0.6)
    metric_panel_heading(axis, field)
    axis.set_axisbelow(True)
    axis.grid(axis="x", alpha=0.17)
    axis.spines["left"].set_visible(False)
    axis.tick_params(axis="y", length=0)
    axis.set_xlim(0, 62 if counts else 115)
    axis.set_xticks([0, 15, 30, 45, 60] if counts else [0, 25, 50, 75, 100])
    axis.set_xlabel("Count out of 62 human inclusions" if counts else "Percent")


def annotate_metric(
    axis: Axes, metric: dict[str, JSON], field: str, index: int
) -> None:
    """Keep count labels outside bars, e.g. annotate_metric(axis, metric, 'recall', 0)."""
    if not metric["complete"]:
        annotate_incomplete(axis, metric, index)
        return
    count = metric_count(metric, field)
    text = count if field == "false_exclusions" else f"({count})"
    annotate_rate(axis, metric[field], field, index)
    axis.text(
        1.02,
        index,
        text,
        transform=axis.get_yaxis_transform(),
        va="center",
        fontsize=10,
        clip_on=False,
    )


def annotate_incomplete(axis: Axes, metric: dict[str, JSON], index: int) -> None:
    """Show coverage instead of inventing a metric, e.g. annotate_incomplete(axis, metric, 7)."""
    total = metric["valid"] + metric["missing_binary_decisions"]
    axis.text(1, index, "incomplete", va="center", fontsize=10, color="#555555")
    axis.text(
        1.02,
        index,
        f"({metric['valid']}/{total} binary)",
        transform=axis.get_yaxis_transform(),
        va="center",
        fontsize=10,
        clip_on=False,
    )


def annotate_rate(axis: Axes, rate: JSON, field: str, index: int) -> None:
    """Handle undefined precision explicitly, e.g. annotate_rate(axis, None, 'precision', 0)."""
    if field != "false_exclusions":
        label = "undefined" if rate is None else f"{rate * 100:.1f}%"
        axis.annotate(
            label,
            ((rate or 0) * 100, index),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=10,
        )


def draw_metric(
    axis: Axes, field: str, metrics: dict[str, dict[str, JSON]], names: dict[str, str]
) -> None:
    """Sort each measure independently, e.g. draw_metric(axis, 'recall', metrics, names)."""
    ordered = sorted(
        names,
        key=lambda key: (metrics[key]["complete"], metrics[key].get(field) or 0),
        reverse=True,
    )
    colors = dict(zip(names, COLORS))
    scale = 1 if field == "false_exclusions" else 100
    values = [(metrics[key].get(field) or 0) * scale for key in ordered]
    axis.barh(
        range(len(names)), values, color=[colors[key] for key in ordered], height=0.55
    )
    decorate_metric_axis(axis, field, [names[key] for key in ordered])
    for index, key in enumerate(ordered):
        annotate_metric(axis, metrics[key], field, index)


def metric_figure(metrics: dict[str, dict[str, JSON]], names: dict[str, str]) -> Figure:
    """Build the four-panel comparison, e.g. metric_figure(metrics, names)."""
    figure, axes = plt.subplots(2, 2, figsize=(20, max(11, len(names) * 0.85 + 4)))
    figure.subplots_adjust(
        left=0.23, right=0.95, bottom=0.07, top=0.86, wspace=0.85, hspace=0.40
    )
    metric_heading(figure, len(names))
    for axis, field in zip(axes.flat, FIELDS):
        draw_metric(axis, field, metrics, names)
    return figure


def metric_heading(figure: Figure, model_count: int) -> None:
    """Summarize the benchmark in one title, e.g. metric_heading(figure, len(names))."""
    figure.suptitle(
        f"Screening benchmark: {model_count} models on 595 papers "
        "(62 human inclusions, 533 human exclusions)",
        fontsize=20,
        x=0.08,
        ha="left",
        y=0.93,
        weight=800,
    )


def disagreement_matrix(
    comparison: dict[str, JSON], names: dict[str, str]
) -> NDArray[np.int64]:
    """Use the scored disagreement counts, e.g. disagreement_matrix(summary, names)."""
    matrix = np.zeros((len(names) + 1, len(names) + 1), dtype=np.int64)
    for index, model in enumerate(names, 1):
        matrix[0, index] = matrix[index, 0] = comparison["human_disagreements"][model]
    pairs = {
        frozenset(pair.split(" / ")): count
        for pair, count in comparison["pairwise_disagreements"].items()
    }
    for (i, left), (j, right) in combinations(enumerate(names, 1), 2):
        matrix[i, j] = matrix[j, i] = pairs[frozenset((left, right))]
    return matrix


def annotate_matrix(axis: Axes, matrix: NDArray[np.int64]) -> None:
    """Show each pair once, e.g. annotate_matrix(axis, matrix)."""
    for i, j in np.ndindex(matrix.shape):
        if j >= i:
            continue
        color = "white" if matrix[i, j] > matrix.max() * 0.55 else "#17212b"
        axis.text(
            j, i, str(matrix[i, j]), ha="center", va="center", fontsize=30, color=color
        )


def disagreement_figure(comparison: dict[str, JSON], names: dict[str, str]) -> Figure:
    """Render the scored lower triangle, e.g. disagreement_figure(summary, names)."""
    names = dict(
        sorted(
            names.items(),
            key=lambda item: comparison["human_disagreements"][item[0]],
            reverse=True,
        )
    )
    matrix = disagreement_matrix(comparison, names)
    figure, axis = plt.subplots(
        figsize=(max(16, len(names) * 1.6 + 5), max(13, len(names) * 1.2 + 3))
    )
    masked = np.ma.masked_where(np.triu(np.ones_like(matrix, dtype=bool)), matrix)
    heat = axis.imshow(masked, cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
    decorate_disagreements(axis, list(names.values()))
    annotate_matrix(axis, matrix)
    colorbar = figure.colorbar(heat, ax=axis, shrink=0.8)
    colorbar.set_label("Papers with different include/exclude decisions", fontsize=22)
    colorbar.ax.tick_params(labelsize=22)
    figure.tight_layout()
    return figure


def decorate_disagreements(axis: Axes, names: list[str]) -> None:
    """Align the triangular matrix labels, e.g. decorate_disagreements(axis, names)."""
    labels = ["Human", *names]
    ticks = [fill(label, width=12) for label in labels[:-1]]
    axis.set_xticks(range(len(names)), ticks, rotation=0, ha="center")
    axis.spines[["left", "bottom"]].set_visible(False)
    axis.tick_params(length=0, labelsize=22, pad=10)
    axis.tick_params(axis="x", labelsize=18 if len(names) > 8 else 22)
    axis.set_yticks(range(1, len(names) + 1), [fill(name, width=24) for name in names])
    axis.set_xlim(-0.5, len(names) - 0.5)
    axis.set_ylim(len(names) + 0.5, 0.5)
    axis.set_title(
        "Pairwise include/exclude disagreements on 595 papers",
        loc="left",
        fontsize=32,
        weight=800,
        pad=24,
    )


def plot_comparison(
    comparison: dict[str, JSON], names: dict[str, str], figures_folder: Path
) -> None:
    """Create the figure directory and plots, e.g. plot_comparison(summary, names, folder)."""
    configure_fonts()
    names = {key: title.removesuffix(" (historical)") for key, title in names.items()}
    figures_folder.mkdir(parents=True, exist_ok=True)
    figures = {
        "metrics": metric_figure(comparison["metrics"], names),
        "disagreements": disagreement_figure(comparison, names),
    }
    for name, figure in figures.items():
        figure.savefig(figures_folder / f"{name}.png", dpi=180, bbox_inches="tight")
        plt.close(figure)
