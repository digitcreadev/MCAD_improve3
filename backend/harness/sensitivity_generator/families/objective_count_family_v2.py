from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from backend.harness.sensitivity_generator.families.controlled_families import (
    ensure_positive_integer,
    normalise_identifier,
    prepare_output_directory,
    relative_instance_directory,
    sha256_payload,
    validate_unique_positive_values,
    write_json,
)
from backend.harness.sensitivity_generator.objective_count_generator_v2 import (
    CONSTRAINTS_PER_OBJECTIVE,
    GENERATOR_VERSION as STRUCTURAL_GENERATOR_VERSION,
    SESSION_SUPPORT_POLICY,
    VIRTUAL_NODES_PER_OBJECTIVE,
    ObjectiveCountV2Config,
    ObjectiveCountV2StructuralManifest,
    generate_objective_count_instance_v2,
)

CAMPAIGN_GENERATOR_VERSION = "mcad-sensitivity-e2.2-objective-count-v2"
FACTOR = "objective_count"


@dataclass(frozen=True)
class ObjectiveCountV2FamilySpec:
    campaign_id: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraints_per_objective: int
    baseline_virtual_nodes_per_objective: int
    selected_objective_index: int
    output_dir: str


@dataclass(frozen=True)
class ObjectiveCountV2InstanceRecord:
    campaign_id: str
    factor: str
    factor_level: int
    replication_index: int
    seed: int
    objective_id: str
    relative_instance_dir: str
    requested_constraint_count: int
    realised_constraint_count: int
    requested_virtual_node_count: int
    realised_virtual_node_count: int
    configuration_digest: str
    instance_digest: str
    generator_version: str
    requested_objective_count: int
    realised_objective_count: int
    objective_count: int
    selected_objective_index: int
    selected_objective_shape_digest: str
    selected_objective_constraint_count: int
    total_constraint_count: int
    useful_virtual_node_count: int
    irrelevant_virtual_node_count: int
    total_virtual_node_count: int
    requirement_set_count: int
    requirement_membership_link_count: int
    maximum_membership_link_count: int
    membership_density: float
    realised_density: float
    session_support_policy: str
    graph_node_count: int
    graph_edge_count: int


@dataclass(frozen=True)
class ObjectiveCountV2FamilyManifest:
    campaign_generator_version: str
    structural_generator_version: str
    campaign_id: str
    factor: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraints_per_objective: int
    baseline_virtual_nodes_per_objective: int
    selected_objective_index: int
    session_support_policy: str
    level_count: int
    replication_count: int
    expected_instance_count: int
    realised_instance_count: int
    campaign_spec_digest: str
    campaign_digest: str


def validate_spec(spec: ObjectiveCountV2FamilySpec) -> None:
    normalise_identifier(spec.campaign_id)
    validate_unique_positive_values("levels", spec.levels)
    validate_unique_positive_values("seeds", spec.seeds)
    ensure_positive_integer(
        "baseline_constraints_per_objective",
        spec.baseline_constraints_per_objective,
    )
    ensure_positive_integer(
        "baseline_virtual_nodes_per_objective",
        spec.baseline_virtual_nodes_per_objective,
    )
    if spec.baseline_constraints_per_objective != CONSTRAINTS_PER_OBJECTIVE:
        raise ValueError("objective-count v2 requires baseline constraint count 8.")
    if spec.baseline_virtual_nodes_per_objective != VIRTUAL_NODES_PER_OBJECTIVE:
        raise ValueError("objective-count v2 requires baseline virtual-node count 32.")
    if (
        isinstance(spec.selected_objective_index, bool)
        or not isinstance(spec.selected_objective_index, int)
        or spec.selected_objective_index < 0
        or spec.selected_objective_index >= min(spec.levels)
    ):
        raise ValueError(
            "selected_objective_index must exist at every objective-count level."
        )
    if not str(spec.output_dir).strip():
        raise ValueError("output_dir must not be empty.")


def stable_spec_payload(spec: ObjectiveCountV2FamilySpec) -> dict[str, object]:
    return {
        "campaign_generator_version": CAMPAIGN_GENERATOR_VERSION,
        "structural_generator_version": STRUCTURAL_GENERATOR_VERSION,
        "campaign_id": spec.campaign_id,
        "factor": FACTOR,
        "levels": list(spec.levels),
        "seeds": list(spec.seeds),
        "baseline_constraints_per_objective": (
            spec.baseline_constraints_per_objective
        ),
        "baseline_virtual_nodes_per_objective": (
            spec.baseline_virtual_nodes_per_objective
        ),
        "selected_objective_index": spec.selected_objective_index,
        "session_support_policy": SESSION_SUPPORT_POLICY,
    }


