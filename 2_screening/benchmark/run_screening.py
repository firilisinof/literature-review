"""Run screening on missing records or print requests offline. Uses only the standard library."""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from screening_api import JSON, MODELS, decision_from, request_body, run_one

FOLDER = Path(__file__).resolve().parent


def request_parser() -> argparse.ArgumentParser:
    """Define request controls, e.g. request_parser().parse_args()."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[*MODELS, "all"], default="all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="Print requests offline (default)"
    )
    mode.add_argument(
        "--execute", action="store_true", help="Send requests for one model"
    )
    parser.add_argument(
        "--limit", type=int, help="First N missing records, in ID order"
    )
    add_output_options(parser)
    return parser


def add_output_options(parser: argparse.ArgumentParser) -> None:
    """Describe output and resume controls, e.g. add_output_options(parser)."""
    parser.add_argument(
        "--output", type=Path, help="New JSONL file, required for live runs"
    )
    parser.add_argument(
        "--completed", type=Path, help="Saved predictions to skip, without retries"
    )
    parser.add_argument("--url", help="Full local endpoint URL for one selected model")
    parser.add_argument("--revision", help="Actual local model and server revisions")


def arguments() -> argparse.Namespace:
    """Validate CLI combinations, e.g. arguments() from the command line."""
    parser = request_parser()
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error(f"--limit={args.limit}: expected a positive integer")
    if args.model == "all" and (args.execute or args.url):
        parser.error(f"--model={args.model}: select one model for --execute or --url")
    if args.url and args.model in {"jev", "decisions"}:
        parser.error(f"--model={args.model}: --url requires a local model")
    if args.execute and not args.output:
        parser.error("--output=None: live runs require a new output path")
    local = args.model in {"kev-4b", "kev-9b", "qwen"}
    if args.execute and local and not args.revision:
        parser.error(
            f"--revision={args.revision}: expected local model and server revisions"
        )
    return args


def screening_records() -> list[dict[str, str]]:
    """Read all screening inputs, e.g. screening_records()."""
    rows = [
        json.loads(line)
        for line in (FOLDER / "benchmark.jsonl").read_text().splitlines()
    ]
    selected = rows
    if len(selected) != 595 or len({row["record_id"] for row in selected}) != 595:
        raise ValueError(f"Expected 595 unique screening records, got {len(selected)}")
    if not all(row["title"].strip() and row["abstract"].strip() for row in selected):
        raise ValueError("Expected a title and abstract for every screening record")
    return [
        {key: row[key] for key in ("record_id", "title", "abstract")}
        for row in sorted(selected, key=lambda row: int(row["record_id"]))
    ]


def saved_ids(
    path: Path | None, model: str, papers: list[dict[str, str]], prompt: str
) -> set[str]:
    """Validate saved requests before skipping them, e.g. saved_ids(path, 'jev', papers, prompt)."""
    if path is None:
        return set()
    indexed = {paper["record_id"]: paper for paper in papers}
    completed: set[str] = set()
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["model"] != model:
            continue
        rid = row["record_id"]
        if rid not in indexed or rid in completed:
            raise ValueError(f"{path}: unexpected or duplicate {model} record {rid}")
        validate_saved(row, indexed[rid], prompt)
        completed.add(rid)
    return completed


def validate_saved(row: dict[str, JSON], paper: dict[str, str], prompt: str) -> None:
    """Reject incompatible saved predictions, e.g. validate_saved(row, paper, prompt)."""
    model = row["model"]
    expected_hash = hashlib.sha256(prompt.encode()).hexdigest()
    if row["dry_run"] or row["prompt_sha256"] != expected_hash:
        raise ValueError(
            f"{model}/{row['record_id']}: expected live prompt {expected_hash}"
        )
    if row["request"] != request_body(model, paper, prompt):
        raise ValueError(
            f"{model}/{row['record_id']}: expected the unchanged screening request"
        )
    validate_response(row)


def validate_response(row: dict[str, JSON]) -> None:
    """Keep errors distinct from labels, e.g. validate_response(row)."""
    model = row["model"]
    if (
        row["status"] == "ok"
        and decision_from(model, row["response"]) == row["decision"]
    ):
        return
    if row["status"] != "error" or row["decision"] is not None:
        raise ValueError(
            f"{model}/{row['record_id']}: expected a valid decision or an explicit technical error"
        )


def main() -> None:
    """Preview requests by default, e.g. python run_screening.py --dry-run --limit 1."""
    args = arguments()
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    papers = screening_records()
    models = list(MODELS) if args.model == "all" else [args.model]
    key_name = MODELS[models[0]][2]
    key = os.environ.get(key_name, "") if args.execute and key_name else ""
    if args.execute and key_name and not key:
        raise SystemExit(f"Set {key_name} before a live run")
    output = args.output.open("x", encoding="utf-8") if args.output else sys.stdout
    try:
        write_run(args, models, papers, prompt, key, output)
    finally:
        if args.output:
            output.close()


def write_run(
    args: argparse.Namespace,
    models: list[str],
    papers: list[dict[str, str]],
    prompt: str,
    key: str,
    output: TextIO,
) -> None:
    """Write one result per paper and model, e.g. write_run(args, models, papers, prompt, key, stream)."""
    counts = [write_model(args, model, papers, prompt, key, output) for model in models]
    count = sum(total for total, _ in counts)
    failures = sum(errors for _, errors in counts)
    print(
        f"{'Ran' if args.execute else 'Prepared'} {count} requests, {failures} errors.",
        file=sys.stderr,
    )
    if failures:
        raise SystemExit(1)


def write_model(
    args: argparse.Namespace,
    model: str,
    papers: list[dict[str, str]],
    prompt: str,
    key: str,
    output: TextIO,
) -> tuple[int, int]:
    """Flush results as they arrive, e.g. write_model(args, 'jev', papers, prompt, key, output)."""
    completed = saved_ids(args.completed, model, papers, prompt)
    selected = [paper for paper in papers if paper["record_id"] not in completed][
        : args.limit
    ]
    failures = 0
    for paper in selected:
        result = screening_result(args, model, paper, prompt, key)
        output.write(json.dumps(result, ensure_ascii=False) + "\n")
        output.flush()
        failures += result.get("status") == "error"
    return len(selected), failures


def screening_result(
    args: argparse.Namespace, model: str, paper: dict[str, str], prompt: str, key: str
) -> dict[str, JSON]:
    """Keep request evidence beside each response, e.g. screening_result(args, 'jev', paper, prompt, key)."""
    url = args.url or MODELS[model][1]
    body = request_body(model, paper, prompt)
    result = {
        "record_id": paper["record_id"],
        "model": model,
        "url": url,
        "revision": args.revision,
        "dry_run": not args.execute,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": body,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    if args.execute:
        result.update(run_one(model, url, body, key))
    return result


if __name__ == "__main__":
    main()
