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


def test_cli_accepts_dry_run_flag():
    args = screening.parse_args(
        ["--input", "papers.csv", "--model", "gpt-5-mini", "--batch-id", "batch-123", "--papers-per-batch", "10", "--dry-run"]
    )

    assert args.dry_run is True


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
        rows=rows,
        papers_per_batch=25,
    )

    assert state["metadata"]["batch_id"] == "batch-123"
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
            "input_file": "papers.csv",
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
        rows=rows,
        papers_per_batch=25,
    )

    assert state["metadata"]["papers_per_batch"] == 25
    assert state["metadata"]["total_papers"] == 1
    assert_has_timestamp(state["metadata"]["started_at"])
    assert_has_timestamp(state["metadata"]["updated_at"])


def test_build_batch_requests_only_for_non_prefiltered_papers(tmp_path):
    rows = [
        {"id": "1", "title": "", "abstract": "Paper abstract"},
        {"id": "2", "title": "HPC sustainability", "abstract": "Lifecycle carbon assessment of HPC systems."},
    ]
    state = screening.build_state(
        batch_id="batch-123",
        input_path=tmp_path / "papers.csv",
        model="gpt-5-mini",
        rows=rows,
        papers_per_batch=25,
    )

    requests = screening.build_batch_requests(rows=rows, state=state, model="gpt-5-mini")

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


def test_render_dashboard_includes_operational_details():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "model": "gpt-5-mini",
            "submitted_count": 2,
            "prefiltered_count": 1,
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
    assert "Polling remote batch" in output
    assert "2026-04-12 10:00 UTC" in output
    assert "(5m ago)" in output


def test_render_dashboard_includes_dry_run_status():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "provider": "openai",
            "dry_run": True,
            "model": "gpt-5-mini",
            "submitted_count": 0,
            "prefiltered_count": 0,
            "current_batch_size": 0,
            "total_papers": 1,
            "started_at": "2026-04-12T10:00:00Z",
            "updated_at": "2026-04-12T10:05:00Z",
        },
        "papers": {},
    }
    console = screening.make_console(io.StringIO())

    console.print(screening.render_dashboard(state, "Dry run: completing simulated batch"))
    output = console.file.getvalue()

    assert "Dry run" in output
    assert "yes" in output


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
        def __init__(self):
            self.submitted = None
            self.get_batch_calls = []

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
        "source": "openai_batch",
        "decision": "include",
        "reason": ["IC1"],
    }


def test_run_once_submits_next_chunk_after_completed_batch(tmp_path):
    class Client:
        def __init__(self):
            self.submitted = None

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
        "source": "openai_batch",
        "decision": "include",
        "reason": ["IC1"],
    }
    assert [request["custom_id"] for request in client.submitted["requests"]] == ["3"]


def test_run_processes_all_chunks_and_renders_rich_output(tmp_path):
    class Client:
        def __init__(self):
            self.submissions = []
            self.downloads = []

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
    assert sleeps == [30, 30]
    assert [request["custom_id"] for request in client.submissions[0]["requests"]] == ["1"]
    assert [request["custom_id"] for request in client.submissions[1]["requests"]] == ["2"]
    assert client.downloads == ["batch-1", "batch-2"]
    output = stdout.getvalue()
    assert "Current action" in output
    assert "Waiting 30s before polling remote batch" in output
    assert "Screening Complete" in output


def test_run_dry_run_processes_all_chunks_without_api_calls(tmp_path):
    class Client:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected API access during dry run: {name}")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n"
        "2,HPC water footprint,Water use in supercomputing facilities.\n",
        encoding="utf-8",
    )
    sleeps = []
    stdout = io.StringIO()

    result = screening.run(
        [
            "--input",
            str(csv_path),
            "--model",
            "gpt-5-mini",
            "--batch-id",
            "dry-run-batch",
            "--papers-per-batch",
            "1",
            "--dry-run",
        ],
        client=Client(),
        workdir=tmp_path,
        sleeper=sleeps.append,
        stdout=stdout,
    )

    assert result["metadata"]["status"] == "done"
    assert result["metadata"]["dry_run"] is True
    assert result["metadata"]["submitted_count"] == 2
    assert result["metadata"]["current_batch_size"] == 0
    assert sleeps == []
    assert result["papers"]["1"] == {
        "source": "dry_run",
        "decision": "include",
        "reason": ["doubt"],
    }
    assert result["papers"]["2"] == {
        "source": "dry_run",
        "decision": "include",
        "reason": ["doubt"],
    }
    output = stdout.getvalue()
    assert "Dry run: completing simulated batch" in output
    assert "Screening Complete" in output


def test_run_displays_dry_run_for_existing_done_state(tmp_path):
    class Client:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected API access: {name}")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "testing.json"
    state_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "batch_id": "testing",
                    "status": "done",
                    "provider": "openai",
                    "dry_run": False,
                    "model": "gpt-5-mini",
                    "seed": screening.SEED,
                    "input_file": str(csv_path),
                    "submitted_count": 1,
                    "prefiltered_count": 0,
                    "papers_per_batch": 500,
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
    stdout = io.StringIO()

    result = screening.run(
        [
            "--input",
            str(csv_path),
            "--model",
            "gpt-5-mini",
            "--batch-id",
            "testing",
            "--papers-per-batch",
            "500",
            "--dry-run",
        ],
        client=Client(),
        workdir=tmp_path,
        stdout=stdout,
    )

    assert result["metadata"]["dry_run"] is False
    output = stdout.getvalue()
    assert "Dry run yes" in output
    assert "Dry run: yes" in output


def test_run_stops_after_failed_chunk_and_renders_failure(tmp_path):
    class Client:
        def __init__(self):
            self.submissions = []

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
