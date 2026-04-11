# Literature Review — Paper Screening

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

### Installation

```bash
uv sync
```

## Batch screening (`screening.py`)

`screening.py` runs the batch screening workflow in the foreground with a Rich dashboard, submits title/abstract screening requests to the OpenAI Batch API, and persists the workflow state in `<batch_id>.json`.

Today the implementation is OpenAI-only, even though the workflow is intentionally structured so another provider client could be added later.

### Input

The input must be a CSV with exactly these columns:

| Column | Description |
|---|---|
| `id` | Stable paper identifier used as the JSON key and batch `custom_id` |
| `title` | Paper title |
| `abstract` | Paper abstract |

### Usage

```bash
uv run python screening.py --input papers/papers.csv --model gpt-5-mini --batch-id april-run-01 --papers-per-batch 250
```

All flags are mandatory:

- `--input`: CSV file with `id,title,abstract` such as `papers/papers.csv`
- `--model`: OpenAI model name passed through to the Responses API
- `--batch-id`: Local batch label used for the state file name `<batch_id>.json`
- `--papers-per-batch`: Maximum number of non-prefiltered papers submitted in each remote batch

Optional flags:

- `--dry-run`: Simulate the workflow without calling the API
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
- With `--dry-run`, the script avoids all API calls, simulates remote batches locally, and records each non-prefiltered paper as `{"decision": "include", "reason": ["doubt"]}` with source `dry_run`.
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
    "dry_run": false,
    "model": "gpt-5-mini",
    "input_file": "papers/papers.csv",
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
- `dry_run = true` means the workflow was simulated locally without API calls.
- `current_batch_size` is the number of papers currently assigned to the active remote batch.
- `remote_batch_id` stores the actual OpenAI batch ID returned by the API so subsequent runs can keep polling the same remote batch while you continue using your chosen local `--batch-id`.
- `started_at` is when the local workflow state was first created.
- `updated_at` is refreshed every time the state file is rewritten.
- `current_batch_submitted_at` records when the currently active remote batch was submitted.

### Estimated cost

The figures below use the observed usage from one complete screening run of the current OpenAI Batch workflow:

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

These are estimates rather than exact bills, but they should now be much closer to the real spend because they are based on observed token usage rather than a conservative upper bound:

```json
{
  "decision": "include",
  "reason": ["IC1"]
}
```

The OpenAI figures use the current API pricing page as of 2026-04-12 and Batch pricing rates from [OpenAI API pricing](https://platform.openai.com/docs/pricing/).

## Data sources

Papers were collected from three databases using a keyword search string targeting environmental impacts of HPC systems. The full search strings and review protocol are documented in [AGENTS.md](/Users/lucas/ws/literature-review/AGENTS.md:1).

Raw BibTeX files are in `papers/`:
- `acm.bib` — ACM Digital Library results
- `ieee.bib` — IEEE Xplore results
- `scopus.bib` — Scopus results
- `papers.bib` — Merged and deduplicated (~3,788 papers)
- `papers.csv` — screening input with canonical `id,title,abstract` columns

Current generated artifacts:
- `<batch_id>.json` — screening workflow state plus decisions keyed by paper `id`
- `results/testing.json` — example captured batch-state artifact
