import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plan():
    return json.loads((ROOT / "delian_native_smoke_plan.json").read_text())


@pytest.fixture
def assertions():
    return json.loads((ROOT / "native_assertions.json").read_text())
