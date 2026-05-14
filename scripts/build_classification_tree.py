"""Generate the classification tree LaTeX figure from scheme.json.

Emits a `forest` block that branches Environmental impacts -> Lifecycle stages,
listing citations at each leaf annotated with badges for System locus
(F/H/S) and Management lever (M/W/I/P).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER_REPO = REPO.parent / "literature-review-paper"

SCHEME_PATH = REPO / "artifacts" / "scheme.json"
METADATA_PATH = REPO / "artifacts" / "metadata.csv"
BIB_PATH = PAPER_REPO / "src" / "_references.bib"
OUTPUT_PATH = PAPER_REPO / "src" / "figures" / "classification_tree.tex"

_SHORT_KEY = re.compile(r"^([A-Za-z]+\d{4})")

ENV_FACET = "Environmental impacts"
LIFECYCLE_FACET = "Lifecycle stages"
LOCUS_FACET = "System locus"
LEVER_FACET = "Management and intervention levers"

LOCUS_CODES = {
    "Facility and energy infrastructure": "F",
    "Compute hardware": "H",
    "Software and workloads": "S",
}
LEVER_CODES = {
    "Measurement and accounting": "M",
    "Workload and runtime optimization": "W",
    "Infrastructure design": "I",
    "Incentives and policy": "P",
}

ENV_SHORT = {
    "Carbon emissions": "Carbon",
    "Materials and waste": "Materials \\& waste",
    "Water use": "Water",
    "Biodiversity and ecosystems": "Biodiversity",
}
LIFECYCLE_SHORT = {
    "Production": "Production",
    "Operational": "Operational",
    "End of Life": "End of Life",
}


def load_facets() -> dict[str, dict[str, set[int]]]:
    data = json.loads(SCHEME_PATH.read_text())
    facets: dict[str, dict[str, set[int]]] = {}
    for facet in data["facets"]:
        facets[facet["name"]] = {
            cat["name"]: set(cat["classification"]) for cat in facet["categories"]
        }
    return facets


def load_bib_keys() -> set[str]:
    keys: set[str] = set()
    with BIB_PATH.open() as fh:
        for line in fh:
            m = re.match(r"^@\w+\{([^,]+),", line)
            if m:
                keys.add(m.group(1))
    return keys


def load_citation_keys() -> dict[int, str]:
    bib_keys = load_bib_keys()
    keys: dict[int, str] = {}
    unresolved: list[str] = []
    with METADATA_PATH.open(newline="") as fh:
        for row in csv.DictReader(fh):
            pid = int(row["paper_id"])
            raw = row["citation_key"].strip()
            if not raw:
                continue
            short_match = _SHORT_KEY.match(raw)
            short = short_match.group(1).lower() if short_match else raw.lower()
            if raw in bib_keys:
                keys[pid] = raw
            elif short in bib_keys:
                keys[pid] = short
            else:
                keys[pid] = raw
                unresolved.append(raw)
    if unresolved:
        print(f"warning: {len(unresolved)} citation keys are not in {BIB_PATH.name}; "
              "left as-is (will be flagged as undefined by latex):")
        for key in unresolved:
            print(f"  - {key}")
    return keys


def badges_for(paper_id: int, locus: dict[str, set[int]], lever: dict[str, set[int]]) -> str:
    locus_tags = [code for name, code in LOCUS_CODES.items() if paper_id in locus.get(name, set())]
    lever_tags = [code for name, code in LEVER_CODES.items() if paper_id in lever.get(name, set())]
    locus_str = "+".join(locus_tags) if locus_tags else "-"
    lever_str = "+".join(lever_tags) if lever_tags else "-"
    return f"{locus_str},{lever_str}"


def render_leaf(paper_ids: list[int], cite_keys: dict[int, str],
                locus: dict[str, set[int]], lever: dict[str, set[int]]) -> str:
    parts = []
    for pid in sorted(paper_ids):
        if pid not in cite_keys:
            continue
        badge = badges_for(pid, locus, lever)
        parts.append(f"\\cite{{{cite_keys[pid]}}}$^{{\\textsf{{{badge}}}}}$")
    return " ".join(parts)


def build_forest(facets: dict[str, dict[str, set[int]]], cite_keys: dict[int, str]) -> str:
    env = facets[ENV_FACET]
    lifecycle = facets[LIFECYCLE_FACET]
    locus = facets[LOCUS_FACET]
    lever = facets[LEVER_FACET]

    all_papers = set(cite_keys)
    total = len(all_papers)

    lines: list[str] = []
    lines.append("\\begin{forest}")
    lines.append("  forked edges,")
    lines.append("  for tree={")
    lines.append("    grow=east,")
    lines.append("    parent anchor=east,")
    lines.append("    child anchor=west,")
    lines.append("    align=left,")
    lines.append("    font=\\footnotesize,")
    lines.append("    l sep=8pt,")
    lines.append("    s sep=4pt,")
    lines.append("    inner sep=2pt,")
    lines.append("  }")
    lines.append(f"  [HPC sustainability\\\\corpus ({total})")

    for env_name in ENV_SHORT:
        env_papers = env.get(env_name, set()) & all_papers
        if not env_papers:
            continue
        lines.append(f"    [{ENV_SHORT[env_name]} ({len(env_papers)})")
        for life_name in LIFECYCLE_SHORT:
            life_papers = sorted(env_papers & lifecycle.get(life_name, set()))
            if not life_papers:
                continue
            leaf = render_leaf(life_papers, cite_keys, locus, lever)
            label = f"\\textbf{{{LIFECYCLE_SHORT[life_name]}}} ({len(life_papers)}). {leaf}"
            lines.append(f"      [{{\\parbox[t]{{12cm}}{{\\raggedright {label}}}}}]")
        lines.append("    ]")
    lines.append("  ]")
    lines.append("\\end{forest}")
    return "\n".join(lines)


def main() -> None:
    facets = load_facets()
    cite_keys = load_citation_keys()
    body = build_forest(facets, cite_keys)

    legend = (
        "\\par\\smallskip\\noindent\\footnotesize\n"
        "\\textbf{Badge legend.} Each citation is followed by $^{\\textsf{L,V}}$ where "
        "\\textsf{L} encodes \\emph{system locus} "
        "(\\textsf{F}=facility \\& energy infrastructure, "
        "\\textsf{H}=compute hardware, "
        "\\textsf{S}=software \\& workloads) "
        "and \\textsf{V} encodes the \\emph{management lever} "
        "(\\textsf{M}=measurement \\& accounting, "
        "\\textsf{W}=workload \\& runtime optimization, "
        "\\textsf{I}=infrastructure design, "
        "\\textsf{P}=incentives \\& policy). "
        "Multi-category papers join codes with `+'; `--' marks an absent facet.\n"
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "% Generated by literature-review/scripts/build_classification_tree.py\n"
        "% Do not edit by hand; rerun the script to refresh.\n"
        "\\noindent\\resizebox{\\linewidth}{!}{%\n"
        f"{body}\n"
        "}\n"
        f"{legend}"
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(PAPER_REPO.parent)}")


if __name__ == "__main__":
    main()
