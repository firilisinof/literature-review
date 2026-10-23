"""Load native models and manage pinned, offline model servers."""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO

from screening_api import (
    JSON,
    LLAMA_ANSWERS,
    LLAMA_FILES,
    MAX_CONTEXT,
    MAX_OUTPUT,
    MODELS,
    NATIVE_REVISIONS,
)

KEV_COMMIT = "1f04cfa28e6a708485b28a9585010b9e436b776e"
REVISIONS = [
    "6cfce5c2fa4b4bd64026336ab649c5ca78857d52",
    "db029f08b290afd9fee4aa4bbcd9ae48602d1eb0",
    "b968826d9c46dd6066d109eabc6255188de91218",
]
BASE_REVISIONS = [
    "1001bb4d826a52d1f399e183466143f4da7b741b",
    "68c46c4b3498877f3ef123c856ecfde50c39f404",
]


SERVER_SETTINGS = dict(
    CUDA_VISIBLE_DEVICES="0",
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    OMP_NUM_THREADS="4",
    KEV_TRUNCATE_STATES="0",
    KEV_FUSED="0",
    KEV_CUDA_GRAPHS="0",
)


@dataclass
class ServerPlan:
    """Describe one fixed server, e.g. server_plans(root)[0]."""

    name: str
    model: dict[str, str]
    command: list[str]
    revision: str
    port: int


