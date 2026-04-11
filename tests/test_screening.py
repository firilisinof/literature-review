from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import screening


def test_cli_requires_input_model_and_batch_id():
    with pytest.raises(SystemExit):
        screening.parse_args([])
