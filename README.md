# Literature Review — Paper Screening

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

### Installation

```bash
uv sync
```

## Batch screening (`screening.py`)

`screening.py` runs the batch screening workflow in the foreground with a Rich dashboard, submits title/abstract screening requests to the OpenAI Batch API, and persists the workflow state in `<batch_id>.json`.

### Input

The input must be a CSV with exactly these columns:

| Column | Description |
|---|---|
| `id` | Stable paper identifier used as the JSON key and batch `custom_id` |
| `title` | Paper title |
| `abstract` | Paper abstract |

### Usage

```bash
uv run python screening.py --input papers_to_screen.csv --model gpt-5-mini --batch-id april-run-01 --papers-per-batch 250
```

All flags are mandatory:

- `--input`: CSV file with `id,title,abstract`
- `--model`: OpenAI model name passed through to the Responses API
- `--batch-id`: Local batch label used for the state file name `<batch_id>.json`
- `--papers-per-batch`: Maximum number of non-prefiltered papers submitted in each remote batch

Optional flags:

- `--poll-interval-seconds`: Poll interval between remote batch checks; defaults to `30`

### Behavior

- The script excludes some papers locally before any API call.
- missing title or abstract -> `missing_metadata`
- `hydroxypropyl cellulose` false positives -> `EC1`
- concrete/materials false positives -> `EC1`
- Remaining papers are sent through the OpenAI Batch API with `temperature=0`, strict JSON-schema output, and low output-token limits.
- The script submits at most `--papers-per-batch` papers per remote batch and keeps only one remote batch active at a time.
- Each invocation is live and foregrounded: it resumes any active remote batch, polls until that batch changes state, merges completed outputs, submits the next chunk automatically, and continues until all papers are processed or a terminal failure occurs.
- The terminal UI shows the local batch id, remote batch id, current status, overall progress, current batch size, remaining papers, and a compact decision summary.
- The expected model response is:

```json
{
  "decision": "include",
  "reason": ["IC1"]
}
```

- If the title and abstract are insufficient, the model is instructed to return:

```json
{
  "decision": "include",
  "reason": ["doubt"]
}
```

### State file

The script writes `<batch_id>.json` with this structure:

```json
{
  "metadata": {
    "batch_id": "april-run-01",
    "status": "waiting batch",
    "provider": "openai",
    "model": "gpt-5-mini",
    "input_file": "papers_to_screen.csv",
    "submitted_count": 42,
    "prefiltered_count": 3,
    "papers_per_batch": 250,
    "total_papers": 1000,
    "current_batch_size": 250,
    "remote_batch_id": "batch_...",
    "started_at": "2026-04-12T10:00:00Z",
    "updated_at": "2026-04-12T10:03:00Z",
    "current_batch_submitted_at": "2026-04-12T10:02:00Z"
  },
  "papers": {
    "1": {
      "source": "prefilter",
      "decision": "exclude",
      "reason": ["EC1"]
    }
  }
}
```

- `metadata.status = "waiting batch"` means the batch is still running or waiting to be checked again.
- `metadata.status = "done"` means the final merged results have already been written and later runs will do nothing.
- `metadata.status = "failed"`, `completed_with_failed_requests`, and `cancelled_with_partial_output` are terminal failure states that stop automatic progress until you inspect the batch.
- `current_batch_size` is the number of papers currently assigned to the active remote batch.
- `remote_batch_id` stores the actual OpenAI batch ID returned by the API so subsequent runs can keep polling the same remote batch while you continue using your chosen local `--batch-id`.
- `started_at` is when the local workflow state was first created.
- `updated_at` is refreshed every time the state file is rewritten.
- `current_batch_submitted_at` records when the currently active remote batch was submitted.

### Estimated cost

The figures below now use the observed usage from one complete screening run of the current workflow:

- submitted requests: `3,465`
- input tokens: `1,839,672`
- output tokens: `73,623`

Using those actual token totals, the estimated total screening cost is roughly:

OpenAI Batch API:

| Model | Conservative upper bound |
|---|---:|
| `gpt-5` | about `$3.04` |
| `gpt-5-mini` | about `$0.61` |
| `gpt-5-nano` | about `$0.12` |

