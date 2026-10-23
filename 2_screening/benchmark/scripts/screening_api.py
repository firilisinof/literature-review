"""Provider request formats and strict binary response parsing."""

import json
import time
import urllib.error
import urllib.request

JSON = str | int | float | bool | None | list["JSON"] | dict[str, "JSON"]

MODELS = {
    "jev": ("jev-1.14.0", "https://api.typesafe.ai/v1/systemone", "TYPESAFE_API_KEY"),
    "decisions": (
        "gpt-6-luna",
        "https://api.openai.com/v1/decisions",
        "OPENAI_API_KEY",
    ),
    "kev-4b": ("kev-latest", "http://localhost:8009/v1/systemone", ""),
    "kev-9b": ("kev-latest", "http://localhost:8010/v1/systemone", ""),
    "qwen": ("Qwen/Qwen3-8B", "http://localhost:8000/v1/chat/completions", ""),
    "llama": ("meta-llama/Llama-3.1-8B-Instruct", "", ""),
    "gemma": ("google/gemma-4-12B-it", "", ""),
    "pplx-flash": ("perplexity-ai/pplx-decider-flash-v1.2", "", ""),
}
NATIVE_REVISIONS = {
    "llama": "0e9e39f249a16976918f6564b8830bc894c89659",
    "gemma": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
    "pplx-flash": "9ff7cf9838e59df461c276b7699d56b244d2af58",
}
MAX_CONTEXT = 8192
MAX_OUTPUT = 16
LLAMA_FILES = [
    "*.json",
    "*.safetensors",
    "*.jinja",
    "LICENSE",
    "README.md",
    "USE_POLICY.md",
]
LLAMA_ANSWERS = ["include", "exclude", "Include", "Exclude"]
OPTIONS = {
    "include": "At least one inclusion criterion applies and no exclusion criterion applies.",
    "exclude": "An exclusion criterion applies or the paper does not meet either inclusion criterion.",
}


REQUEST_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    OSError,
    ValueError,
    KeyError,
    IndexError,
    TypeError,
)


def request_body(model: str, paper: dict[str, str], prompt: str) -> dict[str, JSON]:
    """Build a provider request without human labels, e.g. request_body('jev', row, prompt)."""
    text = json.dumps(
        {"title": paper["title"], "abstract": paper["abstract"]}, ensure_ascii=False
    )
    if model in NATIVE_REVISIONS:
        return native_body(model, text, prompt)
    name = MODELS[model][0]
    if model == "decisions":
        return decisions_body(name, text, prompt)
    if model == "qwen":
        return qwen_body(name, text, prompt)
    question = {"type": "choice", "instructions": prompt, "criteria": OPTIONS}
    return {"model": name, "state": text, "questions": {"screening": question}}


def native_body(model: str, text: str, prompt: str) -> dict[str, JSON]:
    """Preserve each native model's recorded request format."""
    if model == "pplx-flash":
        return {
            "state": text,
            "questions": {
                "screening": {
                    "type": "choice",
                    "instructions": prompt,
                    "criteria": OPTIONS,
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


def native_settings(model: str) -> dict[str, JSON]:
    """Preserve the native model's recorded inference settings."""
    common = {
        "dtype": "bfloat16",
        "attention": "sdpa",
        "batch_size": 1,
        "max_context_tokens": MAX_CONTEXT,
        "truncation": False,
        "cpu_threads": 4,
    }
    if model == "pplx-flash":
        return {**common, "fast": False, "temperature": "checkpoint"}
    return {
        **common,
        "do_sample": False,
        "max_new_tokens": MAX_OUTPUT,
        **({"allowed_answers": LLAMA_ANSWERS} if model == "llama" else {}),
    }


def decisions_body(name: str, text: str, prompt: str) -> dict[str, JSON]:
    """Build the fixed Decisions question, e.g. decisions_body('gpt-6-luna', text, prompt)."""
    question = {
        "name": "screening",
        "type": "choice",
        "instructions": prompt,
        "choices": [
            {"value": key, "description": value} for key, value in OPTIONS.items()
        ],
    }
    return {"model": name, "input": text, "questions": [question]}


def qwen_body(name: str, text: str, prompt: str) -> dict[str, JSON]:
    """Keep Qwen's validated inference settings, e.g. qwen_body(name, text, prompt)."""
    return {
        "model": name,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 16,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def decision_from(model: str, response: dict[str, JSON]) -> str:
    """Accept only complete documented answers, e.g. decision_from('jev', response)."""
    if model in {"llama", "gemma"}:
        if response["finish_reason"] != "stop":
            raise ValueError(
                "Expected an EOS-terminated answer, got an output token limit"
            )
        choice = response["content"].strip().lower()
    elif model == "qwen":
        answer = response["choices"][0]
        if answer["finish_reason"] != "stop":
            raise ValueError(
                f"Qwen finish_reason={answer['finish_reason']!r}: expected stop"
            )
        choice = answer["message"]["content"].strip().lower()
    elif model == "decisions":
        answers = [row for row in response["answers"] if row.get("name") == "screening"]
        if len(answers) != 1 or answers[0].get("type") != "choice":
            raise ValueError("Expected one screening choice answer")
        choice = answers[0]["choice"]
    else:
        choice = response["answers"]["screening"]["choice"]
    if choice not in OPTIONS:
        raise ValueError(f"Decision {choice!r}: expected include or exclude")
    return choice


def send_request(url: str, body: dict[str, JSON], key: str) -> dict[str, JSON]:
    """Send once, without automatic retries, e.g. send_request(url, body, key)."""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        url, json.dumps(body).encode(), headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def run_one(model: str, url: str, body: dict[str, JSON], key: str) -> dict[str, JSON]:
    """Record technical failures without a screening label, e.g. run_one('jev', url, body, key)."""
    started = time.perf_counter()
    result = {"decision": None, "status": "error", "response": None}
    try:
        result["response"] = send_request(url, body, key)
        result["decision"] = decision_from(model, result["response"])
        result["status"] = "ok"
    except REQUEST_ERRORS as error:
        result["error"] = type(error).__name__
        if isinstance(error, urllib.error.HTTPError):
            result["http_status"] = error.code
    result["seconds"] = round(time.perf_counter() - started, 6)
    return result
