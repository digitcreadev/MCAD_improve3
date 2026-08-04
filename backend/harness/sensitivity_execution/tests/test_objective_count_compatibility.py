
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import backend.harness.sensitivity_execution.execute_controlled_family as executor
from backend.harness.sensitivity_generator.families.controlled_families import (
    ControlledFamilySpec,
    generate_controlled_family,
)


def _read_json(
    path: Path,
) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert isinstance(value, dict)

    return value


def _generate_campaign(
    output_dir: Path,
) -> dict[str, Any]:
    generate_controlled_family(
        ControlledFamilySpec(
            campaign_id=(
                "e3_objective_count_profile_test"
            ),
            factor="objective_count",
            levels=(2,),
            seeds=(101,),
            baseline_constraint_count=2,
            baseline_virtual_node_count=6,
            output_dir=str(output_dir),
        )
    )

    return _read_json(
        output_dir / "campaign_manifest.json"
    )


def test_objective_count_campaign_is_accepted(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "objective_count"
    )

    manifest = _generate_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    assert len(instances) == 1

    instance = instances[0]

    assert instance.factor == "objective_count"
    assert instance.factor_level == 2
    assert instance.generator_version == (
        "mcad-sensitivity-e2.1-"
        "objective-count-v1"
    )

    instance_manifest = _read_json(
        instance.manifest_path
    )

    assert (
        instance_manifest[
            "realised_objective_count"
        ]
        == 2
    )
    assert (
        instance_manifest[
            "selected_objective_id"
        ]
        == instance.objective_id
    )


def test_objective_count_cross_profile_is_rejected(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "cross_profile"
    )

    manifest = _generate_campaign(
        campaign_dir
    )

    manifest["factor"] = "constraint_count"

    with pytest.raises(
        executor.E3ExecutionError,
        match=(
            "Unsupported E2.2 campaign "
            "generator version"
        ),
    ):
        executor._discover_all_instances(
            campaign_dir=campaign_dir,
            campaign_manifest=manifest,
        )


def test_objective_count_evidence_uses_exact_versions(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "evidence"

    manifest = _generate_campaign(
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
            "execution_id": (
                "objective-count-evidence-test"
            ),
        },
        workload_path=(
            tmp_path / "workload.json"
        ),
        workload={
            "workload_id": (
                "objective-count-workload"
            ),
            "objective_id": (
                instance.objective_id
            ),
        },
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
        output_dir=tmp_path / "output",
        instances=instances,
    )

    evidence = executor._base_instance_manifest(
        inputs=inputs,
        instance=instance,
        session_id=(
            "objective-count-session"
        ),
    )

    assert evidence[
        "campaign_generator_version"
    ] == (
        "mcad-sensitivity-e2.2-"
        "objective-count-v1"
    )

    assert evidence[
        "structural_generator_version"
    ] == (
        "mcad-sensitivity-e2.1-"
        "objective-count-v1"
    )


def test_objective_count_bootstrap_loads_complete_catalogue(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "objective_count_bootstrap"
    )

    manifest = _generate_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    assert len(instances) == 1

    instance = instances[0]

    ckg = executor._build_instance_ckg(
        instance=instance,
        runtime_output_dir=(
            tmp_path / "runtime"
        ),
    )

    instance_manifest = _read_json(
        instance.manifest_path
    )

    expected_objective_ids = set(
        instance_manifest["objective_ids"]
    )

    assert len(expected_objective_ids) == 2
    assert set(ckg.objectives) == (
        expected_objective_ids
    )

    assert instance.objective_id == (
        instance_manifest[
            "selected_objective_id"
        ]
    )

    assert instance.objective_id in (
        ckg.objectives
    )

    assert not ckg.history
    assert not ckg.session_coverage
    assert not ckg.session_weighted_coverage
    assert not ckg.session_resource_coverage


def test_objective_count_bootstrap_rejects_catalogue_cardinality_mismatch(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "objective_count_bad_cardinality"
    )

    manifest = _generate_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    instance = instances[0]

    instance_manifest = _read_json(
        instance.manifest_path
    )

    instance_manifest["objective_ids"] = (
        instance_manifest["objective_ids"][:1]
    )

    instance.manifest_path.write_text(
        json.dumps(
            instance_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        executor.E3ExecutionError,
        match=(
            "objective_ids cardinality differs "
            "from realised_objective_count"
        ),
    ):
        executor._build_instance_ckg(
            instance=instance,
            runtime_output_dir=(
                tmp_path / "runtime_bad_cardinality"
            ),
        )


def test_objective_count_bootstrap_rejects_selected_objective_mismatch(
    tmp_path: Path,
) -> None:
    campaign_dir = (
        tmp_path / "objective_count_bad_selected"
    )

    manifest = _generate_campaign(
        campaign_dir
    )

    instances = executor._discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=manifest,
    )

    instance = instances[0]

    instance_manifest = _read_json(
        instance.manifest_path
    )

    alternate_objective_id = next(
        objective_id
        for objective_id
        in instance_manifest["objective_ids"]
        if objective_id != instance.objective_id
    )

    instance_manifest[
        "selected_objective_id"
    ] = alternate_objective_id

    instance.manifest_path.write_text(
        json.dumps(
            instance_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        executor.E3ExecutionError,
        match=(
            "selected_objective_id differs "
            "from instances.csv"
        ),
    ):
        executor._build_instance_ckg(
            instance=instance,
            runtime_output_dir=(
                tmp_path / "runtime_bad_selected"
            ),
        )
