from __future__ import annotations

import json
from pathlib import Path

import yaml

from backend.harness.sensitivity_execution.execute_controlled_family import (
    SUPPORTED_GENERATOR_VERSION_PAIRS,
)
from backend.harness.sensitivity_generator.families.objective_count_family import (
    CAMPAIGN_GENERATOR_VERSION,
    STRUCTURAL_GENERATOR_VERSION,
)

ROOT = Path(__file__).resolve().parents[4]

PREREGISTRATION_PATH = (
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

DESIGN_MATRIX_PATH = (
    ROOT
    / "backend"
    / "harness"
    / "sensitivity_design"
    / "design_matrix.yaml"
)


def load_preregistration() -> dict:
    value = json.loads(
        PREREGISTRATION_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(value, dict)

    return value


def load_design() -> dict:
    value = yaml.safe_load(
        DESIGN_MATRIX_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(value, dict)

    return value


def test_preregistration_identity_and_status() -> None:
    preregistration = load_preregistration()

    assert preregistration["schema_version"] == (
        "mcad-sa5-objective-count-stage10-"
        "campaign-preregistration-v1"
    )

    assert preregistration[
        "preregistration_id"
    ] == "sa5_objective_count_stage10_c8_nv32"

    assert preregistration["phase"] == "SA5"
    assert preregistration["factor"] == "objective_count"
    assert preregistration["stage"] == 10
    assert preregistration["status"] == (
        "preregistered_not_materialized"
    )


def test_factor_contract_matches_frozen_design() -> None:
    preregistration = load_preregistration()
    design = load_design()

    contract = preregistration[
        "factor_contract"
    ]

    axis = design["axes"]["objective_count"]

    assert contract["factor_levels"] == [
        1,
        2,
        5,
        10,
        20,
        50,
    ]

    assert contract["factor_levels"] == (
        axis["levels"]
    )

    assert contract[
        "selected_objective_index"
    ] == 0

    assert contract[
        "constraints_per_objective"
    ] == 8

    assert contract[
        "virtual_nodes_per_objective"
    ] == 32

    assert contract["workload_length"] == 40
    assert contract["noise_ratio"] == 0.25
    assert contract["membership_density"] == 1.0

    assert abs(
        sum(
            contract[
                "noise_distribution"
            ].values()
        )
        - 1.0
    ) < 1.0e-12


def test_stage10_replication_contract() -> None:
    preregistration = load_preregistration()

    replication = preregistration[
        "replication_contract"
    ]

    seeds = replication[
        "structural_seeds"
    ]

    assert replication["stage"] == 10
    assert replication["replication_count"] == 10
    assert replication["level_count"] == 6
    assert replication[
        "expected_instance_count"
    ] == 60

    assert len(seeds) == 10
    assert len(set(seeds)) == 10

    assert all(
        isinstance(seed, int)
        and not isinstance(seed, bool)
        and seed > 0
        for seed in seeds
    )

    expected_by_level = {
        1: (8, 32),
        2: (16, 64),
        5: (40, 160),
        10: (80, 320),
        20: (160, 640),
        50: (400, 1600),
    }

    rows = replication[
        "planned_instances_by_level"
    ]

    assert len(rows) == 6

    for row in rows:
        level = row["factor_level"]

        constraints, virtual_nodes = (
            expected_by_level[level]
        )

        assert row[
            "replication_count"
        ] == 10

        assert row[
            "expected_instance_count"
        ] == 10

        assert row[
            "expected_total_constraint_count"
        ] == constraints

        assert row[
            "expected_total_virtual_node_count"
        ] == virtual_nodes


def test_generator_profiles_are_exact() -> None:
    preregistration = load_preregistration()

    binding = preregistration[
        "implementation_binding"
    ]

    assert STRUCTURAL_GENERATOR_VERSION == (
        "mcad-sensitivity-e2.1-"
        "objective-count-v1"
    )

    assert CAMPAIGN_GENERATOR_VERSION == (
        "mcad-sensitivity-e2.2-"
        "objective-count-v1"
    )

    assert binding[
        "structural_generator_version"
    ] == STRUCTURAL_GENERATOR_VERSION

    assert binding[
        "campaign_generator_version"
    ] == CAMPAIGN_GENERATOR_VERSION

    assert (
        SUPPORTED_GENERATOR_VERSION_PAIRS[
            "objective_count"
        ]
        == (
            CAMPAIGN_GENERATOR_VERSION,
            STRUCTURAL_GENERATOR_VERSION,
        )
    )


def test_common_workload_is_seed_shared() -> None:
    preregistration = load_preregistration()

    workload = preregistration[
        "common_workload_contract"
    ]

    assert workload[
        "workload_count_per_replication"
    ] == 1

    assert workload["workload_length"] == 40
    assert workload["noise_ratio"] == 0.25

    assert (
        "shared across all six"
        in workload["sharing_rule"]
    )

    assert (
        "selected_objective_index 0"
        in workload["objective_binding_rule"]
    )

    assert (
        "byte-equivalent"
        in workload[
            "semantic_equivalence_rule"
        ]
    )


def test_execution_remains_unauthorized() -> None:
    preregistration = load_preregistration()

    authorization = preregistration[
        "authorization"
    ]

    assert authorization[
        "preregistration_persistence_authorized"
    ] is True

    assert authorization[
        "campaign_materialization_authorized_now"
    ] is False

    assert authorization[
        (
            "campaign_materialization_authorized_"
            "after_preregistration_merge"
        )
    ] is True

    assert authorization[
        "functional_execution_authorized"
    ] is False

    assert authorization[
        "timing_execution_authorized"
    ] is False

    assert authorization[
        "precision_analysis_authorized"
    ] is False

    assert authorization[
        "bootstrap_execution_authorized"
    ] is False

    assert authorization[
        "stage20_execution_authorized"
    ] is False

    assert authorization[
        "latency_claim_authorized"
    ] is False

    assert authorization[
        "manuscript_integration_authorized"
    ] is False

    assert authorization[
        "global_scientific_freeze"
    ] is False


def test_preregistration_records_no_execution() -> None:
    preregistration = load_preregistration()

    controls = preregistration[
        "scientific_controls"
    ]

    assert controls[
        "canonical_campaign_generated"
    ] is False

    assert controls[
        "scientific_execution_performed"
    ] is False

    assert controls[
        "timing_execution_performed"
    ] is False

    assert controls[
        "bootstrap_execution_performed"
    ] is False

    assert controls[
        "manuscript_modified"
    ] is False

    assert preregistration["next_stage"] == (
        "materialize_sa5_objective_count_stage10_"
        "structure_and_common_workloads"
    )
