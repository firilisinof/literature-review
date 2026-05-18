"""Generate the presence-matrix LaTeX `longtable` from merge.csv.

Emits a multi-page `longtable` with one row per report and one column per
facet category (4+3+3+4=14), grouped by facet. A `\\checkmark` marks
membership. Rows are grouped by primary environmental impact (Carbon,
Materials, Water, Biodiversity) and sorted by publication year within
each group. The longtable is meant to be wrapped in a `landscape`
environment by the caller.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

MERGE_PATH = REPO / "artifacts" / "merge.csv"
BIB_PATH = REPO / "artifacts" / "included.bib"
OUTPUT_PATH = REPO / "tables" / "presence-matrix.tex"

_SHORT_KEY = re.compile(r"^([A-Za-z]+\d{4})")


def load_bib_keys() -> set[str]:
    keys: set[str] = set()
    with BIB_PATH.open() as fh:
        for line in fh:
            m = re.match(r"^@\w+\{([^,]+),", line)
            if m:
                keys.add(m.group(1))
    return keys


def resolve_key(raw: str, bib_keys: set[str]) -> str:
    raw = raw.strip()
    if raw in bib_keys:
        return raw
    short_match = _SHORT_KEY.match(raw)
    if short_match:
        short = short_match.group(1).lower()
        if short in bib_keys:
            return short
    return raw


ENV_FACET = "Environmental impacts"
LIFECYCLE_FACET = "Lifecycle stages"
LOCUS_FACET = "System locus"
LEVER_FACET = "Management and intervention levers"

ENV_ORDER = [
    ("Carbon emissions", "Carbon"),
    ("Materials and waste", "Materials and waste"),
    ("Water use", "Water"),
    ("Biodiversity and ecosystems", "Biodiversity"),
]
LIFECYCLE_ORDER = [
    ("Production", "Production"),
    ("Operational", "Operational"),
    ("End of Life", "End of Life"),
]
LOCUS_ORDER = [
    ("Facility and energy infrastructure", "Facility and energy"),
    ("Compute hardware", "Compute hardware"),
    ("Software and workloads", "Software and workloads"),
]
LEVER_ORDER = [
    ("Measurement and accounting", "Measurement and accounting"),
    ("Workload and runtime optimization", "Workload and runtime"),
    ("Infrastructure design", "Infrastructure design"),
    ("Incentives and policy", "Incentives and policy"),
]

# Group labels are stacked across multiple lines via \shortstack so the
# multicolumn group header fits over the narrow rotated sub-columns.
GROUPS = [
    (ENV_FACET, "\\textbf{Environmental}\\\\\\textbf{impacts}", ENV_ORDER),
    (LIFECYCLE_FACET, "\\textbf{Lifecycle}\\\\\\textbf{stages}", LIFECYCLE_ORDER),
    (LOCUS_FACET, "\\textbf{System}\\\\\\textbf{locus}", LOCUS_ORDER),
    (LEVER_FACET, "\\textbf{Management and}\\\\\\textbf{intervention}\\\\\\textbf{levers}", LEVER_ORDER),
]

CAPTION_FULL = (
    "Presence matrix of the corpus across the four classification facets. "
    "Each row is a report and each column is a facet category; a check mark "
    "indicates that the report is tagged with that category. Rows are grouped "
    "by primary environmental impact and sorted by publication year within "
    "each group."
)
CAPTION_SHORT = "Presence matrix of the corpus across the four classification facets."


def split_cell(value: str) -> set[str]:
    return {part.strip() for part in value.split(";") if part.strip()}


def load_rows() -> list[dict]:
    bib_keys = load_bib_keys()
    rows = []
    with MERGE_PATH.open(newline="") as fh:
        for raw in csv.DictReader(fh):
            rows.append({
                "paper_id": int(raw["paper_id"]),
                "year": int(raw["publication_year"]),
                "cite": resolve_key(raw["citation_key"], bib_keys),
                ENV_FACET: split_cell(raw[ENV_FACET]),
                LIFECYCLE_FACET: split_cell(raw[LIFECYCLE_FACET]),
                LOCUS_FACET: split_cell(raw[LOCUS_FACET]),
                LEVER_FACET: split_cell(raw[LEVER_FACET]),
            })
    return rows


def primary_env_index(row: dict) -> int:
    for i, (name, _) in enumerate(ENV_ORDER):
        if name in row[ENV_FACET]:
            return i
    return len(ENV_ORDER)


def build_longtable(rows: list[dict]) -> str:
    rows_sorted = sorted(rows, key=lambda r: (primary_env_index(r), r["year"], r["paper_id"]))

    n_cols_per_group = [len(order) for _, _, order in GROUPS]
    total_cols = 2 + sum(n_cols_per_group)

    col_spec_parts = ["lc"]
    for n in n_cols_per_group:
        col_spec_parts.append("|")
        col_spec_parts.append("c" * n)
    col_spec = "".join(col_spec_parts)

    # Wrap multi-line group headers in tabular without a [t]/[b] position so
    # the box is vertically centered; this also vertically centers Report/Year
    # against the middle of the tallest stack.
    super_parts = [
        "\\multicolumn{1}{c}{\\textbf{Report}}",
        "\\textbf{Year}",
    ]
    cmidrules = []
    cursor = 3
    for _, label, order in GROUPS:
        n = len(order)
        cell = (
            "\\multicolumn{" + str(n) + "}{c}{"
            "\\begin{tabular}{@{}c@{}}" + label + "\\end{tabular}}"
        )
        super_parts.append(cell)
        cmidrules.append(f"\\cmidrule(lr){{{cursor}-{cursor + n - 1}}}")
        cursor += n
    super_row = " & ".join(super_parts) + " \\\\"
    cmid_row = " ".join(cmidrules)

    header_parts = ["", ""]
    for _, _, order in GROUPS:
        for _, short in order:
            header_parts.append(f"\\rothead{{{short}}}")
    header_row = " & ".join(header_parts) + " \\\\"

    lines: list[str] = []
    lines.append("\\begingroup")
    lines.append("\\footnotesize")
    lines.append("\\setlength{\\tabcolsep}{3pt}")
    lines.append("\\renewcommand{\\arraystretch}{1.1}")
    # Fixed-width \makebox so columns are evenly spaced regardless of whether
    # the rotated label has descenders (e.g. 'y' in Biodiversity), which would
    # otherwise widen that column.
    lines.append("\\def\\rothead#1{\\makebox[1.1em][c]{\\rotatebox{90}{#1}}}")
    lines.append(f"\\begin{{longtable}}{{{col_spec}}}")
    lines.append(f"\\caption[{CAPTION_SHORT}]{{{CAPTION_FULL}}}\\label{{tab:classification-matrix}}\\\\")
    lines.append("\\toprule")
    lines.append(super_row)
    lines.append(cmid_row)
    lines.append(header_row)
    lines.append("\\midrule")
    lines.append("\\endfirsthead")
    lines.append(f"\\multicolumn{{{total_cols}}}{{l}}{{\\footnotesize\\itshape (continued from previous page)}} \\\\")
    lines.append("\\toprule")
    lines.append(super_row)
    lines.append(cmid_row)
    lines.append(header_row)
    lines.append("\\midrule")
    lines.append("\\endhead")
    lines.append("\\midrule")
    lines.append(f"\\multicolumn{{{total_cols}}}{{r}}{{\\footnotesize\\itshape (continued on next page)}} \\\\")
    lines.append("\\endfoot")
    lines.append("\\bottomrule")
    lines.append("\\endlastfoot")

    placed = 0
    current_block = -1
    for row in rows_sorted:
        block = primary_env_index(row)
        if current_block != -1 and block != current_block:
            lines.append("\\midrule")
        current_block = block

        cells = [f"\\cite{{{row['cite']}}}", str(row["year"])]
        for facet_key, _, order in GROUPS:
            for cat_name, _ in order:
                cells.append("\\checkmark" if cat_name in row[facet_key] else "")
        lines.append(" & ".join(cells) + " \\\\")
        placed += 1

    lines.append("\\end{longtable}")
    lines.append("\\endgroup")

    print(f"placed {placed}/{len(rows)}")
    return "\n".join(lines)


def main() -> None:
    rows = load_rows()
    body = build_longtable(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "% Generated by 4_analysis/scripts/build_presence_matrix.py\n"
        "% Do not edit by hand; rerun the script to refresh.\n"
        f"{body}\n"
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
