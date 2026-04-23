You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC).
For more information regarding the review, including the research questions, scope, and workflow, refer to `README.md` in the repository root.

For each paper, extract the fields below using only the exact allowed values.

- Use semicolons for multi-value fields.
- Leave a field blank if none of its allowed values are evidenced.
- Do not overwrite already-filled cells in `artifacts/extraction.csv`.
- If all retained fields are already filled for a paper, skip that paper.
- Use `notes` for a brief rationale when helpful. It does not need to justify every field, only the main assumptions, ambiguities, or notable choices.

| Field | Allowed values | Guidance |
| --- | --- | --- |
| `id` | Existing paper id | Use the existing identifier from `artifacts/extraction.csv`. |
| `methodological_approach` | `data analysis`, `modeling`, `simulations`, `experiments on real systems`, `literature analysis` | Methods used in the study. Separate multiple values with semicolons. |
| `data_source` | `primary`, `secondary` | Whether the study relies on primary data, secondary data, or both. Separate multiple values with semicolons. |
| `assessment_orientation` | `ex post`, `ex ante` | Whether the assessment is retrospective/measured or predictive/forward-looking. Separate multiple values with semicolons only when both orientations are evidenced. |
| `notes` | Free text | Brief rationale supporting choices, especially assumptions, ambiguities, or boundary cases. Keep it concise. |

Your output is to fill only the fields `id`, `methodological_approach`, `data_source`, `assessment_orientation`, and `notes` in `artifacts/extraction.csv` for each paper revised.
