from __future__ import annotations

from pathlib import Path

import pytest

from backend.harness.sensitivity_generator.membership_density_generator import (
    GENERATOR_VERSION,
    MembershipDensityConfig,
    MembershipDensityGenerationError,
    balanced_membership_allocation,
    generate_membership_density_instance,
)
from backend.harness.sensitivity_generator.oracles.membership_density_oracle import (
    assert_valid_density,
    load_objectives_yaml,
)


@pytest.mark.parametrize(
    (
        "level",
        "expected_count",
        "expected_allocation",
    ),
    (
        (25, 6, (2, 2, 1, 1)),
        (50, 12, (3, 3, 3, 3)),
        (75, 18, (5, 5, 4, 4)),
        (100, 24, (6, 6, 6, 6)),
    ),
)
def test_exact_density_levels(
    tmp_path: Path,
    level: int,
    expected_count: int,
    expected_allocation: tuple[int, ...],
) -> None:
    output_dir = (
        tmp_path / f"density_{level}"
    )

    manifest = (
        generate_membership_density_instance(
            MembershipDensityConfig(
                objective_id=(
                    f"O_DENSITY_{level}"
                ),
                n_constraints=4,
                n_virtual_nodes=24,
                membership_density_percent=(
                    level
                ),
                seed=101,
                output_dir=str(output_dir),
            )
        )
    )

    assert manifest.generator_version == (
        GENERATOR_VERSION
    )

    assert (
        manifest.requirement_membership_link_count
        == expected_count
    )

    assert (
        manifest.maximum_membership_link_count
        == 24
    )

    assert manifest.membership_density == (
        level / 100
    )

    assert (
        balanced_membership_allocation(
            (6, 6, 6, 6),
            expected_count,
        )
        == expected_allocation
    )

    document = load_objectives_yaml(
        output_dir / "objectives.yaml"
    )

    observation = assert_valid_density(
        document,
        density_percent=level,
    )

    assert (
        observation.membership_count_by_constraint
        == expected_allocation
    )


def test_same_configuration_is_deterministic(
    tmp_path: Path,
) -> None:
    manifests = []

    for name in ("first", "second"):
        manifests.append(
            generate_membership_density_instance(
                MembershipDensityConfig(
                    objective_id="O_DETERMINISTIC",
                    n_constraints=4,
                    n_virtual_nodes=24,
                    membership_density_percent=50,
                    seed=202,
                    output_dir=str(
                        tmp_path / name
                    ),
                )
            )
        )

    assert (
        manifests[0].configuration_digest
        == manifests[1].configuration_digest
    )

    assert (
        manifests[0].instance_digest
        == manifests[1].instance_digest
    )


def test_inexact_density_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        MembershipDensityGenerationError
    ):
        generate_membership_density_instance(
            MembershipDensityConfig(
                objective_id="O_INEXACT",
                n_constraints=4,
                n_virtual_nodes=24,
                membership_density_percent=33,
                seed=1,
                output_dir=str(
                    tmp_path / "inexact"
                ),
            )
        )


def test_density_cannot_empty_requirement_sets(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        MembershipDensityGenerationError
    ):
        generate_membership_density_instance(
            MembershipDensityConfig(
                objective_id="O_TOO_LOW",
                n_constraints=4,
                n_virtual_nodes=24,
                membership_density_percent=10,
                seed=1,
                output_dir=str(
                    tmp_path / "too_low"
                ),
            )
        )
