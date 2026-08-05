from __future__ import annotations

import json
from pathlib import Path

from backend.harness.sensitivity_execution.tools.objective_count_noise_operators_v2 import (
    NOISE_CLASS_ORDER,
    OPERATOR_REGISTRY_VERSION,
    apply_noise_operator,
    build_noise_schedule,
    changed_semantic_fields,
    semantic_projection,
    sha256_payload,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    SCHEMA_VERSION,
    validate_workload_spec,
)

ROOT = Path(__file__).resolve().parents[4]
AMENDMENT = ROOT / "reports/article_experiments/sensitivity/e3_controlled_execution/planning/sa5_objective_count_noise_operator_and_redundancy_ordering_amendment.json"

BASE_QUERY = {
    "cube": "SyntheticFact",
    "measures": ["Sales"],
    "group_by": ["Time.Month", "Geography.Region"],
    "slicers": {"Geography.Region": "Region_01", "Time.Year": "2001"},
    "aggregators": ["SUM"],
    "units": ["USD"],
    "window_start": "2001-01-01",
    "window_end": "2001-12-31",
    "time_members": [],
}


def _workload(query):
    return {
        "contract_version": SCHEMA_VERSION,
        "workload_id": "noise-operator-test",
        "objective_id": "O_TEST",
        "session_id": "S_TEST",
        "steps": [{"step_index": 1, "step_id": "step-1", "query_spec": query}],
    }


def test_schedules_match_preregistered_rows() -> None:
    amendment = json.loads(AMENDMENT.read_text())
    rows = amendment["revised_noise_schedule_contract"]["schedule_rows"]
    for expected in rows:
        schedule = build_noise_schedule(expected["seed"])
        assert list(schedule.noise_positions) == expected["noise_positions"]
        assert list(schedule.contributive_positions) == expected["contributive_positions"]
        assert schedule.redundant_contribution_position == expected["redundant_contribution_position"]
        assert schedule.redundant_source_step_index == expected["redundant_source_step_index"]
        assert schedule.redundant_source_support_ordinal == expected["redundant_source_support_ordinal"]
        assert {str(k): v for k, v in schedule.class_by_position.items()} == expected["class_by_position"]
        assert schedule.target_support_ordinal_by_class == expected["target_support_ordinal_by_class"]


def test_exact_operator_changed_fields_and_provenance() -> None:
    expected = {
        "wrong_measure": ("measures",),
        "wrong_context": ("slicers",),
        "insufficient_grain": ("group_by",),
        "invalid_aggregation": ("aggregators",),
        "invalid_unit": ("units",),
        "invalid_time_window": ("window_start", "window_end"),
        "missing_cube": ("cube",),
        "redundant_contribution": (),
    }
    for noise_class in NOISE_CLASS_ORDER:
        mutated = apply_noise_operator(
            noise_class,
            BASE_QUERY,
            target_support_ordinal=3,
            source_step_index=1 if noise_class == "redundant_contribution" else None,
        )
        assert changed_semantic_fields(BASE_QUERY, mutated) == expected[noise_class]
        metadata = mutated["mcad_controlled_noise"]
        assert metadata["operator_registry_version"] == OPERATOR_REGISTRY_VERSION
        assert metadata["noise_class"] == noise_class
        assert metadata["source_semantic_digest"] == sha256_payload(semantic_projection(BASE_QUERY))
        assert metadata["mutated_semantic_digest"] == sha256_payload(semantic_projection(mutated))
        validate_workload_spec(_workload(mutated))
