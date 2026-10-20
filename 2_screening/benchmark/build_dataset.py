"""Rebuild benchmark.jsonl from the original screening files. No model requests."""

import csv
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

import bibtexparser

Row = dict[str, str]
SEED = 20261020
# User-approved removals. Sources and reasons are in README.md.
NO_ABSTRACT = {
    "230",
    "271",
    "582",
    "2118",
    "2405",
    "2570",
    "2696",
    "3173",
    "3241",
    "3242",
    "3642",
}
TITLE_PAGES = {"1330", "1461", "1504"}
# cd60158 introduced these incorrect aliases. Keep the original screening IDs.
BAD_ALIASES = {"3794": "2042", "3795": "299"}
# (source group, human label): (available records, development records).
STRATA = {
    ("initial", "include"): (25, 5),
    ("initial", "exclude"): (335, 67),
    ("snowball", "include"): (5, 1),
    ("later", "include"): (32, 6),
    ("later", "exclude"): (198, 40),
}


def read_csv(path: Path, key: str = "id") -> dict[str, Row]:
    """Read unique source IDs, e.g. read_csv(root / 'decisions/first.csv')."""
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"{path}: expected unique {key} values")
    return indexed


def title_key(title: str) -> str:
    """Ignore export formatting for title checks, e.g. title_key('HPC!')."""
    decoded = html.unescape(title).casefold()
    unescaped = decoded.replace("\\", "")
    return re.sub(r"[\W_]+", "", unescaped)


def usable_abstract(text: str) -> bool:
    """Reject missing-text markers, e.g. usable_abstract('N/A')."""
    normalized = text.strip().casefold()
    missing = {"", "n/a", "no abstract available", "no abstract available."}
    return normalized not in missing and not normalized.startswith(
        "presents the title page"
    )


def later_label(left: Row, right: Row, conflict: Row | None) -> tuple[str, str]:
    """Use the recorded resolution for disagreements, e.g. later_label(l, r, c)."""
    if left["decision"] == right["decision"]:
        if conflict is not None:
            raise ValueError(f"{left['id']}: expected no conflict for matching votes")
        return left["decision"], "2_screening/decisions/lucas.csv + victor.csv"
    if conflict is None or not conflict.get("resolution", "").strip():
        raise ValueError(f"{left['id']}: expected a recorded adjudication")
    for reviewer, vote in (("lucas", left), ("victor", right)):
        for field in ("decision", "reason"):
            if conflict[f"{reviewer}_{field}"] != vote[field]:
                raise ValueError(f"{left['id']}: expected matching {reviewer} {field}")
    return conflict["final_decision"], "artifacts/conflicts.csv"


def human_labels(root: Path) -> dict[str, Row]:
    """Join original human decisions by ID, e.g. human_labels(repo_root)."""
    first = read_csv(root / "2_screening/decisions/first.csv")
    left = read_csv(root / "2_screening/decisions/lucas.csv")
    right = read_csv(root / "2_screening/decisions/victor.csv")
    conflicts = read_csv(root / "artifacts/conflicts.csv")
    if set(left) != set(right) or set(first) & set(left) or set(conflicts) - set(left):
        raise ValueError(
            "Human ID sets: expected disjoint initial and paired later records"
        )
    labels = {
        key: {
            "label": row["decision"],
            "cohort": "snowball" if "Snowball" in row["reason"] else "initial",
            "label_source": "2_screening/decisions/first.csv",
        }
        for key, row in first.items()
    }
    for key, vote in left.items():
        label, source = later_label(vote, right[key], conflicts.get(key))
        labels[key] = {"label": label, "cohort": "later", "label_source": source}
    return labels


def bibliography_abstracts(root: Path) -> dict[str, list[tuple[str, str]]]:
    """Index recovery sources by title, e.g. bibliography_abstracts(repo_root)."""
    indexed: dict[str, list[tuple[str, str]]] = {}
    for name in ("scopus", "ieee", "acm"):
        source = f"1_search/{name}.bib"
        entries = bibtexparser.loads((root / source).read_text()).entries
        for entry in entries:
            key = title_key(entry.get("title", ""))
            indexed.setdefault(key, []).append(
                (entry.get("abstract", ""), f"{source}#{entry['ID']}")
            )
    return indexed


