from __future__ import annotations

from pathlib import Path

import pytest

from backend.harness.sensitivity_execution.tools.audit_membership_density_common_workload import (
    MembershipDensityWorkloadAuditError,
    _validate_nested_membership_edges,
    audit_membership_density_campaign,
)
from backend.harness.sensitivity_generator.families.membership_density_family import (
    MembershipDensityFamilySpec,
    generate_membership_density_family,
)


def generate_campaign(
    output_dir: Path,
    *,
    levels: tuple[int, ...] = (
        25,
        50,
        75,
        100,
    ),
    seeds: tuple[int, ...] = (
        101,
        202,
    ),
) -> None:
    generate_membership_density_family(
        MembershipDensityFamilySpec(
            campaign_id=(
                "sa4_membership_density_"
                "auditor_test"
            ),
            levels=levels,
            seeds=seeds,
            baseline_constraint_count=4,
            baseline_virtual_node_count=24,
            output_dir=str(output_dir),
        )
    )


def test_valid_campaign_passes(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"

    generate_campaign(campaign_dir)

    audit = audit_membership_density_campaign(
        campaign_dir
    )

    assert audit["status"] == "success"
    assert audit["replication_count"] == 2
    assert audit["instance_count"] == 8

    assert audit["workload_strategy"] == (
        "one_workload_per_structural_seed_"
        "shared_across_density_levels"
    )

    assert (
        audit["execution_partition_required"]
        is True
    )

    assert (
        audit["global_diagnostics"][
            "global_workload_authorized"
        ]
        is False
    )

    for replication in audit["replications"]:
        assert replication[
            "semantic_node_count"
        ] == 24

        assert replication[
            "strict_common_semantic_node_count"
        ] == 24

        assert replication[
            "membership_counts_by_level"
        ] == {
            "25": 6,
            "50": 12,
            "75": 18,
            "100": 24,
        }

        assert replication[
            "membership_edges_strictly_nested"
        ] is True

        assert replication[
            "semantic_sets_exactly_equal"
        ] is True

        assert replication[
            "query_specs_identical"
        ] is True

        blueprint = replication[
            "workload_blueprint"
        ]

        assert blueprint["step_count"] == 24
        assert len(blueprint["steps"]) == 24

        assert set(
            blueprint["instance_ids_by_level"]
        ) == {
            "25",
            "50",
            "75",
            "100",
        }


def test_audit_is_deterministic(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    generate_campaign(first_dir)
    generate_campaign(second_dir)

    first = audit_membership_density_campaign(
        first_dir
    )

    second = audit_membership_density_campaign(
        second_dir
    )

    assert first["audit_digest"] == (
        second["audit_digest"]
    )

    assert [
        item["workload_blueprint_digest"]
        for item in first["replications"]
    ] == [
        item["workload_blueprint_digest"]
        for item in second["replications"]
    ]


def test_incomplete_level_matrix_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "incomplete"

    generate_campaign(
        campaign_dir,
        levels=(25, 50, 75),
    )

    with pytest.raises(
        MembershipDensityWorkloadAuditError,
        match="exact density-level matrix",
    ):
        audit_membership_density_campaign(
            campaign_dir
        )


def test_non_nested_membership_edges_are_rejected() -> None:
    edges = {
        25: frozenset(
            {
                (0, 0, 0),
            }
        ),
        50: frozenset(
            {
                (0, 0, 1),
                (0, 0, 2),
            }
        ),
        75: frozenset(
            {
                (0, 0, 1),
                (0, 0, 2),
                (0, 0, 3),
            }
        ),
        100: frozenset(
            {
                (0, 0, 1),
                (0, 0, 2),
                (0, 0, 3),
                (0, 0, 4),
            }
        ),
    }

    with pytest.raises(
        MembershipDensityWorkloadAuditError,
        match="not strictly nested",
    ):
        _validate_nested_membership_edges(
            edges,
            (25, 50, 75, 100),
        )


def test_invalid_required_level_contract_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"

    generate_campaign(campaign_dir)

    with pytest.raises(
        MembershipDensityWorkloadAuditError,
        match="requires the exact levels",
    ):
        audit_membership_density_campaign(
            campaign_dir,
            required_levels=(25, 50, 100),
        )
