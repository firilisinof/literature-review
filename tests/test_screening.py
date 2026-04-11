import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import screening


def test_cli_requires_input_model_and_batch_id():
    with pytest.raises(SystemExit):
        screening.parse_args([])


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


def test_build_state_includes_prefiltered_papers(tmp_path):
    csv_path = tmp_path / "papers.csv"
    rows = [{"id": "1", "title": "", "abstract": "Paper abstract"}]

    state = screening.build_state(
        batch_id="batch-123",
        input_path=csv_path,
        model="gpt-5-mini",
        rows=rows,
    )

    assert state == {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(csv_path),
            "submitted_count": 0,
            "prefiltered_count": 1,
        },
        "papers": {
            "1": {
                "source": "prefilter",
                "decision": "exclude",
                "reason": ["missing_metadata"],
            }
        },
    }


def test_load_or_create_state_reuses_waiting_batch_file(tmp_path):
    state_path = tmp_path / "batch-123.json"
    existing_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": "papers.csv",
            "submitted_count": 1,
            "prefiltered_count": 1,
        },
        "papers": {"1": {"source": "prefilter", "decision": "exclude", "reason": ["EC1"]}},
    }
    state_path.write_text(json.dumps(existing_state), encoding="utf-8")

    state = screening.load_or_create_state(
        state_path=state_path,
        batch_id="batch-123",
        input_path=tmp_path / "papers.csv",
        model="gpt-5-mini",
        rows=[],
    )

    assert state == existing_state


def test_run_exits_without_api_calls_when_state_is_done(tmp_path):
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
                },
                "papers": {"1": {"source": "openai_batch", "decision": "include", "reason": ["IC1"]}},
            }
        ),
        encoding="utf-8",
    )

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "done"


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
    )

    requests = screening.build_batch_requests(rows=rows, state=state, model="gpt-5-mini")

    assert requests == [
        {
            "custom_id": "2",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": "gpt-5-mini",
                "seed": screening.SEED,
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


def test_format_state_summary_reports_counts():
    state = {
        "metadata": {
            "batch_id": "testing",
            "status": "waiting batch",
            "submitted_count": 2,
            "prefiltered_count": 1,
            "remote_batch_id": "batch_remote_123",
        },
        "papers": {
            "1": {"source": "prefilter", "decision": "exclude", "reason": ["EC1"]},
            "2": {"source": "openai_batch", "decision": "include", "reason": ["IC1"]},
        },
    }

    summary = screening.format_state_summary(state)

    assert summary == (
        "batch_id=testing status=waiting batch submitted=2 prefiltered=1 "
        "decisions=2 include=1 exclude=1 remote_batch_id=batch_remote_123"
    )


def test_run_submits_batch_and_writes_waiting_state(tmp_path):
    class Client:
        def __init__(self):
            self.submitted = None
            self.get_batch_calls = []

        def get_batch(self, batch_id):
            self.get_batch_calls.append(batch_id)
            return None

        def submit_batch(self, *, batch_id, requests):
            self.submitted = {"batch_id": batch_id, "requests": requests}
            return {"id": batch_id, "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,,Paper abstract\n"
        "2,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n",
        encoding="utf-8",
    )
    client = Client()

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
        client=client,
        workdir=tmp_path,
    )

    assert client.get_batch_calls == []
    assert client.submitted["batch_id"] == "batch-123"
    assert [request["custom_id"] for request in client.submitted["requests"]] == ["2"]
    assert result["metadata"]["status"] == "waiting batch"
    assert result["metadata"]["submitted_count"] == 1
    assert (tmp_path / "batch-123.json").exists()


def test_run_submits_new_batch_without_retrieving_local_batch_label(tmp_path):
    class Client:
        def __init__(self):
            self.get_batch_calls = []
            self.submitted = None

        def get_batch(self, batch_id):
            self.get_batch_calls.append(batch_id)
            return None

        def submit_batch(self, *, batch_id, requests):
            self.submitted = {"batch_id": batch_id, "requests": requests}
            return {"id": "batch_remote_123", "status": "in_progress"}

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text(
        "id,title,abstract\n"
        "1,HPC sustainability,Lifecycle carbon assessment of HPC systems.\n",
        encoding="utf-8",
    )
    client = Client()

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-nano", "--batch-id", "testing"],
        client=client,
        workdir=tmp_path,
    )

    assert client.get_batch_calls == []
    assert client.submitted == {
        "batch_id": "testing",
        "requests": screening.build_batch_requests(
            rows=[{"id": "1", "title": "HPC sustainability", "abstract": "Lifecycle carbon assessment of HPC systems."}],
            state=result,
            model="gpt-5-nano",
        ),
    }
    assert result["metadata"]["remote_batch_id"] == "batch_remote_123"


