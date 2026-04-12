#!/usr/bin/env python3

import argparse
import csv
import json
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypedDict

from openai import NotFoundError, OpenAI
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.table import Table

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
REASON_CODE_RE = re.compile(r"\b(?:IC1|IC2|EC1|EC2|EC3|doubt|missing_metadata)\b", re.IGNORECASE)
TERMINAL_STATUSES = {
    "done",
    "failed",
    "expired",
    "cancelled",
    "completed_with_failed_requests",
    "cancelled_with_partial_output",
}


class RequestCounts(TypedDict):
    total: int
    completed: int
    failed: int


class BatchInfo(TypedDict):
    id: str
    status: str
    output_file_id: str | None
    error_file_id: str | None
    request_counts: RequestCounts | None


class BatchOutput(TypedDict):
    custom_id: str
    output_text: str


class BatchClient(Protocol):
    source_name: str

    def build_requests(self, *, rows: list[dict[str, str]], model: str) -> list[dict[str, object]]: ...

    def get_batch(self, batch_id: str) -> BatchInfo | None: ...

    def submit_batch(self, *, batch_id: str, requests: list[dict[str, object]]) -> BatchInfo: ...

    def download_output(self, batch_id: str) -> list[BatchOutput]: ...


class BatchOutputDownloadError(ValueError):
    pass


def timestamp_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_timestamp(timestamp: str | None, *, now: datetime | None = None) -> str:
    if not timestamp:
        return "-"

    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)
    now = now or datetime.now(UTC)
    delta_seconds = max(int((now - parsed).total_seconds()), 0)

    if delta_seconds < 60:
        relative = f"{delta_seconds}s ago"
    elif delta_seconds < 3600:
        relative = f"{delta_seconds // 60}m ago"
    elif delta_seconds < 86400:
        relative = f"{delta_seconds // 3600}h ago"
    else:
        relative = f"{delta_seconds // 86400}d ago"

    return f"{parsed.strftime('%Y-%m-%d %H:%M')} UTC ({relative})"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live batch paper screening via API.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--papers-per-batch", required=True, type=positive_int)
    parser.add_argument("--provider", choices=("openai", "anthropic", "gemini"), default="openai")
    parser.add_argument("--poll-interval-seconds", type=positive_int, default=30)
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
    *,
    batch_id: str,
    input_path: Path,
    model: str,
    provider: str,
    rows: list[dict[str, str]],
    papers_per_batch: int,
) -> dict[str, object]:
    papers = {}
    for row in rows:
        prefilter = prefilter_paper(row)
        if prefilter:
            papers[row["id"]] = prefilter

    now = timestamp_now()
    return {
        "metadata": {
            "batch_id": batch_id,
            "status": "waiting batch",
            "provider": provider,
            "model": model,
            "seed": SEED,
            "input_file": str(input_path),
            "submitted_count": 0,
            "prefiltered_count": len(papers),
            "papers_per_batch": papers_per_batch,
            "total_papers": len(rows),
            "current_batch_size": 0,
            "started_at": now,
            "updated_at": now,
        },
        "papers": papers,
    }


def build_prompt(row: dict[str, str]) -> str:
    return (
        "You are screening studies for a systematic mapping study on the environmental "
        "impacts of high-performance computing (HPC).\n\n"
        "Include if ANY of the following apply:\n"
        "- IC1: The paper addresses at least one environmental impact in the HPC context\n"
        "- IC2: The paper presents methodologies for predicting or measuring the environmental impacts of HPC systems\n\n"
        "Exclude if ANY of the following apply:\n"
        "- EC1: The paper is not related to the environmental impacts of HPC\n"
        "- EC2: The paper focuses solely on energy consumption without connecting to broader environmental impacts\n"
        "- EC3: The paper is not in English, is unavailable, or is inaccessible\n\n"
        "Return JSON only with keys decision and reason.\n"
        "Allowed decisions: include, exclude.\n"
        "Allowed reason values: IC1, IC2, EC1, EC2, EC3, doubt.\n"
        "If title and abstract are insufficient, return decision include with reason [\"doubt\"].\n\n"
        f"Title: {row['title']}\n"
        f"Abstract: {row['abstract']}\n"
    )

