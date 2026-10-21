"""Compare saved development runs and plot metrics. No model requests are made."""

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from run_development import decision_from

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--date", default="20261021", help="Date suffix of all five saved runs"
)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
results = folder / "results"
names = {
    "jev": "Jev 1.14.0",
    "decisions": "OpenAI Decisions",
    "kev-4b": "Kev-4B",
    "kev-9b": "Kev-9B",
    "qwen": "Qwen3-8B",
}
# Select by split before using labels, titles, or abstracts for this comparison.
labels = {}
with (folder / "benchmark.jsonl").open() as stream:
    for line in stream:
        record = json.loads(line)
        if record["split"] != "development":
            continue
        labels[str(record["record_id"])] = record
assert len(labels) == 119, f"Expected 119 development records, got {len(labels)}"
assert Counter(row["label"] for row in labels.values()) == {
    "include": 12,
    "exclude": 107,
}
prompt_hash = hashlib.sha256(
    (folder / "prompt.txt").read_text().strip().encode()
).hexdigest()
predictions = {}
metrics = {}
response_hashes = {}
for key in names:
    path = results / f"{key}-development-{args.date}.jsonl"
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 119 and len({str(r["record_id"]) for r in rows}) == 119, key
    assert {str(r["record_id"]) for r in rows} == set(labels), key
    assert all(r["model"] == key and not r["dry_run"] for r in rows), key
    assert all(r["prompt_sha256"] == prompt_hash for r in rows), key
    assert all(
        r["status"] == "ok" for r in rows
    ), f"{key}: incomplete run, cannot score"
    assert all(decision_from(key, r["response"]) == r["decision"] for r in rows), key
    predictions[key] = {str(r["record_id"]): r["decision"] for r in rows}
    response_hashes[key] = hashlib.sha256(raw).hexdigest()
    counts = Counter(
        (labels[rid]["label"], decision) for rid, decision in predictions[key].items()
    )
    tp, fn = counts["include", "include"], counts["include", "exclude"]
    fp, tn = counts["exclude", "include"], counts["exclude", "exclude"]
    recall = tp / 12
    z = 1.959963984540054
    denominator = 1 + z * z / 12
    center = (recall + z * z / 24) / denominator
    radius = (
        z * math.sqrt(recall * (1 - recall) / 12 + z * z / (4 * 12**2)) / denominator
    )
    metrics[key] = {
        "true_inclusions": tp,
        "false_exclusions": fn,
        "false_inclusions": fp,
        "true_exclusions": tn,
        "recall": recall,
        "recall_wilson_95": [center - radius, center + radius],
        "precision": tp / (tp + fp) if tp + fp else None,
        "retained": tp + fp,
        "retained_fraction": (tp + fp) / 119,
        "human_disagreements": fp + fn,
        "errors": 0,
        "coverage": 1.0,
        "false_exclusion_ids": [
            rid
            for rid in labels
            if labels[rid]["label"] == "include" and predictions[key][rid] == "exclude"
        ],
    }

comparison = {
    "split": "development",
    "records": 119,
    "human_includes": 12,
    "human_excludes": 107,
    "prompt_sha256": prompt_hash,
    "response_sha256": response_hashes,
    "metrics": metrics,
    "pairwise_disagreements": {
        f"{a} / {b}": sum(predictions[a][rid] != predictions[b][rid] for rid in labels)
        for a, b in itertools.combinations(names, 2)
    },
    "all_five_agree": sum(
        len({predictions[k][rid] for k in names}) == 1 for rid in labels
    ),
    "all_five_wrong_ids": [
        rid
        for rid in labels
        if all(predictions[k][rid] != labels[rid]["label"] for k in names)
    ],
    "disagreements": [],
}
for rid in sorted(labels, key=int):
    votes = {key: predictions[key][rid] for key in names}
    if any(vote != labels[rid]["label"] for vote in votes.values()):
        comparison["disagreements"].append(
            {
                "record_id": rid,
                "title": labels[rid]["title"],
                "human": labels[rid]["label"],
                "models": votes,
            }
        )
