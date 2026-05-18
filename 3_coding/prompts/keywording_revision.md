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

Your task is to revise the existing `keywords` and `notes` for a single paper using only the paper's introduction and conclusion.

Inputs:
- The current row values for one paper: `id`, `title`, `abstract`, `keywords`, `notes`
- The full paper in markdown

Evidence boundary:
- Use only evidence from the `Introduction` and `Conclusion` sections of the markdown paper.
- Do not use evidence from the abstract, related work, methods, results, discussion, references, tables, figures, appendices, or any other section.
- You may use the existing row only as prior coding to revise, not as evidence.
- If the introduction and conclusion do not provide enough evidence to revise a field confidently, keep the current value unless it is clearly contradicted.
- If the introduction and conclusion contradict the current row, revise the row and explain the reason briefly in `notes`.

`keywords`: 4-8 concepts at a consistent level of abstraction. Avoid highly specific technical terms unless they directly represent the environmental contribution. Prefer conceptual terms that would help cluster papers thematically. Always include at least one keyword reflecting an environmental impact dimension when the introduction or conclusion provides evidence for one (e.g., carbon emissions / GHG, waste heat, embodied carbon, e-waste, water use, biodiversity, resource/metal depletion). Energy consumption and energy efficiency are drivers/inputs, not impact dimensions, so they do not satisfy this requirement on their own — include them as topical keywords when central to the paper, but flag in `notes` when the introduction and conclusion frame things only via energy with no direct downstream impact. Separate with semicolons.

`notes`: Flag anything worth preserving like gaps between claims and practice, partial coverage of environmental dimensions or lifecycle stages, notable negative results, or boundary conditions explicitly mentioned in the introduction or conclusion. When revising the current row, explain only the important change. Do not mention sections outside the introduction and conclusion. Keep concise.

Your output is to update the fields `keywords` and `notes` in `keywording.csv` for the revised paper.
