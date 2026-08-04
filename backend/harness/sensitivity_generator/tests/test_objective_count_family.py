
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from backend.harness.sensitivity_generator.families.objective_count_family import (
    CAMPAIGN_GENERATOR_VERSION,
    STRUCTURAL_GENERATOR_VERSION,
    ObjectiveCountFamilySpec,
    generate_objective_count_family,
)
from backend.harness.sensitivity_generator.objective_count_generator import (
    ObjectiveCountConfig,
    generate_objective_count_instance,
)


def _rows(
    path: Path,
) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def _spec(
    output_dir: Path,
) -> ObjectiveCountFamilySpec:
    return ObjectiveCountFamilySpec(
        campaign_id=(
            "objective_count_family_test"
        ),
        levels=(1, 2, 5),
        seeds=(101, 202),
        baseline_constraints_per_objective=2,
        baseline_virtual_nodes_per_objective=6,
        selected_objective_index=0,
        output_dir=str(output_dir),
    )


def test_structural_generator_realises_exact_objective_count(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "structural"

    manifest = (
        generate_objective_count_instance(
            ObjectiveCountConfig(
                instance_id=(
                    "objective_count_structural_test"
                ),
                objective_count=5,
                selected_objective_index=0,
                constraints_per_objective=2,
                virtual_nodes_per_objective=6,
                seed=20260723,
                output_dir=str(output_dir),
            )
        )
    )

    assert (
        manifest.requested_objective_count
        == 5
    )
    assert (
        manifest.realised_objective_count
        == 5
    )
    assert manifest.total_constraint_count == 10
    assert manifest.total_virtual_node_count == 30
    assert manifest.membership_density == 1.0

    document = yaml.safe_load(
        (
            output_dir / "objectives.yaml"
        ).read_text(encoding="utf-8")
    )

    assert len(document["objectives"]) == 5
    assert all(
        len(item["constraints"]) == 2
        for item in document["objectives"]
    )

    stored = json.loads(
        (
            output_dir / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    expected = asdict(manifest)
    expected["objective_ids"] = list(
        expected["objective_ids"]
    )

    assert stored == expected


def test_selected_objective_shape_is_level_invariant(
    tmp_path: Path,
) -> None:
    one = generate_objective_count_instance(
        ObjectiveCountConfig(
            instance_id="campaign_l1_r000",
            objective_count=1,
            selected_objective_index=0,
            constraints_per_objective=2,
            virtual_nodes_per_objective=6,
            seed=901,
            output_dir=str(
                tmp_path / "one"
            ),
        )
    )

    five = generate_objective_count_instance(
        ObjectiveCountConfig(
            instance_id="campaign_l5_r000",
            objective_count=5,
            selected_objective_index=0,
            constraints_per_objective=2,
            virtual_nodes_per_objective=6,
            seed=901,
            output_dir=str(
                tmp_path / "five"
            ),
        )
    )

    assert (
        one.selected_objective_shape_digest
        == five.selected_objective_shape_digest
    )


def test_family_matrix_and_ofat_invariants(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "family"

    manifest = generate_objective_count_family(
        _spec(output_dir)
    )

    assert (
        manifest.campaign_generator_version
        == CAMPAIGN_GENERATOR_VERSION
    )
    assert (
        manifest.structural_generator_version
        == STRUCTURAL_GENERATOR_VERSION
    )
    assert manifest.factor == "objective_count"
    assert manifest.expected_instance_count == 6
    assert manifest.realised_instance_count == 6

    rows = _rows(
        output_dir / "instances.csv"
    )

    assert len(rows) == 6

    assert {
        int(row["factor_level"])
        for row in rows
    } == {1, 2, 5}

    shapes: dict[
        tuple[int, int],
        set[str],
    ] = {}

    for row in rows:
        level = int(row["factor_level"])

        assert row["factor"] == "objective_count"
        assert int(
            row["realised_objective_count"]
        ) == level
        assert int(
            row["requested_constraint_count"]
        ) == 2
        assert int(
            row["realised_constraint_count"]
        ) == 2
        assert int(
            row["requested_virtual_node_count"]
        ) == 6
        assert int(
            row["realised_virtual_node_count"]
        ) == 6
        assert int(
            row["total_constraint_count"]
        ) == level * 2
        assert int(
            row["total_virtual_node_count"]
        ) == level * 6
        assert float(
            row["membership_density"]
        ) == 1.0

        key = (
            int(row["replication_index"]),
            int(row["seed"]),
        )

        shapes.setdefault(
            key,
            set(),
        ).add(
            row[
                "selected_objective_shape_digest"
            ]
        )

        document = yaml.safe_load(
            (
                output_dir
                / row["relative_instance_dir"]
                / "objectives.yaml"
            ).read_text(encoding="utf-8")
        )

        assert (
            len(document["objectives"])
            == level
        )

    assert all(
        len(digests) == 1
        for digests in shapes.values()
    )


def test_family_is_deterministic_across_directories(
    tmp_path: Path,
) -> None:
    first_spec = _spec(
        tmp_path / "first"
    )

    second_spec = ObjectiveCountFamilySpec(
        **{
            **asdict(first_spec),
            "output_dir": str(
                tmp_path / "second"
            ),
        }
    )

    first = generate_objective_count_family(
        first_spec
    )
    second = generate_objective_count_family(
        second_spec
    )

    assert (
        first.campaign_spec_digest
        == second.campaign_spec_digest
    )
    assert (
        first.campaign_digest
        == second.campaign_digest
    )
    assert _rows(
        tmp_path / "first" / "instances.csv"
    ) == _rows(
        tmp_path / "second" / "instances.csv"
    )


@pytest.mark.parametrize(
    (
        "levels",
        "selected_index",
    ),
    (
        ((), 0),
        ((0,), 0),
        ((1,), -1),
        ((1,), 1),
    ),
)
def test_invalid_family_spec_is_rejected(
    tmp_path: Path,
    levels: tuple[int, ...],
    selected_index: int,
) -> None:
    with pytest.raises(ValueError):
        generate_objective_count_family(
            ObjectiveCountFamilySpec(
                campaign_id="invalid",
                levels=levels,
                seeds=(101,),
                baseline_constraints_per_objective=2,
                baseline_virtual_nodes_per_objective=6,
                selected_objective_index=(
                    selected_index
                ),
                output_dir=str(
                    tmp_path
                    / (
                        f"invalid_{len(levels)}_"
                        f"{selected_index}"
                    )
                ),
            )
        )
