# 2 — Screening

Title/abstract screening across three AI raters (OpenAI, Anthropic, Gemini) plus two human raters. Unanimous AI includes are sent to the humans; their decisions are merged and conflicts resolved manually.

## Layout

- `scripts/generate_payloads.py` — read `artifacts/all_papers.csv`, write per-provider batch payloads into `payloads/` (gitignored: regenerated on demand).
- `scripts/submit_payload.py` — submit one payload file to a provider's batch API.
- `results/` — raw batch outputs (`{provider}-batch-{NNN}.jsonl`) kept for reproducibility.
- `decisions/first.csv` — initial pilot screening on the first search.
- `decisions/lucas.csv`, `decisions/victor.csv` — two human raters on the April 2026 AI-unanimous set.
- `notebooks/evaluate_raters.ipynb` — AI rater agreement and screening cache.
- `notebooks/analyze_decisions.ipynb` — human screening merge, conflict log, included BibTeX.

## Run order

```sh
uv run python scripts/generate_payloads.py
uv run python scripts/submit_payload.py payloads/<file>.jsonl   # per provider, per chunk
# Wait for batches to complete, then fetch results into results/ via each provider's batch API.
uv run jupyter lab notebooks/evaluate_raters.ipynb       # -> processed.csv, unanimous_include.csv
# Fill decisions/lucas.csv and decisions/victor.csv for the unanimous-include subset
uv run jupyter lab notebooks/analyze_decisions.ipynb     # -> conflicts.csv, included.bib
```

## Outputs

| Artifact | Notebook |
| -------- | -------- |
| `../artifacts/processed.csv` | `evaluate_raters.ipynb` |
| `../artifacts/unanimous_include.csv` | `evaluate_raters.ipynb` |
| `../artifacts/conflicts.csv` | `analyze_decisions.ipynb` |
| `../artifacts/included.bib` | `analyze_decisions.ipynb` |

The screening prompt's IC/EC strings are embedded in `scripts/generate_payloads.py`. The current `results/*.jsonl` were produced under earlier phrasing; only future re-runs reflect the updated text.
