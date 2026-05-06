You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC).
For more information regarding the review, including the research questions, scope, and workflow, refer to `README.md` in the repository root.

Your task is to maintain the SMS classification scheme over paper keywords and to classify each batch of papers into that scheme in the same pass. You will be run iteratively over successive batches of papers.

Scope:
- Maintain only the SMS scheme facets derived from keywording.
- Derive and revise facets only from dimensions evidenced in `keywords`.
- Do not add research-type or methodology-coding dimensions to the scheme. `research_type`, methodological approach, data source, and assessment orientation stay in the extraction/others workflow.
- Preserve the `artifacts/scheme.json` shape. This prompt owns both scheme revision and `classification` population.

Per-batch workflow:
- Read the current scheme from `artifacts/scheme.json`. If the file does not exist or is empty, you are in the first round and must derive the scheme from scratch from the batch.
- Read the batch rows from `keywording.csv` using these fields: `id`, `title`, `abstract`, `keywords`, `notes`.
- Read `artifacts/scheme_log.md` if it exists so the new entry follows the same format; otherwise create it on this run.
- Revise the scheme and classify the batch in one interleaved loop:
  - Use `keywords` as the primary evidence for facets and categories.
  - Use `title`, `abstract`, and `notes` only as supporting context to disambiguate placement in scheme facets.
  - Add new categories to existing facets when new papers require them.
  - Add a new facet only when a recurring dimension from keywording does not fit any existing facet.
  - Split a category if new evidence shows it conflates distinct concepts.
  - Merge categories if they are not distinguishable in practice.
  - If a keyword still does not fit any category and does not justify a scheme change yet, mention it in the batch log rather than forcing it into the scheme.
  - Update descriptions and `example_keywords` to reflect the latest evidence.
  - Preserve all structure and ids that the new batch does not challenge.
- For every paper in the batch, append its numeric `id` to the `classification` array of every matching category, preserving prior ids and avoiding duplicates.
- If a paper does not fit any category within a facet, revise the scheme first instead of leaving the paper unclassified in that facet.
- Append one batch entry to `artifacts/scheme_log.md`.
- Write the updated scheme back to `artifacts/scheme.json`.

Facet derivation:
- A scheme facet is a distinct keyword-evidenced dimension along which papers can be meaningfully compared.
- Derive facets bottom-up from the keywords. Do not impose contribution, research-type, or methodology structure that belongs elsewhere in the pipeline.
- Keep facets orthogonal. If two facets substantially overlap, merge or refocus them and record the decision in the batch log.
- Aim for 3-5 scheme facets. If fewer or more are justified, explain why in the batch log.

Category derivation:
- Categories within a facet should be mutually exclusive where practical, while still broad enough to cover multiple papers.
- Prefer broader reusable categories over categories tailored to a single paper.
- If a keyword still does not fit any category and does not justify a scheme change yet, keep it out of the JSON and record the unresolved term in the batch log.
- If two candidate categories are hard to distinguish in practice, merge them and note the decision in the batch log.

Classification rules:
- Classify a paper under a category only if the paper genuinely addresses it, not if it merely mentions it in passing.
- A paper can belong to multiple categories within the same facet if it genuinely spans them.
- A paper should normally appear in at least one category in every facet. If none fit, extend the scheme rather than skipping the paper.
- Preserve prior `classification` ids for unchanged categories.
- If you rename a category, carry its existing `classification` ids forward unchanged.
- If you merge categories, union their `classification` ids and deduplicate them.
- If you split a category, preserve inherited ids conservatively rather than dropping them. If only the current batch can be reassigned confidently, keep earlier ids on the closest successor category and note the limitation in the batch log.

Scheme log (`artifacts/scheme_log.md`):
- Append one dated heading per batch using `# YYYY-MM-DD` (date only, no time). Multiple entries on the same day are fine; each gets its own heading.
- Write the entry in a natural, concise tone. Do not use labeled sections like `Batch:`, `Scheme changes:`, etc. Match the style of the existing entries in the file.
- Open with one short line under the heading that identifies the batch (e.g. "Third batch: papers 21-30.") and gives a one-sentence summary of the round (e.g. "No structural changes this round, just broadening." or "Biodiversity showed up as a distinct impact.").
- Follow with a short bullet list that covers, as applicable:
  - new facets or categories, and any splits, merges, renames, or notable description changes;
  - keywords newly left unresolved in the log or resolved by a scheme change;
  - any paper that required a scheme revision before it could be placed, and brief rationale for ambiguous or multi-category placements;
  - any notable scheme-level observations.
- Omit bullets that have nothing to report. Skip per-category counts unless a number is genuinely informative.

Scheme structure (`artifacts/scheme.json`):

```json
{
  "facets": [
    {
      "name": "facet name",
      "rationale": "why this facet is justified by the keywords",
      "categories": [
        {
          "name": "category name",
          "description": "brief definition to guide classification",
          "example_keywords": ["keyword1", "keyword2"],
          "classification": [12, 47]
        }
      ]
    }
  ]
}
```

The `classification` field must always be present as a JSON array of numeric paper ids. Use an empty array when a category has no ids yet.

Your outputs are:
- Write the updated scheme to `artifacts/scheme.json`.
- Append the new batch entry to `artifacts/scheme_log.md`.