def read_field(value: object, field_name: str) -> object | None:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def read_string_field(value: object, field_name: str, context: str) -> str:
    field_value = read_field(value, field_name)
    if not isinstance(field_value, str):
        raise ValueError(f"Expected {context}.{field_name} to be a string")
    return field_value


def read_optional_string_field(value: object, field_name: str) -> str | None:
    field_value = read_field(value, field_name)
    if field_value is None:
        return None
    if not isinstance(field_value, str):
        raise ValueError(f"Expected {field_name} to be a string")
    return field_value


def normalize_request_counts(*, total: int, completed: int, failed: int) -> RequestCounts:
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
    }


def validate_resume_metadata(
    *,
    metadata: dict[str, object],
    input_path: Path,
    model: str,
    provider: str,
) -> None:
    if metadata.get("dry_run") is True:
        raise ValueError(f"Cannot resume legacy dry-run state for batch {metadata.get('batch_id')}")

    metadata.pop("dry_run", None)
    saved_provider = metadata.setdefault("provider", "openai")
    comparisons = (
        ("provider", saved_provider, provider),
        ("model", metadata.get("model"), model),
        ("input_file", metadata.get("input_file"), str(input_path)),
    )
    for field_name, saved_value, requested_value in comparisons:
        if saved_value != requested_value:
            raise ValueError(
                f"Cannot resume batch {metadata.get('batch_id')}: saved {field_name}={saved_value!r}, "
                f"requested {field_name}={requested_value!r}"
            )


def build_batch_client(provider: str) -> BatchClient:
    if provider == "openai":
        return OpenAIBatchClient()
    if provider == "anthropic":
        return AnthropicBatchClient()
    if provider == "gemini":
        return GeminiBatchClient()
    raise ValueError(f"Unsupported provider: {provider}")