def server_plans(root: Path) -> list[ServerPlan]:
    """Validate cached revisions before inference, e.g. server_plans(root)."""
    models = json.loads((root / "model-downloads.json").read_text())
    revisions = [model["revision"] for model in models]
    if revisions != REVISIONS:
        raise ValueError(f"Cached revisions {revisions}: expected {REVISIONS}")
    bases = [model["base_revision"] for model in models[:2]]
    if bases != BASE_REVISIONS:
        raise ValueError(f"Cached base revisions {bases}: expected {BASE_REVISIONS}")
    commit = subprocess.check_output(
        ["git", "-C", str(root / "kev-src"), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != KEV_COMMIT:
        raise ValueError(f"Kev server commit {commit}: expected {KEV_COMMIT}")
    return [make_plan(root, model, index) for index, model in enumerate(models)]


def make_plan(root: Path, model: dict[str, str], index: int) -> ServerPlan:
    """Preserve the validated serving settings, e.g. make_plan(root, model, 0)."""
    if index == 2:
        revision = f"model={model['revision']}; vllm=0.10.2; transformers=4.55.2; torch=2.8.0+cu128"
        return ServerPlan("qwen", model, qwen_command(root, model), revision, 8000)
    port = 8009 + index
    revision = (
        f"model={model['revision']}; base={model['base_revision']}; server={KEV_COMMIT}"
    )
    return ServerPlan(
        f"kev-{4 if index == 0 else 9}b",
        model,
        kev_command(root, model, port),
        revision,
        port,
    )


def qwen_command(root: Path, model: dict[str, str]) -> list[str]:
    """Preserve Qwen's validated configuration, e.g. qwen_command(root, model)."""
    command = [str(root / "qwen-env/bin/vllm"), "serve", model["path"]]
    options = {
        "--served-model-name": model["repo"],
        "--host": "127.0.0.1",
        "--port": "8000",
        "--dtype": "bfloat16",
        "--max-model-len": "8192",
        "--max-num-seqs": "1",
        "--gpu-memory-utilization": "0.70",
    }
    return command + [item for pair in options.items() for item in pair]


def kev_command(root: Path, model: dict[str, str], port: int) -> list[str]:
    """Use the pinned Kev server entry point, e.g. kev_command(root, model, 8009)."""
    command = [str(root / "kev-env/bin/python"), "-m", "kev.serve"]
    options = {
        "--run": model["path"],
        "--device": "cuda",
        "--host": "127.0.0.1",
        "--port": str(port),
    }
    return command + [item for pair in options.items() for item in pair]


def server_environment() -> dict[str, str]:
    """Keep inference offline on GPU 0, e.g. server_environment()."""
    return dict(os.environ, **SERVER_SETTINGS)


def wait_for_server(
    process: subprocess.Popen[bytes], plan: ServerPlan
) -> dict[str, JSON]:
    """Bound startup to 15 minutes, e.g. wait_for_server(process, plan)."""
    started = time.monotonic()
    while process.poll() is None:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{plan.port}/v1/models", timeout=2
            ) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if time.monotonic() - started > 900:
                raise TimeoutError(
                    f"{plan.name}: expected readiness within 900 seconds"
                )
            time.sleep(2)
    raise RuntimeError(
        f"{plan.name}: server exited with {process.returncode}, expected a running server"
    )


def stop_server(process: subprocess.Popen[bytes]) -> None:
    """Release this run's process group, e.g. stop_server(process)."""
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


@contextmanager
def running_server(
    plan: ServerPlan, environment: dict[str, str], log: TextIO
) -> Iterator[subprocess.Popen[bytes]]:
    """Always stop servers, including on failure, e.g. with running_server(plan, env, log)."""
    process = subprocess.Popen(
        plan.command,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        yield process
    except BaseException:
        log.seek(0)
        print(log.read(), flush=True)
        raise
    finally:
        stop_server(process)


class NativeModel:
    """Load pinned weights and preserve their native decision protocol."""

    def __init__(self, model):
        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoModelForCausalLM, AutoModelForMultimodalLM
        from transformers import AutoProcessor, AutoTokenizer

        self.torch = torch
        self.name = model
        torch.set_num_threads(4)
        torch.manual_seed(0)
        repo, revision = MODELS[model][0], NATIVE_REVISIONS[model]
        checkpoint = Path(
            snapshot_download(
                repo,
                revision=revision,
                local_files_only=True,
                allow_patterns=LLAMA_FILES if model == "llama" else None,
            )
        )
        if checkpoint.name != revision:
            raise ValueError(f"Expected cached snapshot {revision}, got {checkpoint}")
        self.checkpoint = checkpoint
        if model == "pplx-flash":
            sys.path.insert(0, str(checkpoint / "source" / "src"))
            from pplx_decider import Decider

            self.model = Decider.from_pretrained(
                checkpoint,
                device="cuda:0",
                fast=False,
                max_length=MAX_CONTEXT,
                cpu_threads=4,
            )
            return
        if model == "gemma":
            self.processor = AutoProcessor.from_pretrained(
                checkpoint, local_files_only=True
            )
            self.tokenizer = self.processor.tokenizer
            loader = AutoModelForMultimodalLM
        else:
            self.processor = AutoTokenizer.from_pretrained(
                checkpoint, local_files_only=True
            )
            self.tokenizer = self.processor
            loader = AutoModelForCausalLM
        self.model = (
            loader.from_pretrained(
                checkpoint,
                dtype=torch.bfloat16,
                device_map={"": "cuda:0"},
                attn_implementation="sdpa",
                local_files_only=True,
            )
            .eval()
            .requires_grad_(False)
        )

    def inputs(self, body):
        kwargs = {"enable_thinking": False} if self.name == "gemma" else {}
        return self.processor.apply_chat_template(
            body["messages"],
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            **kwargs,
        )

    def token_count(self, body):
        if self.name == "pplx-flash":
            return sum(
                chunk.length for chunk in self.model.encoder.plan(body, MAX_CONTEXT)
            )
        length = self.inputs(body)["input_ids"].shape[-1]
        if length + MAX_OUTPUT > MAX_CONTEXT:
            raise ValueError(
                f"Request needs {length} input tokens plus {MAX_OUTPUT} output tokens"
            )
        return length

    def predict(self, body):
        with self.torch.inference_mode():
            if self.name == "pplx-flash":
                return self.model.decide(body)
            inputs = {
                key: value.to("cuda:0") for key, value in self.inputs(body).items()
            }
            pad_id = self.model.generation_config.pad_token_id
            if pad_id is None:
                pad_id = self.tokenizer.eos_token_id
            constraints = {}
            if self.name == "llama":
                constraints["prefix_allowed_tokens_fn"] = self.answer_constraint(
                    inputs["input_ids"].shape[-1]
                )
            output = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=MAX_OUTPUT,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=pad_id,
                **constraints,
            )
            tokens = output[0, inputs["input_ids"].shape[-1] :].tolist()
            raw = self.tokenizer.decode(tokens, skip_special_tokens=False)
            eos_ids = self.model.generation_config.eos_token_id
            if isinstance(eos_ids, int):
                eos_ids = [eos_ids]
            response = {
                "raw_text": raw,
                "token_ids": tokens,
                "finish_reason": (
                    "stop" if tokens and tokens[-1] in eos_ids else "length"
                ),
                "usage": {
                    "input_tokens": inputs["input_ids"].shape[-1],
                    "output_tokens": len(tokens),
                },
            }
            if self.name == "gemma":
                prefix = self.tokenizer.decode(
                    inputs["input_ids"][0], skip_special_tokens=False
                )
                response["parsed_message"] = self.processor.parse_response(
                    raw, prefix=prefix
                )
                response["content"] = response["parsed_message"]["content"]
            else:
                response["content"] = self.tokenizer.decode(
                    tokens, skip_special_tokens=True
                )
            return response

    def answer_constraint(self, input_length):
        answers = [
            self.tokenizer.encode(text, add_special_tokens=False)
            for text in LLAMA_ANSWERS
        ]
        eos_ids = self.model.generation_config.eos_token_id
        if isinstance(eos_ids, int):
            eos_ids = [eos_ids]

        def allowed_tokens(batch_id, input_ids):
            prefix = input_ids[input_length:].tolist()
            allowed = set()
            for answer in answers:
                if answer[: len(prefix)] == prefix:
                    if len(prefix) == len(answer):
                        allowed.update(eos_ids)
                    else:
                        allowed.add(answer[len(prefix)])
            if not allowed:
                raise ValueError(f"Unexpected binary answer prefix {prefix}")
            return sorted(allowed)

        return allowed_tokens