(results / f"all-models-development-{args.date}-summary.json").write_text(
    json.dumps(comparison, indent=2, ensure_ascii=False) + "\n"
)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)
colors = ["#0072B2", "#009E73", "#E69F00", "#CC79A7", "#6B5BA6"]
y = np.arange(5)
fig, axes = plt.subplots(2, 2, figsize=(14, 8.5))
fig.subplots_adjust(
    left=0.16, right=0.95, bottom=0.12, top=0.84, wspace=1.05, hspace=0.48
)
fig.suptitle(
    "Five models on 119 development records",
    fontsize=20,
    x=0.08,
    ha="left",
    y=0.97,
    weight="bold",
)
fig.text(
    0.08,
    0.915,
    "12 human inclusions | 107 human exclusions",
    fontsize=11,
    color="#444444",
)
for ax, field, title in zip(
    axes.flat,
    ["recall", "false_exclusions", "precision", "retained_fraction"],
    ["Recall", "False exclusions", "Inclusion precision", "Retained fraction"],
):
    values = [metrics[key][field] for key in names]
    scale = 1 if field == "false_exclusions" else 100
    ax.barh(y, np.array(values) * scale, color=colors, height=0.55, alpha=0.88)
    ax.set_yticks(y, names.values())
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=12)
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.17)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 12 if field == "false_exclusions" else 100)
    ax.set_xticks(
        [0, 3, 6, 9, 12] if field == "false_exclusions" else [0, 25, 50, 75, 100]
    )
    ax.set_xlabel(
        "Count out of 12 human inclusions" if field == "false_exclusions" else "Percent"
    )
    for index, key in enumerate(names):
        m = metrics[key]
        count = {
            "recall": f"{m['true_inclusions']}/12",
            "false_exclusions": str(m["false_exclusions"]),
            "precision": f"{m['true_inclusions']}/{m['retained']}",
            "retained_fraction": f"{m['retained']}/119",
        }[field]
        text = (
            count if field == "false_exclusions" else f"{m[field]*100:.1f}% ({count})"
        )
        ax.text(
            1.02,
            index,
            text,
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=10,
            clip_on=False,
        )
fig.savefig(
    results / f"development-{args.date}-metrics.png", dpi=180, bbox_inches="tight"
)
plt.close(fig)

raters = {
    "Human": {rid: labels[rid]["label"] for rid in labels},
    **{names[key]: predictions[key] for key in names},
}
matrix = np.array(
    [
        [sum(raters[a][rid] != raters[b][rid] for rid in labels) for b in raters]
        for a in raters
    ]
)
assert np.array_equal(matrix, matrix.T) and np.all(np.diag(matrix) == 0)
assert all(
    matrix[0, index + 1] == metrics[key]["human_disagreements"]
    for index, key in enumerate(names)
)
fig, ax = plt.subplots(figsize=(9, 7.2))
heat = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=60)
ax.set_xticks(range(6), raters.keys(), rotation=35, ha="right")
ax.set_yticks(range(6), raters.keys())
ax.set_title(
    "Decision disagreements on 119 development records",
    fontsize=15,
    weight="bold",
    pad=22,
)
for i, j in np.ndindex(matrix.shape):
    ax.text(
        j,
        i,
        "-" if i == j else str(matrix[i, j]),
        ha="center",
        va="center",
        fontsize=14,
        color="white" if matrix[i, j] > 32 else "#17212b",
    )
fig.colorbar(
    heat, ax=ax, shrink=0.8, label="Number of different include/exclude decisions"
)
fig.tight_layout()
fig.savefig(
    results / f"development-{args.date}-disagreements.png", dpi=180, bbox_inches="tight"
)
plt.close(fig)
print(
    json.dumps(
        {
            k: v
            for k, v in comparison.items()
            if k not in ("disagreements", "response_sha256")
        },
        indent=2,
    )
)
