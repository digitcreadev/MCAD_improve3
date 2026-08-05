from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

E3 = (
    ROOT
    / "reports/article_experiments/sensitivity"
    / "e3_controlled_execution"
)

REPORT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "functional_completion"
    / "combined_60_functional_steps_audit.json"
)


def load_report() -> dict:
    return json.loads(
        REPORT.read_text(encoding="utf-8")
    )


def test_combined_functional_counts() -> None:
    report = load_report()

    assert report["status"] == "pass"
    assert report["replication_count"] == 10
    assert report["instance_count"] == 30
    assert report["functional_step_count"] == 60
    assert len(report["runs"]) == 10


def test_each_replication_has_three_instances_and_six_steps() -> None:
    report = load_report()

    assert [
        item["replication_index"]
        for item in report["runs"]
    ] == list(range(10))

    for item in report["runs"]:
        assert item["status"] == "pass"
        assert item["selected_instance_count"] == 3
        assert item["functional_step_count"] == 6
        assert len(item["instances"]) == 3
        assert item["timing_artifact_count"] == 0


def test_historical_prefix_is_reused_without_rerun() -> None:
    report = load_report()
    prefix = report["historical_prefix"]

    assert prefix["replications"] == [0, 1]
    assert prefix["instance_count"] == 6
    assert prefix["functional_step_count"] == 12
    assert prefix["reused"] is True
    assert prefix["rerun_performed"] is False
    assert prefix["rerun_required"] is False


def test_no_timing_or_latency_claim() -> None:
    report = load_report()

    assert report["timing_execution_performed"] is False
    assert report["timing_artifact_count"] == 0
    assert report["latency_claim_authorized"] is False
