# Literature Review Artifacts

Artifacts pipeline of the paper "The Environmental Impacts Of High-Performance Computing: A Systematic Mapping Study".

The pipeline is organized into four phases. Each phase has its own folder with a README.

```
1_search/      Database exports and merged BibTeX
2_screening/   AI + human title/abstract screening
3_coding/      Prompt-driven keywording, extraction, and scheme classification
4_analysis/    Scripts and notebooks that produce paper-facing tables and figures
artifacts/     All generated outputs (read by every phase)
figures/       Generated figures (consumed by the paper)
tables/        Generated LaTeX tables (consumed by the paper)
```

The project is managed by `uv`. Run any Python entry point with `uv run python <path>`.

## Research questions

| ID | Research question |
| :--- | :--- |
| RQ1 | What is the current landscape of research on the environmental impacts of HPC? |
| RQ2 | How does the literature study and address the environmental impacts of HPC? |
| RQ3 | Where are the blind spots in current research on the environmental impacts of HPC? |

## Selection criteria

Include if any apply:
- **IC1**: Reports addressing at least one environmental impact in the HPC context.
- **IC2**: Reports presenting methodologies for predicting or measuring the environmental impacts of HPC systems.

Exclude if any apply:
- **EC1**: Reports not related to the literature review scope.
- **EC2**: Reports focusing solely on energy without connecting to broader environmental impacts.
- **EC3**: Reports not in English, unavailable, or inaccessible.

## Search string

```
(
    TITLE-ABS-KEY("high-performance computing" OR supercomputing OR supercomputer OR HPC)
    AND
    TITLE-ABS-KEY("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth")
)
```

Initial run used `TITLE` only for the HPC terms. The April 2026 run added abstract and keywords.

## Search yields (April 2026 re-run)

| Database | Papers |
| -------- | -----: |
| ACM | 532 |
| IEEE | 1,505 |
| Scopus | 2,775 |

| Stage | Papers |
| -------- | -----: |
| After the searches | 4,812 |
| After deduplication | 3,788 |
| Rows in `artifacts/all_papers.csv` after merging with the first search | 3,795 |
| Unique papers after collapsing duplicate aliases via `canonical_id` | 3,793 |
| Unanimous includes across the three AI raters (`unanimous_include.csv`) | 244 |
| New papers included in the final corpus | 33 |
| Final corpus (consumed by the paper) | 62 |

## Pipeline

### Phase 1 — Search and merge (`1_search/`)

Manual exports from each database. The merge step produces `papers.bib` and the screening input `artifacts/all_papers.csv`.

Outputs:
- `1_search/acm.bib`, `ieee.bib`, `scopus.bib` — raw exports
- `1_search/papers.bib` — merged, deduplicated
- `artifacts/all_papers.csv` — screening input with columns `id, canonical_id, title, abstract`

### Phase 2 — AI and human screening (`2_screening/`)

Three AI providers (OpenAI, Anthropic, Gemini) screen every paper in `all_papers.csv`. Papers unanimously included are routed to two human raters whose decisions are merged into a final include/exclude set.

```sh
uv run python 2_screening/scripts/generate_payloads.py
uv run python 2_screening/scripts/submit_payload.py 2_screening/payloads/<file>.jsonl
```

Then open the notebooks (`uv run jupyter lab`):
- `2_screening/notebooks/evaluate_raters.ipynb` — rater agreement metrics, writes `artifacts/processed.csv` and `artifacts/unanimous_include.csv`.
- `2_screening/notebooks/analyze_decisions.ipynb` — merges `2_screening/decisions/{first,lucas,victor}.csv`; writes `artifacts/conflicts.csv` and `artifacts/included.bib`.

Observation: Papers 865 and 2140 returned `"type": "succeeded"` from the Anthropic API with an empty `content: []`. Known rare Anthropic edge case (successful response, empty output).

### Phase 3 — Coding (`3_coding/`)

Prompt-driven per-paper coding against markdown copies of the corpus papers. The markdowns themselves are not included in this repository because the underlying papers are third-party publications and not redistributable; obtain them from the original publishers via the DOIs in `artifacts/included.bib`. Each prompt owns specific columns in specific artifact files:

| Prompt | Updates |
| ------ | ------- |
| `prompts/keywording.md` (initial) and `prompts/keywording_revision.md` (full-text revision) | `artifacts/keywording.csv` |
| `prompts/extraction.md` | `artifacts/extraction.csv` |
| `prompts/scheme.md` | `artifacts/scheme.json`, `artifacts/scheme_log.md`, `artifacts/others.csv` |

The scheme workflow is iterative. `scheme.md` derives and revises the four SMS facets from `keywording.csv`, stores per-category paper-id arrays in `classification`, and appends a dated entry to `scheme_log.md` for every batch.

### Phase 4 — Analysis and outputs (`4_analysis/`)

```sh
uv run python 4_analysis/scripts/build_merge.py                    # -> artifacts/merge.csv
uv run python 4_analysis/scripts/build_presence_matrix.py          # -> tables/presence-matrix.tex
uv run python 4_analysis/scripts/build_venue_categories_table.py   # -> tables/venue-categories.tex
```

Open `4_analysis/notebooks/plots.ipynb` (`uv run jupyter lab`) and run all cells to refresh `figures/`.

The paper repository copies `figures/` and `tables/` in when it builds. Nothing in this repository writes outside its own tree.

## Artifacts reference

All files live in `artifacts/` unless noted.

| File | Producer | Consumer | Notes |
| ---- | -------- | -------- | ----- |
| `all_papers.csv` | Search merge (manual) | screening payloads, every downstream notebook | screening input, 3,795 rows |
| `processed.csv` | `evaluate_raters.ipynb` | `evaluate_raters.ipynb` | normalized AI screening cache |
| `unanimous_include.csv` | `evaluate_raters.ipynb` | human rater input | 244 papers |
| `conflicts.csv` | `analyze_decisions.ipynb` | `analyze_decisions.ipynb` | human-rater disagreement log, resolved manually |
| `included.bib` | `analyze_decisions.ipynb` | the paper bibliography | BibTeX export of included papers; refresh when the corpus changes |
| `keywording.csv` | `prompts/keywording.md` | `prompts/scheme.md` | per-paper keywords |
| `extraction.csv` | `prompts/extraction.md` | `build_merge.py` | source of truth for `methodological_approach`, `data_source`, `assessment_orientation` |
| `others.csv` | `prompts/scheme.md` | `build_merge.py` | only `research_type` is used downstream; the other columns duplicate `extraction.csv` and are kept as a transparency byproduct of the scheme workflow (not part of the final analysis) |
| `scheme.json` | `prompts/scheme.md` | `build_merge.py` | facet definitions and `classification` arrays |
| `scheme_log.md` | `prompts/scheme.md` | reproducibility audit | dated per-batch revision notes |
| `metadata.csv` | one-shot Zotero sync and venue enrichment, committed | `build_merge.py` | paper metadata spine for the 62-paper corpus |
| `merge.csv` | `build_merge.py` | tables, figures | master joined view |

## Repository conventions

- Managed with `uv`. Do not invoke `python` directly; use `uv run python <script>`.
- Do not list AI systems in `Co-authored-by:` trailers.
- Keep commit messages concise.
