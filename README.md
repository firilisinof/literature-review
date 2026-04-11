# Literature Review — Paper Screening

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

### Installation

```bash
uv sync
```

## Batch screening (`screening.py`)

`screening.py` submits title/abstract screening requests to the OpenAI Batch API and persists the workflow state in `<batch_id>.json`.

### Input

The input must be a CSV with exactly these columns:

| Column | Description |
|---|---|
| `id` | Stable paper identifier used as the JSON key and batch `custom_id` |
| `title` | Paper title |
| `abstract` | Paper abstract |

### Usage

```bash
python screening.py --input papers_to_screen.csv --model gpt-5-mini --batch-id april-run-01
```

All flags are mandatory:

- `--input`: CSV file with `id,title,abstract`
- `--model`: OpenAI model name passed through to the Responses API
- `--batch-id`: Local batch label used for the state file name `<batch_id>.json`

### Behavior

- The script excludes some papers locally before any API call:
  - missing title or abstract -> `missing_metadata`
  - `hydroxypropyl cellulose` false positives -> `EC1`
  - concrete/materials false positives -> `EC1`
- Remaining papers are sent through the OpenAI Batch API with a fixed seed, `temperature=0`, strict JSON-schema output, and low output-token limits.
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
    "seed": 12345,
    "input_file": "papers_to_screen.csv",
    "submitted_count": 42,
    "prefiltered_count": 3,
    "remote_batch_id": "batch_..."
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
- `remote_batch_id` stores the actual OpenAI batch ID returned by the API so subsequent runs can keep polling the same remote batch while you continue using your chosen local `--batch-id`.

### Expected cost

With the current dataset, `screening.py` locally filters some obvious false positives before submitting anything to OpenAI. Based on the current corpus:

- total papers: about `3,795`
- locally prefiltered: about `326`
- submitted to OpenAI: about `3,469`

Using the same workload estimate throughout:

- submitted prompts: about `3,469`
- estimated input tokens total: about `1.61M`
- conservative output upper bound: about `277,520` tokens (`80` per paper)

the expected total screening cost is roughly:

OpenAI Batch API:

| Model | Conservative upper bound |
|---|---:|
| `gpt-5` | about `$4.10` |
| `gpt-5-mini` | about `$1.23` |
| `gpt-5-nano` | about `$0.34` |

Anthropic Message Batches:

| Model | Conservative upper bound |
|---|---:|
| `claude-opus-4.6` | about `$7.51` |
| `claude-sonnet-4.6` | about `$4.50` |
| `claude-haiku-4.5` | about `$1.50` |

Gemini Batch API:

| Model | Conservative upper bound |
|---|---:|
| `gemini-2.5-pro` | about `$2.40` |
| `gemini-2.5-flash` | about `$0.59` |
| `gemini-2.5-flash-lite` | about `$0.14` |

These are estimates rather than exact bills. Actual cost should usually be a bit lower because the expected JSON response is very small:

```json
{
  "decision": "include",
  "reason": ["IC1"]
}
```

The Anthropic and Gemini figures use the current batch pricing pages as of 2026-04-11 and the same token assumptions as the OpenAI estimates above. The Anthropic table uses current non-deprecated Claude text models from [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing). The Gemini table uses current stable Gemini text models from [Gemini batch pricing](https://ai.google.dev/gemini-api/docs/pricing#batch). For Gemini, this assumes each screening prompt stays in the `<= 200k` input-token tier, which it should by a large margin for title/abstract screening.

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
