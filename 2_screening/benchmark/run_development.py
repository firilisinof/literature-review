"""Run development screening or print requests offline. Uses only the standard library."""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

FOLDER = Path(__file__).resolve().parent
MODELS = {
    "jev": ("jev-1.14.0", "https://api.typesafe.ai/v1/systemone", "TYPESAFE_API_KEY"),
    "decisions": (
        "gpt-6-luna",
        "https://api.openai.com/v1/decisions",
        "OPENAI_API_KEY",
    ),
    "kev-4b": ("kev-latest", "http://localhost:8009/v1/systemone", ""),
    "kev-9b": ("kev-latest", "http://localhost:8010/v1/systemone", ""),
    "qwen": ("Qwen/Qwen3-8B", "http://localhost:8000/v1/chat/completions", ""),
}
OPTIONS = {
    "include": "At least one inclusion criterion applies and no exclusion criterion applies.",
    "exclude": "An exclusion criterion applies or the paper does not meet either inclusion criterion.",
}


def arguments() -> argparse.Namespace:
    """Parse a bounded development run, e.g. arguments() from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[*MODELS, "all"], default="all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print requests without network access (default)",
    )
    mode.add_argument(
        "--execute", action="store_true", help="Send requests for one selected model"
    )
    parser.add_argument(
        "--limit", type=int, help="First N development records, in ID order"
    )
    parser.add_argument(
        "--output", type=Path, help="New JSONL file, required for live runs"
    )
    parser.add_argument("--url", help="Full local endpoint URL for one selected model")
    parser.add_argument(
        "--revision",
        help="Actual local model and server revisions, recorded with results",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.model == "all" and (args.execute or args.url):
        parser.error("Select one --model for --execute or --url")
    if args.execute and (
        not args.output
        or (args.model in {"kev-4b", "kev-9b", "qwen"} and not args.revision)
    ):
        parser.error(
            "Live runs require --output and local runs also require --revision"
        )
    return args


def development_records() -> list[dict[str, str]]:
    """Read only development inputs, e.g. development_records()."""
    rows = [
        json.loads(line)
        for line in (FOLDER / "benchmark.jsonl").read_text().splitlines()
    ]
    selected = [row for row in rows if row["split"] == "development"]
    if len(selected) != 119 or len({row["record_id"] for row in selected}) != 119:
        raise ValueError("Expected 119 unique development records")
    if not all(row["title"].strip() and row["abstract"].strip() for row in selected):
        raise ValueError("Expected a title and abstract for every development record")
    return [
        {key: row[key] for key in ("record_id", "title", "abstract")}
        for row in sorted(selected, key=lambda row: int(row["record_id"]))
    ]


def request_body(model: str, paper: dict[str, str], prompt: str) -> dict:
    """Build a provider request without human labels, e.g. request_body('jev', row, prompt)."""
    text = json.dumps(
        {"title": paper["title"], "abstract": paper["abstract"]}, ensure_ascii=False
    )
    name = MODELS[model][0]
    if model == "decisions":
        return {
            "model": name,
            "input": text,
            "questions": [
                {
                    "name": "screening",
                    "type": "choice",
                    "instructions": prompt,
                    "choices": [
                        {"value": key, "description": value}
                        for key, value in OPTIONS.items()
                    ],
                }
            ],
        }
    if model == "qwen":
        return {
            "model": name,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": 16,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    return {
        "model": name,
        "state": text,
        "questions": {
            "screening": {"type": "choice", "instructions": prompt, "criteria": OPTIONS}
        },
    }


def decision_from(model: str, response: dict) -> str:
    """Accept only complete documented answers, e.g. decision_from('jev', response)."""
    if model == "qwen":
        answer = response["choices"][0]
        if answer["finish_reason"] != "stop":
            raise ValueError("Expected a completed Qwen answer")
        choice = answer["message"]["content"].strip().lower()
    elif model == "decisions":
        answers = [row for row in response["answers"] if row.get("name") == "screening"]
        if len(answers) != 1 or answers[0].get("type") != "choice":
            raise ValueError("Expected one screening choice answer")
        choice = answers[0]["choice"]
    else:
        choice = response["answers"]["screening"]["choice"]
    if choice not in OPTIONS:
        raise ValueError("Expected include or exclude")
    return choice


def send_request(url: str, body: dict, key: str) -> dict:
    """Send once, without automatic retries, e.g. send_request(url, body, key)."""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        url, json.dumps(body).encode(), headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def run_one(model: str, url: str, body: dict, key: str) -> dict:
    """Record technical failures without a screening label, e.g. run_one('jev', url, body, key)."""
    started = time.perf_counter()
    result = {"decision": None, "status": "error", "response": None}
    try:
        result["response"] = send_request(url, body, key)
        result["decision"] = decision_from(model, result["response"])
        result["status"] = "ok"
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        result["error"] = type(error).__name__
        if isinstance(error, urllib.error.HTTPError):
            result["http_status"] = error.code
    result["seconds"] = round(time.perf_counter() - started, 6)
    return result


def main() -> None:
    """Preview requests by default, e.g. python run_development.py --dry-run --limit 1."""
    args = arguments()
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    papers = development_records()[: args.limit]
    models = list(MODELS) if args.model == "all" else [args.model]
    key_name = MODELS[models[0]][2]
    key = os.environ.get(key_name, "") if args.execute and key_name else ""
    if args.execute and key_name and not key:
        raise SystemExit(f"Set {key_name} before a live run")
    if args.url and args.model in {"jev", "decisions"}:
        raise SystemExit("--url is for local models only")
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
    for model in models:
        url = args.url or MODELS[model][1]
        for paper in papers:
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
            output.write(json.dumps(result, ensure_ascii=False) + "\n")
            output.flush()
    print(
        f"{'Ran' if args.execute else 'Prepared'} {len(papers) * len(models)} requests.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
