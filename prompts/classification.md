You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC). The study's research questions are:

RQ1: How largely does HPC research cover environmental dimensions?
RQ1a: How is coverage distributed across lifecycle stages?
RQ2: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
RQ2a: How do mitigation strategies vary between software and hardware?
RQ2b: Which methodological approaches yield more thorough assessments?
RQ2c: Does analytical scale affect assessment comprehensiveness?
RQ3: How has comprehensiveness evolved over time?

Your task is to classify papers against the existing faceted schema by populating the `classification` field of each category with the ids of papers that belong to it. You will be run iteratively over successive batches of papers.

Workflow:
- Read the current schema from `schema.json`. It must already exist — it is produced by a separate schema-building workflow (see `schema.md`).
- Read the batch of papers to classify from `keywording.csv` (fields: `id`, `title`, `abstract`, `keywords`, `research_type`, `notes`). Treat `research_type` and `notes` as context only.
- For each paper, determine which categories it belongs to across all facets.
- Append the paper's `id` to the `classification` string of every matching category, separated by semicolons. Preserve ids already present from prior rounds and do not duplicate them.
- Write the updated schema back to `schema.json`.

Classification rules:
- Mark a paper under a category only if it genuinely addresses it — not if it is merely mentioned in passing.
- A paper can belong to multiple categories within the same facet if it genuinely covers several.
- A paper should normally be classified under at least one category in every facet. If no category in a facet applies, update the schema rather than skipping the paper (see below).
- Do not modify facet names, category names, descriptions, `example_keywords`, `unresolved_keywords`, or `schema_notes` unless a paper cannot be classified (see below).

Schema updates during classification:
- If a paper cannot be classified under any category of a given facet, revise the schema by adding a new category to the most appropriate existing facet, or a new facet if no existing one fits — following the same JSON structure as `schema.md`.
- When adding a new category, include `name`, `description`, `example_keywords`, and a `classification` field initialized with the ids of the paper(s) that motivated it.
- Briefly note any structural change in `schema_notes`.

Your output is to write the updated schema (with populated `classification` fields) to `schema.json`.
