#!/usr/bin/env python3
"""
screen.py — AI-assisted title/abstract screening for systematic mapping studies.

Calls a CLI agent (claude, gemini, or codex) for each paper in a BibTeX file
and records include/exclude decisions in a CSV. Designed to be run once per
agent; re-runs skip already-screened papers unless they errored.

Usage:
    python screen.py --agent claude
    python screen.py --agent gemini --limit 10 --workers 5
    python screen.py --agent codex --input papers/papers.bib --output screening_results.csv
"""

import argparse
import csv
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import bibtexparser

# ---------------------------------------------------------------------------
# Configuration — edit command lists here if needed
# ---------------------------------------------------------------------------

AGENT_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "-p"],   # prompt appended as next arg
    "gemini": ["gemini", "-p"],
    "codex":  ["codex", "exec"],
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

TIMEOUT = 60  # seconds per agent call

# ---------------------------------------------------------------------------
# BibTeX helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip BibTeX braces and normalise whitespace."""
    text = text.replace("{", "").replace("}", "")
    return " ".join(text.split())


def load_bib(path: Path) -> list[dict]:
    """Parse a BibTeX file and return a list of {key, title, abstract} dicts."""
    with open(path, encoding="utf-8", errors="replace") as f:
        db = bibtexparser.load(f)
    entries = []
    for e in db.entries:
        title    = _clean(e.get("title", ""))
        abstract = _clean(e.get("abstract", "")) or "N/A"
        entries.append({
            "key":      e.get("ID", ""),
            "title":    title,
            "abstract": abstract,
        })
    return entries

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> dict[str, dict]:
    """Load an existing results CSV into a dict keyed by citation key."""
    if not path.exists():
        return {}
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
    except subprocess.TimeoutExpired:
        return "error", "timeout"
    except FileNotFoundError:
        sys.exit(f"Error: '{agent}' CLI not found. Is it installed and on PATH?")

    dec_match = re.search(r"Decision:\s*(include|exclude)", output, re.IGNORECASE)
    rea_match = re.search(r"Reason:\s*(.+)", output, re.IGNORECASE)

    decision = dec_match.group(1).lower() if dec_match else "error"
    reason   = rea_match.group(1).strip() if rea_match else output[:300]
    return decision, reason

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screen BibTeX papers with a CLI AI agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent", required=True, choices=list(AGENT_COMMANDS),
        help="CLI agent to use for screening",
    )
    parser.add_argument(
        "--input", default="papers/papers.bib",
        help="Path to BibTeX file (default: papers/papers.bib)",
    )
    parser.add_argument(
        "--output", default="screening_results.csv",
        help="Path to output CSV (default: screening_results.csv)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process only the first N papers (useful for testing)",
    )
    parser.add_argument(
        "--workers", type=int, default=1, metavar="N",
        help="Number of parallel agent calls (default: 1, recommended: 5–10)",
    )
    args = parser.parse_args()

    bib_path = Path(args.input)
    csv_path = Path(args.output)
    agent    = args.agent
    dec_col  = f"{agent}_decision"
    rea_col  = f"{agent}_reason"

    # On first run, build the CSV from the BibTeX file.
    # On subsequent runs, load the CSV directly — no BibTeX parsing needed.
    if csv_path.exists():
        print(f"Loading {csv_path} ...", file=sys.stderr)
        results = load_csv(csv_path)
        print(f"  {len(results)} papers loaded from CSV.", file=sys.stderr)
    else:
        print(f"No CSV found. Parsing {bib_path} to initialise {csv_path} ...", file=sys.stderr)
        results = {}
        for e in load_bib(bib_path):
            results[e["key"]] = {col: "" for col in CSV_COLUMNS} | {
                "key":      e["key"],
                "title":    e["title"],
                "abstract": e["abstract"],
            }
        save_csv(csv_path, results)
        print(f"  {len(results)} papers written to {csv_path}.", file=sys.stderr)

    entries = list(results.values())

    if args.limit is not None:
        entries = entries[: args.limit]
        print(f"  Limiting to first {args.limit} papers.", file=sys.stderr)

    # Split into already-done and pending
    to_screen = [
        e for e in entries
        if not results[e["key"]].get(dec_col) or results[e["key"]].get(dec_col) == "error"
    ]
    skipped = len(entries) - len(to_screen)

    print(
        f"  {skipped} already screened, {len(to_screen)} to process "
        f"({args.workers} worker{'s' if args.workers != 1 else ''}).",
        file=sys.stderr,
    )

    csv_lock  = threading.Lock()
    completed = 0
    errors    = 0
    total     = len(to_screen)

    def screen_one(entry: dict) -> tuple[dict, str, str]:
        prompt = PROMPT_TEMPLATE.format(
            title=entry["title"] or "(no title)",
            abstract=entry["abstract"],
        )
        decision, reason = call_agent(agent, prompt)
        return entry, decision, reason

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(screen_one, e): e for e in to_screen}
        for fut in as_completed(futures):
            try:
                entry, decision, reason = fut.result()
            except Exception as exc:
                entry    = futures[fut]
                decision = "error"
                reason   = str(exc)[:300]

            with csv_lock:
                results[entry["key"]][dec_col] = decision
                results[entry["key"]][rea_col] = reason
                completed += 1
                if decision == "error":
                    errors += 1
                save_csv(csv_path, results)

            print(
                f"[{completed}/{total}] {agent} → {decision}: {entry['title'][:70]}",
                file=sys.stderr,
            )

    print(
        f"\nDone.  Screened: {completed}  Errors: {errors}  "
        f"Skipped (already done): {skipped}  Total: {len(entries)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
