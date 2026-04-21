You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC). The study's research questions are:

RQ1: How largely does HPC research cover environmental dimensions?
RQ1a: How is coverage distributed across lifecycle stages?
RQ2: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
RQ2a: How do mitigation strategies vary between software and hardware?
RQ2b: Which methodological approaches yield more thorough assessments?
RQ2c: Does analytical scale affect assessment comprehensiveness?
RQ3: How has comprehensiveness evolved over time?

Your task is to maintain a single topical faceted schema over paper keywords and to classify each batch of papers into that schema in the same pass. You will be run iteratively over successive batches of papers.

Scope:
- Build facets only from topical dimensions evidenced in `keywords`.
- Treat `research_type` in `keywording.csv` as context only. It is already coded separately using Wieringa's research types and must not be turned into a facet here.
- Treat contribution and methodology axes captured in `extraction.csv` (`hardware_management_practices`, `software_optimization_strategies`, `methodological_dimensions`, `scale`, and related fields) as orthogonal dimensions. Do not duplicate them in the schema.
- Preserve the existing `artifacts/schema.json` shape. This prompt owns both schema revision and `classification` population.

Per-batch workflow:
- Read the current schema from `artifacts/schema.json`. If the file does not exist or is empty, you are in the first round and must derive the schema from scratch from the batch.
- Read the batch rows from `keywording.csv` using these fields: `id`, `title`, `abstract`, `keywords`, `research_type`, `notes`.
- Read `artifacts/schema_log.md` if it exists so the new entry follows the same format; otherwise create it on this run.
- Revise the schema and classify the batch in one interleaved loop:
  - Use `keywords` as the primary evidence for facets and categories.
  - Use `title`, `abstract`, `research_type`, and `notes` only as supporting context to disambiguate topical placement.
  - Add new categories to existing facets when new papers require them.
  - Add a new facet only when a recurring topical dimension does not fit any existing facet.
  - Split a category if new evidence shows it conflates distinct topical concepts.
  - Merge categories if they are not distinguishable in practice.
  - Move keywords out of `unresolved_keywords` when they now fit a category.
  - Update descriptions and `example_keywords` to reflect the latest evidence.
  - Preserve all structure and ids that the new batch does not challenge.
- For every paper in the batch, append its numeric `id` to the `classification` array of every matching category, preserving prior ids and avoiding duplicates.
- If a paper does not fit any category within a facet, revise the schema first instead of leaving the paper unclassified in that facet.
- Append one batch entry to `artifacts/schema_log.md`.
- Write the updated schema back to `artifacts/schema.json`.

Facet derivation:
- A facet is a distinct topical dimension along which papers can be meaningfully compared.
- Derive facets bottom-up from the keywords. Do not impose contribution, research, or methodology structure that belongs elsewhere in the pipeline.
- Keep facets orthogonal. If two facets substantially overlap, merge or refocus them and record the decision in `schema_notes`.
- Aim for 3-5 facets. If fewer or more are justified, explain why in `schema_notes` and in the batch log.

Category derivation:
- Categories within a facet should be mutually exclusive where practical, while still broad enough to cover multiple papers.
- Prefer broader reusable categories over categories tailored to a single paper.
- If a keyword still does not fit any category and does not justify a schema change yet, add it to `unresolved_keywords` rather than forcing it.
- If two candidate categories are hard to distinguish in practice, merge them and note the decision in `schema_notes`.

Classification rules:
- Classify a paper under a category only if the paper genuinely addresses it, not if it merely mentions it in passing.
- A paper can belong to multiple categories within the same facet if it genuinely spans them.
- A paper should normally appear in at least one category in every facet. If none fit, extend the schema rather than skipping the paper.
- Preserve prior `classification` ids for unchanged categories.
- If you rename a category, carry its existing `classification` ids forward unchanged.
- If you merge categories, union their `classification` ids and deduplicate them.
- If you split a category, preserve inherited ids conservatively rather than dropping them. If only the current batch can be reassigned confidently, keep earlier ids on the closest successor category and note the limitation in `schema_notes` and the batch log.

Schema log (`artifacts/schema_log.md`):
- Append one timestamped heading per batch in ISO 8601 format.
- Under that heading, add short bullet sections in this order:
  - `Batch:` identifier or id range and the number of papers processed.
  - `Schema changes:` new facets, new/split/merged/renamed categories, and any notable description changes.
  - `Keyword resolution:` keywords moved out of `unresolved_keywords` and new items added there.
  - `Classification:` brief counts per facet, plus any ambiguous or multi-category placements with a one-line rationale, and any paper that required a schema revision before it could be placed.
  - `Notes:` anything added to or changed in `schema_notes`.

Schema structure (`artifacts/schema.json`):

```json
{
  "facets": [
    {
      "name": "facet name",
      "rationale": "why this topical facet is justified by the keywords",
      "categories": [
        {
          "name": "category name",
          "description": "brief definition to guide classification",
          "example_keywords": ["keyword1", "keyword2"],
          "classification": [12, 47]
        }
      ]
    }
  ],
  "unresolved_keywords": ["keywords that did not fit any facet or category"],
  "schema_notes": "overall observations — gaps, dominant clusters, facets that may need splitting as more papers are added"
}
```

The `classification` field must always be present as a JSON array of numeric paper ids. Use an empty array when a category has no ids yet.

Your outputs are:
- Write the updated schema to `artifacts/schema.json`.
- Append the new batch entry to `artifacts/schema_log.md`.
