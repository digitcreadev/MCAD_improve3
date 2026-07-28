from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.harness.sensitivity_generator.families.membership_density_family import (
    CAMPAIGN_GENERATOR_VERSION,
    FACTOR,
    MembershipDensityFamilySpec,
    generate_membership_density_family,
)
from backend.harness.sensitivity_generator.membership_density_generator import (
    GENERATOR_VERSION,
)


LEVELS = (25, 50, 75, 100)
SEEDS = (101, 202)


def make_spec(
    output_dir: Path,
) -> MembershipDensityFamilySpec:
    return MembershipDensityFamilySpec(
        campaign_id=(
            "sa4_membership_density_test"
        ),
        levels=LEVELS,
        seeds=SEEDS,
        baseline_constraint_count=4,
        baseline_virtual_node_count=24,
        output_dir=str(output_dir),
    )


def test_complete_family_and_oracle(
    tmp_path: Path,
) -> None:
    output_dir = (
        tmp_path / "campaign"
    )

    manifest = (
        generate_membership_density_family(
            make_spec(output_dir)
        )
    )

    assert manifest.factor == FACTOR

    assert (
        manifest.campaign_generator_version
        == CAMPAIGN_GENERATOR_VERSION
    )

    assert (
        manifest.structural_generator_version
        == GENERATOR_VERSION
    )

    assert manifest.levels == LEVELS
    assert manifest.seeds == SEEDS
    assert manifest.realised_instance_count == 8

    with (
        output_dir / "instances.csv"
    ).open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 8

    assert {
        int(row["factor_level"])
        for row in rows
    } == set(LEVELS)

    assert {
        int(row["replication_index"])
        for row in rows
    } == {0, 1}

    expected_counts = {
        25: 6,
        50: 12,
        75: 18,
        100: 24,
    }

    for row in rows:
        level = int(
            row["factor_level"]
        )

        assert row["factor"] == FACTOR

        assert (
            int(
                row[
                    "requirement_membership_link_count"
                ]
            )
            == expected_counts[level]
        )

        assert (
            float(
                row["membership_density"]
            )
            == level / 100
        )

    oracle = json.loads(
        (
            output_dir
            / "oracle_validation.json"
        ).read_text(encoding="utf-8")
    )

    assert oracle["status"] == "success"
    assert set(
        oracle["replications"]
    ) == {"0", "1"}


def test_family_digest_is_deterministic(
    tmp_path: Path,
) -> None:
    first = (
        generate_membership_density_family(
            make_spec(
                tmp_path / "first"
            )
        )
    )

    second = (
        generate_membership_density_family(
            make_spec(
                tmp_path / "second"
            )
        )
    )

    assert (
        first.campaign_spec_digest
        == second.campaign_spec_digest
    )

    assert (
        first.campaign_digest
        == second.campaign_digest
    )
