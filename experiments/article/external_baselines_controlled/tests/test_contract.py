import json
from pathlib import Path

from schema_subset import validate


ROOT = Path(__file__).parents[1]


def _load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_schema_validates_registry_and_all_adapter_fixtures():
    schema = _load("contract.schema.json")
    registry = _load("registry.yaml")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    validate(registry, schema)

    from adapters import AssessAdapter, DelianPostAdapter, DelianPreAdapter, DjedainiAdapter

    fixtures = [
        DelianPreAdapter().record_native_outputs("sha256:pre", {"DirectNovelty": 0.2}),
        DelianPostAdapter().record_native_outputs("sha256:post", {"LabelSurprise": 0.8}),
        DjedainiAdapter().status("sha256:djedaini"),
        AssessAdapter().status("sha256:assess"),
    ]
    for fixture in fixtures:
        validate(fixture, schema)
        assert fixture["normalized_binary_decision"] is None


def test_observation_requirements_and_raw_outputs_are_preserved():
    from adapters import DelianPostAdapter, DelianPreAdapter

    raw = {"DirectNovelty": 0.125, "native_note": "unchanged"}
    pre = DelianPreAdapter().record_native_outputs("sha256:one", raw)
    post = DelianPostAdapter().record_native_outputs("sha256:two", {"LabelSurprise": 4})
    assert pre["raw_outputs"] == raw
    assert pre["requires_current_query_result"] is False
    assert post["requires_current_query_result"] is True
    assert pre["physical_query_count"] == pre["auxiliary_query_count"] == 0
