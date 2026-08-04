from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from backend.harness.sensitivity_generator.structural_generator import (
    StructuralConfig,
    StructuralManifest,
    generate_structural_instance,
)


CAMPAIGN_GENERATOR_VERSION = "mcad-sensitivity-e2.2-v1"
STRUCTURAL_GENERATOR_VERSION = "mcad-sensitivity-e2.1-v1"

SUPPORTED_FACTORS = {
    "constraint_count",
    "virtual_node_count",
    "objective_count",
}


@dataclass(frozen=True)
class ControlledFamilySpec:
    campaign_id: str
    factor: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraint_count: int
    baseline_virtual_node_count: int
    output_dir: str


@dataclass(frozen=True)
class InstanceRecord:
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
    requirement_set_count: int
    requirement_membership_link_count: int
    membership_density: float
    graph_node_count: int
    graph_edge_count: int
    configuration_digest: str
    instance_digest: str
    generator_version: str


@dataclass(frozen=True)
class ControlledFamilyManifest:
    campaign_generator_version: str
    structural_generator_version: str
    campaign_id: str
    factor: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraint_count: int
    baseline_virtual_node_count: int
    level_count: int
    replication_count: int
    expected_instance_count: int
    realised_instance_count: int
    campaign_spec_digest: str
    campaign_digest: str


