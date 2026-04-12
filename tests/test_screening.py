import io
import json
from datetime import datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import screening


def assert_has_timestamp(value: str) -> None:
    assert isinstance(value, str)
    assert value.endswith("Z")
    assert "T" in value


def waiting_metadata(csv_path: Path, **overrides):
    metadata = {
        "batch_id": "batch-123",
        "status": "waiting batch",
        "provider": "openai",
        "model": "gpt-5-mini",
        "seed": screening.SEED,
        "input_file": str(csv_path),
        "submitted_count": 1,
        "prefiltered_count": 0,
        "papers_per_batch": 25,
        "total_papers": 1,
        "current_batch_size": 1,
        "remote_batch_id": "batch-123",
        "started_at": "2026-04-12T10:00:00Z",
        "updated_at": "2026-04-12T10:00:00Z",
        "current_batch_submitted_at": "2026-04-12T10:00:00Z",
    }
    metadata.update(overrides)
    return metadata


def test_cli_requires_input_model_and_batch_id():
    with pytest.raises(SystemExit):
        screening.parse_args([])


def test_cli_requires_papers_per_batch():
    with pytest.raises(SystemExit):
        screening.parse_args(["--input", "papers.csv", "--model", "gpt-5-mini", "--batch-id", "batch-123"])


