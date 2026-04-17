You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC). The study's research questions are:

RQ1: How largely does HPC research cover environmental dimensions?
RQ1a: How is coverage distributed across lifecycle stages?
RQ2: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
RQ2a: How do mitigation strategies vary between software and hardware?
RQ2b: Which methodological approaches yield more thorough assessments?
RQ2c: Does analytical scale affect assessment comprehensiveness?
RQ3: How has comprehensiveness evolved over time?

For each paper, extract the fields below using only the exact allowed values.

- Use semicolons for multi-value fields.
- Leave a multi-value field blank if none of its allowed values are evidenced.
- For the five `*_footprint` and practice fields, use exactly one of: `addressed`, `partially addressed`, `not addressed`.
- Prefer conservative coding: if a dimension is only mentioned as motivation or background, use `partially addressed` rather than `addressed`.
- Use `notes` for a brief rationale when helpful. It does not need to justify every field, only the main assumptions, ambiguities, or notable choices.

| Field | Allowed values | Guidance |
| --- | --- | --- |
| `carbon_footprint` | `addressed`, `partially addressed`, `not addressed` | Coverage of carbon-related impacts. Use `addressed` only when the paper meaningfully analyzes or measures carbon impacts. |
| `water_footprint` | `addressed`, `partially addressed`, `not addressed` | Coverage of water-related impacts such as consumption, withdrawal, or water stress. |
| `material_footprint` | `addressed`, `partially addressed`, `not addressed` | Coverage of material-related impacts such as raw materials, critical materials, recyclability, or e-waste. |
| `hardware_management_practices` | `addressed`, `partially addressed`, `not addressed` | Whether the paper addresses hardware-side management or infrastructure practices as part of the environmental discussion. |
| `software_optimization_strategies` | `addressed`, `partially addressed`, `not addressed` | Whether the paper addresses software-side optimization strategies as part of the environmental discussion. |
| `scopes` | `scope 1`, `scope 2`, `scope 3` | Carbon accounting scopes considered by the paper. Separate multiple values with semicolons. |
| `carbon_stages` | `production`, `operational`, `eol` | Lifecycle stages considered for carbon impacts. `eol` means end-of-life. |
| `water_stages` | `production`, `operational`, `eol` | Lifecycle stages considered for water impacts. |
| `material_stages` | `production`, `operational`, `eol` | Lifecycle stages considered for material impacts. |
| `effects` | `first order`, `second order`, `higher order` | Environmental effect order covered by the paper. |
| `methodological_dimensions` | `data analysis`, `modeling`, `simulations`, `experiments on real systems`, `literature analysis` | Methods used in the study. Separate multiple values with semicolons. |
| `sources` | `primary`, `secondary` | Whether the study relies on primary sources, secondary sources, or both. |
| `scale` | `micro`, `meso`, `macro` | Analytical scale used in the paper. |
| `assement_type` | `ex post`, `ex ante` | Whether the assessment is retrospective/measured or predictive/forward-looking. |
| `notes` | Free text | Brief rationale supporting some choices, especially assumptions, ambiguities, or boundary cases. Keep it concise. |

Your output is to fill the fields `id`, `carbon_footprint`, `water_footprint`, `material_footprint`, `hardware_management_practices`, `software_optimization_strategies`, `scopes`, `carbon_stages`, `water_stages`, `material_stages`, `effects`, `methodological_dimensions`, `sources`, `scale`, `assement_type`, and `notes` in `extraction.csv` for each paper revised.

NOTE: If the paper already have the fields filled you MUST NOT change them. Just skip this paper.