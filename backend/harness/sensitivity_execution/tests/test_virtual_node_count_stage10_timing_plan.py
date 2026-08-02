from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

E3 = (
    ROOT
    / "reports/article_experiments/sensitivity"
    / "e3_controlled_execution"
)

PLAN = (
    E3
    / "planning"
    / "virtual_node_count_stage10_timing_execution_plan.json"
)

VALIDATION = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "timing_preparation"
    / "timing_runner_validation.json"
)


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def test_runner_and_analyzer_match_preregistration() -> None:
    plan = load_json(PLAN)
    validation = load_json(VALIDATION)

    assert plan["status"] == "prepared"
    assert validation["status"] == "pass"

    assert (
        plan["runner"][
            "sha256_matches_preregistration"
        ]
        is True
    )
    assert (
        plan["precision_analyzer"][
            "sha256_matches_preregistration"
        ]
        is True
    )

    assert (
        validation[
            "runner_sha256_matches_preregistration"
        ]
        is True
    )
    assert (
        validation[
            "precision_analyzer_sha256_matches_preregistration"
        ]
        is True
    )


def test_stage10_timing_plan_counts() -> None:
    plan = load_json(PLAN)
    scope = plan["scope"]

    assert scope["replication_count"] == 10
    assert scope["timing_cell_count"] == 60
    assert scope["warmups_per_cell"] == 10
    assert scope["measurements_per_cell"] == 100
    assert scope["expected_warmup_count"] == 600
    assert scope["expected_measurement_count"] == 6000

    assert len(plan["replications"]) == 10

    assert sum(
        item["timing_cell_count"]
        for item in plan["replications"]
    ) == 60

    assert sum(
        item["expected_warmup_count"]
        for item in plan["replications"]
    ) == 600

    assert sum(
        item["expected_measurement_count"]
        for item in plan["replications"]
    ) == 6000


def test_replication_matrix_and_seeds_are_complete() -> None:
    plan = load_json(PLAN)
    replications = plan["replications"]

    assert [
        item["replication_index"]
        for item in replications
    ] == list(range(10))

    assert [
        item["execution_order_seed"]
        for item in replications
    ] == [
        20260728 + index
        for index in range(10)
    ]

    for item in replications:
        assert item["factor_levels"] == [6, 12, 24]
        assert item["steps_per_instance"] == 2
        assert item["timing_cell_count"] == 6
        assert item["functional_digest_check_required"] is True
        assert item["fresh_ckg_state_required"] is True
        assert item["reuse_successful"] is True
        assert item["logical_status"] == "ready"
        assert item["runner_invocation_performed"] is False


def test_preparation_performed_no_execution() -> None:
    plan = load_json(PLAN)
    state = plan["execution_state"]
    prohibitions = plan["prohibitions"]

    assert state == {
        "runner_invocation_performed": False,
        "timing_execution_performed": False,
        "warmup_count_observed": 0,
        "measurement_count_observed": 0,
        "timing_output_directories_created": False,
    }

    assert (
        prohibitions[
            "functional_execution_rerun_authorized"
        ]
        is False
    )
    assert (
        prohibitions[
            "historical_prefix_rerun_authorized"
        ]
        is False
    )
    assert (
        prohibitions[
            "stage20_execution_authorized"
        ]
        is False
    )
    assert (
        prohibitions[
            "latency_claim_authorized"
        ]
        is False
    )