def test_cli_rejects_non_positive_papers_per_batch():
    with pytest.raises(SystemExit):
        screening.parse_args(
            ["--input", "papers.csv", "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "0"]
        )


def test_cli_rejects_non_positive_poll_interval():
    with pytest.raises(SystemExit):
        screening.parse_args(
            [
                "--input",
                "papers.csv",
                "--model",
                "gpt-5-mini",
                "--batch-id",
                "batch-123",
                "--papers-per-batch",
                "10",
                "--poll-interval-seconds",
                "0",
            ]
        )


def test_cli_rejects_removed_dry_run_flag():
    with pytest.raises(SystemExit):
        screening.parse_args(
            ["--input", "papers.csv", "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "10", "--dry-run"]
        )


def test_cli_accepts_provider_and_defaults_to_openai():
    default_args = screening.parse_args(
        ["--input", "papers.csv", "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "10"]
    )
    explicit_args = screening.parse_args(
        [
            "--input",
            "papers.csv",
            "--model",
            "gpt-5-mini",
            "--batch-id",
            "batch-123",
            "--papers-per-batch",
            "10",
            "--provider",
            "gemini",
        ]
    )

    assert default_args.provider == "openai"
    assert explicit_args.provider == "gemini"


def test_load_rows_with_id_title_and_abstract(tmp_path):
    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")

    rows = screening.load_rows(csv_path)

    assert rows == [{"id": "1", "title": "Paper title", "abstract": "Paper abstract"}]


def test_load_rows_requires_id_title_and_abstract_columns(tmp_path):
    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title\n1,Paper title\n", encoding="utf-8")

    with pytest.raises(ValueError, match="id,title,abstract"):
        screening.load_rows(csv_path)


def test_prefilter_missing_abstract_marks_missing_metadata():
    row = {"id": "1", "title": "Paper title", "abstract": ""}

    result = screening.prefilter_paper(row)

    assert result == {
        "source": "prefilter",
        "decision": "exclude",
        "reason": ["missing_metadata"],
    }


def test_prefilter_missing_title_marks_missing_metadata():
    row = {"id": "1", "title": "", "abstract": "Paper abstract"}

    result = screening.prefilter_paper(row)

    assert result == {
        "source": "prefilter",
        "decision": "exclude",
        "reason": ["missing_metadata"],
    }


def test_prefilter_hydroxypropyl_cellulose_papers_as_ec1():
    row = {
        "id": "1",
        "title": "Optical properties of HPC films",
        "abstract": "We evaluate hydroxypropyl cellulose films for sustainable materials.",
    }

    result = screening.prefilter_paper(row)

    assert result == {
        "source": "prefilter",
        "decision": "exclude",
        "reason": ["EC1"],
    }


def test_prefilter_concrete_materials_papers_as_ec1():
    row = {
        "id": "1",
        "title": "Durability assessment of high-performance concrete",
        "abstract": "This materials study evaluates sustainable concrete reinforced with waste fibers.",
    }

    result = screening.prefilter_paper(row)

    assert result == {
        "source": "prefilter",
        "decision": "exclude",
        "reason": ["EC1"],
    }


def test_build_state_includes_prefiltered_papers_and_timestamps(tmp_path):
    csv_path = tmp_path / "papers.csv"
    rows = [{"id": "1", "title": "", "abstract": "Paper abstract"}]

    state = screening.build_state(
        batch_id="batch-123",
        input_path=csv_path,
        model="gpt-5-mini",
        provider="openai",
        rows=rows,
        papers_per_batch=25,
    )

    assert state["metadata"]["batch_id"] == "batch-123"
    assert state["metadata"]["provider"] == "openai"
    assert state["metadata"]["prefiltered_count"] == 1
    assert state["metadata"]["current_batch_size"] == 0
    assert_has_timestamp(state["metadata"]["started_at"])
    assert_has_timestamp(state["metadata"]["updated_at"])
    assert state["papers"] == {
        "1": {
            "source": "prefilter",
            "decision": "exclude",
            "reason": ["missing_metadata"],
        }
    }


def test_load_or_create_state_adds_missing_timestamp_fields(tmp_path):
    state_path = tmp_path / "batch-123.json"
    rows = [{"id": "1", "title": "Paper title", "abstract": "Paper abstract"}]
    existing_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(tmp_path / "papers.csv"),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "papers_per_batch": 25,
            "total_papers": 1,
            "current_batch_size": 0,
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    state = screening.load_or_create_state(
        state_path=state_path,
        batch_id="batch-123",
        input_path=tmp_path / "papers.csv",
        model="gpt-5-mini",
        provider="openai",
        rows=rows,
        papers_per_batch=25,
    )

    assert state["metadata"]["papers_per_batch"] == 25
    assert state["metadata"]["total_papers"] == 1
    assert_has_timestamp(state["metadata"]["started_at"])
    assert_has_timestamp(state["metadata"]["updated_at"])
    assert state["metadata"]["provider"] == "openai"

def test_load_or_create_state_defaults_legacy_provider_to_openai(tmp_path):
    state_path = tmp_path / "batch-123.json"
    rows = [{"id": "1", "title": "Paper title", "abstract": "Paper abstract"}]
    existing_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(tmp_path / "papers.csv"),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "papers_per_batch": 25,
            "total_papers": 1,
            "current_batch_size": 0,
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    state = screening.load_or_create_state(
        state_path=state_path,
        batch_id="batch-123",
        input_path=tmp_path / "papers.csv",
        model="gpt-5-mini",
        provider="openai",
        rows=rows,
        papers_per_batch=25,
    )

    assert state["metadata"]["provider"] == "openai"


def test_load_or_create_state_rejects_resume_provider_mismatch(tmp_path):
    state_path = tmp_path / "batch-123.json"
    rows = [{"id": "1", "title": "Paper title", "abstract": "Paper abstract"}]
    existing_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(tmp_path / "papers.csv"),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "papers_per_batch": 25,
            "total_papers": 1,
            "current_batch_size": 0,
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    with pytest.raises(ValueError, match="provider"):
        screening.load_or_create_state(
            state_path=state_path,
            batch_id="batch-123",
            input_path=tmp_path / "papers.csv",
            model="gpt-5-mini",
            provider="anthropic",
            rows=rows,
            papers_per_batch=25,
        )


def test_load_or_create_state_rejects_legacy_dry_run_state(tmp_path):
    state_path = tmp_path / "batch-123.json"
    rows = [{"id": "1", "title": "Paper title", "abstract": "Paper abstract"}]
    existing_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "dry_run": True,
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(tmp_path / "papers.csv"),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "papers_per_batch": 25,
            "total_papers": 1,
            "current_batch_size": 0,
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    with pytest.raises(ValueError, match="dry-run"):
        screening.load_or_create_state(
            state_path=state_path,
            batch_id="batch-123",
            input_path=tmp_path / "papers.csv",
            model="gpt-5-mini",
            provider="openai",
            rows=rows,
            papers_per_batch=25,
        )


def test_batch_clients_expose_source_names():
    assert screening.OpenAIBatchClient.source_name == "openai_batch"
    assert screening.AnthropicBatchClient.source_name == "anthropic_batch"
    assert screening.GeminiBatchClient.source_name == "gemini_batch"


def test_openai_batch_client_build_requests_matches_current_format(tmp_path):
    rows = [
        {"id": "1", "title": "", "abstract": "Paper abstract"},
        {"id": "2", "title": "HPC sustainability", "abstract": "Lifecycle carbon assessment of HPC systems."},
    ]
    state = screening.build_state(
        batch_id="batch-123",
        input_path=tmp_path / "papers.csv",
        model="gpt-5-mini",
        provider="openai",
        rows=rows,
        papers_per_batch=25,
    )

    requests = screening.OpenAIBatchClient(client=object()).build_requests(
        rows=screening.pending_rows(rows, state),
        model="gpt-5-mini",
    )

    assert requests == [
        {
            "custom_id": "2",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": "gpt-5-mini",
                "temperature": 0,
                "max_output_tokens": screening.MAX_OUTPUT_TOKENS,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "screening_decision",
                        "schema": screening.RESPONSE_SCHEMA,
                        "strict": True,
                    }
                },
                "input": screening.build_prompt(rows[1]),
                "reasoning": {"effort": "none"},
            },
        }
    ]