def test_run_keeps_waiting_state_while_remote_batch_is_running(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "in_progress"}

        def submit_batch(self, *, batch_id, requests):
            raise AssertionError("submit_batch should not be called")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    state_path.write_text(
        json.dumps(
                {
                    "metadata": {
                        "batch_id": "batch-123",
                        "status": "waiting batch",
                        "provider": "openai",
                        "model": "gpt-5-mini",
                        "seed": screening.SEED,
                        "input_file": str(csv_path),
                        "submitted_count": 1,
                        "prefiltered_count": 0,
                        "remote_batch_id": "batch-123",
                    },
                    "papers": {},
                }
            ),
        encoding="utf-8",
    )

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "waiting batch"


def test_run_merges_completed_batch_outputs_and_marks_done(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "completed"}

        def submit_batch(self, *, batch_id, requests):
            raise AssertionError("submit_batch should not be called")

        def download_output(self, batch_id):
            assert batch_id == "batch-123"
            return [
                {
                    "custom_id": "2",
                    "output_text": json.dumps({"decision": "include", "reason": ["IC1"]}),
                }
            ]

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
                    "metadata": {
                        "batch_id": "batch-123",
                        "status": "waiting batch",
                        "provider": "openai",
                        "model": "gpt-5-mini",
                        "seed": screening.SEED,
                        "input_file": str(csv_path),
                        "submitted_count": 1,
                        "prefiltered_count": 1,
                        "remote_batch_id": "batch-123",
                    },
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

    result = screening.run(
        ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
        client=Client(),
        workdir=tmp_path,
    )

    assert result["metadata"]["status"] == "done"
    assert result["papers"]["1"]["source"] == "prefilter"
    assert result["papers"]["2"] == {
        "source": "openai_batch",
        "decision": "include",
        "reason": ["IC1"],
    }


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


def test_run_raises_for_failed_remote_batch_and_keeps_waiting_state(tmp_path):
    class Client:
        def get_batch(self, batch_id):
            assert batch_id == "batch-123"
            return {"id": batch_id, "status": "failed"}

        def submit_batch(self, *, batch_id, requests):
            raise AssertionError("submit_batch should not be called")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    waiting_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(csv_path),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "remote_batch_id": "batch-123",
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(waiting_state), encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed"):
        screening.run(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
            client=Client(),
            workdir=tmp_path,
        )

    assert json.loads(state_path.read_text(encoding="utf-8")) == waiting_state


def test_run_raises_for_completed_batch_with_failed_requests(tmp_path):
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

        def download_output(self, batch_id):
            raise AssertionError("download_output should not be called")

    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("id,title,abstract\n1,Paper title,Paper abstract\n", encoding="utf-8")
    state_path = tmp_path / "batch-123.json"
    waiting_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(csv_path),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "remote_batch_id": "batch-123",
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(waiting_state), encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed requests"):
        screening.run(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
            client=Client(),
            workdir=tmp_path,
        )

    assert json.loads(state_path.read_text(encoding="utf-8")) == waiting_state


def test_run_raises_for_cancelled_batch_with_partial_output(tmp_path):
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
    waiting_state = {
        "metadata": {
            "batch_id": "batch-123",
            "status": "waiting batch",
            "provider": "openai",
            "model": "gpt-5-mini",
            "seed": screening.SEED,
            "input_file": str(csv_path),
            "submitted_count": 1,
            "prefiltered_count": 0,
            "remote_batch_id": "batch-123",
        },
        "papers": {},
    }
    state_path.write_text(json.dumps(waiting_state), encoding="utf-8")

    with pytest.raises(RuntimeError, match="partial results"):
        screening.run(
            ["--input", str(csv_path), "--model", "gpt-5-mini", "--batch-id", "batch-123"],
            client=Client(),
            workdir=tmp_path,
        )

    assert json.loads(state_path.read_text(encoding="utf-8")) == waiting_state
