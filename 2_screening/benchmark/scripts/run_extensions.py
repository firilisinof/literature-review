"""Screen with pinned Llama, Gemma, or Perplexity weights using native inference."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from run_screening import FOLDER, screening_records
from screening_api import OPTIONS

MODELS = {
    "llama": (
        "meta-llama/Llama-3.1-8B-Instruct",
        "0e9e39f249a16976918f6564b8830bc894c89659",
    ),
    "gemma": (
        "google/gemma-4-12B-it",
        "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
    ),
    "pplx-flash": (
        "perplexity-ai/pplx-decider-flash-v1.2",
        "9ff7cf9838e59df461c276b7699d56b244d2af58",
    ),
}
MAX_CONTEXT = 8192
MAX_OUTPUT = 16
LLAMA_FILES = ["*.json", "*.safetensors", "*.jinja", "LICENSE", "README.md", "USE_POLICY.md"]
LLAMA_ANSWERS = ["include", "exclude", "Include", "Exclude"]


def request_body(model, paper, prompt):
    text = json.dumps(
        {"title": paper["title"], "abstract": paper["abstract"]}, ensure_ascii=False
    )
    if model == "pplx-flash":
        return {
            "state": text,
            "questions": {
                "screening": {
                    "type": "choice", "instructions": prompt, "criteria": OPTIONS
                }
            },
        }
    return {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        "do_sample": False,
        "max_new_tokens": MAX_OUTPUT,
        **({"enable_thinking": False} if model == "gemma" else {}),
        **({"allowed_answers": LLAMA_ANSWERS} if model == "llama" else {}),
    }


def settings(model):
    common = {
        "dtype": "bfloat16", "attention": "sdpa", "batch_size": 1,
        "max_context_tokens": MAX_CONTEXT, "truncation": False, "cpu_threads": 4,
    }
    if model == "pplx-flash":
        return {**common, "fast": False, "temperature": "checkpoint"}
    return {
        **common, "do_sample": False, "max_new_tokens": MAX_OUTPUT,
        **({"allowed_answers": LLAMA_ANSWERS} if model == "llama" else {}),
    }


def decision_from(model, response):
    if model == "pplx-flash":
        choice = response["answers"]["screening"]["choice"]
    else:
        if response["finish_reason"] != "stop":
            raise ValueError("Expected an EOS-terminated answer, got an output token limit")
        choice = response["content"].strip().lower()
    if choice not in OPTIONS:
        raise ValueError(f"Decision {choice!r}: expected include or exclude")
    return choice


def validate_saved(row, paper, prompt):
    model = row["model"]
    if (
        row["dry_run"]
        or row["revision"] != MODELS[model][1]
        or row["repository"] != MODELS[model][0]
        or row["settings"] != settings(model)
        or row["prompt_sha256"] != hashlib.sha256(prompt.encode()).hexdigest()
        or row["request"] != request_body(model, paper, prompt)
    ):
        raise ValueError(f"{model}/{paper['record_id']}: incompatible saved request")
    if row["status"] == "ok":
        if row["decision"] != decision_from(model, row["response"]):
            raise ValueError(f"{model}/{paper['record_id']}: inconsistent saved decision")
    elif row["status"] != "error" or row["decision"] is not None:
        raise ValueError(f"{model}/{paper['record_id']}: expected a decision or explicit error")


class NativeModel:
    def __init__(self, model):
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCausalLM, AutoModelForMultimodalLM
        from transformers import AutoProcessor, AutoTokenizer

        self.torch = torch
        self.name = model
        torch.set_num_threads(4)
        torch.manual_seed(0)
        repo, revision = MODELS[model]
        checkpoint = Path(snapshot_download(
            repo, revision=revision, local_files_only=True,
            allow_patterns=LLAMA_FILES if model == "llama" else None,
        ))
        if checkpoint.name != revision:
            raise ValueError(f"Expected cached snapshot {revision}, got {checkpoint}")
        self.checkpoint = checkpoint
        if model == "pplx-flash":
            sys.path.insert(0, str(checkpoint / "source" / "src"))
            from pplx_decider import Decider

            self.model = Decider.from_pretrained(
                checkpoint, device="cuda:0", fast=False,
                max_length=MAX_CONTEXT, cpu_threads=4,
            )
            return
        if model == "gemma":
            self.processor = AutoProcessor.from_pretrained(checkpoint, local_files_only=True)
            self.tokenizer = self.processor.tokenizer
            loader = AutoModelForMultimodalLM
        else:
            self.processor = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
            self.tokenizer = self.processor
            loader = AutoModelForCausalLM
        self.model = loader.from_pretrained(
            checkpoint, dtype=torch.bfloat16, device_map={"": "cuda:0"},
            attn_implementation="sdpa", local_files_only=True,
        ).eval().requires_grad_(False)

    def inputs(self, body):
        kwargs = {"enable_thinking": False} if self.name == "gemma" else {}
        return self.processor.apply_chat_template(
            body["messages"], tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt", **kwargs,
        )

    def token_count(self, body):
        if self.name == "pplx-flash":
            return sum(chunk.length for chunk in self.model.encoder.plan(body, MAX_CONTEXT))
        length = self.inputs(body)["input_ids"].shape[-1]
        if length + MAX_OUTPUT > MAX_CONTEXT:
            raise ValueError(f"Request needs {length} input tokens plus {MAX_OUTPUT} output tokens")
        return length

    def predict(self, body):
        with self.torch.inference_mode():
            if self.name == "pplx-flash":
                return self.model.decide(body)
            inputs = {key: value.to("cuda:0") for key, value in self.inputs(body).items()}
            pad_id = self.model.generation_config.pad_token_id
            if pad_id is None:
                pad_id = self.tokenizer.eos_token_id
            constraints = {}
            if self.name == "llama":
                constraints["prefix_allowed_tokens_fn"] = self.answer_constraint(
                    inputs["input_ids"].shape[-1]
                )
            output = self.model.generate(
                **inputs, do_sample=False, max_new_tokens=MAX_OUTPUT,
                temperature=None, top_p=None, top_k=None, pad_token_id=pad_id,
                **constraints,
            )
            tokens = output[0, inputs["input_ids"].shape[-1]:].tolist()
            raw = self.tokenizer.decode(tokens, skip_special_tokens=False)
            eos_ids = self.model.generation_config.eos_token_id
            if isinstance(eos_ids, int):
                eos_ids = [eos_ids]
            response = {
                "raw_text": raw, "token_ids": tokens,
                "finish_reason": "stop" if tokens and tokens[-1] in eos_ids else "length",
                "usage": {"input_tokens": inputs["input_ids"].shape[-1], "output_tokens": len(tokens)},
            }
            if self.name == "gemma":
                prefix = self.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=False)
                response["parsed_message"] = self.processor.parse_response(raw, prefix=prefix)
                response["content"] = response["parsed_message"]["content"]
            else:
                response["content"] = self.tokenizer.decode(tokens, skip_special_tokens=True)
            return response

    def answer_constraint(self, input_length):
        answers = [self.tokenizer.encode(text, add_special_tokens=False) for text in LLAMA_ANSWERS]
        eos_ids = self.model.generation_config.eos_token_id
        if isinstance(eos_ids, int):
            eos_ids = [eos_ids]

        def allowed_tokens(batch_id, input_ids):
            prefix = input_ids[input_length:].tolist()
            allowed = set()
            for answer in answers:
                if answer[:len(prefix)] == prefix:
                    if len(prefix) == len(answer):
                        allowed.update(eos_ids)
                    else:
                        allowed.add(answer[len(prefix)])
            if not allowed:
                raise ValueError(f"Unexpected binary answer prefix {prefix}")
            return sorted(allowed)

        return allowed_tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="Default, no ML imports or network")
    parser.add_argument("--output", type=Path, help="New JSONL file, required with --execute")
    parser.add_argument("--completed", type=Path, help="Skip all saved attempts, including errors")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--smoke-test", action="store_true", help="Use two synthetic inputs, without benchmark papers")
    args = parser.parse_args()
    if args.execute and args.output is None:
        parser.error("--execute requires --output")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.smoke_test and args.completed:
        parser.error("--smoke-test cannot use --completed")
    prompt = (FOLDER / "prompt.txt").read_text().strip()
    papers = screening_records()
    if args.smoke_test:
        papers = [
            {"record_id": "synthetic-hpc", "title": "Measuring HPC carbon emissions",
             "abstract": "We measure life-cycle greenhouse gas emissions of a high-performance computing system, including hardware manufacture and electricity generation, and compare carbon-aware scheduling strategies."},
            {"record_id": "synthetic-history", "title": "Trade in medieval cities",
             "abstract": "This historical study examines trade routes between European cities in the fourteenth century using archival tax records."},
        ]
    completed = set()
    if args.completed:
        indexed = {paper["record_id"]: paper for paper in papers}
        for line in args.completed.read_text().splitlines():
            row = json.loads(line)
            if row["model"] != args.model:
                continue
            rid = row["record_id"]
            if rid not in indexed or rid in completed:
                raise ValueError(f"Unexpected or duplicate record {rid}")
            validate_saved(row, indexed[rid], prompt)
            completed.add(rid)
    papers = [paper for paper in papers if paper["record_id"] not in completed][:args.limit]
    output = args.output.open("x", encoding="utf-8") if args.output else sys.stdout
    failures = 0
    try:
        runtime = None
        if args.execute and papers:
            started = time.perf_counter()
            native = NativeModel(args.model)
            lengths = [native.token_count(request_body(args.model, paper, prompt)) for paper in papers]
            runtime = {
                "python": platform.python_version(),
                "packages": {name: importlib.metadata.version(name) for name in
                             ("torch", "transformers", "huggingface-hub", "accelerate")},
                "gpu": native.torch.cuda.get_device_name(0),
                "checkpoint": str(native.checkpoint),
                "startup_seconds": round(time.perf_counter() - started, 6),
                "max_input_tokens": max(lengths),
            }
            print(json.dumps(runtime), file=sys.stderr, flush=True)
        for index, paper in enumerate(papers, 1):
            body = request_body(args.model, paper, prompt)
            row = {
                "record_id": paper["record_id"], "model": args.model,
                "repository": MODELS[args.model][0], "revision": MODELS[args.model][1],
                "settings": settings(args.model), "dry_run": not args.execute,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "request": body,
            }
            if args.execute:
                started = time.perf_counter()
                row.update(status="error", decision=None, response=None, runtime=runtime)
                try:
                    row["response"] = native.predict(body)
                    row["decision"] = decision_from(args.model, row["response"])
                    row["status"] = "ok"
                except Exception as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                    failures += 1
                row["seconds"] = round(time.perf_counter() - started, 6)
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            output.flush()
            if args.execute:
                print(f"{args.model} {index}/{len(papers)} {paper['record_id']} {row['status']} {row['decision']}", file=sys.stderr, flush=True)
    finally:
        if args.output:
            output.close()
    print(f"{'Ran' if args.execute else 'Prepared'} {len(papers)} requests, {failures} errors.", file=sys.stderr)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