def test_anthropic_batch_client_build_requests_uses_messages_batch_shape():
    rows = [{"id": "2", "title": "HPC sustainability", "abstract": "Lifecycle carbon assessment of HPC systems."}]

    requests = screening.AnthropicBatchClient(client=object()).build_requests(rows=rows, model="claude-sonnet-4")

    assert requests == [
        {
            "custom_id": "2",
            "params": {
                "model": "claude-sonnet-4",
                "max_tokens": screening.MAX_OUTPUT_TOKENS,
                "messages": [{"role": "user", "content": screening.build_prompt(rows[0])}],
            },
        }
    ]


def test_anthropic_batch_client_get_batch_normalizes_counts_and_status():
    class Counts:
        def __init__(self):
            self.processing = 1
            self.succeeded = 2
            self.errored = 3
            self.expired = 4
            self.canceled = 5

    class Batch:
        def __init__(self):
            self.id = "remote-123"
            self.processing_status = "ended"
            self.request_counts = Counts()
            self.results_url = "results://remote-123"

    class Batches:
        def retrieve(self, batch_id):
            assert batch_id == "remote-123"
            return Batch()

    class Messages:
        def __init__(self):
            self.batches = Batches()

    client = screening.AnthropicBatchClient(client=type("StubClient", (), {"messages": Messages()})())

    batch = client.get_batch("remote-123")

    assert batch == {
        "id": "remote-123",
        "status": "completed",
        "output_file_id": "results://remote-123",
        "error_file_id": None,
        "request_counts": {"total": 15, "completed": 2, "failed": 12},
    }


def test_anthropic_batch_client_submit_batch_uses_messages_batches_api():
    class Counts:
        def __init__(self):
            self.processing = 0
            self.succeeded = 1
            self.errored = 0
            self.expired = 0
            self.canceled = 0

    class Batch:
        def __init__(self):
            self.id = "remote-123"
            self.processing_status = "in_progress"
            self.request_counts = Counts()
            self.results_url = "results://remote-123"

    class Batches:
        def __init__(self):
            self.created = None

        def create(self, *, requests):
            self.created = requests
            return type("CreatedBatch", (), {"id": "remote-123"})()

        def retrieve(self, batch_id):
            assert batch_id == "remote-123"
            return Batch()

    batches = Batches()
    client = screening.AnthropicBatchClient(client=type("StubClient", (), {"messages": type("Messages", (), {"batches": batches})()})())

    batch = client.submit_batch(batch_id="local-123", requests=[{"custom_id": "paper-1", "params": {"model": "claude"}}])

    assert batches.created == [{"custom_id": "paper-1", "params": {"model": "claude"}}]
    assert batch["id"] == "remote-123"
    assert batch["status"] == "in_progress"


def test_anthropic_batch_client_download_output_extracts_text():
    class TextBlock:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    class Message:
        def __init__(self, text):
            self.content = [TextBlock(text)]

    class ResultPayload:
        def __init__(self, text):
            self.type = "succeeded"
            self.message = Message(text)

    class Result:
        def __init__(self, custom_id, text):
            self.custom_id = custom_id
            self.result = ResultPayload(text)

    class Batches:
        def results(self, batch_id):
            assert batch_id == "remote-123"
            return [Result("paper-1", "{\"decision\":\"include\",\"reason\":[\"IC1\"]}")]

    class Messages:
        def __init__(self):
            self.batches = Batches()

    client = screening.AnthropicBatchClient(client=type("StubClient", (), {"messages": Messages()})())

    outputs = client.download_output("remote-123")

    assert outputs == [{"custom_id": "paper-1", "output_text": "{\"decision\":\"include\",\"reason\":[\"IC1\"]}"}]


