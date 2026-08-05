from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]

PLANNING_ROOT = (
    ROOT
    / "reports"
    / "article_experiments"
    / "sensitivity"
    / "e3_controlled_execution"
    / "planning"
)

PREREG_PATH = (
    PLANNING_ROOT
    / (
        "sa5_objective_count_stage10_"
        "campaign_preregistration.json"
    )
)

AMENDMENT_001_PATH = (
    PLANNING_ROOT
    / (
        "sa5_objective_count_"
        "materialization_contract_amendment.json"
    )
)

AMENDMENT_002_PATH = (
    PLANNING_ROOT
    / (
        "sa5_objective_count_workload_"
        "contribution_capacity_amendment.json"
    )
)

AMENDMENT_003_PATH = (
    PLANNING_ROOT
    / (
        "sa5_objective_count_noise_operator_"
        "and_redundancy_ordering_amendment.json"
    )
)

EXPECTED_PREREG_SHA = (
    "a92bb672c2c0ac61d3700ce49c9f3340"
    "ffe6b2f01f08b0f94dd354f96c8c8d5e"
)

EXPECTED_AMENDMENT_001_SHA = (
    "2e0ff32570d9e427e753fdda5bc81699"
    "6d2608778879c1c4c5568fc47bf088e1"
)

EXPECTED_AMENDMENT_002_SHA = (
    "32b3f28d0815fa3e0713f00bc0a4188"
    "63e28089f00fe4079e20c7f257ac960dc"
)


def load_json(
    path: Path,
) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert isinstance(value, dict)

    return value


