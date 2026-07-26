from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from backend.harness.sensitivity_execution.validate_workload_spec import (
    SCHEMA_VERSION,
    load_workload_spec,
    validate_workload_spec,
)


SCHEMA_PATH = Path(
    "backend/harness/sensitivity_execution/"
    "workload_spec.schema.json"
)


def canonical_workload() -> dict[str, Any]:
    return {
        "contract_version": SCHEMA_VERSION,
        "workload_id": "e3-test-workload",
        "objective_id": "O_E3_TEST",
        "session_id": "e3-test-session",
        "steps": [
            {
                "step_index": 1,
                "step_id": "step-0001",
                "query_spec": {
                    "cube": "SyntheticFact",
                    "measures": ["Sales"],
                    "group_by": [
                        "Time.Month",
                        "Geography.Region",
                    ],
                    "slicers": {
                        "Geography.Region": "Region_01",
                        "Time.Year": "2017",
                    },
                    "aggregators": ["SUM"],
                    "units": ["USD"],
                    "window_start": "2017-01-01",
                    "window_end": "2017-12-31",
                    "time_members": ["2017"],
                },
            },
            {
                "step_index": 2,
                "step_id": "step-0002",
                "query_spec": {
                    "cube": "SyntheticFact",
                    "measures": ["Cost"],
                    "group_by": [
                        "Time.Month",
                        "Geography.Region",
                    ],
                    "slicers": {
                        "Geography.Region": "Region_02",
                        "Time.Year": "2018",
                    },
                    "aggregators": ["AVG"],
                    "units": ["PERCENT"],
                    "window_start": "2018-01-01",
                    "window_end": "2018-12-31",
                    "time_members": ["2018"],
                },
            },
        ],
    }


def test_schema_file_exists_and_is_valid_json() -> None:
    assert SCHEMA_PATH.is_file()

    raw = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert raw["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert raw["type"] == "object"
    assert raw["additionalProperties"] is False


def test_canonical_workload_is_valid() -> None:
    validate_workload_spec(canonical_workload())


def test_minimal_workload_is_valid() -> None:
    workload = {
        "contract_version": SCHEMA_VERSION,
        "workload_id": "minimal",
        "objective_id": "O_MINIMAL",
        "session_id": "S_MINIMAL",
        "steps": [
            {
                "step_index": 1,
                "step_id": "step-1",
                "query_spec": {
                    "cube": "SyntheticFact",
                    "measures": ["Sales"],
                },
            }
        ],
    }

    validate_workload_spec(workload)


@pytest.mark.parametrize(
    "field",
    [
        "workload_id",
        "objective_id",
        "session_id",
    ],
)
def test_rejects_missing_top_level_identifier(
    field: str,
) -> None:
    workload = canonical_workload()
    workload.pop(field)

    with pytest.raises(
        AssertionError,
        match=field,
    ):
        validate_workload_spec(workload)


def test_rejects_wrong_contract_version() -> None:
    workload = canonical_workload()
    workload["contract_version"] = "unsupported-version"

    with pytest.raises(
        AssertionError,
        match="contract_version",
    ):
        validate_workload_spec(workload)


def test_rejects_empty_steps() -> None:
    workload = canonical_workload()
    workload["steps"] = []

    with pytest.raises(
        AssertionError,
        match="steps must not be empty",
    ):
        validate_workload_spec(workload)


def test_rejects_duplicate_step_index() -> None:
    workload = canonical_workload()
    workload["steps"][1]["step_index"] = 1

    with pytest.raises(
        AssertionError,
        match="duplicate step_index",
    ):
        validate_workload_spec(workload)


def test_rejects_non_increasing_step_indices() -> None:
    workload = canonical_workload()
    workload["steps"][0]["step_index"] = 2
    workload["steps"][1]["step_index"] = 1

    with pytest.raises(
        AssertionError,
        match="strictly increasing",
    ):
        validate_workload_spec(workload)


def test_rejects_duplicate_step_id() -> None:
    workload = canonical_workload()
    workload["steps"][1]["step_id"] = "step-0001"

    with pytest.raises(
        AssertionError,
        match="duplicate step_id",
    ):
        validate_workload_spec(workload)


@pytest.mark.parametrize(
    "invalid_index",
    [
        0,
        -1,
        1.5,
        True,
        "1",
        None,
    ],
)
def test_rejects_invalid_step_index(
    invalid_index: Any,
) -> None:
    workload = canonical_workload()
    workload["steps"][0]["step_index"] = invalid_index

    with pytest.raises(
        AssertionError,
        match="step_index",
    ):
        validate_workload_spec(workload)


@pytest.mark.parametrize(
    "field",
    [
        "cube",
        "measures",
    ],
)
def test_rejects_missing_required_query_field(
    field: str,
) -> None:
    workload = canonical_workload()
    workload["steps"][0]["query_spec"].pop(field)

    with pytest.raises(
        AssertionError,
        match=field,
    ):
        validate_workload_spec(workload)


def test_rejects_empty_measures() -> None:
    workload = canonical_workload()
    workload["steps"][0]["query_spec"]["measures"] = []

    with pytest.raises(
        AssertionError,
        match="measures must not be empty",
    ):
        validate_workload_spec(workload)


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
        "evaluator_latency_ms",
        "status",
    ],
)
def test_rejects_evaluator_output_fields_in_step(
    field: str,
) -> None:
    workload = canonical_workload()
    workload["steps"][0][field] = "forbidden"

    with pytest.raises(
        AssertionError,
        match="evaluator output fields",
    ):
        validate_workload_spec(workload)


