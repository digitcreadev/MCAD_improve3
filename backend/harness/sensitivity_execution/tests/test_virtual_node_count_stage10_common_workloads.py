from __future__ import annotations

import json
from pathlib import Path

from backend.harness.sensitivity_execution.validate_execution_spec import (
    validate_execution_spec,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    validate_workload_spec,
)


ROOT = Path(__file__).resolve().parents[4]

E3 = (
    ROOT
    / "reports/article_experiments/sensitivity"
    / "e3_controlled_execution"
)

AUDIT_ROOT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "common_workloads"
)

WORKLOAD_DIR = E3 / "workloads"
EXECUTION_DIR = E3 / "execution_specs"
RUNS_DIR = E3 / "runs"


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def test_stage10_common_workload_audit_passes() -> None:
    report = load_json(
        AUDIT_ROOT
        / "stage10_common_workload_audit.json"
    )

    assert report["status"] == "pass"
    assert report["replication_count"] == 10
    assert report["workload_count"] == 10
    assert report["execution_spec_count"] == 10
    assert (
        report["common_query_count_per_replication"]
        == 2
    )
    assert report["all_replications_usable"] is True


def test_all_workloads_and_execution_specs_validate() -> None:
    for replication_index in range(10):
        stem = (
            "virtual_node_count_stage10_"
            f"rep_{replication_index:03d}_strict_common"
        )

        workload_path = (
            WORKLOAD_DIR / f"{stem}.json"
        )
        execution_path = (
            EXECUTION_DIR / f"{stem}.json"
        )

        workload = load_json(workload_path)
        execution = load_json(execution_path)

        validate_workload_spec(workload)
        validate_execution_spec(execution)

        assert len(workload["steps"]) == 2
        assert (
            len(
                execution[
                    "instance_selection"
                ]["instance_ids"]
            )
            == 3
        )


def test_historical_prefix_is_reused_without_rerun() -> None:
    report = load_json(
        AUDIT_ROOT
        / "stage10_common_workload_audit.json"
    )

    assert (
        report["historical_prefix_audit_matches"]
        is True
    )
    assert (
        report["historical_prefix_workload_matches"]
        is True
    )
    assert (
        report["historical_prefix_rerun_required"]
        is False
    )


def test_no_execution_or_timing_was_performed() -> None:
    report = load_json(
        AUDIT_ROOT
        / "stage10_common_workload_audit.json"
    )

    assert (
        report["functional_execution_performed"]
        is False
    )
    assert report["timing_execution_performed"] is False
    assert (
        report["new_functional_execution_authorized"]
        is False
    )
    assert (
        report["formal_timing_execution_authorized"]
        is False
    )

    for replication_index in range(10):
        stem = (
            "virtual_node_count_stage10_"
            f"rep_{replication_index:03d}_strict_common"
        )

        assert not (RUNS_DIR / stem).exists()
