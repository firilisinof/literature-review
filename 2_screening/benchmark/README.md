# HPC screening benchmark

Compare the agreed models with human decisions from the published HPC review.
Keep the published criteria fixed. No paid model requests are authorized yet.

## Files and use

- `benchmark.jsonl`: all 595 records, one JSON object per line.
- `build_dataset.py`: rebuilds the dataset from the original screening files.
- `README.md`: the evaluation plan and source notes.

Each record has `record_id`, `title`, `abstract`, `label`, `split`, `cohort`,
`label_source`, and `abstract_source`. Use the `split` field to select records.
The source fields point to the original evidence. Use `record_id` to find the
human decision in its source file.

Send only `title` and `abstract` to a model. Keep `record_id` as a request key.
Do not send the full row, human label, source notes, or historical model answers.

To rebuild from the repository root:

```sh
uv run --no-project --with bibtexparser==1.4.4 python 2_screening/benchmark/build_dataset.py
```

The script checks IDs, human decisions, abstract matches, and split counts before
writing the dataset. It makes no model requests. `uv` can download the parser
package if it is not cached. There is no separate test command or audit file.

## Split and evaluation

| Set | Include | Exclude | Total |
| --- | ---: | ---: | ---: |
| Development | 12 | 107 | 119 |
| Held-out | 50 | 426 | 476 |

The seed is `20261020`. The split preserves the agreed assignments.
Within each label and source group, sort by the SHA-256 hash of
`20261020:<record_id>` and take the first records for development.
The development quotas are 5 initial includes, 67 initial excludes,
1 snowball include, 6 later includes, and 40 later excludes.
All remaining records belong to the held-out set.

Use development records to check prompts, output formats, and error handling.
Keep the criteria fixed. Do not fine-tune models for this comparison.
Before the final run, fix the prompt, model revisions, inference settings,
output parser, and retry policy. Use the same titles and abstracts for all models.

Use the held-out set once for the final comparison. Do not use its labels or
results to adjust the setup. Save predictions before scoring them.

Each model makes a binary decision: `include` or `exclude`. Use its best-supported
choice without a confidence threshold or human intervention. Score decisions
against the existing human labels. Do not ask a person to resolve model uncertainty.

Record failed requests and invalid answers as technical errors without a decision.
Report the failure count and decision coverage: valid decisions divided by 476.
A run with missing decisions is incomplete. Do not assign labels to errors or
silently remove those records from the denominator. Report the full-set metrics
below only when all 476 records have valid decisions.

Let `R` be the number of records the model includes. Let `E` be the number
of eligible papers among those records.

| Metric | Calculation |
| --- | --- |
| Eligible-paper recall | `E / 50` |
| False exclusions | `50 - E` |
| Retained fraction | `R / 476` |
| Inclusion precision | `E / R`, or undefined when `R = 0` |
| Cost | Total cost and cost per record, including retries |
| Processing time | Total elapsed time and time per record |

The retained fraction measures how much of the collection remains after screening.
This benchmark has no human review step. Inclusion precision measures the fraction
of included records that match a human inclusion label.

Report counts beside rates and report technical failures separately.
Prioritize recall and false exclusions. Each false exclusion reduces recall
by two percentage points. Report a two-sided 95% Wilson interval for recall.
The interval does not correct the selection bias described below.

Record concurrency and hardware. Report local GPU time and model load time.
State any local cost assumptions. Absence of API billing does not mean zero cost.

Use the historical three-model unanimous-include rule as the baseline on the
same held-out IDs. Treat missing or invalid historical responses as technical
errors and report baseline coverage. The same complete-run rule applies.
This is a descriptive comparison: historical runs used original abstracts,
and the later group was selected by unanimous historical inclusion.
The baseline therefore includes all records in that group.

## Criteria and models

| Criterion | Published wording |
| --- | --- |
| IC1 | Reports addressing at least one environmental impact in the HPC context |
| IC2 | Reports presenting methodologies for predicting or measuring the environmental impacts of HPC systems |
| EC1 | Reports not related to the study scope |
| EC2 | Reports focusing solely on energy without connecting to broader environmental impacts |
| EC3 | Reports not in English, unavailable, or inaccessible |

| Model | Configuration |
| --- | --- |
| Jev | `jev-1.14.0`, hosted |
| OpenAI Decisions | `gpt-6-luna`, hosted |
| Kev-4B | `jaredpalmer/kev-4b`, `v1.0`, local |
| Kev-9B | `jaredpalmer/kev-9b`, `v1.0`, local |
| Qwen3-8B | `Qwen/Qwen3-8B`, thinking disabled, local |

