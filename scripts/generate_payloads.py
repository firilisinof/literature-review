#!/usr/bin/env python3

import csv
import json
from pathlib import Path
from typing import Literal, TypedDict

REQUIRED_COLUMNS: tuple[str, str, str] = ("id", "title", "abstract")
PAYLOAD_SIZE: int = 1000
MAX_OUTPUT_TOKENS: int = 80
PROJECT_DIR: Path = Path(__file__).resolve().parent.parent
INPUT_PATH: Path = PROJECT_DIR / "artifacts" / "all_papers.csv"
OUTPUT_DIR: Path = PROJECT_DIR / "payloads"
SYSTEM_INTRO: str = (
    "You are screening studies for a systematic mapping study on the environmental "
    "impacts of high-performance computing (HPC)."
)
SYSTEM_RULES: str = (
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
    "If title and abstract are insufficient, return decision include with reason [\"doubt\"]."
)
ProviderName = Literal["openai", "anthropic", "gemini"]


class PaperRow(TypedDict):
    id: str
    title: str
    abstract: str


class ProviderConfig(TypedDict):
    model: str
    prefix: str


PROVIDER_CONFIGS: dict[ProviderName, ProviderConfig] = {
    "openai": {"model": "gpt-5.4-2026-03-05", "prefix": "openai"},
    "anthropic": {"model": "claude-sonnet-4-5", "prefix": "anthropic"},
    "gemini": {"model": "gemini-2.5-pro", "prefix": "gemini"},
}
PROVIDER_ORDER: tuple[ProviderName, ProviderName, ProviderName] = ("openai", "anthropic", "gemini")


def load_rows(path: Path) -> list[PaperRow]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            raise ValueError(f"CSV must contain {','.join(REQUIRED_COLUMNS)} columns: {path}")
        rows: list[PaperRow] = []
        for row in reader:
            rows.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "abstract": row["abstract"],
                }
            )
        return rows


def chunk_rows(rows: list[PaperRow], chunk_size: int) -> list[list[PaperRow]]:
    return [rows[index : index + chunk_size] for index in range(0, len(rows), chunk_size)]


def build_screening_prompt(row: PaperRow) -> str:
    return (
        f"{SYSTEM_INTRO}\n\n"
        f"{SYSTEM_RULES}\n\n"
        f"Title: {row['title']}\n"
        f"Abstract: {row['abstract']}\n"
    )


def build_anthropic_user_prompt(row: PaperRow) -> str:
    return f"Title: {row['title']}\nAbstract: {row['abstract']}\n"


def build_openai_payload_line(row: PaperRow, model: str) -> dict[str, object]:
    return {
        "custom_id": row["id"],
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "input": build_screening_prompt(row),
            "reasoning": {"effort": "none"},
        },
    }


def build_anthropic_payload_line(row: PaperRow, model: str) -> dict[str, object]:
    return {
        "custom_id": row["id"],
        "params": {
            "model": model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": [
                {"type": "text", "text": SYSTEM_INTRO},
                {"type": "text", "text": SYSTEM_RULES},
            ],
            "messages": [
                {
                    "role": "user",
                    "content": build_anthropic_user_prompt(row),
                }
            ],
        },
    }


def build_gemini_payload_line(row: PaperRow) -> dict[str, object]:
    return {
        "key": row["id"],
        "request": {
            "contents": [{"parts": [{"text": build_screening_prompt(row)}]}],
        },
    }


def build_payload_line(provider: ProviderName, row: PaperRow, model: str) -> dict[str, object]:
    if provider == "openai":
        return build_openai_payload_line(row, model)
    if provider == "anthropic":
        return build_anthropic_payload_line(row, model)
    if provider == "gemini":
        return build_gemini_payload_line(row)
    raise ValueError(f"Unsupported provider: {provider}")


def remove_existing_payload_files(output_dir: Path, prefix: str) -> None:
    pattern: str = f"{prefix}-payload-*.jsonl"
    for path in output_dir.glob(pattern):
        path.unlink()


def write_payload_file(output_path: Path, payload_lines: list[dict[str, object]]) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        for payload_line in payload_lines:
            handle.write(json.dumps(payload_line) + "\n")


def write_provider_payloads(
    output_dir: Path,
    provider: ProviderName,
    config: ProviderConfig,
    rows: list[PaperRow],
    chunk_size: int,
) -> list[Path]:
    chunks: list[list[PaperRow]] = chunk_rows(rows, chunk_size)
    remove_existing_payload_files(output_dir, config["prefix"])

    payload_paths: list[Path] = []
    for index, chunk in enumerate(chunks, 1):
        payload_lines: list[dict[str, object]] = [
            build_payload_line(provider, row, config["model"]) for row in chunk
        ]
        output_path: Path = output_dir / f"{config['prefix']}-payload-{index:03d}.jsonl"
        write_payload_file(output_path, payload_lines)
        payload_paths.append(output_path)
    return payload_paths


def write_all_payloads(rows: list[PaperRow], output_dir: Path, chunk_size: int) -> dict[ProviderName, list[Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: dict[ProviderName, list[Path]] = {}
    for provider in PROVIDER_ORDER:
        config: ProviderConfig = PROVIDER_CONFIGS[provider]
        written_paths[provider] = write_provider_payloads(output_dir, provider, config, rows, chunk_size)
    return written_paths


def main() -> None:
    rows: list[PaperRow] = load_rows(INPUT_PATH)
    written_paths: dict[ProviderName, list[Path]] = write_all_payloads(rows, OUTPUT_DIR, PAYLOAD_SIZE)
    summary: dict[str, list[str]] = {
        provider: [str(path) for path in paths] for provider, paths in written_paths.items()
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
