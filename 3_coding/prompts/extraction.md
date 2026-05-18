You are assisting with a systematic mapping study (SMS) on environmental impacts in high-performance computing (HPC).

## Research questions

- **RQ1**: To what extent does HPC research cover environmental dimensions?
- **RQ1a**: How is the coverage of environmental impacts distributed across lifecycle stages?
- **RQ2**: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
- **RQ2a**: How do mitigation strategies vary between software and hardware interventions?
- **RQ2b**: Which methodological approaches yield more thorough environmental assessments?
- **RQ2c**: Does analytical scale affect assessment comprehensiveness?
- **RQ3**: How has the comprehensiveness of environmental assessments evolved over time in HPC research?

## Selection criteria

Include if any apply:
- **IC1**: Reports addressing at least one environmental impact in the HPC context.
- **IC2**: Reports presenting methodologies for predicting or measuring the environmental impacts of HPC systems.

Exclude if any apply:
- **EC1**: Reports not related to the literature review scope.
- **EC2**: Reports focusing solely on energy without connecting to broader environmental impacts.
- **EC3**: Reports not in English, unavailable, or inaccessible.

## Task

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
