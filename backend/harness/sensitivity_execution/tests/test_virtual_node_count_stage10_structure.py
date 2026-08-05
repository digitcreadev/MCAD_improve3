from __future__ import annotations

from pathlib import Path

from backend.harness.sensitivity_execution.tools.generate_virtual_node_count_stage10_structure import (
    validate_stage10_structure,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def test_stage10_structural_matrix_is_complete() -> None:
    report = validate_stage10_structure(REPO_ROOT)

    assert report["status"] == "pass"
    assert report["stage10_replication_count"] == 10
    assert report["stage10_level_count"] == 3
    assert report["stage10_instance_count"] == 30
    assert report["fixed_constraint_count"] == 4


def test_historical_prefix_is_semantically_identical() -> None:
    report = validate_stage10_structure(REPO_ROOT)

    assert report["prefix_expected_instance_count"] == 6
    assert report["prefix_compared_instance_count"] == 6
    assert report["prefix_matching_instance_count"] == 6

    for item in report["prefix_results"]:
        assert item["row_semantic_match"] is True
        assert item["manifest_semantic_match"] is True
        assert item["objectives_semantic_match"] is True
        assert item["prefix_match"] is True


def test_no_functional_or_timing_execution_occurred() -> None:
    report = validate_stage10_structure(REPO_ROOT)

    assert (
        report["historical_functional_prefix_rerun_required"]
        is False
    )
    assert report["functional_execution_performed"] is False
    assert report["timing_execution_performed"] is False
    assert (
        report["new_functional_execution_authorized"]
        is False
    )
    assert (
        report["formal_timing_execution_authorized"]
        is False
    )