def canonical_json_bytes(
    payload: Any,
) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_payload(
    payload: Any,
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()


def write_json(
    path: Path,
    payload: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def normalise_identifier(
    value: str,
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        value.strip(),
    )

    cleaned = re.sub(
        r"_+",
        "_",
        cleaned,
    ).strip("_")

    if not cleaned:
        raise ValueError(
            "Identifier must contain at least one "
            "alphanumeric character."
        )

    return cleaned


def ensure_positive_integer(
    name: str,
    value: int,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be an integer."
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be strictly positive."
        )


def validate_unique_positive_values(
    name: str,
    values: Sequence[int],
) -> None:
    if not values:
        raise ValueError(
            f"{name} must not be empty."
        )

    for value in values:
        ensure_positive_integer(
            f"{name} value",
            value,
        )

    if len(set(values)) != len(values):
        raise ValueError(
            f"{name} values must be unique."
        )


def validate_spec(
    spec: ControlledFamilySpec,
) -> None:
    normalise_identifier(spec.campaign_id)

    if spec.factor not in SUPPORTED_FACTORS:
        raise ValueError(
            "Unsupported E2.2 factor: "
            f"{spec.factor!r}. "
            f"Expected one of "
            f"{sorted(SUPPORTED_FACTORS)}."
        )

    validate_unique_positive_values(
        "levels",
        spec.levels,
    )

    validate_unique_positive_values(
        "seeds",
        spec.seeds,
    )

    ensure_positive_integer(
        "baseline_constraint_count",
        spec.baseline_constraint_count,
    )

    ensure_positive_integer(
        "baseline_virtual_node_count",
        spec.baseline_virtual_node_count,
    )

    if not str(spec.output_dir).strip():
        raise ValueError(
            "output_dir must not be empty."
        )


def stable_spec_payload(
    spec: ControlledFamilySpec,
) -> dict[str, Any]:
    return {
        "campaign_generator_version": (
            CAMPAIGN_GENERATOR_VERSION
        ),
        "structural_generator_version": (
            STRUCTURAL_GENERATOR_VERSION
        ),
        "campaign_id": spec.campaign_id,
        "factor": spec.factor,
        "levels": list(spec.levels),
        "seeds": list(spec.seeds),
        "baseline_constraint_count": (
            spec.baseline_constraint_count
        ),
        "baseline_virtual_node_count": (
            spec.baseline_virtual_node_count
        ),
    }


def factor_configuration(
    spec: ControlledFamilySpec,
    level: int,
) -> tuple[int, int]:
    if spec.factor == "constraint_count":
        return (
            level,
            spec.baseline_virtual_node_count,
        )

    if spec.factor == "virtual_node_count":
        return (
            spec.baseline_constraint_count,
            level,
        )

    raise ValueError(
        f"Unsupported factor: {spec.factor!r}"
    )


def objective_identifier(
    spec: ControlledFamilySpec,
    level: int,
    replication_index: int,
) -> str:
    campaign = normalise_identifier(
        spec.campaign_id
    ).upper()

    factor = normalise_identifier(
        spec.factor
    ).upper()

    return (
        f"O_{campaign}_"
        f"{factor}_"
        f"L{level}_"
        f"R{replication_index:03d}"
    )


def relative_instance_directory(
    level: int,
    replication_index: int,
    seed: int,
) -> Path:
    return (
        Path("instances")
        / f"level_{level:06d}"
        / (
            f"rep_{replication_index:03d}"
            f"_seed_{seed}"
        )
    )


def prepare_output_directory(
    output_dir: Path,
) -> None:
    if output_dir.exists():
        contents = list(
            output_dir.iterdir()
        )

        if contents:
            raise ValueError(
                "E2.2 output directory must be "
                "absent or empty: "
                f"{output_dir}"
            )
    else:
        output_dir.mkdir(
            parents=True,
            exist_ok=False,
        )


def build_instance_record(
    spec: ControlledFamilySpec,
    level: int,
    replication_index: int,
    seed: int,
    relative_dir: Path,
    manifest: StructuralManifest,
) -> InstanceRecord:
    if (
        manifest.generator_version
        != STRUCTURAL_GENERATOR_VERSION
    ):
        raise ValueError(
            "Unexpected E2.1 generator version: "
            f"{manifest.generator_version!r}"
        )

    requested_constraints, requested_nvs = (
        factor_configuration(
            spec,
            level,
        )
    )

    if (
        manifest.requested_constraint_count
        != requested_constraints
    ):
        raise ValueError(
            "E2.1 constraint count differs from "
            "the E2.2 condition."
        )

    if (
        manifest.requested_virtual_node_count
        != requested_nvs
    ):
        raise ValueError(
            "E2.1 virtual-node count differs from "
            "the E2.2 condition."
        )

    return InstanceRecord(
        campaign_id=spec.campaign_id,
        factor=spec.factor,
        factor_level=level,
        replication_index=replication_index,
        seed=seed,
        objective_id=manifest.objective_id,
        relative_instance_dir=relative_dir.as_posix(),
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
        configuration_digest=(
            manifest.configuration_digest
        ),
        instance_digest=(
            manifest.instance_digest
        ),
        generator_version=(
            manifest.generator_version
        ),
    )


def validate_instance_files(
    output_dir: Path,
    records: Iterable[InstanceRecord],
) -> None:
    for record in records:
        instance_dir = (
            output_dir
            / record.relative_instance_dir
        )

        manifest_path = (
            instance_dir
            / "manifest.json"
        )

        objectives_path = (
            instance_dir
            / "objectives.yaml"
        )

        if not manifest_path.is_file():
            raise ValueError(
                "Missing E2.1 manifest: "
                f"{manifest_path}"
            )

        if not objectives_path.is_file():
            raise ValueError(
                "Missing E2.1 objectives file: "
                f"{objectives_path}"
            )


def validate_condition_matrix(
    spec: ControlledFamilySpec,
    records: Sequence[InstanceRecord],
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

    if realised != expected:
        raise ValueError(
            "Incomplete or duplicated E2.2 "
            "condition matrix."
        )

    if len(records) != len(expected):
        raise ValueError(
            "Each E2.2 condition must be "
            "generated exactly once."
        )


def validate_ofat_invariants(
    spec: ControlledFamilySpec,
    records: Sequence[InstanceRecord],
) -> None:
    for record in records:
        if record.factor != spec.factor:
            raise ValueError(
                "Instance factor differs from "
                "campaign factor."
            )

        if (
            record.generator_version
            != STRUCTURAL_GENERATOR_VERSION
        ):
            raise ValueError(
                "Instance generator version differs "
                "from the E2.1 binding."
            )

        if (
            record.realised_constraint_count
            != record.requested_constraint_count
        ):
            raise ValueError(
                "Realised constraint count differs "
                "from requested count."
            )

        if (
            record.realised_virtual_node_count
            != record.requested_virtual_node_count
        ):
            raise ValueError(
                "Realised virtual-node count differs "
                "from requested count."
            )

        if record.membership_density != 1.0:
            raise ValueError(
                "E2.2 v1 requires membership "
                "density equal to 1.0."
            )

        if spec.factor == "constraint_count":
            if (
                record.requested_constraint_count
                != record.factor_level
            ):
                raise ValueError(
                    "Constraint factor level was "
                    "not applied."
                )

            if (
                record.requested_virtual_node_count
                != spec.baseline_virtual_node_count
            ):
                raise ValueError(
                    "Virtual-node baseline changed "
                    "inside constraint family."
                )

        elif spec.factor == "virtual_node_count":
            if (
                record.requested_virtual_node_count
                != record.factor_level
            ):
                raise ValueError(
                    "Virtual-node factor level was "
                    "not applied."
                )

            if (
                record.requested_constraint_count
                != spec.baseline_constraint_count
            ):
                raise ValueError(
                    "Constraint baseline changed "
                    "inside virtual-node family."
                )


def write_instances_csv(
    path: Path,
    records: Sequence[InstanceRecord],
) -> None:
    rows = [
        asdict(record)
        for record in records
    ]

    if not rows:
        raise ValueError(
            "Cannot write an empty instances.csv."
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


def generate_controlled_family(
    spec: ControlledFamilySpec,
) -> ControlledFamilyManifest:
    if spec.factor == "objective_count":
        from backend.harness.sensitivity_generator.families.objective_count_family import (
            ObjectiveCountFamilySpec,
            generate_objective_count_family,
        )

        return generate_objective_count_family(
            ObjectiveCountFamilySpec(
                campaign_id=spec.campaign_id,
                levels=spec.levels,
                seeds=spec.seeds,
                baseline_constraints_per_objective=(
                    spec.baseline_constraint_count
                ),
                baseline_virtual_nodes_per_objective=(
                    spec.baseline_virtual_node_count
                ),
                selected_objective_index=0,
                output_dir=spec.output_dir,
            )
        )

    validate_spec(spec)

    output_dir = Path(
        spec.output_dir
    )

    prepare_output_directory(
        output_dir
    )

    stable_spec = stable_spec_payload(
        spec
    )

    spec_digest = sha256_payload(
        stable_spec
    )

    write_json(
        output_dir / "campaign_spec.json",
        {
            **stable_spec,
            "campaign_spec_digest": spec_digest,
        },
    )

    records: list[InstanceRecord] = []

    for level in spec.levels:
        (
            constraint_count,
            virtual_node_count,
        ) = factor_configuration(
            spec,
            level,
        )

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

            absolute_dir = (
                output_dir
                / relative_dir
            )

            objective_id = objective_identifier(
                spec,
                level,
                replication_index,
            )

            structural_manifest = (
                generate_structural_instance(
                    StructuralConfig(
                        objective_id=objective_id,
                        n_constraints=(
                            constraint_count
                        ),
                        n_virtual_nodes=(
                            virtual_node_count
                        ),
                        seed=seed,
                        output_dir=str(
                            absolute_dir
                        ),
                    )
                )
            )

            records.append(
                build_instance_record(
                    spec=spec,
                    level=level,
                    replication_index=(
                        replication_index
                    ),
                    seed=seed,
                    relative_dir=relative_dir,
                    manifest=structural_manifest,
                )
            )

    validate_condition_matrix(
        spec,
        records,
    )

    validate_ofat_invariants(
        spec,
        records,
    )

    validate_instance_files(
        output_dir,
        records,
    )

    record_payloads = [
        asdict(record)
        for record in records
    ]

    campaign_digest = sha256_payload(
        {
            "campaign_spec_digest": spec_digest,
            "instances": record_payloads,
        }
    )

    expected_count = (
        len(spec.levels)
        * len(spec.seeds)
    )

    manifest = ControlledFamilyManifest(
        campaign_generator_version=(
            CAMPAIGN_GENERATOR_VERSION
        ),
        structural_generator_version=(
            STRUCTURAL_GENERATOR_VERSION
        ),
        campaign_id=spec.campaign_id,
        factor=spec.factor,
        levels=spec.levels,
        seeds=spec.seeds,
        baseline_constraint_count=(
            spec.baseline_constraint_count
        ),
        baseline_virtual_node_count=(
            spec.baseline_virtual_node_count
        ),
        level_count=len(spec.levels),
        replication_count=len(spec.seeds),
        expected_instance_count=expected_count,
        realised_instance_count=len(records),
        campaign_spec_digest=spec_digest,
        campaign_digest=campaign_digest,
    )

    write_instances_csv(
        output_dir / "instances.csv",
        records,
    )

    write_json(
        output_dir / "campaign_manifest.json",
        asdict(manifest),
    )

    return manifest
