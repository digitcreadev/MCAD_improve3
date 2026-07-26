from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from backend.harness.sensitivity_execution.validate_execution_spec import (
    SCHEMA_VERSION,
    load_execution_spec,
    validate_execution_spec,
)


SCHEMA_PATH = Path(
    "backend/harness/sensitivity_execution/"
    "execution_spec.schema.json"
)


def canonical_execution_spec() -> dict[str, Any]:
    return {
        "contract_version": SCHEMA_VERSION,
        "execution_id": "e3-test-execution",
        "campaign_dir": "/tmp/e2-campaign",
        "workload_path": "/tmp/e3-workload.json",
        "output_dir": "/tmp/e3-results",
        "overwrite": False,
        "continue_on_instance_failure": False,
    }


def test_schema_file_exists_and_is_valid_json() -> None:
    assert SCHEMA_PATH.is_file()

    raw = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert raw["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert raw["type"] == "object"
    assert raw["additionalProperties"] is False


def test_canonical_execution_spec_is_valid() -> None:
    validate_execution_spec(canonical_execution_spec())


def test_minimal_execution_spec_is_valid() -> None:
    execution_spec = {
        "contract_version": SCHEMA_VERSION,
        "execution_id": "minimal",
        "campaign_dir": "/tmp/campaign",
        "workload_path": "/tmp/workload.json",
        "output_dir": "/tmp/results",
    }

    validate_execution_spec(execution_spec)


@pytest.mark.parametrize(
    "field",
    [
        "execution_id",
        "campaign_dir",
        "workload_path",
        "output_dir",
    ],
)
def test_rejects_missing_required_identifier(
    field: str,
) -> None:
    execution_spec = canonical_execution_spec()
    execution_spec.pop(field)

    with pytest.raises(
        AssertionError,
        match=field,
    ):
        validate_execution_spec(execution_spec)


def test_rejects_wrong_contract_version() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["contract_version"] = "unsupported-version"

    with pytest.raises(
        AssertionError,
        match="contract_version",
    ):
        validate_execution_spec(execution_spec)


@pytest.mark.parametrize(
    "field",
    [
        "execution_id",
        "campaign_dir",
        "workload_path",
        "output_dir",
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        "   ",
        None,
        123,
        [],
    ],
)
def test_rejects_invalid_required_string(
    field: str,
    invalid_value: Any,
) -> None:
    execution_spec = canonical_execution_spec()
    execution_spec[field] = invalid_value

    with pytest.raises(
        AssertionError,
        match=field,
    ):
        validate_execution_spec(execution_spec)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "false",
        0,
        1,
        None,
        [],
    ],
)
def test_rejects_non_boolean_overwrite(
    invalid_value: Any,
) -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["overwrite"] = invalid_value

    with pytest.raises(
        AssertionError,
        match="overwrite must be a boolean",
    ):
        validate_execution_spec(execution_spec)


@pytest.mark.parametrize(
    "invalid_value",
    [
        True,
        "false",
        0,
        None,
    ],
)
def test_rejects_continue_on_instance_failure(
    invalid_value: Any,
) -> None:
    execution_spec = canonical_execution_spec()
    execution_spec[
        "continue_on_instance_failure"
    ] = invalid_value

    with pytest.raises(
        AssertionError,
        match="continue_on_instance_failure must be false",
    ):
        validate_execution_spec(execution_spec)


def test_accepts_instance_selection() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["instance_selection"] = {
        "instance_ids": [
            "level_001/rep_001",
            "level_002/rep_001",
        ]
    }

    validate_execution_spec(execution_spec)


def test_rejects_empty_instance_selection() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["instance_selection"] = {
        "instance_ids": []
    }

    with pytest.raises(
        AssertionError,
        match="must not be empty",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_duplicate_instance_ids() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["instance_selection"] = {
        "instance_ids": [
            "level_001/rep_001",
            "level_001/rep_001",
        ]
    }

    with pytest.raises(
        AssertionError,
        match="must be unique",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_missing_instance_ids() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["instance_selection"] = {}

    with pytest.raises(
        AssertionError,
        match="instance_selection.instance_ids is required",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_unsupported_instance_selection_field() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["instance_selection"] = {
        "instance_ids": ["level_001/rep_001"],
        "factor_level": "level_001",
    }

    with pytest.raises(
        AssertionError,
        match="unsupported fields",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_unknown_top_level_field() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["unexpected"] = True

    with pytest.raises(
        AssertionError,
        match="unsupported fields",
    ):
        validate_execution_spec(execution_spec)


@pytest.mark.parametrize(
    "field",
    [
        "sat",
        "real",
        "real_node_ids",
        "ceval",
        "calculable_constraints",
        "phi",
        "phi_weighted",
        "phi_leq_t",
        "delta_phi_t",
        "metrics",
        "timeline",
        "audit",
        "status",
        "evaluator_latency_ms",
    ],
)
def test_rejects_execution_output_fields(
    field: str,
) -> None:
    execution_spec = canonical_execution_spec()
    execution_spec[field] = "forbidden"

    with pytest.raises(
        AssertionError,
        match="execution output fields",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_output_dir_equal_to_campaign_dir() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["output_dir"] = execution_spec["campaign_dir"]

    with pytest.raises(
        AssertionError,
        match="outside campaign_dir",
    ):
        validate_execution_spec(execution_spec)


def test_rejects_output_dir_inside_campaign_dir() -> None:
    execution_spec = canonical_execution_spec()
    execution_spec["output_dir"] = (
        "/tmp/e2-campaign/e3-results"
    )

    with pytest.raises(
        AssertionError,
        match="outside campaign_dir",
    ):
        validate_execution_spec(execution_spec)


def test_load_execution_spec_reads_valid_json(
    tmp_path: Path,
) -> None:
    execution_spec_path = tmp_path / "execution_spec.json"
    execution_spec_path.write_text(
        json.dumps(canonical_execution_spec()),
        encoding="utf-8",
    )

    loaded = load_execution_spec(execution_spec_path)

    assert loaded == canonical_execution_spec()


def test_load_execution_spec_rejects_missing_file(
    tmp_path: Path,
) -> None:
    execution_spec_path = tmp_path / "missing.json"

    with pytest.raises(
        AssertionError,
        match="does not exist",
    ):
        load_execution_spec(execution_spec_path)


def test_load_execution_spec_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    execution_spec_path = tmp_path / "invalid.json"
    execution_spec_path.write_text(
        '{"execution_id": ',
        encoding="utf-8",
    )

    with pytest.raises(
        AssertionError,
        match="invalid JSON",
    ):
        load_execution_spec(execution_spec_path)


def test_validation_is_deterministic() -> None:
    execution_spec = canonical_execution_spec()
    first = deepcopy(execution_spec)
    second = deepcopy(execution_spec)

    validate_execution_spec(first)
    validate_execution_spec(second)

    assert first == second == execution_spec
