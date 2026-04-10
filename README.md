# Literature Review — Paper Screening

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

## Screening script (`screen.py`)

`screen.py` reads a BibTeX file, calls one or more AI CLI agents for each paper, and records include/exclude decisions in a CSV. Three agents (claude, gemini, codex) are supported and their decisions are written to separate columns for later comparison.

### Prerequisites

- **Python ≥ 3.14** and [uv](https://docs.astral.sh/uv/)
- At least one AI CLI agent installed and authenticated:
  - `claude` — [Claude Code](https://claude.ai/code)
  - `gemini` — [Gemini CLI](https://github.com/google-gemini/gemini-cli)
  - `codex` — [OpenAI Codex CLI](https://github.com/openai/codex)

### Installation

```bash
uv sync
```

### Usage

```bash
# Screen with a specific agent
python screen.py --agent claude
python screen.py --agent gemini
python screen.py --agent codex

# Omit --agent to run all three agents (claude, gemini, codex)
python screen.py

# Test with the first 10 papers before committing to the full run
python screen.py --agent claude --limit 10

# Override input/output paths
python screen.py --agent claude --input papers/papers.bib --output screening_results.csv

# Increase parallel agent calls (workers)
python screen.py --agent claude --workers 5
```

Each command is independent and can be run on different machines or at different times. Re-running is safe: papers that already have a successful decision for the selected agents are skipped.

### Output

Results are written to `screening_results.csv` with the following columns:

| Column | Values | Description |
|---|---|---|
| `key` | string | BibTeX citation key (primary key) |
| `title` | string | Paper title |
| `abstract` | string | Abstract text, or `N/A` if missing |
| `claude_decision` | `include` / `exclude` / `error` | Claude's screening decision |
| `claude_reason` | string | One-sentence rationale |
| `codex_decision` | `include` / `exclude` / `error` | Codex's screening decision |
| `codex_reason` | string | One-sentence rationale |
| `gemini_decision` | `include` / `exclude` / `error` | Gemini's screening decision |
| `gemini_reason` | string | One-sentence rationale |

### Observations and caveats

- **Checkpoint/resume**: The CSV is written after every paper. If the run is interrupted, restart the same command — already-screened papers are skipped automatically.
- **Error retry**: Papers where the agent returned an unparseable response (`error`) are always retried on the next run, unlike successful decisions.
- **Missing abstracts**: Papers without an abstract field in the BibTeX are sent to the agent with the note `N/A`. The agent is asked to decide on title alone.
- **Timeout**: Each agent call times out after 60 seconds. Timed-out papers are marked `error` and retried on the next run.
- **Response parsing**: The script looks for `Decision: include|exclude` and `Reason: ...` in the agent's output. If the agent's response does not match this format, the decision is set to `error` and the first 300 characters of the raw output are stored as the reason.
- **Parallel execution**: By default, papers are processed sequentially with one worker. You can increase parallelism with `--workers`; for example, with 5 workers, the script runs up to 5 agent calls in parallel. For ~3,788 papers at ~10 seconds per call, wall-clock time scales roughly with `1 / workers` in optimistic settings.
- **Agent commands**: The CLI commands used for each agent are defined at the top of `screen.py` in `AGENT_COMMANDS`. Edit them if your installation uses different flags or paths.

## Data sources

Papers were collected from three databases using a keyword search string targeting environmental impacts of HPC systems. See `main.md` for the full search string, database details, and preprocessing steps.

Raw BibTeX files are in `papers/`:
- `acm.bib` — ACM Digital Library results
- `ieee.bib` — IEEE Xplore results
- `scopus.bib` — Scopus results
- `papers.bib` — Merged and deduplicated (~3,788 papers)
