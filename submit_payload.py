#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Literal

from anthropic import Anthropic
from google import genai
from openai import OpenAI

COMPLETION_WINDOW: str = "24h"
OPENAI_ENDPOINT: str = "/v1/responses"
GEMINI_MODEL: str = "gemini-2.5-pro"
ProviderName = Literal["openai", "anthropic", "gemini"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit one provider batch payload JSONL file.")
    parser.add_argument("payload_path")
    return parser.parse_args()


def infer_provider(payload_path: Path) -> ProviderName:
    normalized_path: str = str(payload_path).lower()
    if "openai" in normalized_path:
        return "openai"
    if "anthropic" in normalized_path:
        return "anthropic"
    if "gemini" in normalized_path:
        return "gemini"
    raise ValueError(f"Unable to infer provider from payload path: {payload_path}")


def load_jsonl_requests(path: Path) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue
        request = json.loads(stripped_line)
        if not isinstance(request, dict):
            raise ValueError(f"Invalid request row in {path}")
        requests.append(request)
    if not requests:
        raise ValueError(f"No requests found in {path}")
    return requests


def submit_openai_payload(client: OpenAI, payload_path: Path) -> dict[str, object]:
    with payload_path.open("rb") as handle:
        uploaded_file = client.files.create(file=handle, purpose="batch")

    batch = client.batches.create(
        completion_window=COMPLETION_WINDOW,
        endpoint=OPENAI_ENDPOINT,
        input_file_id=uploaded_file.id,
    )
    return {
        "payload_path": str(payload_path),
        "provider": "openai",
        "batch_id": batch.id,
        "status": batch.status,
        "input_file_id": batch.input_file_id,
    }


def submit_anthropic_payload(client: Anthropic, payload_path: Path) -> dict[str, object]:
    requests = load_jsonl_requests(payload_path)
    batch = client.messages.batches.create(requests=requests)
    return {
        "payload_path": str(payload_path),
        "provider": "anthropic",
        "batch_id": batch.id,
        "processing_status": batch.processing_status,
    }


def submit_gemini_payload(client: genai.Client, payload_path: Path) -> dict[str, object]:
    uploaded_file = client.files.upload(
        file=str(payload_path),
        config={"display_name": payload_path.stem, "mime_type": "jsonl"},
    )
    batch = client.batches.create(
        model=GEMINI_MODEL,
        src=uploaded_file.name,
        config={"display_name": payload_path.stem},
    )
    return {
        "payload_path": str(payload_path),
        "provider": "gemini",
        "batch_name": batch.name,
    }


def submit_payload(payload_path: Path) -> dict[str, object]:
    provider = infer_provider(payload_path)
    if provider == "openai":
        return submit_openai_payload(OpenAI(), payload_path)
    if provider == "anthropic":
        return submit_anthropic_payload(Anthropic(), payload_path)
    if provider == "gemini":
        return submit_gemini_payload(genai.Client(), payload_path)
    raise ValueError(f"Unsupported provider: {provider}")


def main() -> None:
    args = parse_args()
    payload_path = Path(args.payload_path).resolve()
    result = submit_payload(payload_path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
