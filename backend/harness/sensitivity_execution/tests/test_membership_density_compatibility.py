from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

import backend.harness.sensitivity_execution.execute_controlled_family as executor
from backend.harness.sensitivity_generator.families.controlled_families import (
    ControlledFamilySpec,
    generate_controlled_family,
)
from backend.harness.sensitivity_generator.families.membership_density_family import (
    MembershipDensityFamilySpec,
    generate_membership_density_family,
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert isinstance(value, dict)

    return value


def generate_legacy_campaign(
    output_dir: Path,
) -> dict[str, Any]:
    generate_controlled_family(
        ControlledFamilySpec(
            campaign_id="e3_legacy_profile_test",
            factor="constraint_count",
            levels=(2,),
            seeds=(101,),
            baseline_constraint_count=4,
            baseline_virtual_node_count=24,
            output_dir=str(output_dir),
        )
    )

    return read_json(
        output_dir / "campaign_manifest.json"
    )


def generate_density_campaign(
    output_dir: Path,
) -> dict[str, Any]:
    generate_membership_density_family(
        MembershipDensityFamilySpec(
            campaign_id="e3_density_profile_test",
            levels=(25,),
            seeds=(101,),
            baseline_constraint_count=4,
            baseline_virtual_node_count=24,
            output_dir=str(output_dir),
        )
    )

    return read_json(
        output_dir / "campaign_manifest.json"
    )


def test_executor_registers_exact_generator_profiles() -> None:
    assert executor.E3_EXECUTOR_VERSION == (
        "mcad-sensitivity-e3-v2"
    )

    assert (
        executor.SUPPORTED_GENERATOR_VERSION_PAIRS
        == {
            "constraint_count": (
                "mcad-sensitivity-e2.2-v1",
                "mcad-sensitivity-e2.1-v1",
            ),
            "virtual_node_count": (
                "mcad-sensitivity-e2.2-v1",
                "mcad-sensitivity-e2.1-v1",
            ),
            "membership_density": (
                "mcad-sensitivity-e2.2-"
                "membership-density-v1",
                "mcad-sensitivity-e2.1-"
                "membership-density-v1",
            ),
        }
    )


def test_legacy_campaign_remains_accepted(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "legacy"

    manifest = generate_legacy_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    assert len(instances) == 1
    assert instances[0].factor == "constraint_count"
    assert instances[0].generator_version == (
        "mcad-sensitivity-e2.1-v1"
    )


def test_density_campaign_is_accepted(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "density"

    manifest = generate_density_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    assert len(instances) == 1
    assert instances[0].factor == "membership_density"
    assert instances[0].factor_level == 25
    assert instances[0].generator_version == (
        "mcad-sensitivity-e2.1-"
        "membership-density-v1"
    )


def test_unknown_factor_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "unknown"

    manifest = generate_density_campaign(
        campaign_dir
    )

    manifest["factor"] = "unknown_factor"

    with pytest.raises(
        executor.E3ExecutionError,
        match="Unsupported controlled-experiment factor",
    ):
        executor._discover_all_instances(
            campaign_dir=campaign_dir,
            campaign_manifest=manifest,
        )


def test_cross_factor_version_pair_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "cross_pair"

    manifest = generate_density_campaign(
        campaign_dir
    )

    manifest["factor"] = "constraint_count"

    with pytest.raises(
        executor.E3ExecutionError,
        match="Unsupported E2.2 campaign generator version",
    ):
        executor._discover_all_instances(
            campaign_dir=campaign_dir,
            campaign_manifest=manifest,
        )


def test_campaign_structural_version_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "campaign_structural_mismatch"
    )

    manifest = generate_density_campaign(
        campaign_dir
    )

    manifest["structural_generator_version"] = (
        "mcad-sensitivity-e2.1-v1"
    )

    with pytest.raises(
        executor.E3ExecutionError,
        match="Unsupported E2.1 structural generator version",
    ):
        executor._discover_all_instances(
            campaign_dir=campaign_dir,
            campaign_manifest=manifest,
        )


def test_instance_generator_profile_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "instance_generator_mismatch"
    )

    manifest = generate_density_campaign(
        campaign_dir
    )

    instances_csv = (
        campaign_dir / "instances.csv"
    )

    with instances_csv.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    assert len(rows) == 1

    row = rows[0]

    row["generator_version"] = (
        "mcad-sensitivity-e2.1-v1"
    )

    with instances_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    instance_manifest_path = (
        campaign_dir
        / row["relative_instance_dir"]
        / "manifest.json"
    )

    instance_manifest = read_json(
        instance_manifest_path
    )

    instance_manifest["generator_version"] = (
        "mcad-sensitivity-e2.1-v1"
    )

    instance_manifest_path.write_text(
        json.dumps(
            instance_manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        executor.E3ExecutionError,
        match="unexpected generator version",
    ):
        executor._discover_all_instances(
            campaign_dir=campaign_dir,
            campaign_manifest=manifest,
        )


def test_instance_evidence_uses_actual_campaign_version(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "evidence"

    manifest = generate_density_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    instance = instances[0]

    inputs = executor.ExecutionInputs(
        execution_spec_path=(
            tmp_path / "execution_spec.json"
        ),
        execution_spec={
            "execution_id": "density-evidence-test",
        },
        workload_path=(
            tmp_path / "workload.json"
        ),
        workload={
            "workload_id": "density-workload",
            "objective_id": instance.objective_id,
        },
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
        output_dir=tmp_path / "output",
        instances=instances,
    )

    evidence = executor._base_instance_manifest(
        inputs=inputs,
        instance=instance,
        session_id="density-session",
    )

    assert evidence[
        "campaign_generator_version"
    ] == (
        "mcad-sensitivity-e2.2-"
        "membership-density-v1"
    )

    assert evidence[
        "structural_generator_version"
    ] == (
        "mcad-sensitivity-e2.1-"
        "membership-density-v1"
    )
