You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC).
For more information regarding the review, including the research questions, scope, and workflow, refer to `README.md` in the repository root.

Your task is to revise the existing `keywords`, `research_type`, and `notes` for a single paper using only the paper's introduction and conclusion.

Inputs:
- The current row values for one paper: `id`, `title`, `abstract`, `keywords`, `research_type`, `notes`
- The full paper in markdown

Evidence boundary:
- Use only evidence from the `Introduction` and `Conclusion` sections of the markdown paper.
- Do not use evidence from the abstract, related work, methods, results, discussion, references, tables, figures, appendices, or any other section.
- You may use the existing row only as prior coding to revise, not as evidence.
- If the introduction and conclusion do not provide enough evidence to revise a field confidently, keep the current value unless it is clearly contradicted.
- If the introduction and conclusion contradict the current row, revise the row and explain the reason briefly in `notes`.

`keywords`: 4-8 concepts at a consistent level of abstraction. Avoid highly specific technical terms unless they directly represent the environmental contribution. Prefer conceptual terms that would help cluster papers thematically. Always include at least one keyword reflecting an environmental impact dimension when the introduction or conclusion provides evidence for one (e.g., carbon emissions / GHG, waste heat, embodied carbon, e-waste, water use, biodiversity, resource/metal depletion). Energy consumption and energy efficiency are drivers/inputs, not impact dimensions, so they do not satisfy this requirement on their own — include them as topical keywords when central to the paper, but flag in `notes` when the introduction and conclusion frame things only via energy with no direct downstream impact. Separate with semicolons.

`research_type`: Classify using exactly one of the categories in the table below (taken from Wieringa et al.). Base the classification only on what the introduction and conclusion make clear. If the best-fitting category is still imperfect, choose the closest one and mention the ambiguity in `notes`.

| Category | Description |
| --- | --- |
| Validation Research | Techniques investigated are novel and have not yet been implemented in practice. Techniques used are for example experiments, i.e., work done in the lab. |
| Evaluation Research | Techniques are implemented in practice and an evaluation of the technique is conducted. That means, it is shown how the technique is implemented in practice (solution implementation) and what are the consequences of the implementation in terms of benefits and drawbacks (implementation evaluation). This also includes to identify problems in industry. |
| Solution Proposal | A solution for a problem is proposed, the solution can be either novel or a significant extension of an existing technique. The potential benefits and the applicability of the solution is shown by a small example or a good line of argumentation. |
| Philosophical Paper | These papers sketch a new way of looking at existing things by structuring the field in form of a taxonomy or conceptual framework. |
| Opinion Paper | These papers express the personal opinion of somebody whether a certain technique is good or bad, or how things should be done. They do not rely on related work and research methodologies. |
| Experience Paper | These papers explain what and how something has been done in practice. It has to be the personal experience of the author. |

`notes`: Flag anything worth preserving like gaps between claims and practice, partial coverage of environmental dimensions or lifecycle stages, ambiguous or approximate Wieringa classification, notable negative results or boundary conditions explicitly mentioned in the introduction or conclusion. When revising the current row, explain only the important change. Do not mention sections outside the introduction and conclusion. Keep concise.

Your output is to update the fields `keywords`, `research_type`, and `notes` in `keywording.csv` for the revised paper.
