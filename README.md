# Literature Review

Tools for collecting and screening papers in a systematic mapping study on the environmental impacts of high-performance computing (HPC).

## Data sources

Papers were collected from three databases using a keyword search string targeting environmental impacts of HPC systems. The full search strings and review protocol are documented in below.

Raw BibTeX files are in `papers/`:
- `acm.bib` — ACM Digital Library results
- `ieee.bib` — IEEE Xplore results
- `scopus.bib` — Scopus results
- `papers.bib` — Merged and deduplicated (~3,788 papers)
- `papers.csv` — screening input: `id,title,abstract` columns

## About this literature review

My goal was to explore how environmental impacts are quantified in high-performance computing (HPC). The literature on HPC energy consumption is extensive; however, this metric alone is insufficient for fully understanding the sustainability of these systems. Through preliminary searches, I was unable to identify papers that addressed environmental impacts comprehensively. I therefore decided to conduct a literature review on this topic.

After receiving the journal reviews, I need to revise several parts of the study. I am currently reframing the paper as a systematic mapping study. I am also repeating the searches to identify additional papers. The new searches returned 3,788 papers. I am using an automated AI batch-screening process for screening that evaluates titles and abstracts and decides whether to include or exclude each paper.

### Research questions

| ID | Research Question |
| :--- | :--- |
| RQ1 | To what extent does HPC research cover environmental dimensions? |
| RQ1a | How is the coverage of environmental impacts distributed across lifecycle stages? |
| RQ2 | How do methodological dimensions vary across environmental dimensions and lifecycle stages? |
| RQ2a | How do mitigation strategies vary between software and hardware interventions? |
| RQ2b | Which methodological approaches yield more thorough environmental assessments? |
| RQ2c | Does analytical scale affect assessment comprehensiveness? |
| RQ3 | How has the comprehensiveness of environmental assessments evolved over time in HPC research? |


### Search string

The search string used to find papers is:

```
(
    TITLE-ABS-KEY("high-performance computing" OR supercomputing OR supercomputer OR HPC) 
    AND 
    TITLE-ABS-KEY("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth")
)
```

Initially, it was just TITLE for the HPC terms. The last search included abstract and keywords too.

### Databases

Three databases were used to collect papers:

- ACM Digital Library
- IEEE Xplore
- Scopus

### Selection criteria

The paper selection process consists of the following steps:

1. Search for papers in the three databases using the proposed search string
2. Merge the papers from all sources into a single set without duplications
3. Screen titles and abstracts against the selection criteria
4. Apply a snowballing technique to identify additional papers

| ID | Inclusion Criteria (IC) |
| :--- | :--- |
| IC1 | Reports addressing at least one environmental impact in the HPC context |
| IC2 | Reports presenting methodologies for predicting or measuring the environmental impacts of HPC systems |

| ID | Exclusion Criteria (EC) |
| :--- | :--- |
| EC1 | Reports not related to the literature review scope |
| EC2 | Reports focusing solely on energy without connecting to broader environmental impacts |
| EC3 | Reports not in English, unavailable, or inaccessible |

### Search results

Done in April 11, 2026.

| Database | Number of papers |
| -------- | ------- |
| ACM | 532 |
| IEEE | 1505 |
| Scopus | 2775 |

| Stage | Number of papers |
| -------- | ------- |
| After the searches | 4812 |
| After removing duplicates | 3788 |

### Data extraction

For each selected paper, we extracted the fields described in the table below.