Laya is excluded. Resolve local model tags to fixed revisions before running.
The Qwen revision is not yet fixed.

## Human labels and source notes

The source collection has 609 human-screened records. The benchmark keeps 595:
62 include and 533 exclude. The 14 approved removals are listed below.
Original screening files remain unchanged.

`2_screening/decisions/first.csv` provides 360 initial decisions and five
snowball inclusions. The later 244 records have decisions in `lucas.csv` and
`victor.csv` in the same folder. The reviewers agreed on 185 records.
For the other 59, use the final decisions in `artifacts/conflicts.csv`.
The script joins decisions by ID and checks adjudications against the votes.

The historical file `6c32f22^:screening.csv` confirmed the titles and labels
for all 365 initial records. Treat the old EC4 reason for record 3380 as EC3,
as clarified by the author. The original reason stays in the source file.

Commit `cd60158` introduced two incorrect canonical IDs. Keep the original IDs:

| Record | Incorrect target | Evidence |
| --- | --- | --- |
| 3794 | 2042 | Different chapters: `10.1021/bk-2021-1388.ch001` and `10.1021/bk-2021-1388.ch009`. Source: `1_search/scopus.bib#Penchoff20213`. |
| 3795 | 299 | Different papers: `10.1109/tpds.2015.2485980` and `10.1145/2980765.2980768`. Source: `1_search/ieee.bib#7289462`. |

The historical screening file confirms both human exclusions by title.
No label is transferred to the incorrect target.

The active dataset contains 577 original abstracts and 18 recovered abstracts.
Nine came from `artifacts/unanimous_include.csv`, three from
`artifacts/metadata.csv`, and six from `1_search/scopus.bib`.
The script requires a matching title before it uses a recovered abstract.

The user approved removal of all three `[Title page i]` records:
1330, 1461, and 1504. They are noise and already have human exclusion labels.

The user also approved removal of the following 11 human exclusions after
reviewing the online sources. The search date was 2026-10-20.
No formal abstract was verified for these records.

| ID | Finding | Source |
| --- | --- | --- |
| 230 | Not found. Contents and local IEEE metadata indicate a title-page item. Full item unavailable. | [Proceedings contents](https://www.proceedings.com/content/017/017846webtoc.pdf) |
| 271 | Official keynote summary found. Its equivalence to the proceedings abstract is unverified. | [HPDC 2009](https://hpdc.sci.utah.edu/2009/keynoteGENTZSCH.php) |
| 582 | No abstract in the inspected two-page author-hosted paper. It starts with Introduction. | [GE Vernova paper](https://www.gevernova.com/gev/sites/default/files/2024-07/paper_optimizing-emissions-for-machine-learning-training.pdf) |
| 2118 | No separate abstract in the publisher news feature. A short standfirst is available. | [Nature](https://www.nature.com/articles/d41586-017-07523-y) |
| 2405 | No abstract in the publisher full text. | [PLOS](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013481) |
| 2570 | No separate abstract in the indexed publisher preview. This is a special-issue introduction. | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2210537918303901) |
| 2696 | Exact magazine item not retrieved. A related company press release is available. | [Verne Global release](https://www.prnewswire.com/news-releases/verne-global-helps-the-bmw-group-to-cut-carbon-emissions-by-3570-metric-tons-per-year-with-switch-to-icelandic-data-centre-173440011.html) |
| 3173 | No abstract in the institutional record. Full foreword not retrieved. | [ORNL](https://impact.ornl.gov/en/publications/foreword-sustainable-project-pathways-for-hpc-software-2024-works/) |
| 3241 | Abstract not found for the exact 2025 front-matter item. | [ACM proceedings, retrieval failed](https://dl.acm.org/doi/proceedings/10.1145/3731599) |
| 3242 | Same search result as 3241. Separate Scopus entry, same title/year/page. | [ACM proceedings, retrieval failed](https://dl.acm.org/doi/proceedings/10.1145/3731599) |
| 3642 | Exact workshop editorial not retrieved. Page 1859 also starts a different paper. | [2023 proceedings index](https://dblp.org/db/conf/sc/sc2023w.html) |

For 582, 2118, 2405, and 2570, no abstract was present in the inspected version.
For the other seven, the abstract was not found. This does not prove that no
abstract exists. Summaries, introductions, and related press releases were not
used as replacement abstracts. Record 230's title-page description was also
not treated as an abstract.

The later records were selected by historical models. Records without human
labels and the 14 approved removals are outside this benchmark. Scores apply to
this selected sample, not to all search results. Some human decisions used
information beyond the title and abstract. Possible model training exposure to
these public papers remains unknown.