def test_gemini_batch_client_build_requests_creates_json_ready_records():
    rows = [{"id": "2", "title": "HPC sustainability", "abstract": "Lifecycle carbon assessment of HPC systems."}]

    requests = screening.GeminiBatchClient(client=object()).build_requests(rows=rows, model="gemini-2.5-pro")

    assert requests == [
        {
            "custom_id": "2",
            "model": "gemini-2.5-pro",
            "request": {
                "contents": [{"parts": [{"text": screening.build_prompt(rows[0])}]}],
                "generation_config": {
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_json_schema": screening.RESPONSE_SCHEMA,
                },
            },
        }
    ]


def test_gemini_batch_client_get_batch_normalizes_job_states():
    class State:
        def __init__(self, name):
            self.name = name

    class Dest:
        def __init__(self):
            self.file_name = "files/result.jsonl"

    class Batch:
        def __init__(self, state_name):
            self.name = "operations/123"
            self.state = State(state_name)
            self.dest = Dest()

    class Batches:
        def get(self, *, name):
            return Batch(name)

    client = screening.GeminiBatchClient(client=type("StubClient", (), {"batches": Batches()})())

    assert client.get_batch("JOB_STATE_SUCCEEDED")["status"] == "completed"
    assert client.get_batch("JOB_STATE_FAILED")["status"] == "failed"
    assert client.get_batch("JOB_STATE_CANCELLED")["status"] == "cancelled"
    assert client.get_batch("JOB_STATE_EXPIRED")["status"] == "expired"
    assert client.get_batch("JOB_STATE_RUNNING")["status"] == "in_progress"


def test_gemini_batch_client_submit_batch_uploads_jsonl_and_creates_batch():
    class UploadedFile:
        def __init__(self):
            self.name = "files/input.jsonl"

    class CreatedBatch:
        def __init__(self):
            self.name = "operations/123"

    class State:
        def __init__(self):
            self.name = "JOB_STATE_RUNNING"

    class Dest:
        def __init__(self):
            self.file_name = "files/output.jsonl"

    class Batch:
        def __init__(self):
            self.name = "operations/123"
            self.state = State()
            self.dest = Dest()

    class Files:
        def __init__(self):
            self.uploads = []
            self.upload_contents = []

        def upload(self, *, file, config):
            self.upload_contents.append(Path(file).read_text(encoding="utf-8"))
            self.uploads.append({"file": file, "config": config})
            return UploadedFile()

    class Batches:
        def __init__(self):
            self.created = []

        def create(self, *, model, src, config):
            self.created.append({"model": model, "src": src, "config": config})
            return CreatedBatch()

        def get(self, *, name):
            assert name == "operations/123"
            return Batch()

    files = Files()
    batches = Batches()
    client = screening.GeminiBatchClient(client=type("StubClient", (), {"files": files, "batches": batches})())
    requests = client.build_requests(
        rows=[{"id": "paper-1", "title": "Paper title", "abstract": "Paper abstract"}],
        model="gemini-2.5-pro",
    )

    batch = client.submit_batch(
        batch_id="local-123",
        requests=requests,
    )

    assert files.uploads[0]["config"]["mime_type"] == "jsonl"
    uploaded_line = json.loads(files.upload_contents[0].strip())
    assert uploaded_line["key"] == "paper-1"
    assert uploaded_line["request"]["generation_config"]["response_mime_type"] == "application/json"
    assert uploaded_line["request"]["generation_config"]["response_json_schema"] == screening.RESPONSE_SCHEMA
    assert batches.created == [
        {"model": "gemini-2.5-pro", "src": "files/input.jsonl", "config": {"display_name": "local-123"}}
    ]
    assert batch["id"] == "operations/123"
    assert batch["status"] == "in_progress"


