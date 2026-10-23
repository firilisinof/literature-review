"""Verify original screening choices against their raw batch responses offline."""

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from screening_api import JSON

HISTORICAL_MODELS = {
    "historical-openai": ("openai", "GPT-5.4 (historical)", "gpt-5.4-2026-03-05"),
    "historical-anthropic": (
        "anthropic",
        "Sonnet 4.5 (historical)",
        "claude-sonnet-4-5-20250929",
    ),
    "historical-gemini": ("gemini", "Gemini 2.5 Pro (historical)", "gemini-2.5-pro"),
}


@dataclass
class HistoricalRun:
    """Keep recorded choices separate from live predictions, e.g. HistoricalRun({}, {})."""

    choices: dict[str, str]
    metadata: dict[str, JSON]


@dataclass
class HistoricalResponse:
    """Describe one original provider result, e.g. HistoricalResponse(model, text, stop)."""

    model: str
    text: str
    finish_reason: str


def historical_binary_choices(run: HistoricalRun) -> dict[str, str]:
    """Count historical doubt as inclusion without changing evidence, e.g. historical_binary_choices(run)."""
    return {
        rid: "include" if choice == "doubt" else choice
        for rid, choice in run.choices.items()
    }


def extract_original_choice(text: str) -> tuple[str, str]:
    """Preserve the notebook's extraction policy, e.g. extract_original_choice(text)."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))["decision"], "json"
    try:
        return json.loads(text)["decision"], "json"
    except json.JSONDecodeError:
        recovered = re.search(r'"decision"\s*:\s*"(include|exclude)"', text)
    if recovered:
        return recovered.group(1), "decision_field_recovery"
    raise ValueError(
        f"Historical output {text[:100]!r}: expected JSON or an explicit binary decision field"
    )


def original_response(provider: str, row: dict[str, JSON]) -> HistoricalResponse:
    """Read provider evidence without changing it, e.g. original_response('openai', row)."""
    readers = {
        "openai": openai_history_response,
        "anthropic": anthropic_history_response,
        "gemini": gemini_history_response,
    }
    if provider not in readers:
        raise ValueError(
            f"Historical provider {provider!r}: expected one of {list(readers)}"
        )
    return readers[provider](row)


def openai_history_response(row: dict[str, JSON]) -> HistoricalResponse:
    """Require a completed original OpenAI response, e.g. openai_history_response(row)."""
    body = row["response"]["body"]
    if (
        row.get("error")
        or row["response"]["status_code"] != 200
        or body["status"] != "completed"
    ):
        raise ValueError(
            f"Historical OpenAI response {row.get('custom_id')}: expected HTTP 200 and completed"
        )
    texts = [
        part["text"]
        for output in body["output"]
        if output["type"] == "message"
        for part in output["content"]
        if part["type"] == "output_text"
    ]
    return HistoricalResponse(body["model"], "".join(texts), body["status"])


def anthropic_history_response(row: dict[str, JSON]) -> HistoricalResponse:
    """Retain Sonnet's original stop reason, e.g. anthropic_history_response(row)."""
    if row["result"]["type"] != "succeeded":
        raise ValueError(
            f"Historical Anthropic result {row['result']['type']!r}: expected succeeded"
        )
    body = row["result"]["message"]
    if body["stop_reason"] not in {"end_turn", "max_tokens"}:
        raise ValueError(
            f"Historical Anthropic stop {body['stop_reason']!r}: expected end_turn or max_tokens"
        )
    return HistoricalResponse(
        body["model"], body["content"][0]["text"], body["stop_reason"]
    )


def gemini_history_response(row: dict[str, JSON]) -> HistoricalResponse:
    """Require a completed original Gemini response, e.g. gemini_history_response(row)."""
    body = row["response"]
    candidate = body["candidates"][0]
    if candidate["finishReason"] != "STOP":
        raise ValueError(
            f"Historical Gemini stop {candidate['finishReason']!r}: expected STOP"
        )
    return HistoricalResponse(
        body["modelVersion"],
        candidate["content"]["parts"][0]["text"],
        candidate["finishReason"],
    )


def cached_historical_votes(source: Path, ids: set[str]) -> dict[str, dict[str, str]]:
    """Require one original choice per provider/record, e.g. cached_historical_votes(path, ids)."""
    votes = {provider: {} for provider, _, _ in HISTORICAL_MODELS.values()}
    with source.open() as stream:
        for row in csv.DictReader(stream):
            rid, provider, choice = row["paper_id"], row["provider"], row["decision"]
            if rid not in ids:
                continue
            if (
                provider not in votes
                or rid in votes[provider]
                or choice not in {"include", "exclude", "doubt"}
            ):
                raise ValueError(
                    f"Historical {provider}/{rid}/{choice}: expected a unique include, exclude, or doubt"
                )
            votes[provider][rid] = choice
    return votes


def raw_historical_records(
    paths: list[Path], ids: set[str]
) -> dict[str, dict[str, JSON]]:
    """Join raw responses by original ID, e.g. raw_historical_records(paths, ids)."""
    indexed: dict[str, dict[str, JSON]] = {}
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rid = str(row.get("custom_id", row.get("key")))
            if rid not in ids:
                continue
            if rid in indexed:
                raise ValueError(
                    f"{path}/{rid}: expected one historical response per record"
                )
            indexed[rid] = row
    if set(indexed) != ids:
        difference = set(indexed) ^ ids
        raise ValueError(f"Historical IDs {difference}: expected all {len(ids)} IDs")
    return indexed


def verify_historical_choices(
    provider: str, model: str, raw: dict[str, dict[str, JSON]], cached: dict[str, str]
) -> dict[str, JSON]:
    """Cross-check the saved choices and parser recoveries, e.g. verify_historical_choices(provider, model, raw, cache)."""
    reasons: Counter[str] = Counter()
    recovered: list[str] = []
    for rid, row in raw.items():
        response = original_response(provider, row)
        choice, method = extract_original_choice(response.text)
        if response.model != model or choice != cached.get(rid):
            raise ValueError(
                f"Historical {provider}/{rid}: got {response.model}/{choice}, expected {model}/{cached.get(rid)}"
            )
        reasons[response.finish_reason] += 1
        if method == "decision_field_recovery":
            recovered.append(rid)
    return historical_response_metadata(model, reasons, recovered)


def historical_response_metadata(
    model: str, reasons: Counter[str], recovered: list[str]
) -> dict[str, JSON]:
    """Expose legacy parser and length-limit behavior, e.g. historical_response_metadata(model, counts, ids)."""
    return {
        "model": model,
        "finish_reasons": dict(reasons),
        "truncated_responses": reasons["max_tokens"],
        "decision_field_recovery_ids": sorted(recovered, key=int),
    }


def historical_runs(root: Path, ids: set[str]) -> dict[str, HistoricalRun]:
    """Load all three original runs without requests, e.g. historical_runs(repo_root, ids)."""
    source = root / "artifacts/processed.csv"
    cached = cached_historical_votes(source, ids)
    runs: dict[str, HistoricalRun] = {}
    for key, (provider, _, model) in HISTORICAL_MODELS.items():
        paths = sorted((root / "2_screening/results").glob(f"{provider}-batch-*.jsonl"))
        raw = raw_historical_records(paths, ids)
        if set(cached[provider]) != ids:
            raise ValueError(
                f"Historical {provider} cache IDs {set(cached[provider]) ^ ids}: expected all benchmark IDs"
            )
        metadata = verify_historical_choices(provider, model, raw, cached[provider])
        metadata["source_sha256"] = {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [source, *paths]
        }
        runs[key] = HistoricalRun(cached[provider], metadata)
    return runs
