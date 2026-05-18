"""Build artifacts/merge.csv by joining the coding outputs.

merge.csv is the master view consumed by the analysis scripts and notebooks.
It is reproducible from four upstream artifacts:

  metadata.csv    - paper metadata (spine)
  extraction.csv  - methodological coding (source of truth for
                    methodological_approach, data_source, assessment_orientation)
  others.csv      - research_type per paper
  scheme.json     - SMS classification scheme; the four facets are derived
                    by inverting each facet's category->paper-id arrays

venue_type in metadata.csv uses fine-grained categories; merge.csv collapses
them into three categories used in the paper figures and tables.

Note: re-running this script regenerates merge.csv from the four sources above.
The committed merge.csv may differ from a fresh regeneration in two cosmetic
ways: the order of multi-valued facet cells (now always scheme.json order) and
any historical hand-edits to citation_key. Inspect any diff before committing.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO / "artifacts"
METADATA_PATH = ARTIFACTS / "metadata.csv"
EXTRACTION_PATH = ARTIFACTS / "extraction.csv"
OTHERS_PATH = ARTIFACTS / "others.csv"
SCHEME_PATH = ARTIFACTS / "scheme.json"
OUTPUT_PATH = ARTIFACTS / "merge.csv"

FACET_ORDER = (
    "Environmental impacts",
    "Lifecycle stages",
    "System locus",
    "Management and intervention levers",
)

VENUE_TYPE_MAP = {
    "hpc systems": "HPC Venues",
    "parallel distributed": "Parallel and Distributed Venues",
    "domain specific": "Other Venues",
    "general cs": "Other Venues",
    "sustainability energy": "Other Venues",
    "other": "Other Venues",
}

OUTPUT_COLUMNS = (
    "paper_id",
    "title",
    "abstract",
    "publication_year",
    "doi",
    "satisfy_ic1",
    "satisfy_ic2",
    "from_snowballing",
    "papers_backward_snowballing",
    "papers_forward_snowballing",
    "citation_key",
    "publication_type",
    "venue",
    "venue_type",
    "research_type",
    "methodological_approach",
    "data_source",
    "assessment_orientation",
    *FACET_ORDER,
)


def load_csv_by_id(path: Path, id_field: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return {row[id_field]: row for row in csv.DictReader(fh)}


def load_facet_assignments(scheme_path: Path) -> dict[str, dict[str, list[str]]]:
    """Return {facet_name: {paper_id: [category names in scheme order]}}."""
    with scheme_path.open(encoding="utf-8") as fh:
        scheme = json.load(fh)

    by_facet: dict[str, dict[str, list[str]]] = {}
    for facet in scheme["facets"]:
        facet_name = facet["name"]
        per_paper: dict[str, list[str]] = {}
        for category in facet["categories"]:
            cat_name = category["name"]
            for paper_id in category.get("classification", []):
                per_paper.setdefault(str(paper_id), []).append(cat_name)
        by_facet[facet_name] = per_paper
    return by_facet


def map_venue_type(value: str) -> str:
    key = value.strip().lower()
    if key not in VENUE_TYPE_MAP:
        raise ValueError(f"Unknown venue_type {value!r} in metadata.csv")
    return VENUE_TYPE_MAP[key]


def build_rows() -> list[dict[str, str]]:
    metadata = load_csv_by_id(METADATA_PATH, "paper_id")
    extraction = load_csv_by_id(EXTRACTION_PATH, "id")
    others = load_csv_by_id(OTHERS_PATH, "id")
    facets = load_facet_assignments(SCHEME_PATH)

    rows: list[dict[str, str]] = []
    for paper_id, meta in metadata.items():
        ex = extraction.get(paper_id, {})
        ot = others.get(paper_id, {})
        row = {col: meta.get(col, "") for col in OUTPUT_COLUMNS if col in meta}
        row["venue_type"] = map_venue_type(meta["venue_type"])
        row["research_type"] = ot.get("research_type", "")
        row["methodological_approach"] = ex.get("methodological_approach", "")
        row["data_source"] = ex.get("data_source", "")
        row["assessment_orientation"] = ex.get("assessment_orientation", "")
        for facet_name in FACET_ORDER:
            row[facet_name] = ";".join(facets.get(facet_name, {}).get(paper_id, []))
        rows.append(row)
    return rows


def main() -> None:
    rows = build_rows()
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(OUTPUT_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in OUTPUT_COLUMNS})
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