def test_gemini_batch_client_download_output_parses_jsonl_and_raises_on_record_errors():
    class State:
        def __init__(self, name):
            self.name = name

    class Dest:
        def __init__(self):
            self.file_name = "files/result.jsonl"

    class Batch:
        def __init__(self):
            self.name = "operations/123"
            self.state = State("JOB_STATE_SUCCEEDED")
            self.dest = Dest()

    class Batches:
        def get(self, *, name):
            assert name == "operations/123"
            return Batch()

    class Files:
        def download(self, name):
            assert name == "files/result.jsonl"
            return "\n".join(
                [
                    json.dumps(
                        {
                            "key": "paper-1",
                            "response": {
                                "candidates": [
                                    {
                                        "content": {
                                            "parts": [{"text": "{\"decision\":\"include\",\"reason\":[\"IC1\"]}"}]
                                        }
                                    }
                                ]
                            },
                        }
                    ),
                    json.dumps({"key": "paper-2", "error": {"message": "request failed"}}),
                ]
            ).encode("utf-8")

    client = screening.GeminiBatchClient(client=type("StubClient", (), {"batches": Batches(), "files": Files()})())

    with pytest.raises(screening.BatchOutputDownloadError, match="paper-2"):
        client.download_output("operations/123")


def test_run_once_uses_provider_to_build_default_client_and_state(tmp_path, monkeypatch):
    class Client:
        source_name = "gemini_batch"

        def build_requests(self, *, rows, model):
            return [{"custom_id": row["id"], "model": model} for row in rows]

        def get_batch(self, batch_id):
            return None

        def submit_batch(self, *, batch_id, requests):
            return {"id": "remote-123", "status": "in_progress", "output_file_id": None, "error_file_id": None, "request_counts": None}

        def download_output(self, batch_id):
            raise AssertionError("download_output should not be called")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    created = []

    def fake_build_batch_client(provider):
        created.append(provider)
        return Client()

    monkeypatch.setattr(screening, "build_batch_client", fake_build_batch_client)

    result = screening.run_once(
        args=screening.parse_args(
            [
                "--input",
                str(csv_path),
                "--model",
                "gemini-2.5-pro",
                "--batch-id",
                "batch-123",
                "--papers-per-batch",
                "1",
                "--provider",
                "gemini",
            ]
        ),
        workdir=tmp_path,
    )

    assert created == ["gemini"]
    assert result["metadata"]["provider"] == "gemini"
    assert result["metadata"]["remote_batch_id"] == "remote-123"


def test_derive_progress_reports_operational_counts():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "submitted_count": 2,
            "prefiltered_count": 1,
            "current_batch_size": 2,
            "total_papers": 10,
        },
        "papers": {
            "1": {"source": "prefilter", "decision": "exclude", "reason": ["EC1"]},
            "2": {"source": "openai_batch", "decision": "include", "reason": ["IC1"]},
        },
    }

    progress = screening.derive_progress(state)

    assert progress == {
        "total_papers": 10,
        "completed": 2,
        "included": 1,
        "excluded": 1,
        "prefiltered": 1,
        "current_batch_size": 2,
        "remaining": 6,
        "submitted": 2,
    }


def test_format_timestamp_humanizes_recent_times():
    formatted = screening.format_timestamp(
        "2026-04-12T10:03:00Z",
        now=datetime.fromisoformat("2026-04-12T10:05:30+00:00"),
    )

    assert formatted == "2026-04-12 10:03 UTC (2m ago)"


def test_format_timestamp_humanizes_missing_values():
    assert screening.format_timestamp(None) == "-"


def test_make_console_detects_terminal_streams():
    class TerminalStream(io.StringIO):
        def isatty(self):
            return True

    terminal_console = screening.make_console(TerminalStream())
    file_console = screening.make_console(io.StringIO())

    assert terminal_console.is_terminal is True
    assert file_console.is_terminal is False


def test_render_dashboard_includes_operational_details():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "model": "gpt-5-mini",
            "submitted_count": 2,
            "prefiltered_count": 1,
            "papers_per_batch": 25,
            "current_batch_size": 2,
            "total_papers": 10,
            "remote_batch_id": "batch_remote_123",
            "started_at": "2026-04-12T10:00:00Z",
            "updated_at": "2026-04-12T10:05:00Z",
            "current_batch_submitted_at": "2026-04-12T10:03:00Z",
        },
        "papers": {
            "1": {"source": "prefilter", "decision": "exclude", "reason": ["EC1"]},
            "2": {"source": "openai_batch", "decision": "include", "reason": ["IC1"]},
        },
    }
    console = screening.make_console(io.StringIO())

    console.print(
        screening.render_dashboard(
            state,
            "Polling remote batch",
            now=datetime.fromisoformat("2026-04-12T10:05:30+00:00"),
        )
    )
    output = console.file.getvalue()

    assert "Local batch" in output
    assert "testing" in output
    assert "batch_remote_123" in output
    assert "Remaining" in output
    assert "Configured batch size" in output
    assert "25" in output
    assert "Polling remote batch" in output
    assert "2026-04-12 10:00 UTC" in output
    assert "(5m ago)" in output


