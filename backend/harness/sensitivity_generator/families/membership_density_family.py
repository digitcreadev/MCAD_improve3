from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from backend.harness.sensitivity_generator.membership_density_generator import (
    GENERATOR_VERSION as STRUCTURAL_GENERATOR_VERSION,
)
from backend.harness.sensitivity_generator.membership_density_generator import (
    MembershipDensityConfig,
    MembershipDensityManifest,
    generate_membership_density_instance,
)
from backend.harness.sensitivity_generator.oracles.membership_density_oracle import (
    load_objectives_yaml,
    validate_density_family,
)


CAMPAIGN_GENERATOR_VERSION = (
    "mcad-sensitivity-e2.2-membership-density-v1"
)

FACTOR = "membership_density"


@dataclass(frozen=True)
class MembershipDensityFamilySpec:
    campaign_id: str
    levels: tuple[int, ...]
    seeds: tuple[int, ...]
    baseline_constraint_count: int
    baseline_virtual_node_count: int
    output_dir: str


@dataclass(frozen=True)
class MembershipDensityInstanceRecord:
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

    requested_membership_density_percent: int
    realised_membership_density_percent: int

    requirement_set_count: int
    requirement_membership_link_count: int
    maximum_membership_link_count: int
    membership_density: float

    graph_node_count: int
    graph_edge_count: int

    configuration_digest: str
    instance_digest: str
    generator_version: str


@dataclass(frozen=True)
class MembershipDensityFamilyManifest:
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
        allow_nan=False,
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
            allow_nan=False,
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


def validate_unique_positive_integers(
    name: str,
    values: Sequence[int],
) -> None:
    if not values:
        raise ValueError(
            f"{name} must not be empty."
        )

    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            raise ValueError(
                f"{name} values must be positive "
                "integers."
            )

    if len(set(values)) != len(values):
        raise ValueError(
            f"{name} values must be unique."
        )


def validate_spec(
    spec: MembershipDensityFamilySpec,
) -> None:
    normalise_identifier(
        spec.campaign_id
    )

    validate_unique_positive_integers(
        "levels",
        spec.levels,
    )

    validate_unique_positive_integers(
        "seeds",
        spec.seeds,
    )

    if any(
        level > 100
        for level in spec.levels
    ):
        raise ValueError(
            "Membership-density levels must not "
            "exceed 100."
        )

    if (
        spec.baseline_constraint_count
        != 4
    ):
        raise ValueError(
            "SA4 v1 requires baseline_constraint_count "
            "equal to 4."
        )

    if (
        spec.baseline_virtual_node_count
        != 24
    ):
        raise ValueError(
            "SA4 v1 requires baseline_virtual_node_count "
            "equal to 24."
        )

    if not str(spec.output_dir).strip():
        raise ValueError(
            "output_dir must not be empty."
        )

    maximum_membership_count = (
        spec.baseline_virtual_node_count
    )

    for level in spec.levels:
        numerator = (
            maximum_membership_count
            * level
        )

        if numerator % 100 != 0:
            raise ValueError(
                "A density level does not produce an "
                "exact membership count: "
                f"level={level}."
            )

        if (
            numerator // 100
            < spec.baseline_constraint_count
        ):
            raise ValueError(
                "A density level would leave one or "
                "more requirement sets empty: "
                f"level={level}."
            )


def stable_spec_payload(
    spec: MembershipDensityFamilySpec,
) -> dict[str, Any]:
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
        "baseline_constraint_count": (
            spec.baseline_constraint_count
        ),
        "baseline_virtual_node_count": (
            spec.baseline_virtual_node_count
        ),
    }


def objective_identifier(
    spec: MembershipDensityFamilySpec,
    level: int,
    replication_index: int,
) -> str:
    campaign = normalise_identifier(
        spec.campaign_id
    ).upper()

    return (
        f"O_{campaign}_"
        "MEMBERSHIP_DENSITY_"
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
            f"rep_{replication_index:03d}_"
            f"seed_{seed}"
        )
    )


