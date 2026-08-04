from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

AMENDMENT_PATH = (
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

ORIGINAL_PREREGISTRATION_PATH = (
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

EXPECTED_ORIGINAL_SHA = (
    "a92bb672c2c0ac61d3700ce49c9f3340"
    "ffe6b2f01f08b0f94dd354f96c8c8d5e"
)


def load_amendment() -> dict:
    value = json.loads(
        AMENDMENT_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(value, dict)

    return value


def test_original_preregistration_is_unchanged() -> None:
    digest = hashlib.sha256(
        ORIGINAL_PREREGISTRATION_PATH.read_bytes()
    ).hexdigest()

    assert digest == EXPECTED_ORIGINAL_SHA


def test_amendment_identity_and_precedence() -> None:
    amendment = load_amendment()

    assert amendment["schema_version"] == (
        "mcad-sa5-objective-count-"
        "materialization-contract-amendment-v1"
    )

    assert amendment["status"] == (
        "preregistered_implementation_required"
    )

    assert amendment["factor"] == "objective_count"
    assert amendment["stage"] == 10

    superseded = amendment[
        "amends"
    ]["superseded_original_fields"]

    assert (
        "factor_contract."
        "requirement_sets_per_constraint"
    ) in superseded

    assert (
        "factor_contract.membership_density"
    ) in superseded


def test_structural_micro_design_is_exact() -> None:
    contract = load_amendment()[
        "structural_control_contract"
    ]

    assert contract[
        "constraints_per_objective"
    ] == 8

    assert contract[
        "virtual_nodes_per_objective"
    ] == 32

    assert contract[
        "local_virtual_nodes_per_constraint"
    ] == 4

    assert contract[
        "requirement_sets_per_constraint"
    ] == 2

    assert contract[
        "requirement_set_membership_indices"
    ] == [
        [0, 1],
        [1, 2],
    ]

    assert contract[
        "useful_local_virtual_node_indices"
    ] == [0, 1, 2]

    assert contract[
        "irrelevant_local_virtual_node_indices"
    ] == [3]

    assert contract[
        "useful_virtual_nodes_per_objective"
    ] == 24

    assert contract[
        "irrelevant_virtual_nodes_per_objective"
    ] == 8

    assert contract[
        "useful_virtual_node_ratio"
    ] == 0.75

    assert contract[
        "membership_links_per_objective"
    ] == 32

    assert contract[
        "maximum_membership_links_per_objective"
    ] == 64

    assert contract[
        "expected_realised_density"
    ] == 0.5


def test_structural_counts_scale_only_with_objective_count() -> None:
    contract = load_amendment()[
        "structural_control_contract"
    ]

    rows = contract[
        "counts_by_factor_level"
    ]

    assert [
        row["objective_count"]
        for row in rows
    ] == [1, 2, 5, 10, 20, 50]

    for row in rows:
        level = row["objective_count"]

        assert row["constraint_count"] == 8 * level
        assert row["virtual_node_count"] == 32 * level

        assert (
            row["useful_virtual_node_count"]
            == 24 * level
        )

        assert (
            row["irrelevant_virtual_node_count"]
            == 8 * level
        )

        assert (
            row["requirement_set_count"]
            == 16 * level
        )

        assert (
            row[
                "requirement_membership_link_count"
            ]
            == 32 * level
        )

        assert (
            row["maximum_membership_link_count"]
            == 64 * level
        )

        assert row["realised_density"] == 0.5


def test_noise_integer_allocation_is_deterministic() -> None:
    contract = load_amendment()[
        "workload_noise_contract"
    ]

    classes = contract["noise_class_order"]
    rows = contract["counts_by_replication"]

    assert len(classes) == 8
    assert len(rows) == 10

    recomputed_totals = {
        noise_class: 0
        for noise_class in classes
    }

    for row in rows:
        replication_index = row[
            "replication_index"
        ]

        expected = {
            noise_class: 1
            for noise_class in classes
        }

        expected[
            classes[
                (2 * replication_index) % 8
            ]
        ] += 1

        expected[
            classes[
                (2 * replication_index + 1) % 8
            ]
        ] += 1

        assert row["class_counts"] == expected
        assert sum(expected.values()) == 10

        for noise_class, count in expected.items():
            recomputed_totals[noise_class] += count

    assert recomputed_totals == (
        contract["stage10_class_totals"]
    )

    assert sorted(
        recomputed_totals.values()
    ) == [
        12,
        12,
        12,
        12,
        13,
        13,
        13,
        13,
    ]

    assert contract[
        "stage10_total_noise_query_count"
    ] == 100


def test_materialization_remains_unauthorized() -> None:
    amendment = load_amendment()

    implementation = amendment[
        "implementation_contract"
    ]

    authorization = amendment[
        "authorization"
    ]

    controls = amendment[
        "scientific_controls"
    ]

    assert implementation[
        (
            "implementation_required_"
            "before_materialization"
        )
    ] is True

    assert implementation[
        "target_structural_generator_version"
    ] == (
        "mcad-sensitivity-e2.1-"
        "objective-count-v2"
    )

    assert implementation[
        "target_campaign_generator_version"
    ] == (
        "mcad-sensitivity-e2.2-"
        "objective-count-v2"
    )

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
        "bootstrap_execution_authorized"
    ] is False

    assert controls[
        "canonical_campaign_generated"
    ] is False

    assert controls[
        "functional_execution_performed"
    ] is False

    assert amendment["next_stage"] == (
        "implement_sa5_objective_count_"
        "materialization_contract_v2"
    )
