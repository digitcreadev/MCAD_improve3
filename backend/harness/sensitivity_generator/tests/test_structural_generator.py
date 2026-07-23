from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from backend.harness.sensitivity_generator.structural_generator import (
    StructuralConfig,
    generate_structural_instance,
)


def make_config(
    tmp_path: Path,
    *,
    constraints: int,
    nvs: int,
    seed: int,
    name: str,
    objective_id: str | None = None,
) -> StructuralConfig:
    return StructuralConfig(
        objective_id=objective_id or f"O_{name}",
        n_constraints=constraints,
        n_virtual_nodes=nvs,
        seed=seed,
        output_dir=str(tmp_path / name),
    )


def test_exact_requested_counts(
    tmp_path: Path,
) -> None:
    manifest = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=12,
            seed=11,
            name="exact",
        )
    )

    assert manifest.realised_constraint_count == 4
    assert manifest.realised_virtual_node_count == 12
    assert manifest.requirement_set_count == 4
    assert (
        manifest.requirement_membership_link_count
        == 12
    )
    assert manifest.membership_density == 1.0


def test_constraint_count_varies_independently(
    tmp_path: Path,
) -> None:
    low = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=2,
            nvs=16,
            seed=21,
            name="constraints_low",
            objective_id="O_CONSTRAINT_AXIS",
        )
    )

    high = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=8,
            nvs=16,
            seed=21,
            name="constraints_high",
            objective_id="O_CONSTRAINT_AXIS",
        )
    )

    assert low.realised_constraint_count == 2
    assert high.realised_constraint_count == 8

    assert low.realised_virtual_node_count == 16
    assert high.realised_virtual_node_count == 16

    assert low.seed == high.seed
    assert low.objective_id == high.objective_id


def test_virtual_node_count_varies_independently(
    tmp_path: Path,
) -> None:
    low = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=8,
            seed=31,
            name="nvs_low",
            objective_id="O_NV_AXIS",
        )
    )

    high = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=32,
            seed=31,
            name="nvs_high",
            objective_id="O_NV_AXIS",
        )
    )

    assert low.realised_constraint_count == 4
    assert high.realised_constraint_count == 4

    assert low.realised_virtual_node_count == 8
    assert high.realised_virtual_node_count == 32

    assert low.seed == high.seed
    assert low.objective_id == high.objective_id


def test_same_seed_is_deterministic(
    tmp_path: Path,
) -> None:
    first = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=12,
            seed=41,
            name="same_seed_run_1",
            objective_id="O_DETERMINISM",
        )
    )

    second = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=12,
            seed=41,
            name="same_seed_run_2",
            objective_id="O_DETERMINISM",
        )
    )

    assert (
        first.configuration_digest
        == second.configuration_digest
    )
    assert first.instance_digest == second.instance_digest


def test_different_seeds_change_instance(
    tmp_path: Path,
) -> None:
    first = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=12,
            seed=51,
            name="different_seed_run_1",
            objective_id="O_SEED_VARIATION",
        )
    )

    second = generate_structural_instance(
        make_config(
            tmp_path,
            constraints=4,
            nvs=12,
            seed=52,
            name="different_seed_run_2",
            objective_id="O_SEED_VARIATION",
        )
    )

    assert (
        first.configuration_digest
        != second.configuration_digest
    )
    assert first.instance_digest != second.instance_digest


def test_invalid_nv_count_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be >= n_constraints",
    ):
        generate_structural_instance(
            make_config(
                tmp_path,
                constraints=8,
                nvs=4,
                seed=61,
                name="invalid",
            )
        )


def test_no_production_evaluation_call() -> None:
    from backend.harness.sensitivity_generator import (
        structural_generator,
    )

    source = inspect.getsource(
        structural_generator.generate_structural_instance
    )

    forbidden = [
        ".sat(",
        ".real(",
        ".ceval(",
        ".phi(",
    ]

    for token in forbidden:
        assert token not in source
