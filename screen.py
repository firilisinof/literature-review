#!/usr/bin/env python3
"""
screen.py — AI-assisted title/abstract screening for systematic mapping studies.

Calls a CLI agent (claude, gemini, or codex) for each paper in a screening CSV
and records include/exclude decisions in a CSV. Designed to be run once per
agent; re-runs skip already-screened papers unless they errored.

Usage:
    python screen.py --agent claude
    python screen.py --agent claude --agent codex
    python screen.py --agent claude,gemini
    python screen.py --agent gemini --limit 10 --workers 5
    python screen.py --agent codex
    python screen.py
      # runs claude, gemini, and codex
"""

import argparse
import csv
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — edit command lists here if needed
# ---------------------------------------------------------------------------

AGENT_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "--model", "claude-sonnet-4-6", "--effort", "high", "-p"],   # prompt appended as next arg
    "gemini": ["gemini", "--model", "gemini-3.1-pro-preview", "-p"],
    "codex":  ["codex", "exec", "--model", "gpt-5.4", "--config", 'model_reasoning_effort="high"'],
}

PROMPT_TEMPLATE = """\
You are screening studies for a systematic mapping study on the environmental \
impacts of high-performance computing (HPC).

Include if ANY of the following apply:
- IC1: The paper addresses at least one environmental impact in the HPC context
- IC2: The paper presents methodologies for predicting or measuring the \
environmental impacts of HPC systems

Exclude if ANY of the following apply:
- EC1: The paper is not related to the environmental impacts of HPC
- EC2: The paper focuses solely on energy consumption without connecting to \
broader environmental impacts (e.g., carbon emissions, water use, material depletion)
- EC3: The paper is not in English, is unavailable, or is inaccessible

When uncertain, include.

Title: {title}
Abstract: {abstract}

Respond with EXACTLY this format (two lines, nothing else):
Decision: include
Reason: <one sentence explaining the decision>\
"""

CSV_COLUMNS = [
    "key", "title", "abstract",
    "claude_decision", "claude_reason",
    "codex_decision",  "codex_reason",
    "gemini_decision", "gemini_reason",
]

TIMEOUT = 120  # seconds per agent call


def parse_agents(agent_args: list[str] | None) -> list[str]:
    """Parse repeated/comma-separated --agent values into a validated unique list."""
    if not agent_args:
        return list(AGENT_COMMANDS)

    agents: list[str] = []
    seen: set[str] = set()
    invalid: list[str] = []

    for raw_value in agent_args:
        for agent in (part.strip() for part in raw_value.split(",")):
            if not agent:
                continue
            if agent not in AGENT_COMMANDS:
                invalid.append(agent)
                continue
            if agent not in seen:
                seen.add(agent)
                agents.append(agent)

    if invalid:
        valid_agents = ", ".join(AGENT_COMMANDS)
        invalid_agents = ", ".join(invalid)
        raise argparse.ArgumentTypeError(
            f"invalid agent(s): {invalid_agents}. Choose from: {valid_agents}"
        )

    if not agents:
        raise argparse.ArgumentTypeError("at least one non-empty agent must be provided")

    return agents

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> dict[str, dict]:
    """Load an existing results CSV into a dict keyed by citation key."""
    with open(path, newline="", encoding="utf-8") as f:
        return {row["key"]: row for row in csv.DictReader(f)}


