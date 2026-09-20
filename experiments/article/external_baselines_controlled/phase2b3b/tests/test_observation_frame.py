import copy
import json

import pytest

from conftest import PHASE_ROOT
from projection import build_observation_frame, canonical_json, query_digest, validate_observation_frame
from schema_subset import validate


def test_fixtures_validate_schema_and_semantics(pre_frame, post_frame):
    schema = json.loads((PHASE_ROOT / "observation_frame.schema.json").read_text())
    for frame in (pre_frame, post_frame):
        validate(frame, schema)
        validate_observation_frame(frame)


def test_stage_specific_current_results(pre_frame, post_frame):
    assert pre_frame["current_result"] == {"available": False, "digest": None, "payload": None, "shape": None}
    assert post_frame["current_result"]["available"] is True
    assert post_frame["current_result"]["digest"]
    assert post_frame["current_result"]["payload"] is not None
    assert post_frame["current_result"]["shape"] is not None


def test_query_digest_and_serialization_are_deterministic(pre_frame):
    text = pre_frame["query"]["canonical_text"]
    assert pre_frame["query"]["canonical_digest"] == query_digest(text)
    reordered = {key: pre_frame[key] for key in reversed(pre_frame)}
    assert canonical_json(pre_frame) == canonical_json(reordered)


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_non_finite_numbers(non_finite):
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json({"nested": {"value": non_finite}})


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_projection_cannot_serialize_non_finite_query_content(non_finite):
    frame = build_observation_frame(
        case_id="non_finite_regression",
        dataset_id="synthetic_dataset",
        objective_id="synthetic_objective",
        session_id="synthetic_session",
        step_idx=0,
        observation_stage="pre_result",
        canonical_text="SELECT 1",
        query_spec={"nested": {"value": non_finite}},
        history=[],
        current_result={"available": False, "digest": None, "payload": None, "shape": None},
        source_kind="synthetic_contract_fixture",
        source_identifiers={"fixture_family": "phase2b3b"},
        source_digests={},
    )
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json(frame)


def test_future_and_unordered_history_are_rejected(pre_frame):
    future = copy.deepcopy(pre_frame)
    future["history"][0]["step_idx"] = future["step_idx"]
    try:
        validate_observation_frame(future)
    except ValueError as error:
        assert "prior steps" in str(error)
    else:
        raise AssertionError("future history accepted")
