# 2 Screening

This stage screens titles and abstracts with three AI raters: OpenAI, Anthropic,
and Gemini. Two human reviewers check the records that all three AI raters
include. A manual review resolves disagreements between the human reviewers.

## Layout

| File or folder | Purpose |
| --- | --- |
| `scripts/generate_payloads.py` | Reads `artifacts/all_papers.csv` and writes batch requests for each provider to `payloads/`. Git ignores these generated files. |
| `scripts/submit_payload.py` | Sends one request file to a provider's batch API. |
| `results/` | Keeps raw batch outputs (`{provider}-batch-{NNN}.jsonl`) so results can be checked. |
| `decisions/first.csv` | Contains human decisions for the initial search and snowball findings. |
| `decisions/lucas.csv`, `decisions/victor.csv` | Contain human decisions for the April 2026 set selected by all three AI raters. |
| `notebooks/evaluate_raters.ipynb` | Checks AI agreement and saves screening results. |
| `notebooks/analyze_decisions.ipynb` | Combines human decisions and writes the conflict log and included BibTeX records. |

## Run order

The commands below describe the original screening workflow. The submission
command sends requests to a model provider. For benchmark preparation, use the
local rebuild command in the benchmark README.

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

The IC/EC text for the screening prompt is in `scripts/generate_payloads.py`.
The current `results/*.jsonl` used earlier wording. New runs use the updated text.

## Methodology benchmark

[benchmark/README.md](benchmark/README.md) describes the benchmark with human labels.
It explains ID corrections, abstract sources, approved record removals, and local
checks. The benchmark keeps the published criteria and the original source files.
