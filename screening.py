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
MAX_OUTPUT_TOKENS = 80
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["include", "exclude"]},
        "reason": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["IC1", "IC2", "EC1", "EC2", "EC3", "doubt", "missing_metadata"],
            },
            "minItems": 1,
        },
    },
    "required": ["decision", "reason"],
    "additionalProperties": False,
}


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


def build_prompt(row: dict[str, str]) -> str:
    return (
        "You are screening studies for a systematic mapping study on the environmental "
        "impacts of high-performance computing (HPC).\n\n"
        "Return JSON only with keys decision and reason.\n"
        "Allowed decisions: include, exclude.\n"
        "Allowed reason values: IC1, IC2, EC1, EC2, EC3, doubt.\n"
        "If title and abstract are insufficient, return decision include with reason [\"doubt\"].\n\n"
        f"Title: {row['title']}\n"
        f"Abstract: {row['abstract']}\n"
    )


def build_batch_requests(
    *, rows: list[dict[str, str]], state: dict[str, object], model: str
) -> list[dict[str, object]]:
    requests = []
    papers = state["papers"]
    for row in rows:
        if row["id"] in papers:
            continue
        requests.append(
            {
                "custom_id": row["id"],
                "method": "POST",
                "url": "/v1/responses",
                "body": {
                    "model": model,
                    "seed": SEED,
                    "temperature": 0,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "screening_decision",
                            "schema": RESPONSE_SCHEMA,
                            "strict": True,
                        }
                    },
                    "input": build_prompt(row),
                    "reasoning": {"effort": "minimal"},
                },
            }
        )
    return requests


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


def save_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def run(
    argv: list[str] | None = None,
    *,
    client: object | None = None,
    workdir: Path | None = None,
) -> dict[str, object]:
    args = parse_args(argv)
    state_path = (workdir or Path.cwd()) / f"{args.batch_id}.json"
    rows = load_rows(Path(args.input))
    state = load_or_create_state(
        state_path=state_path,
        batch_id=args.batch_id,
        input_path=Path(args.input),
        model=args.model,
        rows=rows,
    )
    if state["metadata"]["status"] == "done":
        return state

    if client is None:
        raise ValueError("client is required")

    batch = client.get_batch(args.batch_id)
    if batch is None:
        requests = build_batch_requests(rows=rows, state=state, model=args.model)
        client.submit_batch(batch_id=args.batch_id, requests=requests)
        state["metadata"]["submitted_count"] = len(requests)
        save_state(state_path, state)
    return state


def main() -> None:
    run()


if __name__ == "__main__":
    main()