def save_csv(path: Path, rows: dict[str, dict]) -> None:
    """Overwrite the results CSV with current state. Caller must hold csv_lock."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows.values())

# ---------------------------------------------------------------------------
# Agent call
# ---------------------------------------------------------------------------

def call_agent(agent: str, prompt: str) -> tuple[str, str]:
    """
    Invoke the CLI agent non-interactively.
    Returns (decision, reason); both may be 'error' on failure.
    Thread-safe: uses no shared state.
    """
    cmd = AGENT_COMMANDS[agent] + [prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        output = result.stdout.strip()
        error_output = result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "error", "timeout"
    except FileNotFoundError:
        sys.exit(f"Error: '{agent}' CLI not found. Is it installed and on PATH?")

    dec_match = re.search(r"Decision:\s*(include|exclude)", output, re.IGNORECASE)
    rea_match = re.search(r"Reason:\s*(.+)", output, re.IGNORECASE)

    if result.returncode != 0 and not dec_match:
        reason = error_output or output or f"{agent} exited with status {result.returncode}"
        return "error", reason[:300]

    decision = dec_match.group(1).lower() if dec_match else "error"
    fallback_output = output or error_output
    reason   = rea_match.group(1).strip() if rea_match else fallback_output[:300]
    return decision, reason

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screen papers from a CSV with a CLI AI agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent", dest="agents", action="append", metavar="AGENT",
        help=(
            "Agent(s) to use for screening. Repeat the flag or pass a comma-separated "
            "list (for example: --agent claude --agent codex or --agent claude,codex). "
            "Defaults to all agents."
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process the next N pending papers per selected agent (useful for batching)",
    )
    parser.add_argument(
        "--workers", type=int, default=1, metavar="N",
        help="Number of parallel agent calls (default: 1, recommended: 5–10)",
    )
    args = parser.parse_args()
    try:
        agents_to_run = parse_agents(args.agents)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    csv_path = Path("screening.csv")

    if not csv_path.exists():
        sys.exit(f"Error: screening CSV not found: {csv_path}")

    print(f"Loading {csv_path} ...", file=sys.stderr)
    results = load_csv(csv_path)
    print(f"  {len(results)} papers loaded from CSV.", file=sys.stderr)

    entries = list(results.values())

    already_screened_by_agent: dict[str, int] = {}
    selected_entries_by_agent: dict[str, list[dict]] = {}
    to_screen: list[tuple[dict, str]] = []

    for agent in agents_to_run:
        pending_entries = [
            entry for entry in entries
            if not results[entry["key"]].get(f"{agent}_decision")
            or results[entry["key"]].get(f"{agent}_decision") == "error"
        ]
        already_screened_by_agent[agent] = len(entries) - len(pending_entries)

        selected_entries = pending_entries[: args.limit] if args.limit is not None else pending_entries
        selected_entries_by_agent[agent] = selected_entries

    max_rounds = max((len(entries) for entries in selected_entries_by_agent.values()), default=0)
    for idx in range(max_rounds):
        for agent in agents_to_run:
            agent_entries = selected_entries_by_agent[agent]
            if idx < len(agent_entries):
                to_screen.append((agent_entries[idx], agent))

    if args.limit is not None:
        print(f"  Limiting to the next {args.limit} pending papers per selected agent.", file=sys.stderr)

    selected_keys = {entry["key"] for entry, _ in to_screen}
    total_entries = len(selected_keys) if args.limit is not None else len(entries)
    skipped = sum(already_screened_by_agent.values())

    for agent in agents_to_run:
        selected_count = sum(1 for _, task_agent in to_screen if task_agent == agent)
        print(
            f"  {agent}: {already_screened_by_agent[agent]} already screened, "
            f"{selected_count} task{'s' if selected_count != 1 else ''} queued.",
            file=sys.stderr,
        )

    print(
        f"  {len(to_screen)} total task{'s' if len(to_screen) != 1 else ''} to process "
        f"({args.workers} worker{'s' if args.workers != 1 else ''}, round-robin by agent).",
        file=sys.stderr,
    )

    csv_lock  = threading.Lock()
    completed = 0
    errors    = 0
    total     = len(to_screen)

    def screen_one(entry: dict, agent: str) -> tuple[dict, str, str, str]:
        prompt = PROMPT_TEMPLATE.format(
            title=entry["title"] or "(no title)",
            abstract=entry["abstract"],
        )
        decision, reason = call_agent(agent, prompt)
        return entry, agent, decision, reason

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(screen_one, entry, agent): (entry, agent) for entry, agent in to_screen}
        for fut in as_completed(futures):
            try:
                entry, agent, decision, reason = fut.result()
            except Exception as exc:
                entry, agent = futures[fut]
                decision = "error"
                reason   = str(exc)[:300]

            with csv_lock:
                results[entry["key"]][f"{agent}_decision"] = decision
                results[entry["key"]][f"{agent}_reason"] = reason
                completed += 1
                if decision == "error":
                    errors += 1
                save_csv(csv_path, results)

            print(
                f"[{completed}/{total}] agent={agent} result={decision} title={entry['title'][:70]}",
                file=sys.stderr,
            )

    print(
        f"\nDone.  Screened: {completed}  Errors: {errors}  "
        f"Skipped (already done): {skipped}  Total: {total_entries}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
