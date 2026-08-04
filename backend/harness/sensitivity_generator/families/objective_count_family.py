
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
from backend.harness.sensitivity_generator.objective_count_generator import (
    GENERATOR_VERSION as STRUCTURAL_GENERATOR_VERSION,
)
from backend.harness.sensitivity_generator.objective_count_generator import (
    ObjectiveCountConfig,
    ObjectiveCountStructuralManifest,
    generate_objective_count_instance,
)

CAMPAIGN_GENERATOR_VERSION = (
    "mcad-sensitivity-e2.2-objective-count-v1"
)
FACTOR = "objective_count"


@dataclass(frozen=True)
class ObjectiveCountFamilySpec:
    campaign_id: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraints_per_objective: int
    baseline_virtual_nodes_per_objective: int
    selected_objective_index: int
    output_dir: str


@dataclass(frozen=True)
class ObjectiveCountInstanceRecord:
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
    selected_objective_index: int
    selected_objective_shape_digest: str
    total_constraint_count: int
    total_virtual_node_count: int
    requirement_set_count: int
    requirement_membership_link_count: int
    membership_density: float
    graph_node_count: int
    graph_edge_count: int


@dataclass(frozen=True)
class ObjectiveCountFamilyManifest:
    campaign_generator_version: str
    structural_generator_version: str
    campaign_id: str
    factor: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraints_per_objective: int
    baseline_virtual_nodes_per_objective: int
    selected_objective_index: int
    level_count: int
    replication_count: int
    expected_instance_count: int
    realised_instance_count: int
    campaign_spec_digest: str
    campaign_digest: str


def validate_spec(
    spec: ObjectiveCountFamilySpec,
) -> None:
    normalise_identifier(spec.campaign_id)

    validate_unique_positive_values(
        "levels",
        spec.levels,
    )
    validate_unique_positive_values(
        "seeds",
        spec.seeds,
    )

    ensure_positive_integer(
        "baseline_constraints_per_objective",
        spec.baseline_constraints_per_objective,
    )
    ensure_positive_integer(
        "baseline_virtual_nodes_per_objective",
        spec.baseline_virtual_nodes_per_objective,
    )

    if (
        spec.baseline_virtual_nodes_per_objective
        < spec.baseline_constraints_per_objective
    ):
        raise ValueError(
            "baseline_virtual_nodes_per_objective "
            "must be at least "
            "baseline_constraints_per_objective."
        )

    if (
        isinstance(
            spec.selected_objective_index,
            bool,
        )
        or not isinstance(
            spec.selected_objective_index,
            int,
        )
        or spec.selected_objective_index < 0
        or (
            spec.selected_objective_index
            >= min(spec.levels)
        )
    ):
        raise ValueError(
            "selected_objective_index must exist "
            "at every objective-count level."
        )

    if not str(spec.output_dir).strip():
        raise ValueError(
            "output_dir must not be empty."
        )


def stable_spec_payload(
    spec: ObjectiveCountFamilySpec,
) -> dict[str, object]:
    return {
        "campaign_generator_version": (
            CAMPAIGN_GENERATOR_VERSION
        ),
        "structural_generator_version": (
            STRUCTURAL_GENERATOR_VERSION
        ),
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
        "selected_objective_index": (
            spec.selected_objective_index
        ),
    }


def _instance_id(
    spec: ObjectiveCountFamilySpec,
    level: int,
    replication_index: int,
) -> str:
    return (
        f"{normalise_identifier(spec.campaign_id).upper()}"
        "_OBJECTIVE_COUNT_"
        f"L{level}_R{replication_index:03d}"
    )


