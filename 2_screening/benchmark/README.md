# HPC screening benchmark

Compare eight benchmark models and three historical screeners with the existing human decisions for 595 records from the published HPC review: 62 include and 533 exclude. Evaluate the entire collection together. The original five-model run covered an initial 119 records and the remaining 476 records. Llama-3.1-8B-Instruct, Gemma 4 12B, and Perplexity Decider Flash v1.2 each screened the same 595 records afterward.

All eight benchmark models use the same screening, validation, merging, and comparison commands. Their saved requests and responses live in one `results/predictions.jsonl`. The individual figures include all eleven models. The workflow figure compares four fixed groups of models and their unanimous-inclusion rules.

The published criteria, prompt, model revisions, request settings, output parser,
and no-retry policy are fixed across both benchmark runs. The historical runs
retain their original settings and choices. This is a descriptive comparison on
the reviewed collection, not a separate held-out evaluation.

## Files

Python scripts and their tests live in `scripts/`. Dataset, prompt, and dependency files stay here, with outputs in `results/` and `figures/`.

- `benchmark.jsonl`: the single dataset, without an evaluation split.
- `scripts/build_dataset.py`: rebuilds the dataset from original screening files.
- `prompt.txt`: shared screening instructions.
- `scripts/run_screening.py`: previews requests or runs one selected model.
- `scripts/screening_api.py`: model definitions, request formats, and response parsing.
- `scripts/run_local.py`, `scripts/local_server.py`: manage pinned local servers and native model loading.
- `scripts/merge_results.py`: validates and merges response chunks.
- `scripts/compare_results.py`, `scripts/plot_comparison.py`: score predictions and generate plots.
- `scripts/evaluate_workflows.py`: simulate model ensembles routing records to human screening.
- `scripts/historical_screening.py`: checks historical choices against raw batch outputs.
- `scripts/test_screening.py`: offline regression checks for shared validation, inference, and historical import.
- `kev-requirements.txt`, `qwen-requirements.txt`: pinned server dependencies.
- `requirements.txt`: shared dependencies for dataset preparation, plots, and native inference.
- `results/predictions.jsonl`: the 4,760 benchmark requests, responses, decisions, and timings.
- `results/local-runs.json`: local server settings and startup/run timings for both dates.
- `results/comparison.json`: eleven-model metrics, coverage, recall intervals, and disagreements.
- `figures/metrics.png`, `figures/disagreements.png`: full-collection figures.
- `results/workflows.json`: metrics and fixed group definitions for fourteen workflows.
- `figures/workflows.png`: one workflow figure with four model groups.

Each dataset record has `record_id`, `title`, `abstract`, `label`, `cohort`,
`label_source`, and `abstract_source`. Source fields point to original evidence.
Use `record_id` to locate the human decision in its source file.

Send only `title` and `abstract` to models. Keep `record_id` as a request key.
The runner never sends human labels, provenance, or historical model answers.

## Rebuild and check

Run commands from the repository root. Rebuild the dataset without model requests:

```sh
uv run --no-project --with bibtexparser==1.4.4 python 2_screening/benchmark/scripts/build_dataset.py
```

The script checks unique IDs and titles, human decisions, recovered abstracts,
and cohort counts before writing all 595 records.

Preview one request per model without network access:

```sh
python 2_screening/benchmark/scripts/run_screening.py --dry-run --limit 1
```

Validate and score the saved results without requests or plotting dependencies:

```sh
python 2_screening/benchmark/scripts/compare_results.py --no-plots
```

Regenerate the comparison and figures:

```sh
uv run --no-project --with matplotlib==3.10.8 python 2_screening/benchmark/scripts/compare_results.py
```

Plots use the comparison's scored counts and are saved in `figures/` beside the
`results/` folder. The figure directory is created automatically.

Both comparison commands read the combined predictions file. Use `--predictions FILE` to score another saved collection. The disagreement figure sorts models by descending disagreement with humans on both axes.