def _instance_id(
    spec: ObjectiveCountV2FamilySpec,
    level: int,
    replication_index: int,
) -> str:
    return (
        f"{normalise_identifier(spec.campaign_id).upper()}_"
        f"OBJECTIVE_COUNT_L{level}_R{replication_index:03d}"
    )


def _record(
    spec: ObjectiveCountV2FamilySpec,
    level: int,
    replication_index: int,
    seed: int,
    relative_dir: Path,
    manifest: ObjectiveCountV2StructuralManifest,
) -> ObjectiveCountV2InstanceRecord:
    if manifest.generator_version != STRUCTURAL_GENERATOR_VERSION:
        raise ValueError("Unexpected objective-count v2 structural version.")
    if manifest.realised_objective_count != level:
        raise ValueError("Realised objective count differs from factor level.")
    if manifest.session_support_policy != SESSION_SUPPORT_POLICY:
        raise ValueError("Objective-count v2 support policy changed.")

    return ObjectiveCountV2InstanceRecord(
        campaign_id=spec.campaign_id,
        factor=FACTOR,
        factor_level=level,
        replication_index=replication_index,
        seed=seed,
        objective_id=manifest.objective_id,
        relative_instance_dir=relative_dir.as_posix(),
        requested_constraint_count=manifest.requested_constraint_count,
        realised_constraint_count=manifest.realised_constraint_count,
        requested_virtual_node_count=manifest.requested_virtual_node_count,
        realised_virtual_node_count=manifest.realised_virtual_node_count,
        configuration_digest=manifest.configuration_digest,
        instance_digest=manifest.instance_digest,
        generator_version=manifest.generator_version,
        requested_objective_count=manifest.requested_objective_count,
        realised_objective_count=manifest.realised_objective_count,
        objective_count=manifest.objective_count,
        selected_objective_index=manifest.selected_objective_index,
        selected_objective_shape_digest=manifest.selected_objective_shape_digest,
        selected_objective_constraint_count=(
            manifest.selected_objective_constraint_count
        ),
        total_constraint_count=manifest.total_constraint_count,
        useful_virtual_node_count=manifest.useful_virtual_node_count,
        irrelevant_virtual_node_count=manifest.irrelevant_virtual_node_count,
        total_virtual_node_count=manifest.total_virtual_node_count,
        requirement_set_count=manifest.requirement_set_count,
        requirement_membership_link_count=(
            manifest.requirement_membership_link_count
        ),
        maximum_membership_link_count=manifest.maximum_membership_link_count,
        membership_density=manifest.membership_density,
        realised_density=manifest.realised_density,
        session_support_policy=manifest.session_support_policy,
        graph_node_count=manifest.graph_node_count,
        graph_edge_count=manifest.graph_edge_count,
    )


def _validate_matrix(
    spec: ObjectiveCountV2FamilySpec,
    records: Sequence[ObjectiveCountV2InstanceRecord],
) -> None:
    expected = {
        (level, replication_index, seed)
        for level in spec.levels
        for replication_index, seed in enumerate(spec.seeds)
    }
    realised = {
        (record.factor_level, record.replication_index, record.seed)
        for record in records
    }
    if realised != expected or len(records) != len(expected):
        raise ValueError("Incomplete or duplicated objective-count v2 matrix.")


