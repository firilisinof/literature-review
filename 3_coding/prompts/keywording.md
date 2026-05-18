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

For each paper, determine the `keywords` and `notes` fields (explained below).

`keywords`: 4-8 concepts at a consistent level of abstraction. Avoid highly specific technical terms (e.g., "adsorption cooling") unless they directly represent the environmental contribution. Prefer conceptual terms that would help cluster papers thematically. Always include at least one keyword reflecting which environmental impact dimension is addressed (e.g., carbon emissions / GHG, waste heat, embodied carbon, e-waste, water use, biodiversity, resource/metal depletion). Energy consumption and energy efficiency are drivers/inputs, not impact dimensions, so they do not satisfy this requirement on their own — include them as topical keywords when central to the paper, but flag in `notes` when a paper frames things only via energy with no direct downstream impact. Separate with semicolons.

`notes`: Flag anything worth preserving like gaps between claims and practice, partial coverage, or notable negative results. If the abstract and title are insufficient to extract keywords with reasonable confidence, state it here.

Your output is to update the fields `keywords` and `notes` in `keywording.csv` for each paper revised.
