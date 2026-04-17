You are assisting with a systematic mapping study on environmental impacts in high-performance computing (HPC). The study's research questions are:

RQ1: How largely does HPC research cover environmental dimensions?
RQ1a: How is coverage distributed across lifecycle stages?
RQ2: How do methodological dimensions vary across environmental dimensions and lifecycle stages?
RQ2a: How do mitigation strategies vary between software and hardware?
RQ2b: Which methodological approaches yield more thorough assessments?
RQ2c: Does analytical scale affect assessment comprehensiveness?
RQ3: How has comprehensiveness evolved over time?

For each paper, determine the `keywords`, `research_type`, and `notes` fields (explained below).

`keywords`: 4-8 concepts at a consistent level of abstraction. Avoid highly specific technical terms (e.g., "adsorption cooling") unless they directly represent the environmental contribution. Prefer conceptual terms that would help cluster papers thematically. Always include at least one keyword reflecting which environmental impact dimension is addressed (e.g., carbon emissions / GHG, waste heat, embodied carbon, e-waste, water use, biodiversity, resource/metal depletion). Energy consumption and energy efficiency are drivers/inputs, not impact dimensions, so they do not satisfy this requirement on their own — include them as topical keywords when central to the paper, but flag in `notes` when a paper frames things only via energy with no direct downstream impact. Separate with semicolons.

`research_type`: Classify using exactly one of the categories in the table below (taken from Wieringa et al.).

| Category | Description |
| --- | --- |
| Validation Research | Techniques investigated are novel and have not yet been implemented in practice. Techniques used are for example experiments, i.e., work done in the lab. |
| Evaluation Research | Techniques are implemented in practice and an evaluation of the technique is conducted. That means, it is shown how the technique is implemented in practice (solution implementation) and what are the consequences of the implementation in terms of benefits and drawbacks (implementation evaluation). This also includes to identify problems in industry. |
| Solution Proposal | A solution for a problem is proposed, the solution can be either novel or a significant extension of an existing technique. The potential benefits and the applicability of the solution is shown by a small example or a good line of argumentation. |
| Philosophical Paper | These papers sketch a new way of looking at existing things by structuring the field in form of a taxonomy or conceptual framework. |
| Opinion Paper | These papers express the personal opinion of somebody whether a certain technique is good or bad, or how things should be done. They do not rely on related work and research methodologies. |
| Experience Paper | These papers explain what and how something has been done in practice. It has to be the personal experience of the author. |

`notes`: Flag anything worth preserving like gaps between claims and practice, partial coverage, ambiguous classification, notable negative results. If the abstract and title are insufficient to extract keywords or determine research type with reasonable confidence, state it here.

Your output is to update the fields `keywords`, `research_type`, and `notes` in `keywording.csv` for each paper revised.