def _validate_ofat(
    spec: ObjectiveCountV2FamilySpec,
    records: Sequence[ObjectiveCountV2InstanceRecord],
) -> None:
    selected_shapes: dict[tuple[int, int], set[str]] = {}
    for record in records:
        level = record.factor_level
        if record.factor != FACTOR:
            raise ValueError("Instance factor differs from objective_count.")
        if record.generator_version != STRUCTURAL_GENERATOR_VERSION:
            raise ValueError("Objective-count v2 structural binding changed.")
        if record.realised_objective_count != level:
            raise ValueError("Objective-count factor level was not realised.")
        if record.realised_constraint_count != CONSTRAINTS_PER_OBJECTIVE:
            raise ValueError("Selected-objective constraint baseline changed.")
        if record.realised_virtual_node_count != VIRTUAL_NODES_PER_OBJECTIVE:
            raise ValueError("Selected-objective virtual-node baseline changed.")
        if record.total_constraint_count != level * CONSTRAINTS_PER_OBJECTIVE:
            raise ValueError("Total constraint count is inconsistent.")
        if record.total_virtual_node_count != level * VIRTUAL_NODES_PER_OBJECTIVE:
            raise ValueError("Total virtual-node count is inconsistent.")
        if record.useful_virtual_node_count != level * 24:
            raise ValueError("Useful virtual-node count is inconsistent.")
        if record.irrelevant_virtual_node_count != level * 8:
            raise ValueError("Irrelevant virtual-node count is inconsistent.")
        if record.requirement_set_count != level * 16:
            raise ValueError("Requirement-set count is inconsistent.")
        if record.requirement_membership_link_count != level * 32:
            raise ValueError("Membership-link count is inconsistent.")
        if record.maximum_membership_link_count != level * 64:
            raise ValueError("Maximum membership-link count is inconsistent.")
        if record.realised_density != 0.5 or record.membership_density != 0.5:
            raise ValueError("Objective-count v2 requires density 0.5.")
        if record.session_support_policy != SESSION_SUPPORT_POLICY:
            raise ValueError("Objective-count v2 support policy changed.")
        selected_shapes.setdefault(
            (record.replication_index, record.seed), set()
        ).add(record.selected_objective_shape_digest)

    if any(len(digests) != 1 for digests in selected_shapes.values()):
        raise ValueError(
            "Selected-objective structure changed across objective-count levels."
        )


def _write_csv(
    path: Path,
    records: Sequence[ObjectiveCountV2InstanceRecord],
) -> None:
    rows = [asdict(record) for record in records]
    if not rows:
        raise ValueError("Cannot write an empty objective-count v2 instances.csv.")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_objective_count_family_v2(
    spec: ObjectiveCountV2FamilySpec,
) -> ObjectiveCountV2FamilyManifest:
    validate_spec(spec)
    output_dir = Path(spec.output_dir)
    prepare_output_directory(output_dir)

    stable_spec = stable_spec_payload(spec)
    spec_digest = sha256_payload(stable_spec)
    write_json(
        output_dir / "campaign_spec.json",
        {**stable_spec, "campaign_spec_digest": spec_digest},
    )

    records: list[ObjectiveCountV2InstanceRecord] = []
    for level in spec.levels:
        for replication_index, seed in enumerate(spec.seeds):
            relative_dir = relative_instance_directory(
                level, replication_index, seed
            )
            structural = generate_objective_count_instance_v2(
                ObjectiveCountV2Config(
                    instance_id=_instance_id(spec, level, replication_index),
                    objective_count=level,
                    selected_objective_index=spec.selected_objective_index,
                    constraints_per_objective=(
                        spec.baseline_constraints_per_objective
                    ),
                    virtual_nodes_per_objective=(
                        spec.baseline_virtual_nodes_per_objective
                    ),
                    seed=seed,
                    output_dir=str(output_dir / relative_dir),
                )
            )
            records.append(
                _record(
                    spec,
                    level,
                    replication_index,
                    seed,
                    relative_dir,
                    structural,
                )
            )

    _validate_matrix(spec, records)
    _validate_ofat(spec, records)

    for record in records:
        instance_dir = output_dir / record.relative_instance_dir
        if not (instance_dir / "manifest.json").is_file():
            raise ValueError(f"Missing manifest: {instance_dir}")
        if not (instance_dir / "objectives.yaml").is_file():
            raise ValueError(f"Missing objectives: {instance_dir}")

    record_payloads = [asdict(record) for record in records]
    campaign_digest = sha256_payload(
        {"campaign_spec_digest": spec_digest, "instances": record_payloads}
    )
    expected_count = len(spec.levels) * len(spec.seeds)
    manifest = ObjectiveCountV2FamilyManifest(
        campaign_generator_version=CAMPAIGN_GENERATOR_VERSION,
        structural_generator_version=STRUCTURAL_GENERATOR_VERSION,
        campaign_id=spec.campaign_id,
        factor=FACTOR,
        levels=spec.levels,
        seeds=spec.seeds,
        baseline_constraints_per_objective=(
            spec.baseline_constraints_per_objective
        ),
        baseline_virtual_nodes_per_objective=(
            spec.baseline_virtual_nodes_per_objective
        ),
        selected_objective_index=spec.selected_objective_index,
        session_support_policy=SESSION_SUPPORT_POLICY,
        level_count=len(spec.levels),
        replication_count=len(spec.seeds),
        expected_instance_count=expected_count,
        realised_instance_count=len(records),
        campaign_spec_digest=spec_digest,
        campaign_digest=campaign_digest,
    )
    _write_csv(output_dir / "instances.csv", records)
    write_json(output_dir / "campaign_manifest.json", asdict(manifest))
    return manifest