@pytest.mark.parametrize(
    "field",
    [
        "sat",
        "real",
        "ceval",
        "phi",
        "phi_weighted",
    ],
)
def test_rejects_evaluator_output_fields_in_query_spec(
    field: str,
) -> None:
    workload = canonical_workload()
    workload["steps"][0]["query_spec"][field] = "forbidden"

    with pytest.raises(
        AssertionError,
        match="evaluator output fields",
    ):
        validate_workload_spec(workload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("window_start", "2017"),
        ("window_start", "01-01-2017"),
        ("window_end", "2017/12/31"),
        ("window_end", ""),
    ],
)
def test_rejects_invalid_date_format(
    field: str,
    value: str,
) -> None:
    workload = canonical_workload()
    workload["steps"][0]["query_spec"][field] = value

    with pytest.raises(
        AssertionError,
        match=field,
    ):
        validate_workload_spec(workload)


def test_rejects_reversed_window() -> None:
    workload = canonical_workload()
    query_spec = workload["steps"][0]["query_spec"]
    query_spec["window_start"] = "2018-01-01"
    query_spec["window_end"] = "2017-12-31"

    with pytest.raises(
        AssertionError,
        match="window_start must not be after window_end",
    ):
        validate_workload_spec(workload)


def test_rejects_non_string_slicer_member() -> None:
    workload = canonical_workload()
    workload["steps"][0]["query_spec"]["slicers"][
        "Time.Year"
    ] = 2017

    with pytest.raises(
        AssertionError,
        match="must be a non-empty string",
    ):
        validate_workload_spec(workload)


def test_query_spec_allows_extension_fields() -> None:
    workload = canonical_workload()
    query_spec = workload["steps"][0]["query_spec"]

    query_spec["language"] = "mdx"
    query_spec["mdx"] = "SELECT FROM [SyntheticFact]"
    query_spec["custom_metadata"] = {
        "source": "controlled-workload"
    }

    validate_workload_spec(workload)


def test_load_workload_spec_reads_valid_json(
    tmp_path: Path,
) -> None:
    workload_path = tmp_path / "workload_spec.json"
    workload_path.write_text(
        json.dumps(canonical_workload()),
        encoding="utf-8",
    )

    loaded = load_workload_spec(workload_path)

    assert loaded == canonical_workload()


def test_load_workload_spec_rejects_missing_file(
    tmp_path: Path,
) -> None:
    workload_path = tmp_path / "missing.json"

    with pytest.raises(
        AssertionError,
        match="does not exist",
    ):
        load_workload_spec(workload_path)


def test_load_workload_spec_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    workload_path = tmp_path / "invalid.json"
    workload_path.write_text(
        '{"steps": ',
        encoding="utf-8",
    )

    with pytest.raises(
        AssertionError,
        match="invalid JSON",
    ):
        load_workload_spec(workload_path)


def test_validation_is_deterministic() -> None:
    workload = canonical_workload()
    first = deepcopy(workload)
    second = deepcopy(workload)

    validate_workload_spec(first)
    validate_workload_spec(second)

    assert first == second == workload