def _record(
    spec: ObjectiveCountFamilySpec,
    level: int,
    replication_index: int,
    seed: int,
    relative_dir: Path,
    manifest: ObjectiveCountStructuralManifest,
) -> ObjectiveCountInstanceRecord:
    if (
        manifest.generator_version
        != STRUCTURAL_GENERATOR_VERSION
    ):
        raise ValueError(
            "Unexpected objective-count structural "
            "generator version."
        )

    if (
        manifest.requested_objective_count
        != level
    ):
        raise ValueError(
            "Objective-count factor level was not applied."
        )

    if (
        manifest.realised_objective_count
        != level
    ):
        raise ValueError(
            "Realised objective count differs "
            "from the factor level."
        )

    if (
        manifest.requested_constraint_count
        != spec.baseline_constraints_per_objective
    ):
        raise ValueError(
            "Selected-objective constraint "
            "baseline changed."
        )

    if (
        manifest.requested_virtual_node_count
        != spec.baseline_virtual_nodes_per_objective
    ):
        raise ValueError(
            "Selected-objective virtual-node "
            "baseline changed."
        )

    return ObjectiveCountInstanceRecord(
        campaign_id=spec.campaign_id,
        factor=FACTOR,
        factor_level=level,
        replication_index=replication_index,
        seed=seed,
        objective_id=manifest.objective_id,
        relative_instance_dir=(
            relative_dir.as_posix()
        ),
        requested_constraint_count=(
            manifest.requested_constraint_count
        ),
        realised_constraint_count=(
            manifest.realised_constraint_count
        ),
        requested_virtual_node_count=(
            manifest.requested_virtual_node_count
        ),
        realised_virtual_node_count=(
            manifest.realised_virtual_node_count
        ),
        configuration_digest=(
            manifest.configuration_digest
        ),
        instance_digest=(
            manifest.instance_digest
        ),
        generator_version=(
            manifest.generator_version
        ),
        requested_objective_count=(
            manifest.requested_objective_count
        ),
        realised_objective_count=(
            manifest.realised_objective_count
        ),
        selected_objective_index=(
            manifest.selected_objective_index
        ),
        selected_objective_shape_digest=(
            manifest.selected_objective_shape_digest
        ),
        total_constraint_count=(
            manifest.total_constraint_count
        ),
        total_virtual_node_count=(
            manifest.total_virtual_node_count
        ),
        requirement_set_count=(
            manifest.requirement_set_count
        ),
        requirement_membership_link_count=(
            manifest.requirement_membership_link_count
        ),
        membership_density=(
            manifest.membership_density
        ),
        graph_node_count=(
            manifest.graph_node_count
        ),
        graph_edge_count=(
            manifest.graph_edge_count
        ),
    )


def _validate_matrix(
    spec: ObjectiveCountFamilySpec,
    records: Sequence[
        ObjectiveCountInstanceRecord
    ],
) -> None:
    expected = {
        (
            level,
            replication_index,
            seed,
        )
        for level in spec.levels
        for replication_index, seed in enumerate(
            spec.seeds
        )
    }

    realised = {
        (
            record.factor_level,
            record.replication_index,
            record.seed,
        )
        for record in records
    }

    if (
        realised != expected
        or len(records) != len(expected)
    ):
        raise ValueError(
            "Incomplete or duplicated "
            "objective-count matrix."
        )


def _validate_ofat(
    spec: ObjectiveCountFamilySpec,
    records: Sequence[
        ObjectiveCountInstanceRecord
    ],
) -> None:
    selected_shapes: dict[
        tuple[int, int],
        set[str],
    ] = {}

    for record in records:
        if record.factor != FACTOR:
            raise ValueError(
                "Instance factor differs "
                "from objective_count."
            )

        if (
            record.generator_version
            != STRUCTURAL_GENERATOR_VERSION
        ):
            raise ValueError(
                "Objective-count structural "
                "binding changed."
            )

        if (
            record.realised_objective_count
            != record.factor_level
        ):
            raise ValueError(
                "Objective-count factor level "
                "was not realised."
            )

        if (
            record.requested_constraint_count
            != spec.baseline_constraints_per_objective
            or record.realised_constraint_count
            != spec.baseline_constraints_per_objective
        ):
            raise ValueError(
                "Selected-objective constraint "
                "baseline changed."
            )

        if (
            record.requested_virtual_node_count
            != spec.baseline_virtual_nodes_per_objective
            or record.realised_virtual_node_count
            != spec.baseline_virtual_nodes_per_objective
        ):
            raise ValueError(
                "Selected-objective virtual-node "
                "baseline changed."
            )

        if (
            record.total_constraint_count
            != (
                record.factor_level
                * spec.baseline_constraints_per_objective
            )
        ):
            raise ValueError(
                "Total constraint count "
                "is inconsistent."
            )

        if (
            record.total_virtual_node_count
            != (
                record.factor_level
                * spec.baseline_virtual_nodes_per_objective
            )
        ):
            raise ValueError(
                "Total virtual-node count "
                "is inconsistent."
            )

        if record.membership_density != 1.0:
            raise ValueError(
                "Objective-count v1 requires "
                "density 1.0."
            )

        selected_shapes.setdefault(
            (
                record.replication_index,
                record.seed,
            ),
            set(),
        ).add(
            record.selected_objective_shape_digest
        )

    if any(
        len(digests) != 1
        for digests in selected_shapes.values()
    ):
        raise ValueError(
            "Selected-objective structure changed "
            "across objective-count levels."
        )


