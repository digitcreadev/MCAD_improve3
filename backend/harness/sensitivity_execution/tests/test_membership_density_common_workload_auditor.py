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

def test_auditor_import_is_silent_and_does_not_touch_constraint_count_reports(
    tmp_path: Path,
) -> None:
    import hashlib
    import os
    import subprocess
    import sys

    repository_root = (
        Path(__file__).resolve().parents[4]
    )

    constraint_count_report_dir = (
        repository_root
        / "reports/article_experiments/sensitivity/"
        "e3_controlled_execution/audits/"
        "constraint_count"
    )

    def snapshot() -> dict[str, str]:
        if not constraint_count_report_dir.is_dir():
            return {}

        result = {}

        for path in sorted(
            constraint_count_report_dir.rglob("*")
        ):
            if path.is_file():
                relative = str(
                    path.relative_to(
                        constraint_count_report_dir
                    )
                )

                result[relative] = (
                    hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                )

        return result

    before = snapshot()

    environment = dict(os.environ)

    environment["PYTHONPATH"] = str(
        repository_root
    )

    environment[
        "PYTHONDONTWRITEBYTECODE"
    ] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import "
                "backend.harness.sensitivity_execution."
                "tools."
                "audit_membership_density_common_workload"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0, (
        completed.stdout
        + completed.stderr
    )

    assert completed.stdout == ""
    assert completed.stderr == ""
    assert snapshot() == before

def _generate_campaign(
    output_dir,
    *,
    seeds,
    levels=(25, 50, 75, 100),
) -> None:
    """Generate an isolated membership-density test campaign."""
    from backend.harness.sensitivity_generator.families.membership_density_family import (
        MembershipDensityFamilySpec,
        generate_membership_density_family,
    )

    generate_membership_density_family(
        MembershipDensityFamilySpec(
            campaign_id=(
                "sa4_membership_density_"
                "query_equivalence_auditor_test"
            ),
            levels=tuple(levels),
            seeds=tuple(seeds),
            baseline_constraint_count=4,
            baseline_virtual_node_count=24,
            output_dir=str(output_dir),
        )
    )


CANONICAL_STAGE10_SEEDS = (
    101,
    202,
    1198202409,
    796786883,
    1126922093,
    809989256,
    618554674,
    1363159082,
    874332939,
    1767972531,
)


def test_query_equivalent_virtual_nodes_are_grouped_with_metadata(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path
        / "query_equivalent_campaign"
    )

    _generate_campaign(
        campaign_dir,
        seeds=(
            1126922093,
            1767972531,
        ),
    )

    audit = (
        audit_membership_density_campaign(
            campaign_dir
        )
    )

    assert audit[
        "workload_equivalence_key"
    ] == "canonical_query_spec_digest"

    assert audit[
        "workload_step_count_basis"
    ] == "unique_canonical_query_specs"

    assert audit[
        "equivalence_class_metadata_required"
    ] is True

    assert audit[
        "partition_step_count_histogram"
    ] == {
        "23": 2,
    }

    assert audit[
        "structural_virtual_node_count_histogram"
    ] == {
        "24": 2,
    }

    assert len(
        audit["replications"]
    ) == 2

    for replication in audit[
        "replications"
    ]:
        assert replication[
            "semantic_node_count"
        ] == 24

        assert replication[
            "structural_virtual_node_count"
        ] == 24

        assert replication[
            "strict_common_semantic_node_count"
        ] == 23

        assert replication[
            "strict_common_query_spec_count"
        ] == 23

        assert replication[
            "query_equivalence_class_count"
        ] == 23

        assert replication[
            "query_equivalent_virtual_node_count"
        ] == 1

        assert replication[
            "equivalence_class_size_histogram"
        ] == {
            "1": 22,
            "2": 1,
        }

        assert replication[
            "equivalence_class_metadata_preserved"
        ] is True

        blueprint = replication[
            "workload_blueprint"
        ]

        assert blueprint[
            "structural_virtual_node_count"
        ] == 24

        assert blueprint[
            "query_equivalence_class_count"
        ] == 23

        assert blueprint[
            "step_count"
        ] == 23

        assert len(
            blueprint["steps"]
        ) == 23

        equivalent_steps = [
            step
            for step in blueprint[
                "steps"
            ]
            if (
                step[
                    "equivalence_class_size"
                ]
                == 2
            )
        ]

        assert len(
            equivalent_steps
        ) == 1

        equivalent_step = (
            equivalent_steps[0]
        )

        assert equivalent_step[
            "query_spec_digest"
        ] == equivalent_step[
            "equivalence_class_id"
        ]

        assert equivalent_step[
            "semantic_id"
        ] == equivalent_step[
            "equivalence_class_id"
        ]

        assert len(
            equivalent_step[
                "semantic_ids"
            ]
        ) == 1

        ids_by_level = (
            equivalent_step[
                "equivalent_"
                "virtual_node_ids_by_level"
            ]
        )

        assert set(
            ids_by_level
        ) == {
            "25",
            "50",
            "75",
            "100",
        }

        for level, node_ids in (
            ids_by_level.items()
        ):
            assert len(node_ids) == 2
            assert len(set(node_ids)) == 2

            assert all(
                (
                    f"_L{level}_"
                    in node_id
                )
                for node_id
                in node_ids
            )


def test_canonical_seed_schedule_has_preregistered_step_histogram(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path
        / "canonical_seed_schedule"
    )

    _generate_campaign(
        campaign_dir,
        seeds=CANONICAL_STAGE10_SEEDS,
    )

    audit = (
        audit_membership_density_campaign(
            campaign_dir
        )
    )

    assert audit[
        "partition_step_count_histogram"
    ] == {
        "23": 2,
        "24": 8,
    }

    assert audit[
        "structural_virtual_node_count_histogram"
    ] == {
        "24": 10,
    }

    step_counts_by_seed = {
        replication["seed"]: (
            replication[
                "workload_blueprint"
            ]["step_count"]
        )
        for replication
        in audit["replications"]
    }

    assert step_counts_by_seed[
        1126922093
    ] == 23

    assert step_counts_by_seed[
        1767972531
    ] == 23

    for seed in (
        set(CANONICAL_STAGE10_SEEDS)
        - {
            1126922093,
            1767972531,
        }
    ):
        assert (
            step_counts_by_seed[seed]
            == 24
        )

    affected_replications = {
        replication[
            "replication_index"
        ]
        for replication
        in audit["replications"]
        if (
            replication[
                "query_equivalent_virtual_node_count"
            ]
            > 0
        )
    }

    assert affected_replications == {
        4,
        9,
    }