def digest(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def load_amendment() -> dict[str, Any]:
    return load_json(
        AMENDMENT_003_PATH
    )


def test_prior_artifacts_remain_unchanged() -> None:
    assert hashlib.sha256(
        PREREG_PATH.read_bytes()
    ).hexdigest() == EXPECTED_PREREG_SHA

    assert hashlib.sha256(
        AMENDMENT_001_PATH.read_bytes()
    ).hexdigest() == EXPECTED_AMENDMENT_001_SHA

    assert hashlib.sha256(
        AMENDMENT_002_PATH.read_bytes()
    ).hexdigest() == EXPECTED_AMENDMENT_002_SHA


def test_amendment_identity_and_precedence() -> None:
    amendment = load_amendment()

    assert amendment["schema_version"] == (
        "mcad-sa5-objective-count-noise-"
        "operator-and-redundancy-ordering-"
        "amendment-v1"
    )

    assert amendment["amendment_id"] == (
        "sa5_objective_count_noise_operator_"
        "and_redundancy_ordering_amendment_003"
    )

    assert amendment["status"] == (
        "preregistered_implementation_required"
    )

    assert amendment["factor"] == "objective_count"
    assert amendment["stage"] == 10

    superseded = amendment[
        "amends"
    ]["superseded_fields"]

    assert any(
        "class_to_position_assignment"
        in value
        for value in superseded
    )

    assert any(
        "21-file" in value
        for value in superseded
    )


def test_all_eight_noise_operators_are_exact() -> None:
    amendment = load_amendment()

    contract = amendment[
        "noise_operator_contract"
    ]

    classes = contract[
        "noise_class_order"
    ]

    definitions = contract[
        "operator_definitions"
    ]

    assert classes == [
        "wrong_measure",
        "wrong_context",
        "insufficient_grain",
        "invalid_aggregation",
        "invalid_unit",
        "invalid_time_window",
        "missing_cube",
        "redundant_contribution",
    ]

    assert set(definitions) == set(classes)

    for noise_class in classes[:-1]:
        definition = definitions[
            noise_class
        ]

        assert definition[
            "expected_sat"
        ] is False

        assert definition[
            "expected_real_node_count"
        ] == 0

        assert definition[
            "expected_oracle_contributive"
        ] is False

        assert definition[
            "changed_fields"
        ]

    redundant = definitions[
        "redundant_contribution"
    ]

    assert redundant[
        "changed_fields"
    ] == []

    assert redundant[
        "expected_sat"
    ] is True

    assert redundant[
        "expected_real_node_count"
    ] == 1

    assert redundant[
        "expected_gained_resource_count"
    ] == 0

    assert redundant[
        "expected_oracle_contributive"
    ] is False

    assert redundant[
        "prior_contribution_required"
    ] is True


def test_support_query_uniqueness_contract() -> None:
    contract = load_amendment()[
        "canonical_support_query_contract"
    ]

    assert contract[
        "semantic_projection_fields"
    ] == [
        "cube",
        "measures",
        "group_by",
        "slicers",
        "aggregators",
        "units",
        "window_start",
        "window_end",
        "time_members",
    ]

    expected = contract[
        "expected_base_query_outcome"
    ]

    assert expected["sat"] is True
    assert expected["real_node_count"] == 1
    assert expected[
        "oracle_contributive_on_first_use"
    ] is True
    assert expected[
        "gained_resource_count_on_first_use"
    ] == 1

    uniqueness = contract[
        "unique_context_assignment"
    ]

    assert uniqueness[
        "candidate_pair_count"
    ] == 210

    assert uniqueness[
        "required_distinct_context_count_per_constraint"
    ] == 4

    assert uniqueness[
        "support_query_real_node_count_required"
    ] == 1

    assert uniqueness[
        "support_query_signature_duplicate_count_required"
    ] == 0


def test_schedule_is_deterministic_and_redundancy_is_ordered() -> None:
    amendment = load_amendment()

    schedule = amendment[
        "revised_noise_schedule_contract"
    ]

    rows = schedule["schedule_rows"]

    classes = amendment[
        "noise_operator_contract"
    ]["noise_class_order"]

    non_redundant = [
        value
        for value in classes
        if value != "redundant_contribution"
    ]

    assert len(rows) == 10

    for row in rows:
        seed = int(row["seed"])

        expected_noise_positions = sorted(
            sorted(
                range(1, 33),
                key=lambda position: (
                    digest(
                        "mcad-sa5-noise-position-v2"
                        f"|{seed}|{position}"
                    ),
                    position,
                ),
            )[:8]
        )

        assert row[
            "noise_positions"
        ] == expected_noise_positions

        contributive_positions = [
            position
            for position in range(1, 33)
            if position
            not in expected_noise_positions
        ]

        assert row[
            "contributive_positions"
        ] == contributive_positions

        first_contributive = (
            contributive_positions[0]
        )

        eligible = [
            position
            for position
            in expected_noise_positions
            if position > first_contributive
        ]

        redundant_position = min(
            eligible
        )

        assert row[
            "redundant_contribution_position"
        ] == redundant_position

        source_step = max(
            position
            for position in contributive_positions
            if position < redundant_position
        )

        assert row[
            "redundant_source_step_index"
        ] == source_step

        assert row[
            "redundant_source_support_ordinal"
        ] == contributive_positions.index(
            source_step
        )

        assert redundant_position > (
            first_contributive
        )

        class_by_position = row[
            "class_by_position"
        ]

        assert set(
            class_by_position.values()
        ) == set(classes)

        targets = row[
            "target_support_ordinal_by_class"
        ]

        assert set(targets) == set(
            non_redundant
        )

        assert len(
            set(targets.values())
        ) == 7

    replication_two = rows[2]

    assert replication_two[
        "replication_index"
    ] == 2

    assert replication_two[
        "seed"
    ] == 1198202409

    assert replication_two[
        "redundant_contribution_position"
    ] == 8

    assert replication_two[
        "redundant_source_step_index"
    ] == 7


def test_acceptance_contract_closes_noise_semantics() -> None:
    acceptance = load_amendment()[
        "materialization_acceptance_contract"
    ]

    assert acceptance[
        "required_workload_count"
    ] == 10

    assert acceptance[
        "required_workload_length"
    ] == 32

    assert acceptance[
        "required_contributive_query_count_per_workload"
    ] == 24

    assert acceptance[
        "required_non_contributive_query_count_per_workload"
    ] == 8

    assert acceptance[
        "required_count_per_noise_class_per_workload"
    ] == 1

    assert acceptance[
        "required_unique_support_query_count"
    ] == 24

    assert acceptance[
        "required_support_query_signature_duplicate_count"
    ] == 0

    assert acceptance[
        "required_non_redundant_sat_true_count"
    ] == 0

    assert acceptance[
        "required_redundant_sat_true_count"
    ] == 1

    assert acceptance[
        "required_redundant_gained_resource_count"
    ] == 0

    assert acceptance[
        "required_redundancy_ordering_failure_count"
    ] == 0

    assert acceptance[
        "required_operator_oracle_mismatch_count"
    ] == 0


def test_scope_requires_reprojection_and_execution_remains_forbidden() -> None:
    amendment = load_amendment()

    implementation = amendment[
        "implementation_contract"
    ]

    authorization = amendment[
        "authorization"
    ]

    assert implementation[
        "prior_21_file_scope_authoritative"
    ] is False

    assert implementation[
        "implementation_scope_must_be_reprojected_after_merge"
    ] is True

    assert implementation[
        "preserve_v1_generator_module_bytes"
    ] is True

    assert implementation[
        "preserve_historical_factor_behavior"
    ] is True

    assert authorization[
        "v2_patch_authoring_authorized_before_amendment_merge"
    ] is False

    assert authorization[
        "canonical_campaign_materialization_authorized"
    ] is False

    assert authorization[
        "functional_execution_authorized"
    ] is False

    assert authorization[
        "timing_execution_authorized"
    ] is False

    assert authorization[
        "manuscript_integration_authorized"
    ] is False

    assert amendment["next_stage"] == (
        "reproject_sa5_objective_count_v2_"
        "implementation_scope_after_noise_"
        "operator_amendment_merge"
    )
