import json
import sys
from pathlib import Path

import pytest

PHASE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PHASE_ROOT))


@pytest.fixture
def pre_frame():
    return json.loads((PHASE_ROOT / "fixtures/pre_result_case.json").read_text())


@pytest.fixture
def post_frame():
    return json.loads((PHASE_ROOT / "fixtures/post_result_case.json").read_text())
