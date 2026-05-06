You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC).
For more information regarding the review, including the research questions, scope, and workflow, refer to `README.md` in the repository root.

For each paper, determine the `keywords` and `notes` fields (explained below).

`keywords`: 4-8 concepts at a consistent level of abstraction. Avoid highly specific technical terms (e.g., "adsorption cooling") unless they directly represent the environmental contribution. Prefer conceptual terms that would help cluster papers thematically. Always include at least one keyword reflecting which environmental impact dimension is addressed (e.g., carbon emissions / GHG, waste heat, embodied carbon, e-waste, water use, biodiversity, resource/metal depletion). Energy consumption and energy efficiency are drivers/inputs, not impact dimensions, so they do not satisfy this requirement on their own — include them as topical keywords when central to the paper, but flag in `notes` when a paper frames things only via energy with no direct downstream impact. Separate with semicolons.

`notes`: Flag anything worth preserving like gaps between claims and practice, partial coverage, or notable negative results. If the abstract and title are insufficient to extract keywords with reasonable confidence, state it here.

Your output is to update the fields `keywords` and `notes` in `keywording.csv` for each paper revised.