Anthropic Message Batches:

| Model | Conservative upper bound |
|---|---:|
| `claude-opus-4.6` | about `$5.52` |
| `claude-sonnet-4.6` | about `$3.31` |
| `claude-haiku-4.5` | about `$0.88` |

Gemini Batch API:

| Model | Conservative upper bound |
|---|---:|
| `gemini-2.5-pro` | about `$1.52` |
| `gemini-2.5-flash` | about `$0.37` |
| `gemini-2.5-flash-lite` | about `$0.11` |

These are estimates rather than exact bills, but they should now be much closer to the real spend because they are based on observed token usage rather than a conservative upper bound:

```json
{
  "decision": "include",
  "reason": ["IC1"]
}
```

The OpenAI figures use the current API pricing page as of 2026-04-12 and Batch pricing rates from [OpenAI API pricing](https://platform.openai.com/docs/pricing/). The Anthropic figures use 50%-discounted batch pricing derived from the current model pricing page and recent model announcements: [Anthropic pricing](https://docs.anthropic.com/en/docs/about-claude/pricing), [Introducing Claude Opus 4.6](https://www.anthropic.com/news/introducing-claude-opus-4-6), and [Introducing Claude Sonnet 4.6](https://www.anthropic.com/news/introducing-claude-sonnet-4-6). The Gemini figures use current Batch pricing from [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing#batch). For Gemini, this assumes each screening prompt stays in the `<= 200k` input-token tier, which it should by a large margin for title/abstract screening.

## Data sources

Papers were collected from three databases using a keyword search string targeting environmental impacts of HPC systems. See `main.md` for the full search string, database details, and preprocessing steps.

Raw BibTeX files are in `papers/`:
- `acm.bib` — ACM Digital Library results
- `ieee.bib` — IEEE Xplore results
- `scopus.bib` — Scopus results
- `papers.bib` — Merged and deduplicated (~3,788 papers)


## Screening script (`screen.py`)

`screen.py` reads a BibTeX file, calls one or more AI CLI agents for each paper, and records include/exclude decisions in a CSV. Three agents (claude, gemini, codex) are supported and their decisions are written to separate columns for later comparison.

This script is deprecated. Prefer `screening.py` for the current API-based batch workflow.

### Prerequisites

- **Python ≥ 3.14** and [uv](https://docs.astral.sh/uv/)
- At least one AI CLI agent installed and authenticated:
  - `claude` — [Claude Code](https://claude.ai/code)
  - `gemini` — [Gemini CLI](https://github.com/google-gemini/gemini-cli)
  - `codex` — [OpenAI Codex CLI](https://github.com/openai/codex)

### Usage

```bash
# Screen with a specific agent
python screen.py --agent claude
python screen.py --agent gemini
python screen.py --agent codex

# Screen with multiple specific agents
python screen.py --agent claude --agent codex
python screen.py --agent claude,gemini

# Omit --agent to run all three agents (claude, gemini, codex)
python screen.py

# Process the next 10 pending papers for these agents
python screen.py --agent claude --limit 10

# Override input/output paths
python screen.py --agent claude --input papers/papers.bib --output screening_results.csv

# Increase parallel agent calls (workers)
python screen.py --agent claude --workers 5
```

Each command is independent and can be run on different machines or at different times. Re-running is safe: papers that already have a successful decision for the selected agents are skipped. When you use `--limit N`, the script takes the next `N` pending papers for each selected agent, so different agents can advance through different batches if they have different gaps or errors.
When multiple agents are selected in a single run, their pending papers are queued in round-robin order by agent, so work starts across `claude`, `gemini`, and `codex` earlier instead of running one agent's queue first.

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
- **Parallel execution**: By default, papers are processed sequentially with one worker. You can increase parallelism with `--workers`; for example, with 5 workers, the script runs up to 5 agent calls in parallel. In multi-agent runs, tasks are submitted round-robin by agent, so completion logs can interleave agents naturally. For ~3,788 papers at ~10 seconds per call, wall-clock time scales roughly with `1 / workers` in optimistic settings.
- **Agent commands**: The CLI commands used for each agent are defined at the top of `screen.py` in `AGENT_COMMANDS`. Edit them if your installation uses different flags or paths.