def recover_abstract(
    paper: Row,
    supplements: list[tuple[dict[str, Row], str]],
    bibliography: dict[str, list[tuple[str, str]]],
) -> tuple[str, str]:
    """Keep original text or use an exact title match, e.g. recover_abstract(p, s, b)."""
    if usable_abstract(paper["abstract"]):
        return paper["abstract"], "artifacts/all_papers.csv"
    for indexed, source in supplements:
        extra = indexed.get(paper["id"])
        if extra is None:
            continue
        if title_key(extra["title"]) != title_key(paper["title"]):
            raise ValueError(f"{paper['id']}: expected matching title in {source}")
        if usable_abstract(extra["abstract"]):
            return extra["abstract"], source
    for text, source in bibliography.get(title_key(paper["title"]), []):
        if usable_abstract(text):
            return text, source
    return "", ""


def check_record(paper: Row, reference: Row, abstract: str) -> None:
    """Check identity and approved removals, e.g. check_record(paper, label, text)."""
    key = paper["id"]
    if paper["canonical_id"] != BAD_ALIASES.get(key, key):
        raise ValueError(f"{key}: expected the reviewed canonical ID mapping")
    if reference["label"] not in {"include", "exclude"}:
        raise ValueError(f"{key}: expected include or exclude human label")
    if key in NO_ABSTRACT | TITLE_PAGES and reference["label"] != "exclude":
        raise ValueError(f"{key}: expected human exclusion for approved removal")
    if key in NO_ABSTRACT and abstract:
        raise ValueError(f"{key}: abstract now available, review the approved removal")
    if key in TITLE_PAGES and title_key(paper["title"]) != "titlepagei":
        raise ValueError(f"{key}: expected the reviewed title-page record")
    if key not in NO_ABSTRACT | TITLE_PAGES and not abstract:
        raise ValueError(f"{key}: expected a usable abstract")


def collect_records(root: Path) -> list[Row]:
    """Build the active collection from source files, e.g. collect_records(repo_root)."""
    papers, labels = read_csv(root / "artifacts/all_papers.csv"), human_labels(root)
    supplements = [
        (
            read_csv(root / "artifacts/unanimous_include.csv"),
            "artifacts/unanimous_include.csv",
        ),
        (
            read_csv(root / "artifacts/metadata.csv", "paper_id"),
            "artifacts/metadata.csv",
        ),
    ]
    bibliography = bibliography_abstracts(root)
    if len(labels) != 609 or not NO_ABSTRACT | TITLE_PAGES <= labels.keys():
        raise ValueError(
            "Human collection changed: expected 609 records and all 14 removal IDs"
        )
    records: list[Row] = []
    for key in sorted(labels, key=int):
        paper = papers[key]
        abstract, source = recover_abstract(paper, supplements, bibliography)
        check_record(paper, labels[key], abstract)
        if key not in NO_ABSTRACT | TITLE_PAGES:
            records.append(
                {
                    "record_id": key,
                    "title": paper["title"],
                    "abstract": abstract,
                    **labels[key],
                    "abstract_source": source,
                }
            )
    return records


def assign_split(records: list[Row]) -> None:
    """Keep the agreed seed and assignments, e.g. assign_split(records)."""
    counts = Counter((row["cohort"], row["label"]) for row in records)
    if counts != {key: size for key, (size, _) in STRATA.items()}:
        raise ValueError(f"{counts}: expected the agreed label/source counts")
    for (cohort, label), (_, quota) in STRATA.items():
        group = [
            row for row in records if (row["cohort"], row["label"]) == (cohort, label)
        ]
        group.sort(
            key=lambda row: hashlib.sha256(
                f"{SEED}:{row['record_id']}".encode()
            ).digest()
        )
        for position, row in enumerate(group):
            row["split"] = "development" if position < quota else "held_out"


def check_dataset(records: list[Row]) -> None:
    """Check coverage and split totals before writing, e.g. check_dataset(records)."""
    if len({row["record_id"] for row in records}) != 595:
        raise ValueError("Record IDs: expected 595 unique active records")
    if len({title_key(row["title"]) for row in records}) != 595:
        raise ValueError("Titles: expected no repeated normalized titles")
    counts = Counter((row["split"], row["label"]) for row in records)
    expected = {
        ("development", "include"): 12,
        ("development", "exclude"): 107,
        ("held_out", "include"): 50,
        ("held_out", "exclude"): 426,
    }
    if counts != expected:
        raise ValueError(f"{counts}: expected split counts {expected}")


def main() -> None:
    """Rebuild and check the single dataset, e.g. python build_dataset.py."""
    folder = Path(__file__).resolve().parent
    records = collect_records(folder.parents[1])
    assign_split(records)
    check_dataset(records)
    rendered = "\n".join(json.dumps(row, ensure_ascii=False) for row in records)
    (folder / "benchmark.jsonl").write_text(rendered + "\n", encoding="utf-8")
    print("Saved 595 records: development 119 (12 include), held-out 476 (50 include).")


if __name__ == "__main__":
    main()
