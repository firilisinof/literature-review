You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC). The study's research questions are:

RQ1: How largely does HPC research cover environmental dimensions?
RQ1a: How is coverage distributed across lifecycle stages?
RQ2: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
RQ2a: How do mitigation strategies vary between software and hardware?
RQ2b: Which methodological approaches yield more thorough assessments?
RQ2c: Does analytical scale affect assessment comprehensiveness?
RQ3: How has comprehensiveness evolved over time?

Your task is to derive or revise a faceted schema that organizes the keywords assigned to papers, so that papers can be compared along meaningful dimensions. You will be run iteratively over successive batches of papers.

Workflow:
- Read the current schema from `schema.json`. If the file does not exist or is empty, you are in the first round — derive the schema from scratch using the batch of keywords provided.
- Read the new batch of paper keywords from `keywording.csv` (the `keywords` column, semicolon-separated).
- If this is a subsequent round, revise the existing schema by:
  - Adding new categories to existing facets if new keywords justify it
  - Adding new facets if a recurring cluster does not fit any existing facet
  - Splitting a category if new keywords reveal it conflates distinct concepts
  - Merging categories if new keywords suggest they represent the same concept
  - Moving keywords out of `unresolved_keywords` if they now fit an existing category
  - Updating `example_keywords` and descriptions to reflect new evidence
  - Preserving all existing structure that the new keywords do not challenge
- Write the resulting schema back to `schema.json`.

Facet derivation:
- A facet is a dimension along which papers can be meaningfully compared.
- Derive facets bottom-up from the keywords — do not impose structure.
- Each facet should correspond to a distinct, non-overlapping dimension.
- Aim for 4–6 facets. Flag in `schema_notes` if fewer or more seem justified and explain why.

Category derivation:
- Categories within a facet should be mutually exclusive where possible.
- Prefer broader categories over highly specific ones — categories should be applicable to multiple papers, not tailored to a single one.
- If a keyword does not fit any emerging category, add it to `unresolved_keywords` rather than forcing it in.
- If two candidate categories are hard to distinguish in practice, merge them and note the decision in `schema_notes`.

Schema structure (`schema.json`):

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
          "classification": ""
        }
      ]
    }
  ],
  "unresolved_keywords": ["keywords that did not fit any facet or category"],
  "schema_notes": "overall observations — gaps, dominant clusters, facets that may need splitting as more papers are added"
}
```

The `classification` field must always be present and left as an empty string in every category. A separate downstream workflow populates it with paper ids; do not fill it in here, and preserve any existing values if they are already set.

Your output is to write the updated schema to `schema.json`.
