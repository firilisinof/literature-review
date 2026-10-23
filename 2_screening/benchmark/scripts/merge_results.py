"""Validate and merge response chunks into one file without repeating requests."""

import argparse
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from run_screening import FOLDER, screening_records, validate_saved
from screening_api import JSON, MODELS


def collect_predictions(paths: list[Path]) -> list[dict[str, JSON]]:
    """Reject duplicates and changed requests, e.g. collect_predictions([chunk])."""
    papers = {row["record_id"]: row for row in screening_records()}
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    indexed: dict[tuple[str, str], dict[str, JSON]] = {}
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            key = (row["model"], row["record_id"])
            if key in indexed or key[0] not in MODELS or key[1] not in papers:
                raise ValueError(f"{path}: unexpected or duplicate prediction {key}")
            validate_saved(row, papers[key[1]], prompt)
            indexed[key] = row
    validate_revisions(list(indexed.values()))
    return [
        indexed[key] for key in sorted(indexed, key=lambda key: (key[0], int(key[1])))
    ]


def validate_revisions(rows: list[dict[str, JSON]]) -> None:
    """Reject mixed model versions, e.g. validate_revisions(rows)."""
    for model in MODELS:
        revisions = {row["revision"] for row in rows if row["model"] == model}
        if len(revisions) > 1:
            raise ValueError(
                f"{model}: got revisions {revisions}, expected one unchanged revision"
            )


def write_predictions(rows: list[dict[str, JSON]], output: Path) -> None:
    """Replace only after validation, e.g. write_predictions(rows, output)."""
    check_coverage(rows)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=output.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def check_coverage(rows: list[dict[str, JSON]]) -> None:
    """Require every model/record attempt, e.g. check_coverage(rows)."""
    counts = Counter(row["model"] for row in rows)
    if counts != {model: 595 for model in MODELS}:
        raise ValueError(
            f"Coverage {dict(counts)}: expected 595 records for each of {list(MODELS)}"
        )


def main() -> None:
    """Merge complete coverage, e.g. python merge_results.py saved.jsonl remaining.jsonl."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chunks", nargs="+", type=Path)
    parser.add_argument(
        "--output", type=Path, default=FOLDER / "results/predictions.jsonl"
    )
    args = parser.parse_args()
    rows = collect_predictions(args.chunks)
    write_predictions(rows, args.output)
    print(f"Saved {len(rows)} predictions to {args.output}")


if __name__ == "__main__":
    main()
