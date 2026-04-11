#!/usr/bin/env python3

import argparse
import csv
import json
import re
from pathlib import Path

REQUIRED_COLUMNS = ("id", "title", "abstract")
HYDROXYPROPYL_CELLULOSE_RE = re.compile(r"\bhydroxypropyl cellulose\b", re.IGNORECASE)
CONCRETE_MATERIALS_RE = re.compile(
    r"\b(high-performance concrete|materials? study|waste fibers?)\b",
    re.IGNORECASE,
)
SEED = 12345


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch paper screening via API.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args(argv)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise ValueError("CSV must contain id,title,abstract columns")
        return list(reader)


def prefilter_paper(row: dict[str, str]) -> dict[str, object] | None:
    text = f"{row['title']} {row['abstract']}"

    if not row["title"].strip():
        return {
            "source": "prefilter",
            "decision": "exclude",
            "reason": ["missing_metadata"],
        }
    if not row["abstract"].strip():
        return {
            "source": "prefilter",
            "decision": "exclude",
            "reason": ["missing_metadata"],
        }
    if HYDROXYPROPYL_CELLULOSE_RE.search(text):
        return {
            "source": "prefilter",
            "decision": "exclude",
            "reason": ["EC1"],
        }
    if CONCRETE_MATERIALS_RE.search(text):
        return {
            "source": "prefilter",
            "decision": "exclude",
            "reason": ["EC1"],
        }
    return None


def build_state(
    *, batch_id: str, input_path: Path, model: str, rows: list[dict[str, str]]
) -> dict[str, object]:
    papers = {}
    for row in rows:
        prefilter = prefilter_paper(row)
        if prefilter:
            papers[row["id"]] = prefilter

    return {
        "metadata": {
            "batch_id": batch_id,
            "status": "waiting batch",
            "provider": "openai",
            "model": model,
            "seed": SEED,
            "input_file": str(input_path),
            "submitted_count": 0,
            "prefiltered_count": len(papers),
        },
        "papers": papers,
    }


def load_or_create_state(
    *,
    state_path: Path,
    batch_id: str,
    input_path: Path,
    model: str,
    rows: list[dict[str, str]],
) -> dict[str, object]:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))

    return build_state(batch_id=batch_id, input_path=input_path, model=model, rows=rows)


def main() -> None:
    parse_args()


if __name__ == "__main__":
    main()