class OpenAIBatchClient:
    source_name = "openai_batch"

    def __init__(self, client: object | None = None) -> None:
        self.client = client or OpenAI()

    def build_requests(self, *, rows: list[dict[str, str]], model: str) -> list[dict[str, object]]:
        return [
            {
                "custom_id": row["id"],
                "method": "POST",
                "url": "/v1/responses",
                "body": {
                    "model": model,
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
            for row in rows
        ]

    def get_batch(self, batch_id: str) -> BatchInfo | None:
        try:
            batch = self.client.batches.retrieve(batch_id)
        except NotFoundError:
            return None
        request_counts = batch.request_counts.model_dump() if batch.request_counts else None
        return {
            "id": batch.id,
            "status": batch.status,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
            "request_counts": request_counts,
        }

    def submit_batch(self, *, batch_id: str, requests: list[dict[str, object]]) -> BatchInfo:
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

        return {
            "id": batch.id,
            "status": batch.status,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
            "request_counts": batch.request_counts.model_dump() if batch.request_counts else None,
        }

    def download_output(self, batch_id: str) -> list[BatchOutput]:
        batch = self.client.batches.retrieve(batch_id)
        if not batch.output_file_id:
            return []

        response = self.client.files.content(batch.output_file_id)
        lines = response.text.strip().splitlines()
        outputs: list[BatchOutput] = []
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


class AnthropicBatchClient:
    source_name = "anthropic_batch"

    def __init__(self, client: object | None = None) -> None:
        if client is not None:
            self.client = client
            return

        from anthropic import Anthropic

        self.client = Anthropic()

    def build_requests(self, *, rows: list[dict[str, str]], model: str) -> list[dict[str, object]]:
        return [
            {
                "custom_id": row["id"],
                "params": {
                    "model": model,
                    "max_tokens": MAX_OUTPUT_TOKENS,
                    "messages": [{"role": "user", "content": build_prompt(row)}],
                },
            }
            for row in rows
        ]

    def get_batch(self, batch_id: str) -> BatchInfo | None:
        batch = self.client.messages.batches.retrieve(batch_id)
        request_counts = batch.request_counts
        completed = int(read_field(request_counts, "succeeded") or 0)
        failed = int(read_field(request_counts, "errored") or 0) + int(read_field(request_counts, "expired") or 0) + int(
            read_field(request_counts, "canceled") or 0
        )
        total = completed + failed + int(read_field(request_counts, "processing") or 0)
        normalized_status = "completed" if batch.processing_status == "ended" else "in_progress"
        return {
            "id": batch.id,
            "status": normalized_status,
            "output_file_id": read_optional_string_field(batch, "results_url"),
            "error_file_id": None,
            "request_counts": normalize_request_counts(total=total, completed=completed, failed=failed),
        }

    def submit_batch(self, *, batch_id: str, requests: list[dict[str, object]]) -> BatchInfo:
        batch = self.client.messages.batches.create(requests=requests)
        return self.get_batch(batch.id)

    def download_output(self, batch_id: str) -> list[BatchOutput]:
        outputs: list[BatchOutput] = []
        for result in self.client.messages.batches.results(batch_id):
            result_payload = read_field(result, "result")
            result_type = read_string_field(result_payload, "type", "anthropic.result")
            if result_type != "succeeded":
                custom_id = read_string_field(result, "custom_id", "anthropic.result")
                raise BatchOutputDownloadError(f"Batch {batch_id} contains failed result for {custom_id}")

            message = read_field(result_payload, "message")
            content = read_field(message, "content")
            if not isinstance(content, list):
                raise ValueError("Expected anthropic result message content to be a list")

            text_blocks = []
            for block in content:
                if read_field(block, "type") == "text":
                    text_blocks.append(read_string_field(block, "text", "anthropic.text_block"))

            outputs.append(
                {
                    "custom_id": read_string_field(result, "custom_id", "anthropic.result"),
                    "output_text": "".join(text_blocks),
                }
            )
        return outputs


class GeminiBatchClient:
    source_name = "gemini_batch"

    def __init__(self, client: object | None = None) -> None:
        if client is not None:
            self.client = client
            return

        from google import genai

        self.client = genai.Client()

    def build_requests(self, *, rows: list[dict[str, str]], model: str) -> list[dict[str, object]]:
        return [
            {
                "custom_id": row["id"],
                "model": model,
                "request": {
                    "contents": [{"parts": [{"text": build_prompt(row)}]}],
                    "generation_config": {
                        "temperature": 0,
                        "response_mime_type": "application/json",
                        "response_json_schema": RESPONSE_SCHEMA,
                    },
                },
            }
            for row in rows
        ]

    def get_batch(self, batch_id: str) -> BatchInfo | None:
        batch = self.client.batches.get(name=batch_id)
        state = read_field(batch, "state")
        state_name = read_string_field(state, "name", "gemini.batch.state")
        normalized_status = {
            "JOB_STATE_SUCCEEDED": "completed",
            "JOB_STATE_FAILED": "failed",
            "JOB_STATE_CANCELLED": "cancelled",
            "JOB_STATE_EXPIRED": "expired",
        }.get(state_name, "in_progress")
        destination = read_field(batch, "dest")
        return {
            "id": read_string_field(batch, "name", "gemini.batch"),
            "status": normalized_status,
            "output_file_id": read_optional_string_field(destination, "file_name"),
            "error_file_id": None,
            "request_counts": None,
        }

    def submit_batch(self, *, batch_id: str, requests: list[dict[str, object]]) -> BatchInfo:
        if not requests:
            raise ValueError("Gemini batch submission requires at least one request")

        model = requests[0].get("model")
        if not isinstance(model, str):
            raise ValueError("Gemini request is missing model")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
            temp_path = Path(handle.name)
            for request in requests:
                handle.write(json.dumps({"key": request["custom_id"], "request": request["request"]}) + "\n")

        try:
            uploaded_file = self.client.files.upload(
                file=str(temp_path),
                config={"display_name": f"{batch_id}-requests", "mime_type": "jsonl"},
            )
            batch = self.client.batches.create(
                model=model,
                src=read_string_field(uploaded_file, "name", "gemini.uploaded_file"),
                config={"display_name": batch_id},
            )
        finally:
            temp_path.unlink(missing_ok=True)

        return self.get_batch(read_string_field(batch, "name", "gemini.batch"))

    def download_output(self, batch_id: str) -> list[BatchOutput]:
        batch = self.get_batch(batch_id)
        if batch is None or batch["output_file_id"] is None:
            return []

        payload = self.client.files.download(file=batch["output_file_id"])
        if isinstance(payload, bytes):
            content = payload.decode("utf-8")
        elif isinstance(payload, str):
            content = payload
        else:
            content = payload.decode("utf-8")

        outputs: list[BatchOutput] = []
        failed_keys: list[str] = []
        for line in content.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "error" in row:
                failed_keys.append(str(row.get("key")))
                continue
            response = row.get("response", {})
            outputs.append(
                {
                    "custom_id": str(row["key"]),
                    "output_text": response["candidates"][0]["content"]["parts"][0]["text"],
                }
            )

        if failed_keys:
            raise BatchOutputDownloadError(
                f"Batch {batch_id} completed with failed requests: {', '.join(failed_keys)}"
            )
        return outputs


def load_or_create_state(
    *,
    state_path: Path,
    batch_id: str,
    input_path: Path,
    model: str,
    provider: str,
    rows: list[dict[str, str]],
    papers_per_batch: int,
) -> dict[str, object]:
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        metadata = state["metadata"]
        validate_resume_metadata(metadata=metadata, input_path=input_path, model=model, provider=provider)
        metadata["papers_per_batch"] = papers_per_batch
        metadata["total_papers"] = len(rows)
        metadata.setdefault("current_batch_size", 0)
        metadata.setdefault("started_at", timestamp_now())
        metadata.setdefault("updated_at", timestamp_now())
        return state

    return build_state(
        batch_id=batch_id,
        input_path=input_path,
        model=model,
        provider=provider,
        rows=rows,
        papers_per_batch=papers_per_batch,
    )


def save_state(state_path: Path, state: dict[str, object]) -> None:
    state["metadata"]["updated_at"] = timestamp_now()
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def derive_progress(state: dict[str, object]) -> dict[str, int]:
    metadata = state["metadata"]
    papers = state["papers"]
    total_decisions = len(papers)
    included = sum(1 for paper in papers.values() if paper["decision"] == "include")
    excluded = sum(1 for paper in papers.values() if paper["decision"] == "exclude")
    prefiltered = metadata.get("prefiltered_count", 0)
    current_batch_size = metadata.get("current_batch_size", 0)
    total_papers = metadata.get("total_papers", total_decisions)
    remaining = max(total_papers - total_decisions - current_batch_size, 0)
    return {
        "total_papers": total_papers,
        "completed": total_decisions,
        "included": included,
        "excluded": excluded,
        "prefiltered": prefiltered,
        "current_batch_size": current_batch_size,
        "remaining": remaining,
        "submitted": metadata.get("submitted_count", 0),
    }


def pending_rows(rows: list[dict[str, str]], state: dict[str, object]) -> list[dict[str, str]]:
    papers = state["papers"]
    return [row for row in rows if row["id"] not in papers]


def parse_json_object_from_text(output_text: str) -> dict[str, object]:
    stripped_output = output_text.strip()
    try:
        payload = json.loads(stripped_output)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(stripped_output):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(stripped_output[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        preview = stripped_output[:120].replace("\n", "\\n")
        raise ValueError(f"Could not parse JSON object from model output: {preview!r}")

    if not isinstance(payload, dict):
        raise ValueError("Expected model output to be a JSON object")
    return payload


def normalize_reason_codes(reasons: object) -> list[str]:
    if isinstance(reasons, str):
        reason_inputs = [reasons]
    elif isinstance(reasons, list) and all(isinstance(reason, str) for reason in reasons):
        reason_inputs = list(reasons)
    else:
        raise ValueError("Invalid reason")

    normalized_reasons: list[str] = []
    seen_reasons: set[str] = set()
    for reason in reason_inputs:
        extracted_reasons = REASON_CODE_RE.findall(reason)
        if not extracted_reasons:
            candidate_reason = reason.strip()
            if candidate_reason in ALLOWED_REASONS:
                extracted_reasons = [candidate_reason]
        for extracted_reason in extracted_reasons:
            canonical_reason = extracted_reason if extracted_reason in ALLOWED_REASONS else extracted_reason.upper()
            if canonical_reason == "DOUBT":
                canonical_reason = "doubt"
            if canonical_reason == "MISSING_METADATA":
                canonical_reason = "missing_metadata"
            if canonical_reason not in ALLOWED_REASONS:
                raise ValueError("Invalid reason")
            if canonical_reason not in seen_reasons:
                normalized_reasons.append(canonical_reason)
                seen_reasons.add(canonical_reason)

    if not normalized_reasons:
        raise ValueError("Invalid reason")
    return normalized_reasons


def parse_output_text(output_text: str) -> dict[str, object]:
    payload = parse_json_object_from_text(output_text)
    if payload.get("decision") not in {"include", "exclude"}:
        raise ValueError("Invalid decision")
    normalized_reasons = normalize_reason_codes(payload.get("reason"))
    return {"decision": payload["decision"], "reason": normalized_reasons}


def persist_batch_failure(
    *,
    state_path: Path,
    state: dict[str, object],
    batch: dict[str, object],
    status: str,
    failure_message: str,
) -> dict[str, object]:
    state["metadata"]["status"] = status
    state["metadata"]["remote_batch_id"] = batch["id"]
    state["metadata"]["failure_message"] = failure_message
    save_state(state_path, state)
    return state


def submit_next_batch(
    *,
    client: BatchClient,
    args: argparse.Namespace,
    state_path: Path,
    state: dict[str, object],
    rows: list[dict[str, str]],
) -> dict[str, object]:
    batch_rows = pending_rows(rows, state)[: args.papers_per_batch]
    if not batch_rows:
        state["metadata"]["status"] = "done"
        state["metadata"]["current_batch_size"] = 0
        state["metadata"].pop("remote_batch_id", None)
        state["metadata"].pop("current_batch_submitted_at", None)
        state["metadata"].pop("failure_message", None)
        save_state(state_path, state)
        return state
    requests = client.build_requests(rows=batch_rows, model=args.model)
    if not requests:
        raise ValueError("Batch client returned no requests for pending rows")

    batch = client.submit_batch(batch_id=args.batch_id, requests=requests)
    state["metadata"]["remote_batch_id"] = batch["id"]
    state["metadata"]["submitted_count"] += len(requests)
    state["metadata"]["current_batch_size"] = len(requests)
    state["metadata"]["current_batch_submitted_at"] = timestamp_now()
    state["metadata"]["status"] = "waiting batch"
    state["metadata"].pop("failure_message", None)
    save_state(state_path, state)
    return state


def run_once(
    *,
    args: argparse.Namespace,
    client: BatchClient | None = None,
    workdir: Path | None = None,
) -> dict[str, object]:
    state_path = (workdir or Path.cwd()) / f"{args.batch_id}.json"
    state_exists = state_path.exists()
    rows = load_rows(Path(args.input))
    state = load_or_create_state(
        state_path=state_path,
        batch_id=args.batch_id,
        input_path=Path(args.input),
        model=args.model,
        provider=args.provider,
        rows=rows,
        papers_per_batch=args.papers_per_batch,
    )
    if state["metadata"]["status"] in TERMINAL_STATUSES:
        return state

    if client is None:
        client = build_batch_client(args.provider)

    remote_batch_id = state["metadata"].get("remote_batch_id")
    batch = client.get_batch(remote_batch_id) if remote_batch_id else None
    if batch is None:
        return submit_next_batch(
            client=client,
            args=args,
            state_path=state_path,
            state=state,
            rows=rows,
        )
    if not state_exists:
        state["metadata"]["remote_batch_id"] = batch["id"]
        save_state(state_path, state)

    request_counts = batch.get("request_counts") or {}
    failed_requests = request_counts.get("failed", 0)
    if batch["status"] == "completed" and failed_requests:
        return persist_batch_failure(
            state_path=state_path,
            state=state,
            batch=batch,
            status="completed_with_failed_requests",
            failure_message=f"Batch {batch['id']} completed with failed requests: {failed_requests}",
        )

    if batch["status"] == "completed":
        try:
            outputs = client.download_output(batch["id"])
        except BatchOutputDownloadError as error:
            return persist_batch_failure(
                state_path=state_path,
                state=state,
                batch=batch,
                status="completed_with_failed_requests",
                failure_message=str(error),
            )
        for item in outputs:
            try:
                parsed = parse_output_text(item["output_text"])
            except ValueError as error:
                output_preview = item["output_text"].strip().replace("\n", "\\n")[:160]
                return persist_batch_failure(
                    state_path=state_path,
                    state=state,
                    batch=batch,
                    status="completed_with_failed_requests",
                    failure_message=(
                        f"Batch {batch['id']} returned invalid output for {item['custom_id']}: "
                        f"{error}. Output preview: {output_preview!r}"
                    ),
                )
            state["papers"][item["custom_id"]] = {
                "source": client.source_name,
                "decision": parsed["decision"],
                "reason": parsed["reason"],
            }
        state["metadata"]["current_batch_size"] = 0
        state["metadata"].pop("remote_batch_id", None)
        state["metadata"].pop("current_batch_submitted_at", None)
        save_state(state_path, state)
        return submit_next_batch(
            client=client,
            args=args,
            state_path=state_path,
            state=state,
            rows=rows,
        )

    if batch["status"] == "cancelled" and batch.get("output_file_id"):
        return persist_batch_failure(
            state_path=state_path,
            state=state,
            batch=batch,
            status="cancelled_with_partial_output",
            failure_message=f"Batch {batch['id']} was cancelled and has partial results available",
        )

    if batch["status"] in {"failed", "expired", "cancelled"}:
        return persist_batch_failure(
            state_path=state_path,
            state=state,
            batch=batch,
            status=batch["status"],
            failure_message=f"Batch {batch['id']} ended with status {batch['status']}",
        )
    return state


def make_console(stdout: object | None = None) -> Console:
    if isinstance(stdout, Console):
        return stdout
    return Console(file=stdout or sys.stdout, color_system=None)


def build_progress_bar(completed: int, total: int) -> Progress:
    progress = Progress(
        TextColumn("[bold]Progress[/bold]"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TextColumn("{task.completed}/{task.total} papers"),
        expand=True,
    )
    progress.add_task("screening", total=max(total, 1), completed=completed)
    return progress


def render_dashboard(state: dict[str, object], action: str, *, now: datetime | None = None) -> Group:
    metadata = state["metadata"]
    progress = derive_progress(state)

    header = Table.grid(expand=True)
    header.add_column()
    header.add_column(justify="right")
    header.add_row(
        f"[bold]Local batch[/bold] {metadata['batch_id']}",
        f"[bold]Status[/bold] {metadata['status']}",
    )
    header.add_row(
        f"[bold]Remote batch[/bold] {metadata.get('remote_batch_id', '-')}",
        f"[bold]Model[/bold] {metadata['model']}",
    )
    header.add_row(f"[bold]Provider[/bold] {metadata.get('provider', '-')}", "")

    overall = Table.grid(padding=(0, 2))
    overall.add_column()
    overall.add_column()
    overall.add_row("Total papers", str(progress["total_papers"]))
    overall.add_row("Completed decisions", str(progress["completed"]))
    overall.add_row("Current batch", str(progress["current_batch_size"]))
    overall.add_row("Configured batch size", str(metadata.get("papers_per_batch", "-")))
    overall.add_row("Remaining", str(progress["remaining"]))

    decisions = Table.grid(padding=(0, 2))
    decisions.add_column()
    decisions.add_column()
    decisions.add_row("Included", str(progress["included"]))
    decisions.add_row("Excluded", str(progress["excluded"]))
    decisions.add_row("Prefiltered", str(progress["prefiltered"]))
    decisions.add_row("Submitted remotely", str(progress["submitted"]))

    activity = Table.grid(expand=True)
    activity.add_column()
    activity.add_row(f"[bold]Current action[/bold] {action}")
    activity.add_row(f"[bold]Started[/bold] {format_timestamp(metadata.get('started_at'), now=now)}")
    activity.add_row(f"[bold]Updated[/bold] {format_timestamp(metadata.get('updated_at'), now=now)}")
    activity.add_row(
        f"[bold]Batch submitted[/bold] {format_timestamp(metadata.get('current_batch_submitted_at'), now=now)}"
    )
    failure_message = metadata.get("failure_message")
    if failure_message:
        activity.add_row(f"[bold red]Failure[/bold red] {failure_message}")

    return Group(
        Panel(header, title="Batch", border_style="cyan"),
        Panel(build_progress_bar(progress["completed"], progress["total_papers"]), title="Overall Progress", border_style="green"),
        Panel.fit(overall, title="Work Queue", border_style="blue"),
        Panel.fit(decisions, title="Decision Summary", border_style="magenta"),
        Panel(activity, title="Activity", border_style="yellow"),
    )


def render_final_summary(state: dict[str, object]) -> Panel:
    progress = derive_progress(state)
    metadata = state["metadata"]
    lines = [
        f"Status: {metadata['status']}",
        f"Completed decisions: {progress['completed']}/{progress['total_papers']}",
        f"Included: {progress['included']}",
        f"Excluded: {progress['excluded']}",
        f"Prefiltered: {progress['prefiltered']}",
        f"Submitted remotely: {progress['submitted']}",
        f"Configured batch size: {metadata.get('papers_per_batch', '-')}",
    ]
    if metadata.get("remote_batch_id"):
        lines.append(f"Remote batch: {metadata['remote_batch_id']}")
    if metadata.get("failure_message"):
        lines.append(f"Failure: {metadata['failure_message']}")
    border_style = "green" if metadata["status"] == "done" else "red"
    title = "Screening Complete" if metadata["status"] == "done" else "Screening Stopped"
    return Panel("\n".join(lines), title=title, border_style=border_style)


def emit_snapshot(console: Console, state: dict[str, object], action: str) -> None:
    console.print(render_dashboard(state, action))


def run_with_args(
    args: argparse.Namespace,
    *,
    client: object | None = None,
    workdir: Path | None = None,
    sleeper: object | None = None,
    stdout: object | None = None,
) -> dict[str, object]:
    sleeper = sleeper or time.sleep
    console = make_console(stdout)
    state: dict[str, object] | None = None
    action = "Initializing workflow"

    def refresh(current_state: dict[str, object], current_action: str, *, live: Live | None = None) -> None:
        if live is not None:
            live.update(render_dashboard(current_state, current_action))
        else:
            emit_snapshot(console, current_state, current_action)

    def workflow(live: Live | None = None) -> dict[str, object]:
        nonlocal state, action
        action = "Loading local state"
        state = run_once(args=args, client=client, workdir=workdir)
        refresh(state, action, live=live)

        while state["metadata"]["status"] not in TERMINAL_STATUSES:
            remote_batch_id = state["metadata"].get("remote_batch_id")
            if remote_batch_id is None:
                action = "Submitting next batch"
                state = run_once(args=args, client=client, workdir=workdir)
                refresh(state, action, live=live)
                continue

            action = f"Waiting {args.poll_interval_seconds}s before polling remote batch"
            refresh(state, action, live=live)
            sleeper(args.poll_interval_seconds)

            action = "Polling remote batch and merging results if ready"
            state = run_once(args=args, client=client, workdir=workdir)
            refresh(state, action, live=live)

        return state

    if console.is_terminal:
        initial_state = build_state(
            batch_id=args.batch_id,
            input_path=Path(args.input),
            model=args.model,
            provider=args.provider,
            rows=[],
            papers_per_batch=args.papers_per_batch,
        )
        with Live(render_dashboard(initial_state, action), console=console, refresh_per_second=4, transient=False) as live:
            final_state = workflow(live=live)
    else:
        final_state = workflow(live=None)

    console.print(render_final_summary(final_state))
    return final_state


def run(
    argv: list[str] | None = None,
    *,
    client: object | None = None,
    workdir: Path | None = None,
    sleeper: object | None = None,
    stdout: object | None = None,
) -> dict[str, object]:
    args = parse_args(argv)
    return run_with_args(
        args,
        client=client,
        workdir=workdir,
        sleeper=sleeper,
        stdout=stdout,
    )


def main() -> None:
    args = parse_args()
    run_with_args(args)


if __name__ == "__main__":
    main()
