# HPC screening benchmark

Compare the agreed models with human decisions from the published HPC review.
Keep the published criteria fixed. No paid model requests are authorized yet.

## Files and use

- `benchmark.jsonl`: all 595 records, one JSON object per line.
- `build_dataset.py`: rebuilds the dataset from the original screening files.
- `README.md`: the evaluation plan and source notes.
- `prompt.txt`: the shared screening instructions.
- `run_development.py`: prepares or sends development requests.
- `run_local.py`: starts the pinned local servers and runs development requests.
- `compare_development.py`: scores saved development runs and plots the comparison.
- `kev-requirements.txt`, `qwen-requirements.txt`: pinned server dependencies.
- `results/`: dated response files and the local run summary.

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

## Run development screening

The runner uses Python's standard library. It reads only the 119 development
records. It never selects held-out records. Dry-run is the default and needs
no API key, model download, or running server.

Preview one record for each model:

```sh
python 2_screening/benchmark/run_development.py --dry-run --limit 1
```

Prepare all 119 requests for each of the five models in one file:

```sh
python 2_screening/benchmark/run_development.py --dry-run --output preview.jsonl
```

Use `--model jev`, `decisions`, `kev-4b`, `kev-9b`, or `qwen` to select one model.
The prompt and paper text are the same across models. The request format differs
by API. Each model must return `include` or `exclude` under the published criteria.

Live runs require `--execute` and a new `--output` path. Hosted runs also require
`TYPESAFE_API_KEY` for Jev or `OPENAI_API_KEY` for OpenAI Decisions. Do not run a
paid service until paid requests are approved. A later approved Jev run would use:

```sh
python 2_screening/benchmark/run_development.py --model jev --execute --limit 1 --output jev-development.jsonl
```

Local models need a running server. The runner does not install or load weights.
Start Kev from [its source repository](https://github.com/jaredpalmer/kev),
using a local checkpoint downloaded from the selected `v1.0` revision:

```sh
uv run --extra serve python -m kev.serve --run /path/to/kev-4b-checkpoint --port 8009
```

Use port 8010 for Kev-9B. Both Kev servers accept the request model name
`kev-latest`. The checkpoint loaded by each server determines the actual model.
Verify that it matches the selected model and record the checkpoint and server
commit hashes with `--revision`. The runner records this supplied value but
cannot verify the weights loaded by the server.

Serve Qwen with a compatible vLLM installation, using the chosen model commit:

```sh
CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-8B --revision MODEL_COMMIT --port 8000
```

Select the approved GPU index before starting. vLLM 0.10.2 requires a numeric
index in `CUDA_VISIBLE_DEVICES`. It rejects GPU UUIDs in that variable.
Replace `MODEL_COMMIT` with the selected commit hash. Qwen requests disable
thinking with `chat_template_kwargs`, use temperature 0, and allow 16 output
tokens for a single label. Truncated or malformed answers are technical errors.
No input text is truncated by the runner. The server must reject oversized
inputs rather than silently truncate them.

For example, after starting the Kev-4B server:

```sh
python 2_screening/benchmark/run_development.py --model kev-4b --execute --revision 'MODEL_COMMIT; SERVER_COMMIT' --limit 1 --output kev4-development.jsonl
```

Replace the revision placeholders with the actual hashes. Use `--url` to set the
full endpoint URL of a local server on another machine or port. The defaults are
`http://localhost:8009/v1/systemone` for Kev-4B,
`http://localhost:8010/v1/systemone` for Kev-9B, and
`http://localhost:8000/v1/chat/completions` for Qwen.

Each output line records the paper ID, model, request, prompt hash, and run time.
Live results also contain the raw response, elapsed seconds, decision, and status. Raw responses preserve probabilities and token usage when supplied.
The runner makes one request at a time, waits at most 60 seconds per request,
and does not retry. A failed request has `status: error` and `decision: null`.
An error is not an inclusion or exclusion decision. HTTP errors also record the status code. Existing output files are never
overwritten. A dry-run file contains requests only, not simulated predictions.

The runner does not score results or calculate billing. Keep predictions fixed
before joining them to the human labels for the agreed metrics.

Request formats follow the [TypeSafe API](https://docs.typesafe.ai/api),
[OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions),
and [Qwen model card](https://huggingface.co/Qwen/Qwen3-8B).

## Server setup

Use the [server setup notes](/Users/lucas/Pessoal/ai-wiki/memory/literature-review/hpc-server-setup.md)
for the approved access rules, installed environments, fixed revisions, and
serving commands.

On the approved GPU server, keep the benchmark scripts, `prompt.txt`, and a
development-only copy of `benchmark.jsonl` together. The local runner uses
the existing environments, pinned source, and `model-downloads.json` under
`~/hpc-screening-benchmark`. It runs one server at a time on GPU 0 and stops
each server after the requests finish:

```sh
python run_local.py --execute --date YYYYMMDD
```

Use the run date in place of `YYYYMMDD`. Use `--server-home` if the installation
is elsewhere. The script refuses to overwrite an existing run. Model files
must already be cached. It does not download weights or change the prompt.

All model responses use `results/<model>-development-<date>.jsonl`, including
the hosted models. Each file contains the requests, raw responses, revisions,
prompt hash, decisions, errors, and per-request times. Local startup timing
and server settings are kept in `local-development-<date>-summary.json`.
The 20261021 summary also contains the development comparison. Successful
runs do not keep extra logs or duplicate input files.

## Split and evaluation

Install [Roboto Condensed](https://fonts.google.com/specimen/Roboto+Condensed)
as a user font before generating plots. The script requires this font.

Compare all five saved development runs for one date without making requests:

```sh
uv run --no-project --with matplotlib==3.10.8 python 2_screening/benchmark/compare_development.py --date 20261021
```

The script checks the development IDs, prompt hash, response decisions, and
complete coverage before scoring. It writes a comparison JSON and two PNG
plots under `results/`. It uses only development labels. Raw responses stay
unchanged. The comparison JSON includes two-sided 95% Wilson recall intervals.

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

Use the fixed revisions recorded in the server setup notes.

Dataset provenance, recovered abstracts, and approved exclusions are in the
[dataset notes](/Users/lucas/Pessoal/ai-wiki/memory/literature-review/benchmark-dataset-provenance.md).
