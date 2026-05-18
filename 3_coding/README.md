# 3 — Coding

Prompt-driven per-paper coding against markdown copies of the included papers. The markdowns themselves are not included in this repository because the underlying papers are third-party publications and not redistributable; obtain them from the original publishers via the DOIs in `../artifacts/included.bib`. Each prompt owns specific columns in specific artifact files.

| Prompt | Updates |
| ------ | ------- |
| `prompts/keywording.md` | `../artifacts/keywording.csv` (keywords, notes from title/abstract) |
| `prompts/keywording_revision.md` | `../artifacts/keywording.csv` (revise from intro + conclusion full text) |
| `prompts/extraction.md` | `../artifacts/extraction.csv` (methodological_approach, data_source, assessment_orientation) |
| `prompts/scheme.md` | `../artifacts/scheme.json`, `../artifacts/scheme_log.md`, `../artifacts/others.csv` |

## Scheme workflow

`scheme.md` runs iteratively over successive batches of papers. Each batch:
1. Reads the current `scheme.json`, batch rows from `keywording.csv`, and the rolling `scheme_log.md`.
2. Revises the four SMS facets if new evidence requires it.
3. Adds per-category paper-id arrays to `classification`.
4. Appends a dated entry to `scheme_log.md`.

The four facets are: `Environmental impacts`, `Lifecycle stages`, `System locus`, `Management and intervention levers`.

## Note on `others.csv`

The scheme prompt writes a `research_type` column into `others.csv`. The same prompt also writes denormalized copies of `methodological_approach`, `data_source`, and `assessment_orientation` into `others.csv` as a byproduct of how the scheme prompt is structured, but those columns were not used in the final analysis — `extraction.csv` is the source of truth. Kept for transparency.

Each prompt has a self-contained header with the research questions and selection criteria; they do not depend on the top-level README.
