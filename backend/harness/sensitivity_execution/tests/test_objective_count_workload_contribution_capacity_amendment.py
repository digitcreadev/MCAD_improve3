from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

PREREG_PATH = (
    ROOT
    / "reports"
    / "article_experiments"
    / "sensitivity"
    / "e3_controlled_execution"
    / "planning"
    / (
        "sa5_objective_count_stage10_"
        "campaign_preregistration.json"
    )
)

AMENDMENT_001_PATH = (
    ROOT
    / "reports"
    / "article_experiments"
    / "sensitivity"
    / "e3_controlled_execution"
    / "planning"
    / (
        "sa5_objective_count_"
        "materialization_contract_amendment.json"
    )
)

AMENDMENT_002_PATH = (
    ROOT
    / "reports"
    / "article_experiments"
    / "sensitivity"
    / "e3_controlled_execution"
    / "planning"
    / (
        "sa5_objective_count_workload_"
        "contribution_capacity_amendment.json"
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


def load_amendment() -> dict:
    value = json.loads(
        AMENDMENT_002_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(value, dict)

    return value


def test_prior_artifacts_remain_unchanged() -> None:
    assert hashlib.sha256(
        PREREG_PATH.read_bytes()
    ).hexdigest() == EXPECTED_PREREG_SHA

    assert hashlib.sha256(
        AMENDMENT_001_PATH.read_bytes()
    ).hexdigest() == EXPECTED_AMENDMENT_001_SHA


def test_capacity_amendment_identity_and_precedence() -> None:
    amendment = load_amendment()

    assert amendment["schema_version"] == (
        "mcad-sa5-objective-count-workload-"
        "contribution-capacity-amendment-v1"
    )

    assert amendment["amendment_id"] == (
        "sa5_objective_count_workload_"
        "contribution_capacity_amendment_002"
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
        "workload_length" in value
        for value in superseded
    )

    assert any(
        "final 17-file implementation scope"
        in value
        for value in superseded
    )


def test_factor_scoped_support_policy_is_exact() -> None:
    support = load_amendment()[
        "factor_scoped_support_contract"
    ]

    assert support["metadata_field"] == (
        "session_support_policy"
    )

    assert support[
        "objective_count_v2_value"
    ] == "union_requirement_sets"

    assert support[
        "historical_default_value"
    ] == (
        "shortest_requirement_set_"
        "then_lexicographic_tie_break"
    )

    assert support[
        "requirement_set_membership_indices"
    ] == [[0, 1], [1, 2]]

    assert support[
        "support_local_virtual_node_indices"
    ] == [0, 1, 2]

    assert support[
        "support_resources_per_constraint"
    ] == 3

    assert support[
        "support_resources_per_objective"
    ] == 24

    assert support[
        "historical_profiles_must_remain_unchanged"
    ] is True

    assert support[
        "factor_local_dispatch_required"
    ] is True


def test_revised_workload_matches_capacity_and_noise_ratio() -> None:
    workload = load_amendment()[
        "revised_workload_contract"
    ]

    assert workload["workload_length"] == 32
    assert workload["non_contributive_query_count"] == 8
    assert workload["oracle_contributive_query_count"] == 24

    assert (
        workload["non_contributive_query_count"]
        / workload["workload_length"]
    ) == 0.25

    assert workload["contributive_capacity"] == 24
    assert workload["capacity_equality_required"] is True

    coordinates = workload["support_coordinates"]

    assert len(coordinates) == 24

    assert {
        (
            row["constraint_index"],
            row["local_virtual_node_index"],
        )
        for row in coordinates
    } == {
        (
            constraint_index,
            local_index,
        )
        for constraint_index in range(8)
        for local_index in (0, 1, 2)
    }

    assert [
        row["support_ordinal"]
        for row in coordinates
    ] == list(range(24))


def test_noise_allocation_is_exactly_balanced() -> None:
    workload = load_amendment()[
        "revised_workload_contract"
    ]

    classes = workload["noise_class_order"]
    rows = workload["counts_by_replication"]

    assert len(classes) == 8
    assert len(rows) == 10

    totals = {
        noise_class: 0
        for noise_class in classes
    }

    for row in rows:
        assert set(
            row["class_counts"]
        ) == set(classes)

        assert set(
            row["class_counts"].values()
        ) == {1}

        assert sum(
            row["class_counts"].values()
        ) == 8

        for noise_class, count in (
            row["class_counts"].items()
        ):
            totals[noise_class] += count

    assert set(totals.values()) == {10}

    assert totals == workload[
        "stage10_class_totals"
    ]

    assert workload[
        "stage10_total_noise_query_count"
    ] == 80

    assert workload[
        "stage10_maximum_pairwise_class_imbalance"
    ] == 0


def test_implementation_scope_requires_reprojection() -> None:
    amendment = load_amendment()

    implementation = amendment[
        "implementation_contract"
    ]

    authorization = amendment[
        "authorization"
    ]

    assert implementation[
        "prior_17_file_scope_authoritative"
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

    assert amendment["next_stage"] == (
        "reproject_sa5_objective_count_v2_"
        "implementation_scope_after_capacity_"
        "amendment_merge"
    )