def test_render_dashboard_shows_configured_batch_size_when_it_differs_from_current_batch():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "submitted_count": 50,
            "prefiltered_count": 326,
            "papers_per_batch": 10,
            "current_batch_size": 50,
            "total_papers": 3795,
            "remote_batch_id": "batches/123",
            "started_at": "2026-04-12T10:00:00Z",
            "updated_at": "2026-04-12T10:05:00Z",
            "current_batch_submitted_at": "2026-04-12T10:03:00Z",
        },
        "papers": {str(index): {"source": "prefilter", "decision": "exclude", "reason": ["EC1"]} for index in range(326)},
    }
    console = screening.make_console(io.StringIO())

    console.print(screening.render_dashboard(state, "Waiting 30s before polling remote batch"))
    output = console.file.getvalue()

    assert "Current batch" in output
    assert "50" in output
    assert "Configured batch size" in output
    assert "10" in output


def test_parse_output_text_rejects_invalid_reason_codes():
    with pytest.raises(ValueError, match="Invalid reason"):
        screening.parse_output_text(json.dumps({"decision": "include", "reason": ["IC9"]}))


def test_parse_output_text_accepts_doubt_for_includes():
    result = screening.parse_output_text(json.dumps({"decision": "include", "reason": ["doubt"]}))

    assert result == {"decision": "include", "reason": ["doubt"]}


def test_build_prompt_includes_selection_criteria():
    prompt = screening.build_prompt(
        {
            "id": "1",
            "title": "HPC sustainability",
            "abstract": "Lifecycle carbon assessment of HPC systems.",
        }
    )

    assert "Include if ANY of the following apply:" in prompt
    assert "IC1: The paper addresses at least one environmental impact in the HPC context" in prompt
    assert "IC2: The paper presents methodologies for predicting or measuring the environmental impacts of HPC systems" in prompt
    assert "Exclude if ANY of the following apply:" in prompt
    assert "EC2: The paper focuses solely on energy consumption" in prompt


def test_run_once_exits_without_api_calls_when_state_is_done(tmp_path):
    class Client:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected API access: {name}")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "batch_id": "batch-123",
                    "status": "done",
                    "provider": "openai",
                    "model": "gpt-5-mini",
                    "seed": screening.SEED,
                    "input_file": str(csv_path),
                    "submitted_count": 1,
                    "prefiltered_count": 0,
                    "papers_per_batch": 25,
                    "total_papers": 1,
                    "current_batch_size": 0,
                    "started_at": "2026-04-12T10:00:00Z",
                    "updated_at": "2026-04-12T10:00:00Z",
                },
                "papers": {"1": {"source": "openai_batch", "decision": "include", "reason": ["IC1"]}},
            }
        ),
        encoding="utf-8",
    )

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "25"]
        ),
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "done"


def test_run_once_submits_batch_and_writes_waiting_state(tmp_path):
    class Client:
        source_name = "openai_batch"

        def __init__(self):
            self.submitted = None
            self.get_batch_calls = []

        def build_requests(self, *, rows, model):
            return [{"custom_id": row["id"], "model": model} for row in rows]

        def get_batch(self, batch_id):
            self.get_batch_calls.append(batch_id)
            return None

        def submit_batch(self, *, batch_id, requests):
            self.submitted = {"batch_id": batch_id, "requests": requests}
            return {"id": "batch_remote_123", "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,,Paper abstract\n"
        "2,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n",
        encoding="utf-8",
    )
    client = Client()

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "1"]
        ),
        client=client,
        workdir=tmp_path,
    )

    assert client.get_batch_calls == []
    assert client.submitted["batch_id"] == "batch-123"
    assert [request["custom_id"] for request in client.submitted["requests"]] == ["2"]
    assert result["metadata"]["status"] == "waiting batch"
    assert result["metadata"]["remote_batch_id"] == "batch_remote_123"
    assert result["metadata"]["submitted_count"] == 1
    assert result["metadata"]["current_batch_size"] == 1
    assert_has_timestamp(result["metadata"]["current_batch_submitted_at"])


