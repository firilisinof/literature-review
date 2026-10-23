# HPC screening benchmark

Compare five benchmark models and three historical screeners with the existing
human decisions for 595 records from the published HPC review: 62 include and
533 exclude. Evaluate the entire collection together. The initial 119-record
benchmark run checked execution and required no changes. Its predictions are
reused alongside the remaining 476 records.

Three additional open-weight models extend the individual comparison: Llama-3.1-8B-Instruct, Gemma 4 12B, and Perplexity Decider Flash v1.2. Their results are stored separately from the original five-model predictions. The individual figures include all eleven models.

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
- `scripts/screening_api.py`: provider request formats and response parsing.
- `scripts/run_local.py`, `scripts/local_server.py`: run pinned local models sequentially.
- `scripts/run_extensions.py`: native inference for the additional Llama, Gemma, and Perplexity models.
- `scripts/compare_extensions.py`: validate and score those runs, reporting missing model coverage explicitly.
- `scripts/merge_results.py`: validates and merges response chunks.
- `scripts/compare_results.py`, `scripts/plot_comparison.py`: score predictions and generate plots.
- `scripts/historical_screening.py`: checks historical choices against raw batch outputs.
- `scripts/test_historical_screening.py`: offline regression checks for the historical import.
- `kev-requirements.txt`, `qwen-requirements.txt`: pinned server dependencies.
- `extensions-requirements.txt`: isolated dependencies for the additional models.
- `results/predictions.jsonl`: the 2,975 benchmark requests, responses, decisions, and timings.
- `results/local-runs.json`: local server settings and startup/run timings for both dates.
- `results/comparison.json`: eleven-model metrics, coverage, recall intervals, and disagreements.
- `results/*-20261023.jsonl`: separate Llama, Gemma, and Perplexity prediction chunks.
- `results/extensions-comparison.json`: validated scores and coverage for the added models.
- `figures/metrics.png`, `figures/disagreements.png`: full-collection figures.

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

Both comparison commands validate and include the three dated extension chunks by default. Use `--extensions FILE ...` to select other extension chunks, or pass `--extensions` without paths to reproduce the original eight-model comparison.

Install [Roboto Condensed](https://fonts.google.com/specimen/Roboto+Condensed)
as a user font before plotting. These commands check dataset construction,
request preparation, and saved-result integrity.
The comparison verifies record IDs, exact request bodies, prompt hashes, parsed
responses, and complete coverage for the five benchmark models and three additions. It also checks
historical model versions and cached choices against the raw batch outputs.
It makes no model requests.

Run the offline regression checks:

```sh
python -m unittest discover -s 2_screening/benchmark/scripts -p 'test_*.py'
```

## Run screening

Dry-run is the default. `--model` accepts `jev`, `decisions`, `kev-4b`, `kev-9b`,
`qwen`, or `all`. Live runs require one selected model, `--execute`, and a new
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

The runner sends one request at a time per model, waits at most 60 seconds per
request, and does not retry. Failed requests and malformed or truncated answers
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

### Additional open-weight models

The extension runner uses a separate `extensions-env` under `~/hpc-screening-benchmark`. It leaves the Kev and Qwen environments intact. Create it with the existing `tools/bin/uv`, then install `extensions-requirements.txt` using `uv pip install --python extensions-env/bin/python --requirements extensions-requirements.txt`. The first six dependencies match Perplexity's published reference requirements. Accelerate supports Transformers device placement. These wheels include a CUDA 13.0 runtime, which requires a compatible NVIDIA driver.

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
python3 2_screening/benchmark/scripts/run_extensions.py --model gemma --dry-run --limit 1
```

From the server run directory, check two synthetic inputs before screening the collection. Select an available GPU explicitly. Visibility selects a device without reserving it.

```sh
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 ../extensions-env/bin/python scripts/run_extensions.py --model gemma --execute --smoke-test --output results/gemma-smoke.jsonl
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 ../extensions-env/bin/python scripts/run_extensions.py --model gemma --execute --output results/gemma.jsonl
```

Repeat for `llama` and `pplx-flash`, one model at a time. All models use BF16, batch size 1, an 8192-token context budget, four CPU threads, no retries, and no input truncation. All selected inputs are checked for length before screening starts. The LLMs use greedy generation with 16 output tokens. Llama constrains decoding to `include`, `exclude`, and their initial-capital variants, followed by EOS. This was fixed using synthetic inputs before screening the collection, since unconstrained Llama added explanations and hit the output limit. Gemma uses the instruction-tuned checkpoint, disables thinking through its chat template, and parses responses using its published response template. Only complete EOS-terminated binary answers are accepted. Perplexity uses the checkpoint's native decision source, noncausal attention, reference path (`fast=False`), and saved calibration temperature. It does not generate text.

Outputs are created exclusively and flushed per record. Each preserves the exact title/abstract request, prompt and runner hashes, fixed model revision, inference settings, raw response, decision or explicit technical error, timing, and runtime versions. Startup and input-check time are recorded separately from per-record timings. `--completed FILE` validates and skips saved attempts, including errors. Keep these additional predictions separate from the original five-model `predictions.jsonl`, whose validator remains unchanged. The combined comparison validates extension chunks separately before combining their scores and pairwise disagreements.

Validate and score saved extension chunks without ML libraries or model requests:

```sh
python3 2_screening/benchmark/scripts/compare_extensions.py 2_screening/benchmark/results/llama-20261023.jsonl 2_screening/benchmark/results/gemma-20261023.jsonl 2_screening/benchmark/results/pplx-flash-20261023.jsonl
```

This writes `results/extensions-comparison.json`, rejecting duplicate records, changed inputs or settings, and inconsistent decisions. A model without all 595 valid decisions receives coverage counts without accuracy metrics.

## Merge and evaluate

Merge saved predictions and new chunks after all five models have complete
coverage:

```sh
python 2_screening/benchmark/scripts/merge_results.py saved.jsonl jev-new.jsonl decisions-new.jsonl kev4-new.jsonl kev9-new.jsonl qwen-new.jsonl --output merged.jsonl
python 2_screening/benchmark/scripts/compare_results.py --predictions merged.jsonl --no-plots
```

The merger rejects duplicate model/record pairs, unknown IDs, changed requests,
and incompatible responses. It requires exactly 595 attempts per model and
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
