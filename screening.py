#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path

REQUIRED_COLUMNS = ("id", "title", "abstract")


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
    return None


def main() -> None:
    parse_args()


if __name__ == "__main__":
    main()