Install [Roboto Condensed](https://fonts.google.com/specimen/Roboto+Condensed)
as a user font before plotting. These commands check dataset construction,
request preparation, and saved-result integrity.
The comparison verifies record IDs, exact request bodies, prompt hashes, parsed
responses, and complete coverage for all eight benchmark models. It also checks
historical model versions and cached choices against the raw batch outputs.
It makes no model requests.

Run the offline regression checks:

```sh
python -m unittest discover -s 2_screening/benchmark/scripts -p 'test_*.py'
```

## Run screening

Dry-run is the default. `--model` accepts `jev`, `decisions`, `kev-4b`, `kev-9b`,
`qwen`, `llama`, `gemma`, `pplx-flash`, or `all`. Live runs require one selected model, `--execute`, and a new
`--output` file. Hosted requests use `TYPESAFE_API_KEY` or `OPENAI_API_KEY` from
the environment. For example, a complete new hosted run uses:

```sh
python 2_screening/benchmark/scripts/run_screening.py --model jev --execute --output jev-new.jsonl
```

Use `--completed SAVED.jsonl` to send only records absent for that model.
The file may contain multiple models. Saved requests must match current inputs
and settings. Duplicate or incompatible saved records stop the run. Both valid
responses and technical errors count as already attempted, so this option does
not retry errors. `--limit N` selects the first N missing records in ID order.

For example, preview missing records without making requests:

```sh
python 2_screening/benchmark/scripts/run_screening.py --model jev --completed 2_screening/benchmark/results/predictions.jsonl --dry-run
```

The committed file is complete, so this prepares zero requests. Omit
`--completed` to prepare a fresh full run. Output files are never overwritten.
Each response is flushed immediately, preserving completed work if interrupted.

The runner processes one request at a time per model and does not retry. HTTP requests time out after 60 seconds. Native models run directly in the selected GPU environment. Failed requests and malformed or truncated answers
have `status: error` and `decision: null`. Live commands exit unsuccessfully if
any request fails. HTTP errors record their status code. Raw responses preserve
probabilities and token usage when provided.

## Server setup

Use the [server setup notes](/Users/lucas/Pessoal/ai-wiki/memory/literature-review/hpc-server-setup.md)
for access rules, installed environments, and fixed revisions. Run within the
approved schedule. The user environments, pinned Kev source, cached model
weights, and `model-downloads.json` live under `~/hpc-screening-benchmark`.
No system package changes or weight downloads are performed by the runner.

Copy the `scripts/` folder, `prompt.txt`, and `benchmark.jsonl` into one run directory on the approved server, preserving the folder structure. Copy saved predictions too when continuing a run. From that directory, run:

```sh
python3 scripts/run_local.py --execute --date YYYYMMDD --completed results/predictions.jsonl
```

Use `--server-home` for a different installation path, or `--model kev-4b`,
`kev-9b`, or `qwen` for one model. Omit `--completed` for a fresh full run.
Outputs are `results/<model>-<date>.jsonl` and `results/local-<date>-summary.json`.
The runner refuses existing destinations, skips models without missing records,
starts one server at a time on GPU 0, and stops each server after inference.

The same settings used for the initial 119 records apply to the remaining 476:
BF16, concurrency 1, cached weights, no input truncation, and no retries. Kev
uses the pinned checkpoint and base revisions. Qwen uses vLLM 0.10.2, context
length 8192, maximum one sequence, GPU memory utilization 0.70, temperature 0,
thinking disabled, and 16 output tokens. A malformed or truncated answer is a
technical error. `CUDA_VISIBLE_DEVICES=0` selects a GPU but does not reserve it.

To use an already running server, call `scripts/run_screening.py` with `--model`,
`--execute`, `--revision`, and `--output`. Supply actual checkpoint, base, and
server revisions. `--url` overrides a local endpoint. Defaults are
`http://localhost:8009/v1/systemone`, `http://localhost:8010/v1/systemone`, and
`http://localhost:8000/v1/chat/completions` for Kev-4B, Kev-9B, and Qwen.
The common runner records supplied revisions. It cannot inspect server weights.

### Native inference

The shared `requirements.txt` covers dataset preparation, plots, and native inference for Llama, Gemma, and Perplexity. Its first six pins match Perplexity's published reference requirements. Accelerate supports Transformers device placement. The recorded native runs used the server's existing `extensions-env`. To reproduce that environment, install `requirements.txt` with `tools/bin/uv pip install --python extensions-env/bin/python --requirements requirements.txt`. The CUDA 13.0 wheels require a compatible NVIDIA driver. Kev and Qwen retain their separate environment snapshots because their original serving dependencies conflict with these versions.

Download these exact snapshots before inference. Llama requires approved Hugging Face access and a terminal login with `hf auth login`. The Llama loader selects Safetensors and tokenizer/configuration files, excluding the duplicate legacy PyTorch weights. The same allowlist is applied during offline cache validation.

| Runner key | Repository | Revision |
| --- | --- | --- |
| `llama` | `meta-llama/Llama-3.1-8B-Instruct` | `0e9e39f249a16976918f6564b8830bc894c89659` |
| `gemma` | `google/gemma-4-12B-it` | `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` |
| `pplx-flash` | `perplexity-ai/pplx-decider-flash-v1.2` | `9ff7cf9838e59df461c276b7699d56b244d2af58` |

For example, from the server installation directory:

```sh
extensions-env/bin/hf download google/gemma-4-12B-it --revision 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
```

Copy the `scripts/` folder, `prompt.txt`, and `benchmark.jsonl` into a run directory, preserving the folder structure. Create its `results/` folder before running inference. Preview requests locally without importing ML libraries:

```sh
python3 2_screening/benchmark/scripts/run_screening.py --model gemma --dry-run --limit 1
```

From the server run directory, check two synthetic inputs before screening the collection. Select an available GPU explicitly. Visibility selects a device without reserving it.

```sh
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 ../extensions-env/bin/python scripts/run_screening.py --model gemma --execute --smoke-test --output results/gemma-smoke.jsonl
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 ../extensions-env/bin/python scripts/run_screening.py --model gemma --execute --output results/gemma.jsonl
```

Repeat for `llama` and `pplx-flash`, one model at a time. All models use BF16, batch size 1, an 8192-token context budget, four CPU threads, no retries, and no input truncation. All selected inputs are checked for length before screening starts. The LLMs use greedy generation with 16 output tokens. Llama constrains decoding to `include`, `exclude`, and their initial-capital variants, followed by EOS. This was fixed using synthetic inputs before screening the collection, since unconstrained Llama added explanations and hit the output limit. Gemma uses the instruction-tuned checkpoint, disables thinking through its chat template, and parses responses using its published response template. Only complete EOS-terminated binary answers are accepted. Perplexity uses the checkpoint's native decision source, noncausal attention, reference path (`fast=False`), and saved calibration temperature. It does not generate text.

Each native result preserves the exact title/abstract request, prompt and runner hashes, fixed model revision, inference settings, raw response, decision or explicit technical error, timing, and runtime versions. Startup and input-check time are recorded separately from per-record timings. Use the common `--completed FILE` option to validate and skip saved attempts, including errors. Merge new chunks into `results/predictions.jsonl`, then score all models with `scripts/compare_results.py`.

## Merge and evaluate

Merge saved predictions and new chunks after all eight models have complete coverage:

```sh
python 2_screening/benchmark/scripts/merge_results.py saved.jsonl new-chunk.jsonl --output merged.jsonl
python 2_screening/benchmark/scripts/compare_results.py --predictions merged.jsonl --no-plots
```

The merger rejects duplicate model/record pairs, unknown IDs, changed requests,
and incompatible responses. It requires exactly 595 attempts for each of the eight benchmark models and
atomically replaces the output after validation. It preserves response evidence,
revisions, timestamps, and timings. Technical errors remain errors.

The comparison reports technical failures and valid-decision coverage separately.
It withholds full metrics for any model without 595 valid decisions. Errors do
not receive screening labels and are never removed from the denominator.

Let `R` be the number of model inclusions and `E` the number matching human
inclusions. Metrics for a complete model are:

| Metric | Calculation |
| --- | --- |
| Eligible-paper recall | `E / 62` |
| False exclusions | `62 - E` |
| Retained fraction | `R / 595` |
| Inclusion precision | `E / R`, undefined when `R = 0` |
| Processing time | Sum of request times and time per record |

Report counts beside rates. Prioritize recall and false exclusions, and report
the two-sided 95% Wilson recall interval. Retained fraction measures how much of
the collection remains after screening. There is no human intervention or
confidence threshold in model decisions.

Local startup and server lifetime are recorded separately from request times in
`results/local-runs.json`. Request times do not include the overnight gap between
runs. Billing totals and GPU hourly rates are unavailable, so costs are reported
as unknown. No API billing for local models does not imply zero compute cost.

## Historical screening

The three historical models cover the same 595 IDs. Their choices in
`artifacts/processed.csv` are checked against the raw batches in
`2_screening/results/`. Count `doubt` as `include` for metrics, disagreements,
and the unanimous-include baseline. Original responses remain unchanged.

Historical choices retain the original parser, including Sonnet's truncated
responses with recoverable decisions. Versions, source hashes, and recoveries
are recorded in `comparison.json`. Earlier prompts, 18 recovered benchmark
abstracts, and selection of the later cohort through historical inclusion limit
this descriptive comparison. Historical costs and request times are unknown.

## Human screening workflows

Evaluate combined-model routing using the existing predictions, without making requests:

```sh
python 2_screening/benchmark/scripts/evaluate_workflows.py --no-plots
uv run --no-project --with matplotlib==3.10.8 python 2_screening/benchmark/scripts/evaluate_workflows.py
```

The first command needs only the Python standard library. The second also writes `figures/workflows.png` using the same font as the model comparison. It replaces the two earlier workflow figures. `--predictions FILE` selects the combined predictions file and writes `workflows.json` beside it. The default is `results/predictions.jsonl`. Requests, prompt hashes, model revisions, responses, and complete decision coverage are validated before any workflow is scored.

Compare four fixed groups on the same 595 labeled records. Each group shows its individual models and the rule that sends a record to humans only when every model in that group includes it. This produces fourteen workflows:

- Closed-weight LLMs: GPT-5.4, Sonnet 4.5, Gemini 2.5 Pro, and their three-model agreement.
- Open-weight LLMs: Qwen3-8B, Llama-3.1-8B-Instruct, Gemma 4 12B, and their three-model agreement.
- Closed-weight decision models: Jev, OpenAI Decisions, and their two-model agreement.
- Open-weight decision models: Kev-9B, Perplexity Decider Flash v1.2, and their two-model agreement.

The roster is fixed by model category, without ranking or searching combinations using these labels. Kev-4B remains in the original benchmark results but does not enter this grouped comparison. Unanimity sizes are explicit, since a two-model intersection and a three-model intersection impose different requirements. Comparisons across model types remain descriptive. Llama uses binary constrained decoding, while Qwen and Gemma use unconstrained greedy generation with strict response validation. These results compare the recorded inference configurations as well as their weights.

Historical doubt counts as include. Verify historical choices against the raw batches and preserve their source hashes. The closed-weight LLMs retain their original inputs, as approved for this comparison. Automatically exclude records not sent to humans. No record is automatically included. Reviewed records receive their existing human label in this simulation.

The static Matplotlib figure contains four sections on aligned axes. Columns show screening work saved and disagreements with human decisions. Each disagreement bar is split into false inclusions and false exclusions, with exact counts printed as `FP + FN` so small false-exclusion counts remain visible. The agreement rows are shaded and bold. Each row represents one actual policy, without averaging over subsets or range bars. Exact model identities, thresholds, confusion counts, precision, recall, and missed IDs are saved in `workflows.json`. The figure has no subtitle or footer.

Workload reduction is `1 - reviewed / 595`. Human disagreements are `FP + FN` out of all 595 records. False inclusions (`FP`) are model inclusions with a human exclusion label. False exclusions (`FN`) are model exclusions with a human inclusion label. These compare model routing decisions before human review: false inclusions add human screening work, while false exclusions miss known inclusions. Saved results also retain inclusion precision `TP / (TP + FP)`, exclusion precision `TN / (TN + FN)`, recall, and its Wilson interval. Precision is undefined when no records receive the corresponding label. Workload measures records, not reviewer time, full-text assessment, or disagreement resolution. Wilson intervals do not account for selection bias or shared model errors.

The later cohort already passed historical unanimous inclusion before humans screened it. Human labels are unavailable for the other search results. Thus, this analysis cannot estimate recall of the published screening process across the full search. Treat all workflow comparisons as descriptive results on the labeled collection, not validation of a policy for a new review. Estimating missed inclusions among the original model exclusions requires human screening of those records, for example through a probability sample with recorded sampling weights.

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
| Llama-3.1-8B-Instruct | `meta-llama/Llama-3.1-8B-Instruct`, local |
| Gemma 4 12B | `google/gemma-4-12B-it`, thinking disabled, local |
| Perplexity Decider Flash v1.2 | `perplexity-ai/pplx-decider-flash-v1.2`, native reference inference, local |
| GPT-5.4 (historical) | `gpt-5.4-2026-03-05`, original OpenAI batch |
| Sonnet 4.5 (historical) | `claude-sonnet-4-5-20250929`, original Anthropic batch |
| Gemini 2.5 Pro (historical) | `gemini-2.5-pro`, original Gemini batch |

Request formats follow the [TypeSafe API](https://docs.typesafe.ai/api),
[OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions),
and [Qwen model card](https://huggingface.co/Qwen/Qwen3-8B).
Dataset provenance, recovered abstracts, and approved exclusions are in the
[dataset notes](/Users/lucas/Pessoal/ai-wiki/memory/literature-review/benchmark-dataset-provenance.md).