def _write_csv(
    path: Path,
    records: Sequence[
        ObjectiveCountInstanceRecord
    ],
) -> None:
    rows = [
        asdict(record)
        for record in records
    ]

    if not rows:
        raise ValueError(
            "Cannot write an empty objective-count "
            "instances.csv."
        )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def generate_objective_count_family(
    spec: ObjectiveCountFamilySpec,
) -> ObjectiveCountFamilyManifest:
    validate_spec(spec)

    output_dir = Path(spec.output_dir)
    prepare_output_directory(output_dir)

    stable_spec = stable_spec_payload(spec)
    spec_digest = sha256_payload(stable_spec)

    write_json(
        output_dir / "campaign_spec.json",
        {
            **stable_spec,
            "campaign_spec_digest": spec_digest,
        },
    )

    records: list[
        ObjectiveCountInstanceRecord
    ] = []

    for level in spec.levels:
        for replication_index, seed in enumerate(
            spec.seeds
        ):
            relative_dir = (
                relative_instance_directory(
                    level,
                    replication_index,
                    seed,
                )
            )

            structural = (
                generate_objective_count_instance(
                    ObjectiveCountConfig(
                        instance_id=_instance_id(
                            spec,
                            level,
                            replication_index,
                        ),
                        objective_count=level,
                        selected_objective_index=(
                            spec.selected_objective_index
                        ),
                        constraints_per_objective=(
                            spec.baseline_constraints_per_objective
                        ),
                        virtual_nodes_per_objective=(
                            spec.baseline_virtual_nodes_per_objective
                        ),
                        seed=seed,
                        output_dir=str(
                            output_dir / relative_dir
                        ),
                    )
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

    _validate_matrix(
        spec,
        records,
    )
    _validate_ofat(
        spec,
        records,
    )

    for record in records:
        instance_dir = (
            output_dir
            / record.relative_instance_dir
        )

        if not (
            instance_dir / "manifest.json"
        ).is_file():
            raise ValueError(
                f"Missing manifest: {instance_dir}"
            )

        if not (
            instance_dir / "objectives.yaml"
        ).is_file():
            raise ValueError(
                f"Missing objectives: {instance_dir}"
            )

    payloads = [
        asdict(record)
        for record in records
    ]

    campaign_digest = sha256_payload(
        {
            "campaign_spec_digest": spec_digest,
            "instances": payloads,
        }
    )

    expected_count = (
        len(spec.levels)
        * len(spec.seeds)
    )

    manifest = ObjectiveCountFamilyManifest(
        campaign_generator_version=(
            CAMPAIGN_GENERATOR_VERSION
        ),
        structural_generator_version=(
            STRUCTURAL_GENERATOR_VERSION
        ),
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
        selected_objective_index=(
            spec.selected_objective_index
        ),
        level_count=len(spec.levels),
        replication_count=len(spec.seeds),
        expected_instance_count=expected_count,
        realised_instance_count=len(records),
        campaign_spec_digest=spec_digest,
        campaign_digest=campaign_digest,
    )

    _write_csv(
        output_dir / "instances.csv",
        records,
    )

    write_json(
        output_dir / "campaign_manifest.json",
        asdict(manifest),
    )

    return manifest
