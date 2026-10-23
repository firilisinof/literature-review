"""Run pinned local screening models sequentially on the approved GPU server."""

import argparse
import hashlib
import json
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from local_server import (
    SERVER_SETTINGS,
    ServerPlan,
    running_server,
    server_environment,
    server_plans,
    wait_for_server,
)
from run_screening import FOLDER, saved_ids, screening_records, validate_saved
from screening_api import JSON


def arguments() -> argparse.Namespace:
    """Require explicit inference, e.g. arguments() from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-home", type=Path, default=Path.home() / "hpc-screening-benchmark"
    )
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    parser.add_argument(
        "--completed", type=Path, help="Validated predictions to skip without retries"
    )
    parser.add_argument(
        "--model", choices=["all", "kev-4b", "kev-9b", "qwen"], default="all"
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Pass --execute to run inference during an approved time slot")
    return args


def runner_command(
    args: argparse.Namespace, plan: ServerPlan, output: Path
) -> list[str]:
    """Use the common request runner, e.g. runner_command(args, plan, output)."""
    command = [
        "python3",
        str(Path(__file__).with_name("run_screening.py")),
        "--model",
        plan.name,
        "--execute",
        "--revision",
        plan.revision,
        "--output",
        str(output),
    ]
    if args.completed:
        command.extend(["--completed", str(args.completed)])
    return command


def initial_metadata(
    plan: ServerPlan, command: list[str], environment: dict[str, str]
) -> dict[str, JSON]:
    """Record reproducible serving metadata, e.g. initial_metadata(plan, command, env)."""
    return {
        "model": plan.model,
        "server_command": plan.command,
        "runner_command": command,
        "environment": {key: environment[key] for key in SERVER_SETTINGS},
        "gpu_uuid": "GPU-232102f9-4532-ed4b-ea90-14f69694cf48",
        "concurrency": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_output(output: Path, expected: set[str], prompt: str) -> dict[str, JSON]:
    """Check IDs and decisions before accepting a run, e.g. validate_output(path, ids, prompt)."""
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    ids = {row["record_id"] for row in rows}
    if len(rows) != len(expected) or ids != expected:
        raise ValueError(
            f"{output}: got {len(rows)} responses and IDs {ids ^ expected}, expected {len(expected)} unique IDs"
        )
    papers = {paper["record_id"]: paper for paper in screening_records()}
    for row in rows:
        validate_saved(row, papers[row["record_id"]], prompt)
    return {
        "record_ids": sorted(expected, key=int),
        "ok": sum(row["status"] == "ok" for row in rows),
        "errors": sum(row["status"] != "ok" for row in rows),
        "request_seconds": sum(row["seconds"] for row in rows),
    }


def execute_plan(
    plan: ServerPlan,
    command: list[str],
    environment: dict[str, str],
    metadata: dict[str, JSON],
) -> None:
    """Measure server startup separately from requests, e.g. execute_plan(plan, cmd, env, metadata)."""
    with tempfile.TemporaryFile(mode="w+") as log:
        with running_server(plan, environment, log) as process:
            started = time.monotonic()
            metadata["server_models"] = wait_for_server(process, plan)
            metadata["startup_seconds"] = time.monotonic() - started
            run_started = time.monotonic()
            subprocess.run(command, check=True, env=environment)
            metadata["run_seconds"] = time.monotonic() - run_started


def run_model(
    args: argparse.Namespace,
    plan: ServerPlan,
    output: Path,
    expected: set[str],
    prompt: str,
) -> dict[str, JSON]:
    """Run and clean up one model, e.g. run_model(args, plan, path, ids, prompt)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", plan.port))
    environment = server_environment()
    command = runner_command(args, plan, output)
    metadata = initial_metadata(plan, command, environment)
    print(f"START {plan.name}: {len(expected)} records", flush=True)
    started = time.monotonic()
    execute_plan(plan, command, environment, metadata)
    metadata["server_lifetime_seconds"] = time.monotonic() - started
    metadata.update(validate_output(output, expected, prompt))
    print(f"DONE {plan.name}: {metadata['ok']} valid", flush=True)
    return metadata


def pending_runs(
    args: argparse.Namespace, prompt: str
) -> list[tuple[ServerPlan, Path, set[str]]]:
    """Validate every destination before starting servers, e.g. pending_runs(args, prompt)."""
    papers = screening_records()
    planned: list[tuple[ServerPlan, Path, set[str]]] = []
    for plan in server_plans(args.server_home):
        if args.model not in {"all", plan.name}:
            continue
        completed = saved_ids(args.completed, plan.name, papers, prompt)
        expected = {paper["record_id"] for paper in papers} - completed
        output = FOLDER / f"results/{plan.name}-{args.date}.jsonl"
        if not expected:
            continue
        if output.exists():
            raise FileExistsError(f"{output}: expected a new output file")
        planned.append((plan, output, expected))
    return planned


def main() -> None:
    """Run only missing records when given saved predictions, e.g. python run_local.py --execute."""
    args = arguments()
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    planned = pending_runs(args, prompt)
    if not planned:
        print("No missing local predictions.")
        return
    summary_path = FOLDER / f"results/local-{args.date}-summary.json"
    if summary_path.exists():
        raise FileExistsError(f"{summary_path}: expected a new summary file")
    summary_path.parent.mkdir(exist_ok=True)
    summary: dict[str, JSON] = dict(
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), runs={}
    )
    for plan, output, expected in planned:
        summary["runs"][plan.name] = run_model(args, plan, output, expected, prompt)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        if summary["runs"][plan.name]["errors"]:
            raise SystemExit(f"{plan.name}: technical errors saved, run incomplete")


if __name__ == "__main__":
    main()