def prepare_output_directory(
    output_dir: Path,
) -> None:
    if (
        output_dir.exists()
        and any(output_dir.iterdir())
    ):
        raise ValueError(
            "Output directory is not empty: "
            f"{output_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


def build_instance_record(
    *,
    spec: MembershipDensityFamilySpec,
    level: int,
    replication_index: int,
    seed: int,
    relative_dir: Path,
    manifest: MembershipDensityManifest,
) -> MembershipDensityInstanceRecord:
    return MembershipDensityInstanceRecord(
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
        requested_membership_density_percent=(
            manifest
            .requested_membership_density_percent
        ),
        realised_membership_density_percent=(
            manifest
            .realised_membership_density_percent
        ),
        requirement_set_count=(
            manifest.requirement_set_count
        ),
        requirement_membership_link_count=(
            manifest
            .requirement_membership_link_count
        ),
        maximum_membership_link_count=(
            manifest.maximum_membership_link_count
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
    records: Iterable[
        MembershipDensityInstanceRecord
    ],
) -> None:
    for record in records:
        instance_dir = (
            output_dir
            / record.relative_instance_dir
        )

        for filename in (
            "manifest.json",
            "objectives.yaml",
        ):
            path = (
                instance_dir / filename
            )

            if not path.is_file():
                raise ValueError(
                    "Missing instance file: "
                    f"{path}"
                )


def validate_condition_matrix(
    spec: MembershipDensityFamilySpec,
    records: Sequence[
        MembershipDensityInstanceRecord
    ],
) -> None:
    expected = {
        (
            level,
            replication_index,
            seed,
        )
        for level in spec.levels
        for replication_index, seed
        in enumerate(spec.seeds)
    }

    actual = {
        (
            record.factor_level,
            record.replication_index,
            record.seed,
        )
        for record in records
    }

    if actual != expected:
        raise ValueError(
            "Generated condition matrix differs "
            "from the requested matrix."
        )


def validate_ofat_invariants(
    spec: MembershipDensityFamilySpec,
    records: Sequence[
        MembershipDensityInstanceRecord
    ],
) -> None:
    expected_membership_counts = {
        level: (
            spec.baseline_virtual_node_count
            * level
            // 100
        )
        for level in spec.levels
    }

    for record in records:
        if record.factor != FACTOR:
            raise ValueError(
                "Unexpected factor value."
            )

        if (
            record.requested_constraint_count
            != spec.baseline_constraint_count
            or record.realised_constraint_count
            != spec.baseline_constraint_count
        ):
            raise ValueError(
                "Constraint count changed in the "
                "density family."
            )

        if (
            record.requested_virtual_node_count
            != spec.baseline_virtual_node_count
            or record.realised_virtual_node_count
            != spec.baseline_virtual_node_count
        ):
            raise ValueError(
                "Virtual-node count changed in the "
                "density family."
            )

        if record.requirement_set_count != 4:
            raise ValueError(
                "Requirement-set count changed."
            )

        expected_count = (
            expected_membership_counts[
                record.factor_level
            ]
        )

        if (
            record.requirement_membership_link_count
            != expected_count
        ):
            raise ValueError(
                "Membership-link count differs "
                "from the requested density."
            )

        if (
            record.maximum_membership_link_count
            != 24
        ):
            raise ValueError(
                "Maximum membership capacity changed."
            )

        if (
            record.requested_membership_density_percent
            != record.factor_level
            or record.realised_membership_density_percent
            != record.factor_level
        ):
            raise ValueError(
                "Density factor level was not "
                "realised exactly."
            )

        if (
            record.membership_density
            != record.factor_level / 100
        ):
            raise ValueError(
                "Realised membership density differs "
                "from the factor level."
            )

        if (
            record.generator_version
            != STRUCTURAL_GENERATOR_VERSION
        ):
            raise ValueError(
                "Unexpected structural generator "
                "version."
            )


def validate_independent_oracle(
    *,
    spec: MembershipDensityFamilySpec,
    output_dir: Path,
    records: Sequence[
        MembershipDensityInstanceRecord
    ],
) -> dict[str, Any]:
    summaries = {}

    for replication_index, seed in enumerate(
        spec.seeds
    ):
        documents = {}

        for level in spec.levels:
            matching = [
                record
                for record in records
                if (
                    record.factor_level == level
                    and record.replication_index
                    == replication_index
                    and record.seed == seed
                )
            ]

            if len(matching) != 1:
                raise ValueError(
                    "Could not resolve exactly one "
                    "instance for an oracle condition."
                )

            path = (
                output_dir
                / matching[0].relative_instance_dir
                / "objectives.yaml"
            )

            documents[level] = (
                load_objectives_yaml(path)
            )

        summaries[
            str(replication_index)
        ] = validate_density_family(
            documents,
            required_levels=spec.levels,
        )

    return summaries


def write_instances_csv(
    path: Path,
    records: Sequence[
        MembershipDensityInstanceRecord
    ],
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
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)


def generate_membership_density_family(
    spec: MembershipDensityFamilySpec,
) -> MembershipDensityFamilyManifest:
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
            "campaign_spec_digest": (
                spec_digest
            ),
        },
    )

    records: list[
        MembershipDensityInstanceRecord
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
                generate_membership_density_instance(
                    MembershipDensityConfig(
                        objective_id=objective_id,
                        n_constraints=(
                            spec
                            .baseline_constraint_count
                        ),
                        n_virtual_nodes=(
                            spec
                            .baseline_virtual_node_count
                        ),
                        membership_density_percent=(
                            level
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
                    manifest=(
                        structural_manifest
                    ),
                )
            )

    validate_instance_files(
        output_dir,
        records,
    )

    validate_condition_matrix(
        spec,
        records,
    )

    validate_ofat_invariants(
        spec,
        records,
    )

    oracle_summaries = (
        validate_independent_oracle(
            spec=spec,
            output_dir=output_dir,
            records=records,
        )
    )

    campaign_digest = sha256_payload(
        [
            asdict(record)
            for record in records
        ]
    )

    expected_count = (
        len(spec.levels)
        * len(spec.seeds)
    )

    manifest = MembershipDensityFamilyManifest(
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
        baseline_constraint_count=(
            spec.baseline_constraint_count
        ),
        baseline_virtual_node_count=(
            spec.baseline_virtual_node_count
        ),
        level_count=len(spec.levels),
        replication_count=len(spec.seeds),
        expected_instance_count=(
            expected_count
        ),
        realised_instance_count=(
            len(records)
        ),
        campaign_spec_digest=(
            spec_digest
        ),
        campaign_digest=campaign_digest,
    )

    write_instances_csv(
        output_dir / "instances.csv",
        records,
    )

    write_json(
        output_dir / "oracle_validation.json",
        {
            "status": "success",
            "factor": FACTOR,
            "replications": (
                oracle_summaries
            ),
        },
    )

    write_json(
        output_dir / "campaign_manifest.json",
        asdict(manifest),
    )

    return manifest
