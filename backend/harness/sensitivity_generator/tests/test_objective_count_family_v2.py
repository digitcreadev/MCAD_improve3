from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.harness.sensitivity_generator.families.objective_count_family_v2 import (
    CAMPAIGN_GENERATOR_VERSION,
    STRUCTURAL_GENERATOR_VERSION,
    ObjectiveCountV2FamilySpec,
    generate_objective_count_family_v2,
)


def _rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _spec(output: Path):
    return ObjectiveCountV2FamilySpec(
        campaign_id="objective_count_v2_family_test",
        levels=(1, 2),
        seeds=(101, 202),
        baseline_constraints_per_objective=8,
        baseline_virtual_nodes_per_objective=32,
        selected_objective_index=0,
        output_dir=str(output),
    )


def test_family_matrix_and_ofat_invariants(tmp_path: Path) -> None:
    output = tmp_path / "family"
    manifest = generate_objective_count_family_v2(_spec(output))
    assert manifest.campaign_generator_version == CAMPAIGN_GENERATOR_VERSION
    assert manifest.structural_generator_version == STRUCTURAL_GENERATOR_VERSION
    assert manifest.expected_instance_count == 4
    rows = _rows(output / "instances.csv")
    assert len(rows) == 4
    for row in rows:
        level = int(row["factor_level"])
        assert int(row["realised_objective_count"]) == level
        assert int(row["total_constraint_count"]) == 8 * level
        assert int(row["useful_virtual_node_count"]) == 24 * level
        assert int(row["irrelevant_virtual_node_count"]) == 8 * level
        assert int(row["total_virtual_node_count"]) == 32 * level
        assert int(row["requirement_set_count"]) == 16 * level
        assert int(row["requirement_membership_link_count"]) == 32 * level
        assert int(row["maximum_membership_link_count"]) == 64 * level
        assert float(row["realised_density"]) == 0.5
        assert row["session_support_policy"] == "union_requirement_sets"


def test_family_is_deterministic(tmp_path: Path) -> None:
    first = _spec(tmp_path / "first")
    second = ObjectiveCountV2FamilySpec(
        **{**asdict(first), "output_dir": str(tmp_path / "second")}
    )
    a = generate_objective_count_family_v2(first)
    b = generate_objective_count_family_v2(second)
    assert a.campaign_spec_digest == b.campaign_spec_digest
    assert a.campaign_digest == b.campaign_digest
    assert _rows(tmp_path / "first" / "instances.csv") == _rows(
        tmp_path / "second" / "instances.csv"
    )


@pytest.mark.parametrize("constraints,nvs", [(2, 32), (8, 6), (7, 28)])
def test_noncanonical_micro_design_is_rejected(
    tmp_path: Path, constraints: int, nvs: int
) -> None:
    with pytest.raises(ValueError):
        generate_objective_count_family_v2(
            ObjectiveCountV2FamilySpec(
                campaign_id="invalid",
                levels=(1,),
                seeds=(101,),
                baseline_constraints_per_objective=constraints,
                baseline_virtual_nodes_per_objective=nvs,
                selected_objective_index=0,
                output_dir=str(tmp_path / f"bad-{constraints}-{nvs}"),
            )
        )
