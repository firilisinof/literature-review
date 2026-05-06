# Literature Review

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

## Data sources

Papers were collected from three databases using a keyword search string targeting environmental impacts of HPC systems. The full search strings and review protocol are documented in below.

Raw BibTeX files are in `papers/`:
- `acm.bib` — ACM Digital Library results
- `ieee.bib` — IEEE Xplore results
- `scopus.bib` — Scopus results
- `papers.bib` — Merged and deduplicated (3,788 papers)

Generated review artifacts are organized by directory:
- `artifacts/all_papers.csv` — screening input: `id,canonical_id,title,abstract` columns. `id` preserves the original row identifier, while `canonical_id` is used to collapse known duplicate rows when counting unique papers.
- `artifacts/processed.csv` — normalized screening decisions cache built from the provider batch outputs in `results/`
- `artifacts/unanimous_include.csv` — papers unanimously included by Anthropic, OpenAI, and Gemini
- `artifacts/included.bib` — BibTeX export for the included papers
- `artifacts/metadata.csv`, `artifacts/keywording.csv`, `artifacts/extraction.csv`, `artifacts/others.csv`, `artifacts/scheme.json` — downstream review artifacts
- `artifacts/scheme_log.md` — per-batch log of SMS scheme revisions, keyword resolution, and classification decisions
- `decisions/` — manual screening decisions
- `notebooks/` — analysis and batch-download notebooks
- `scripts/` — helper scripts for generating and submitting provider payloads
- `payloads/` — batch request files sent to providers
- `results/` — raw batch outputs downloaded from providers
- `prompts/` — prompt templates used throughout the review workflow
- `papers/markdown/` — markdown copies of selected papers

## Prompt workflow

The review pipeline uses prompt templates in `prompts/` to update the main coding artifacts:

- `prompts/keywording.md` and `prompts/keywording_revision.md` update `artifacts/keywording.csv`
- `prompts/extraction.md` updates `artifacts/extraction.csv`
- `prompts/scheme.md` maintains `artifacts/scheme.json` and classifies each processed batch in the same pass

The scheme workflow is iterative. `prompts/scheme.md` derives and revises the SMS scheme facets using keyword evidence in `keywording.csv`, stores category memberships in `classification` as JSON arrays of numeric paper ids, and appends batch-level provenance to `artifacts/scheme_log.md`. Research type is stored in `artifacts/others.csv` alongside methodology codings organized from `artifacts/extraction.csv`.

## New search results

Done in April 11, 2026.

| Database | Number of papers |
| -------- | ------- |
| ACM | 532 |
| IEEE | 1505 |
| Scopus | 2775 |

| Stage | Number of papers |
| -------- | ------- |
| After the searches | 4812 |
| After removing duplicates | 3788 |
| Rows in `artifacts/all_papers.csv` after merging with the first search | 3795 |
| Unique papers after resolving duplicate aliases via `canonical_id` | 3793 |
| Unanimous choice between the three AI models `decisions/lucas.csv` | 244 |
| New papers included | 33 |

Observation: Papers 865 and 2140 both returned "type": "succeeded" from the Anthropic API but with an empty content: `[]` array. The model was called successfully but produced no output. This is a known (rare) Anthropic API edge case where the response is technically successful but the model emitted nothing.

## About this literature review

My goal was to explore how environmental impacts are quantified in high-performance computing (HPC). The literature on HPC energy consumption is extensive; however, this metric alone is insufficient for fully understanding the sustainability of these systems. Through preliminary searches, I was unable to identify papers that addressed environmental impacts comprehensively. I therefore decided to conduct a literature review on this topic.

After receiving the journal reviews, I need to revise several parts of the study. I am currently reframing the paper as a systematic mapping study. I am also repeating the searches to identify additional papers. The new searches returned 3,788 papers. I am using an automated AI batch-screening process for screening that evaluates titles and abstracts and decides whether to include or exclude each paper.

### Research questions

| ID | Research Question |
| :--- | :--- |
| RQ1 | To what extent does HPC research cover environmental dimensions? |
| RQ1a | How is the coverage of environmental impacts distributed across lifecycle stages? |
| RQ2 | How do methodological dimensions vary across environmental dimensions and lifecycle stages? |
| RQ2a | How do mitigation strategies vary between software and hardware interventions? |
| RQ2b | Which methodological approaches yield more thorough environmental assessments? |
| RQ2c | Does analytical scale affect assessment comprehensiveness? |
| RQ3 | How has the comprehensiveness of environmental assessments evolved over time in HPC research? |


### Search string

The search string used to find papers is:

```
(
    TITLE-ABS-KEY("high-performance computing" OR supercomputing OR supercomputer OR HPC) 
    AND 
    TITLE-ABS-KEY("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth")
)
```

Initially, it was just TITLE for the HPC terms. The last search included abstract and keywords too.

### Databases

Three databases were used to collect papers:

- ACM Digital Library
- IEEE Xplore
- Scopus

### Selection criteria

The paper selection process consists of the following steps:

1. Search for papers in the three databases using the proposed search string
2. Merge the papers from all sources into a single set without duplications
3. Screen titles and abstracts against the selection criteria
4. Apply a snowballing technique to identify additional papers

| ID | Inclusion Criteria (IC) |
| :--- | :--- |
| IC1 | Reports addressing at least one environmental impact in the HPC context |
| IC2 | Reports presenting methodologies for predicting or measuring the environmental impacts of HPC systems |

| ID | Exclusion Criteria (EC) |
| :--- | :--- |
| EC1 | Reports not related to the literature review scope |
| EC2 | Reports focusing solely on energy without connecting to broader environmental impacts |
| EC3 | Reports not in English, unavailable, or inaccessible |
