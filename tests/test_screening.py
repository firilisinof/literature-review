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