| Field Name | Description | Values | Details |
| :--- | :--- | :--- | :--- |
| `paper_id` | A unique numerical identifier assigned to each paper. | `numerical` | Used as the primary key to link metadata, analysis, and tags. |
| `title` | The full title of the research paper. | `text` | The official title as indexed in databases. |
| `publication_year` | The year in which the paper was published. | `numerical` | The calendar year of publication. |
| `doi` | The Digital Object Identifier for the paper. | `text` | Persistent link to the paper's location on the internet. |
| `satisfy_ic1` | Indicator specifying whether the paper meets the first inclusion criterion. | `yes`, `no` | - |
| `satisfy_ic2` | Indicator specifying whether the paper meets the second inclusion criterion. | `yes`, `no` | - |
| `from_snowballing` | Flag indicating discovery via snowballing vs. database search. | `yes`, `no` | `yes` if discovered via snowballing; `no` if via initial search. |
| `papers_backward_snowballing` | Count of bibliography references screened. | `numerical` | Total references from this paper's bibliography that were screened. |
| `papers_forward_snowballing` | Count of newer papers citing this paper that were screened. | `numerical` | Total newer papers citing this paper that were screened. |
| `citation_key` | Unique BibTeX-style key for citation management. | `text` | Unique identifier used for referencing (e.g., in LaTeX). |
| `carbon_footprint` | Assesses whether the paper addresses carbon-related impacts. | `addressed`, `partially addressed`, `not addressed` | `addressed` for comprehensive discussion, `partially addressed` for superficial mention and `not addressed` for no mentions. |
| `production_carbon` | Specifies if production-phase carbon impacts are considered. | `yes`, `no` | Emissions from manufacturing, transport, and construction. |
| `operational_carbon` | Specifies if operational-phase carbon impacts are considered. | `yes`, `no` | Emissions from energy consumption during active use. |
| `eol_carbon` | Specifies if end-of-life carbon impacts are considered. | `yes`, `no` | Emissions from decommissioning, disposal, or recycling. |
| `scope_1` | Specifies if Scope 1 emissions are considered. | `yes`, `no` | Direct emissions from owned or controlled sources. |
| `scope_2` | Specifies if Scope 2 emissions are considered. | `yes`, `no` | Indirect emissions from purchased energy (electricity, heat, etc.). |
| `scope_3` | Specifies if Scope 3 emissions are considered. | `yes`, `no` | All other indirect emissions in the value chain. |
| `water_footprint` | Assesses whether the paper addresses water-related impacts (consumption, extraction, water stress, etc.) | `addressed`, `partially addressed`, `not addressed` | `addressed` for comprehensive discussion, `partially addressed` for superficial mention and `not addressed` for no mentions. |
| `production_water` | Specifies if production-phase water impacts are considered. | `yes`, `no` | Water consumed/withdrawn during manufacturing and construction. |
| `operational_water` | Specifies if operational-phase water impacts are considered. | `yes`, `no` | Water used for cooling or indirect use from electricity generation. |
| `eol_water` | Specifies if end-of-life water impacts are considered. | `yes`, `no` | Water impacts from decommissioning or waste processing. |
| `material_footprint` | Assesses whether the paper addresses material-related impacts (raw materials, e-waste, resource depletion, etc.) | `addressed`, `partially addressed`, `not addressed` | `addressed` for comprehensive discussion, `partially addressed` for superficial mention and `not addressed` for no mentions. |
| `production_materials` | Specifies if production-phase material impacts are considered. | `yes`, `no` | Materials used during manufacturing and construction. |
| `operational_materials` | Specifies if operational-phase material impacts are considered. | `yes`, `no` | Consumables and component replacements during active use. |
| `eol_materials` | Specifies if end-of-life material impacts are considered. | `yes`, `no` | Materials involved in decommissioning or recycling. |
| `hardware_management_practices` | Assesses whether the paper addresses hardware management. | `addressed`, `partially addressed`, `not addressed` | `addressed` for comprehensive discussion, `partially addressed` for superficial mention and `not addressed` for no mentions. |
| `hardware_practices` | Specific practices for hardware management. | `list of strings` | - |
| `software_optimization_strategies` | Assesses whether the paper addresses software optimization. | `addressed`, `partially addressed`, `not addressed` | `addressed` for comprehensive discussion, `partially addressed` for superficial mention and `not addressed` for no mentions. |
| `software_strategies` | Specific strategies for software optimization. | `list of strings` | - |
| `first_order_effects` | Specifies if direct life-cycle impacts are considered. | `yes`, `no` | Direct life-cycle impacts of the systems themselves. |
| `second_order_effects` | Specifies if indirect life-cycle impacts are considered. | `yes`, `no` | Impacts due to changes in reference activities enabled by the system. |
| `higher_order_effects` | Specifies if systemic or structural impacts are considered. | `yes`, `no` | Impacts from broader behavioral or societal changes. |
| `data_analysis` | Specifies if data analysis is used as an experimental approach. | `yes`, `no` | Observing and interpreting measured or collected data. |
| `modeling` | Specifies if modeling is used as an experimental approach. | `yes`, `no` | Creating mathematical or theoretical representations. |
| `simulations` | Specifies if simulations are used as an experimental approach. | `yes`, `no` | Running computational experiments in virtual environments. |
| `experiments_on_real_systems` | Specifies if experiments on real systems are used. | `yes`, `no` | Testing on actual hardware or real physical systems. |
| `literature_analysis` | Specifies if literature analysis is used. | `yes`, `no` | Primarily reviewing and analyzing others' work. |
| `methods` | Specific methodologies used in the study. | `list of strings` | - |
| `primary_sources` | Specifies if primary data sources are used. | `yes`, `no` | Data collected or generated directly by the authors. |
| `secondary_sources` | Specifies if secondary data sources are used. | `yes`, `no` | Data gathered from outside sources or literature. |
| `micro_scale` | Specifies if micro-scale spatial boundaries are adopted. | `yes`, `no` | Compute node level (servers, nodes, processors). |
| `meso_scale` | Specifies if meso-scale spatial boundaries are adopted. | `yes`, `no` | Facility level (data centers, buildings). |
| `macro_scale` | Specifies if macro-scale spatial boundaries are adopted. | `yes`, `no` | Regional, national, or geographic grid level. |
| `ex_post` | Specifies if historical/measured assessment is used. | `yes`, `no` | Analysis of existing systems or historical data. |
| `ex_ante` | Specifies if predictive assessment is used. | `yes`, `no` | Forward-looking analysis or predictions. |
