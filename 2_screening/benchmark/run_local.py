"""Run the pinned local servers and development requests on the approved GPU server."""

import argparse
import tempfile
import hashlib
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from run_development import development_records

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--server-home", type=Path, default=Path.home() / "hpc-screening-benchmark"
)
parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
parser.add_argument(
    "--execute", action="store_true", help="Start servers and send development requests"
)
args = parser.parse_args()
if not args.execute:
    parser.error("Pass --execute to run inference during an approved time slot")
folder = Path(__file__).resolve().parent
root = args.server_home
results = folder / "results"
results.mkdir(exist_ok=True)
summary_path = results / f"local-development-{args.date}-summary.json"
for target in [
    summary_path,
    *(
        results / f"{name}-development-{args.date}.jsonl"
        for name in ("kev-4b", "kev-9b", "qwen")
    ),
]:
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {target}")
inputs = {
    "record_ids": [row["record_id"] for row in development_records()],
    "prompt_sha256": hashlib.sha256(
        (folder / "prompt.txt").read_text().strip().encode()
    ).hexdigest(),
}
summary = {"inputs": inputs, "runs": {}}
models = json.loads((root / "model-downloads.json").read_text())
assert [m["revision"] for m in models] == [
    "6cfce5c2fa4b4bd64026336ab649c5ca78857d52",
    "db029f08b290afd9fee4aa4bbcd9ae48602d1eb0",
    "b968826d9c46dd6066d109eabc6255188de91218",
]
server_commit = subprocess.check_output(
    ["git", "-C", str(root / "kev-src"), "rev-parse", "HEAD"], text=True
).strip()
assert server_commit == "1f04cfa28e6a708485b28a9585010b9e436b776e"
for index, model in enumerate(models):
    qwen = index == 2
    name = "qwen" if qwen else f"kev-{4 if index==0 else 9}b"
    port = 8000 if qwen else 8009 + index
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    env = dict(
        os.environ,
        CUDA_VISIBLE_DEVICES="0",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="4",
        KEV_TRUNCATE_STATES="0",
        KEV_FUSED="0",
        KEV_CUDA_GRAPHS="0",
    )
    if qwen:
        command = [
            str(root / "qwen-env/bin/vllm"),
            "serve",
            model["path"],
            "--served-model-name",
            model["repo"],
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--dtype",
            "bfloat16",
            "--max-model-len",
            "8192",
            "--max-num-seqs",
            "1",
            "--gpu-memory-utilization",
            "0.70",
        ]
        revision = f"model={model['revision']}; vllm=0.10.2; transformers=4.55.2; torch=2.8.0+cu128"
    else:
        command = [
            str(root / "kev-env/bin/python"),
            "-m",
            "kev.serve",
            "--run",
            model["path"],
            "--device",
            "cuda",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        revision = f"model={model['revision']}; base={model['base_revision']}; server={server_commit}"
    runner = [
        "python3",
        str(folder / "run_development.py"),
        "--model",
        name,
        "--execute",
        "--revision",
        revision,
        "--output",
        str(results / f"{name}-development-{args.date}.jsonl"),
    ]
    metadata = dict(
        model=model,
        server_command=command,
        runner_command=runner,
        environment={
            k: env[k]
            for k in (
                "CUDA_VISIBLE_DEVICES",
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "OMP_NUM_THREADS",
                "KEV_TRUNCATE_STATES",
                "KEV_FUSED",
                "KEV_CUDA_GRAPHS",
            )
        },
        gpu_uuid="GPU-232102f9-4532-ed4b-ea90-14f69694cf48",
        concurrency=1,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    print("START", name, flush=True)
    started = time.monotonic()
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(
            command,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited: {process.returncode}")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/v1/models", timeout=2
                    ) as response:
                        metadata["server_models"] = json.load(response)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() - started > 900:
                        raise TimeoutError(name)
                    time.sleep(2)
            metadata["startup_seconds"] = time.monotonic() - started
            run_started = time.monotonic()
            subprocess.run(runner, check=True, env=env)
            metadata["run_seconds"] = time.monotonic() - run_started
            rows = [
                json.loads(line)
                for line in (results / f"{name}-development-{args.date}.jsonl")
                .read_text()
                .splitlines()
            ]
            assert len(rows) == 119 and {str(r["record_id"]) for r in rows} == {
                str(i) for i in inputs["record_ids"]
            }
            assert all(r["prompt_sha256"] == inputs["prompt_sha256"] for r in rows)
            metadata["ok"] = sum(r["status"] == "ok" for r in rows)
            metadata["errors"] = sum(r["status"] != "ok" for r in rows)
            metadata["request_seconds"] = sum(r["seconds"] for r in rows)
            print(
                "DONE",
                name,
                "ok",
                metadata["ok"],
                "errors",
                metadata["errors"],
                "run_seconds",
                metadata["run_seconds"],
                flush=True,
            )
        except BaseException:
            log.seek(0)
            print(log.read(), flush=True)
            raise
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            metadata["server_lifetime_seconds"] = time.monotonic() - started
            summary["runs"][name] = metadata
            summary_path.write_text(json.dumps(summary, indent=2) + "\n")
            print("STOP", name, flush=True)