def test_run_once_keeps_waiting_state_while_remote_batch_is_running(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(json.dumps({"metadata": waiting_metadata(csv_path), "papers": {}}), encoding="utf-8")

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "25"]
        ),
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "waiting batch"
    assert result["metadata"]["current_batch_size"] == 1


def test_run_once_merges_completed_batch_outputs_and_marks_done(tmp_path):
    class Client:
        source_name = "anthropic_batch"

        def build_requests(self, *, rows, model):
            raise AssertionError("build_requests should not be called")

        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "completed"}

        def submit_batch(self, *, batch_id, requests):
            raise AssertionError("submit_batch should not be called")

        def download_output(self, batch_id):
            assert batch_id == "batch-123"
            return [{"custom_id": "2", "output_text": json.dumps({"decision": "include", "reason": ["IC1"]})}]

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,,Paper abstract\n"
        "2,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(
        json.dumps(
            {
                "metadata": waiting_metadata(
                    csv_path,
                    prefiltered_count=1,
                    total_papers=2,
                    current_batch_size=1,
                ),
                "papers": {
                    "1": {
                        "source": "prefilter",
                        "decision": "exclude",
                        "reason": ["missing_metadata"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "25"]
        ),
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "done"
    assert result["metadata"]["current_batch_size"] == 0
    assert "remote_batch_id" not in result["metadata"]
    assert result["papers"]["2"] == {
        "source": "anthropic_batch",
        "decision": "include",
        "reason": ["IC1"],
    }


def test_run_once_submits_next_chunk_after_completed_batch(tmp_path):
    class Client:
        source_name = "gemini_batch"

        def __init__(self):
            self.submitted = None

        def build_requests(self, *, rows, model):
            return [{"custom_id": row["id"], "model": model} for row in rows]

        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "completed"}

        def download_output(self, batch_id):
            assert batch_id == "batch-123"
            return [{"custom_id": "2", "output_text": json.dumps({"decision": "include", "reason": ["IC1"]})}]

        def submit_batch(self, *, batch_id, requests):
            self.submitted = {"batch_id": batch_id, "requests": requests}
            return {"id": "batch-456", "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,,Paper abstract\n"
        "2,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n"
        "3,HPC water footprint,Water use in supercomputing facilities.\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(
        json.dumps(
            {
                "metadata": waiting_metadata(
                    csv_path,
                    prefiltered_count=1,
                    papers_per_batch=1,
                    total_papers=3,
                    current_batch_size=1,
                ),
                "papers": {
                    "1": {
                        "source": "prefilter",
                        "decision": "exclude",
                        "reason": ["missing_metadata"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    client = Client()
    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "1"]
        ),
        client=client,
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "waiting batch"
    assert result["metadata"]["remote_batch_id"] == "batch-456"
    assert result["metadata"]["submitted_count"] == 2
    assert result["metadata"]["current_batch_size"] == 1
    assert result["papers"]["2"] == {
        "source": "gemini_batch",
        "decision": "include",
        "reason": ["IC1"],
    }
    assert [request["custom_id"] for request in client.submitted["requests"]] == ["3"]


def test_run_processes_all_chunks_and_renders_rich_output(tmp_path):
    class Client:
        source_name = "anthropic_batch"

        def __init__(self):
            self.submissions = []
            self.downloads = []

        def build_requests(self, *, rows, model):
            return [{"custom_id": row["id"], "model": model} for row in rows]

        def get_batch(self, batch_id):
            if batch_id == "batch-1":
                return {"id": batch_id, "status": "completed"}
            if batch_id == "batch-2":
                return {"id": batch_id, "status": "completed"}
            raise AssertionError(f"unexpected batch lookup: {batch_id}")

        def submit_batch(self, *, batch_id, requests):
            self.submissions.append({"batch_id": batch_id, "requests": requests})
            if len(self.submissions) == 1:
                return {"id": "batch-1", "status": "in_progress"}
            if len(self.submissions) == 2:
                return {"id": "batch-2", "status": "in_progress"}
            raise AssertionError("submit_batch called too many times")

        def download_output(self, batch_id):
            self.downloads.append(batch_id)
            if batch_id == "batch-1":
                return [{"custom_id": "1", "output_text": json.dumps({"decision": "include", "reason": ["IC1"]})}]
            if batch_id == "batch-2":
                return [{"custom_id": "2", "output_text": json.dumps({"decision": "exclude", "reason": ["EC2"]})}]
            raise AssertionError(f"unexpected download: {batch_id}")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n"
        "2,HPC energy only,Energy efficiency in HPC scheduling.\n",
        encoding="utf-8",
    )
    sleeps = []
    stdout = io.StringIO()
    client = Client()

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "1"],
        client=client,
        workdir=tmp_path,
        sleeper=sleeps.append,
        stdout=stdout,
    )

    assert result["metadata"]["status"] == "done"
    assert result["metadata"]["submitted_count"] == 2
    assert result["metadata"]["current_batch_size"] == 0
    assert result["papers"]["1"]["decision"] == "include"
    assert result["papers"]["2"]["decision"] == "exclude"
    assert result["papers"]["1"]["source"] == "anthropic_batch"
    assert result["papers"]["2"]["source"] == "anthropic_batch"
    assert sleeps == [30, 30]
    assert [request["custom_id"] for request in client.submissions[0]["requests"]] == ["1"]
    assert [request["custom_id"] for request in client.submissions[1]["requests"]] == ["2"]
    assert client.downloads == ["batch-1", "batch-2"]
    output = stdout.getvalue()
    assert "Current action" in output
    assert "Waiting 30s before polling remote batch" in output
    assert "Screening Complete" in output




def test_run_stops_after_failed_chunk_and_renders_failure(tmp_path):
    class Client:
        source_name = "openai_batch"

        def __init__(self):
            self.submissions = []

        def build_requests(self, *, rows, model):
            return [{"custom_id": row["id"], "model": model} for row in rows]

        def get_batch(self, batch_id):
            if batch_id == "batch-1":
                return {"id": batch_id, "status": "failed"}
            raise AssertionError(f"unexpected batch lookup: {batch_id}")

        def submit_batch(self, *, batch_id, requests):
            self.submissions.append({"batch_id": batch_id, "requests": requests})
            return {"id": "batch-1", "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n"
        "2,HPC water footprint,Water use in supercomputing facilities.\n",
        encoding="utf-8",
    )
    sleeps = []
    stdout = io.StringIO()
    client = Client()

    result = screening.run(
        [
            "--input",
            str(csv_path),
            "--model",
            "gpt-5-mini",
            "--batch-id",
            "batch-123",
            "--papers-per-batch",
            "1",
            "--poll-interval-seconds",
            "7",
        ],
        client=client,
        workdir=tmp_path,
        sleeper=sleeps.append,
        stdout=stdout,
    )

    assert result["metadata"]["status"] == "failed"
    assert result["metadata"]["failure_message"] == "Batch batch-1 ended with status failed"
    assert result["metadata"]["submitted_count"] == 1
    assert sleeps == [7]
    output = stdout.getvalue()
    assert "Screening Stopped" in output
    assert "Batch batch-1 ended with status failed" in output


def test_run_once_marks_completed_batch_with_failed_requests_in_state(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {
                "id": batch_id,
                "status": "completed",
                "output_file_id": "file-out",
                "error_file_id": "file-err",
                "request_counts": {"total": 2, "completed": 1, "failed": 1},
            }

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(json.dumps({"metadata": waiting_metadata(csv_path), "papers": {}}), encoding="utf-8")

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "25"]
        ),
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "completed_with_failed_requests"
    assert result["metadata"]["failure_message"] == "Batch batch-123 completed with failed requests: 1"


def test_run_once_marks_cancelled_batch_with_partial_output_in_state(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {
                "id": batch_id,
                "status": "cancelled",
                "output_file_id": "file-out",
                "error_file_id": None,
                "request_counts": {"total": 2, "completed": 1, "failed": 0},
            }

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(json.dumps({"metadata": waiting_metadata(csv_path), "papers": {}}), encoding="utf-8")

    result = screening.run_once(
        args=screening.parse_args(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "25"]
        ),
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "cancelled_with_partial_output"
    assert result["metadata"]["failure_message"] == "Batch batch-123 was cancelled and has partial results available"
