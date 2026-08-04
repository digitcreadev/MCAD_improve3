from __future__ import annotations

import csv
import inspect
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.harness.sensitivity_generator.families.controlled_families import (
    CAMPAIGN_GENERATOR_VERSION,
    STRUCTURAL_GENERATOR_VERSION,
    ControlledFamilySpec,
    generate_controlled_family,
)


def make_spec(
    output_dir: Path,
    *,
    campaign_id: str = "e22_test",
    factor: str = "constraint_count",
    levels: tuple[int, ...] = (2, 4, 8),
    seeds: tuple[int, ...] = (
        20260723,
        20260724,
    ),
    baseline_constraint_count: int = 4,
    baseline_virtual_node_count: int = 12,
) -> ControlledFamilySpec:
    return ControlledFamilySpec(
        campaign_id=campaign_id,
        factor=factor,
        levels=levels,
        seeds=seeds,
        baseline_constraint_count=(
            baseline_constraint_count
        ),
        baseline_virtual_node_count=(
            baseline_virtual_node_count
        ),
        output_dir=str(output_dir),
    )


def read_csv(
    path: Path,
) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        return list(
            csv.DictReader(stream)
        )


def test_constraint_family_matrix_and_invariants(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "constraint_family"

    manifest = generate_controlled_family(
        make_spec(
            output_dir,
            factor="constraint_count",
            levels=(2, 4, 8),
            seeds=(101, 202),
            baseline_virtual_node_count=12,
        )
    )

    assert manifest.campaign_generator_version == (
        CAMPAIGN_GENERATOR_VERSION
    )

    assert manifest.structural_generator_version == (
        STRUCTURAL_GENERATOR_VERSION
    )

    assert manifest.factor == "constraint_count"
    assert manifest.level_count == 3
    assert manifest.replication_count == 2
    assert manifest.expected_instance_count == 6
    assert manifest.realised_instance_count == 6

    rows = read_csv(
        output_dir / "instances.csv"
    )

    assert len(rows) == 6

    assert {
        int(row["factor_level"])
        for row in rows
    } == {2, 4, 8}

    assert {
        int(row["seed"])
        for row in rows
    } == {101, 202}

    assert {
        int(row["requested_virtual_node_count"])
        for row in rows
    } == {12}

    for row in rows:
        assert (
            int(row["requested_constraint_count"])
            == int(row["factor_level"])
        )

        assert float(
            row["membership_density"]
        ) == 1.0


def test_virtual_node_family_matrix_and_invariants(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "nv_family"

    manifest = generate_controlled_family(
        make_spec(
            output_dir,
            factor="virtual_node_count",
            levels=(5, 10, 20),
            seeds=(303,),
            baseline_constraint_count=4,
        )
    )

    assert manifest.factor == "virtual_node_count"
    assert manifest.expected_instance_count == 3
    assert manifest.realised_instance_count == 3

    rows = read_csv(
        output_dir / "instances.csv"
    )

    assert {
        int(row["requested_constraint_count"])
        for row in rows
    } == {4}

    for row in rows:
        assert (
            int(row["requested_virtual_node_count"])
            == int(row["factor_level"])
        )


def test_required_outputs_exist(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "outputs"

    generate_controlled_family(
        make_spec(
            output_dir,
            levels=(2, 3),
            seeds=(111, 222),
        )
    )

    assert (
        output_dir / "campaign_spec.json"
    ).is_file()

    assert (
        output_dir / "campaign_manifest.json"
    ).is_file()

    assert (
        output_dir / "instances.csv"
    ).is_file()

    rows = read_csv(
        output_dir / "instances.csv"
    )

    for row in rows:
        instance_dir = (
            output_dir
            / row["relative_instance_dir"]
        )

        assert (
            instance_dir / "manifest.json"
        ).is_file()

        assert (
            instance_dir / "objectives.yaml"
        ).is_file()


def test_same_spec_is_deterministic_across_directories(
    tmp_path: Path,
) -> None:
    first = generate_controlled_family(
        make_spec(
            tmp_path / "first",
            campaign_id="deterministic_campaign",
            levels=(3, 6),
            seeds=(701, 702),
        )
    )

    second = generate_controlled_family(
        make_spec(
            tmp_path / "second",
            campaign_id="deterministic_campaign",
            levels=(3, 6),
            seeds=(701, 702),
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

    first_rows = read_csv(
        tmp_path / "first" / "instances.csv"
    )

    second_rows = read_csv(
        tmp_path / "second" / "instances.csv"
    )

    assert first_rows == second_rows


def test_seed_change_changes_campaign_digest(
    tmp_path: Path,
) -> None:
    first = generate_controlled_family(
        make_spec(
            tmp_path / "seed_first",
            campaign_id="seed_campaign",
            levels=(4,),
            seeds=(1001,),
        )
    )

    second = generate_controlled_family(
        make_spec(
            tmp_path / "seed_second",
            campaign_id="seed_campaign",
            levels=(4,),
            seeds=(1002,),
        )
    )

    assert (
        first.campaign_spec_digest
        != second.campaign_spec_digest
    )

    assert (
        first.campaign_digest
        != second.campaign_digest
    )


@pytest.mark.parametrize(
    ("factor", "levels", "seeds"),
    [
        ("unsupported", (2,), (1,)),
        ("constraint_count", (), (1,)),
        ("constraint_count", (0,), (1,)),
        ("constraint_count", (-1,), (1,)),
        ("constraint_count", (2, 2), (1,)),
        ("constraint_count", (2,), ()),
        ("constraint_count", (2,), (1, 1)),
        ("constraint_count", (2,), (0,)),
    ],
)
def test_invalid_specs_are_rejected(
    tmp_path: Path,
    factor: str,
    levels: tuple[int, ...],
    seeds: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        generate_controlled_family(
            make_spec(
                tmp_path / (
                    f"invalid_{factor}_"
                    f"{len(levels)}_"
                    f"{len(seeds)}"
                ),
                factor=factor,
                levels=levels,
                seeds=seeds,
            )
        )


def test_non_empty_output_directory_is_rejected(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "non_empty"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text(
        "do not overwrite\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="absent or empty",
    ):
        generate_controlled_family(
            make_spec(
                output_dir,
                levels=(2,),
                seeds=(1,),
            )
        )


def test_manifest_file_matches_returned_manifest(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "manifest_match"

    manifest = generate_controlled_family(
        make_spec(
            output_dir,
            levels=(2,),
            seeds=(777,),
        )
    )

    stored = json.loads(
        (
            output_dir
            / "campaign_manifest.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    expected = asdict(manifest)
    expected["levels"] = list(
        expected["levels"]
    )
    expected["seeds"] = list(
        expected["seeds"]
    )

    assert stored == expected


def test_no_production_evaluation_call() -> None:
    import backend.harness.sensitivity_generator.families.controlled_families as module

    source = inspect.getsource(
        module
    )

    forbidden_call_tokens = (
        ".sat(",
        ".real(",
        ".ceval(",
        ".phi(",
    )

    for token in forbidden_call_tokens:
        assert token not in source


def test_objective_count_dispatch_uses_dedicated_profile(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "objective_count_dispatch"

    manifest = generate_controlled_family(
        make_spec(
            output_dir,
            factor="objective_count",
            levels=(1, 2),
            seeds=(101,),
            baseline_constraint_count=2,
            baseline_virtual_node_count=6,
        )
    )

    assert manifest.factor == "objective_count"
    assert manifest.campaign_generator_version == (
        "mcad-sensitivity-e2.2-objective-count-v1"
    )
    assert manifest.structural_generator_version == (
        "mcad-sensitivity-e2.1-objective-count-v1"
    )

    rows = read_csv(
        output_dir / "instances.csv"
    )

    assert len(rows) == 2

    assert {
        int(row["realised_objective_count"])
        for row in rows
    } == {1, 2}
