#!/usr/bin/env python3

import argparse
import csv
import json
import re
import tempfile
from pathlib import Path

from openai import NotFoundError, OpenAI

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
ALLOWED_REASONS = {"IC1", "IC2", "EC1", "EC2", "EC3", "doubt", "missing_metadata"}


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
                    "reasoning": {"effort": "none"},
                },
            }
        )
    return requests


class OpenAIBatchClient:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI()

    def get_batch(self, batch_id: str) -> dict[str, object] | None:
        try:
            batch = self.client.batches.retrieve(batch_id)
        except NotFoundError:
            return None
        return {
            "id": batch.id,
            "status": batch.status,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
            "request_counts": batch.request_counts.model_dump() if batch.request_counts else None,
        }

    def submit_batch(self, *, batch_id: str, requests: list[dict[str, object]]) -> dict[str, object]:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
            temp_path = Path(handle.name)
            for request in requests:
                handle.write(json.dumps(request) + "\n")

        try:
            with temp_path.open("rb") as request_file:
                uploaded_file = self.client.files.create(file=request_file, purpose="batch")
            batch = self.client.batches.create(
                completion_window="24h",
                endpoint="/v1/responses",
                input_file_id=uploaded_file.id,
                metadata={"local_batch_id": batch_id},
            )
        finally:
            temp_path.unlink(missing_ok=True)

        return {"id": batch.id, "status": batch.status, "output_file_id": batch.output_file_id}

    def download_output(self, batch_id: str) -> list[dict[str, str]]:
        batch = self.client.batches.retrieve(batch_id)
        if not batch.output_file_id:
            return []
        response = self.client.files.content(batch.output_file_id)
        lines = response.text.strip().splitlines()
        outputs = []
        for line in lines:
            payload = json.loads(line)
            body = payload.get("response", {}).get("body", {})
            outputs.append(
                {
                    "custom_id": payload["custom_id"],
                    "output_text": body["output"][0]["content"][0]["text"],
                }
            )
        return outputs


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


def parse_output_text(output_text: str) -> dict[str, object]:
    payload = json.loads(output_text)
    if payload.get("decision") not in {"include", "exclude"}:
        raise ValueError("Invalid decision")
    reasons = payload.get("reason")
    if not isinstance(reasons, list) or not reasons or any(reason not in ALLOWED_REASONS for reason in reasons):
        raise ValueError("Invalid reason")
    return {"decision": payload["decision"], "reason": reasons}


def run(
    argv: list[str] | None = None,
    *,
    client: object | None = None,
    workdir: Path | None = None,
) -> dict[str, object]:
    args = parse_args(argv)
    state_path = (workdir or Path.cwd()) / f"{args.batch_id}.json"
    state_exists = state_path.exists()
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
        client = OpenAIBatchClient()

    remote_batch_id = state["metadata"].get("remote_batch_id", args.batch_id)
    batch = client.get_batch(remote_batch_id)
    if batch is None:
        requests = build_batch_requests(rows=rows, state=state, model=args.model)
        batch = client.submit_batch(batch_id=args.batch_id, requests=requests)
        state["metadata"]["remote_batch_id"] = batch["id"]
        state["metadata"]["submitted_count"] = len(requests)
        save_state(state_path, state)
        return state
    if not state_exists:
        state["metadata"]["remote_batch_id"] = batch["id"]
        save_state(state_path, state)

    request_counts = batch.get("request_counts") or {}
    failed_requests = request_counts.get("failed", 0)
    if batch["status"] == "completed" and failed_requests:
        raise RuntimeError(
            f"Batch {batch['id']} completed with failed requests: {failed_requests}"
        )

    if batch["status"] == "completed":
        for item in client.download_output(batch["id"]):
            parsed = parse_output_text(item["output_text"])
            state["papers"][item["custom_id"]] = {
                "source": "openai_batch",
                "decision": parsed["decision"],
                "reason": parsed["reason"],
            }
        state["metadata"]["status"] = "done"
        save_state(state_path, state)
        return state

    if batch["status"] == "cancelled" and batch.get("output_file_id"):
        raise RuntimeError(f"Batch {batch['id']} was cancelled and has partial results available")

    if batch["status"] in {"failed", "expired", "cancelled"}:
        raise RuntimeError(f"Batch {batch['id']} ended with status {batch['status']}")
    return state


def main() -> None:
    run()


if __name__ == "__main__":
    main()
