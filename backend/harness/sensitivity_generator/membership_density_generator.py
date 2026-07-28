from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.sensitivity_generator.structural_generator import (
    StructuralConfig,
    build_objectives_document,
    count_structure,
    sha256_digest,
    validate_graph_projection,
    validate_reference_integrity,
    write_yaml,
)


GENERATOR_VERSION = (
    "mcad-sensitivity-e2.1-membership-density-v1"
)


class MembershipDensityGenerationError(
    RuntimeError
):
    """Raised when a density-controlled instance is invalid."""


@dataclass(frozen=True)
class MembershipDensityConfig:
    objective_id: str
    n_constraints: int
    n_virtual_nodes: int
    membership_density_percent: int
    seed: int
    output_dir: str


@dataclass(frozen=True)
class MembershipDensityManifest:
    generator_version: str
    objective_id: str

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

    seed: int
    configuration_digest: str
    instance_digest: str


def validate_config(
    config: MembershipDensityConfig,
) -> None:
    integer_fields = {
        "n_constraints": config.n_constraints,
        "n_virtual_nodes": config.n_virtual_nodes,
        "membership_density_percent": (
            config.membership_density_percent
        ),
        "seed": config.seed,
    }

    for name, value in integer_fields.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise MembershipDensityGenerationError(
                f"{name} must be an integer."
            )

    if config.n_constraints <= 0:
        raise MembershipDensityGenerationError(
            "n_constraints must be positive."
        )

    if (
        config.n_virtual_nodes
        < config.n_constraints
    ):
        raise MembershipDensityGenerationError(
            "n_virtual_nodes must be greater than "
            "or equal to n_constraints."
        )

    if not (
        1
        <= config.membership_density_percent
        <= 100
    ):
        raise MembershipDensityGenerationError(
            "membership_density_percent must lie "
            "between 1 and 100."
        )

    if not str(config.objective_id).strip():
        raise MembershipDensityGenerationError(
            "objective_id must not be empty."
        )

    if not str(config.output_dir).strip():
        raise MembershipDensityGenerationError(
            "output_dir must not be empty."
        )


def _constraints(
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    objectives = document.get("objectives")

    if (
        not isinstance(objectives, list)
        or len(objectives) != 1
        or not isinstance(objectives[0], dict)
    ):
        raise MembershipDensityGenerationError(
            "The structural document must contain "
            "exactly one objective."
        )

    constraints = objectives[0].get(
        "constraints"
    )

    if not isinstance(constraints, list):
        raise MembershipDensityGenerationError(
            "The objective must contain a "
            "constraints list."
        )

    if not constraints:
        raise MembershipDensityGenerationError(
            "The constraints list must not be empty."
        )

    if not all(
        isinstance(constraint, dict)
        for constraint in constraints
    ):
        raise MembershipDensityGenerationError(
            "Every constraint must be an object."
        )

    return constraints


def _virtual_node_ids(
    constraint: dict[str, Any],
) -> list[str]:
    raw_nodes = (
        constraint.get("virtual_nodes") or []
    )

    if not isinstance(raw_nodes, list):
        raise MembershipDensityGenerationError(
            "virtual_nodes must be a list."
        )

    result = []

    for node in raw_nodes:
        if not isinstance(node, dict):
            raise MembershipDensityGenerationError(
                "Every virtual node must be an object."
            )

        identifier = node.get("id")

        if (
            not isinstance(identifier, str)
            or not identifier
        ):
            raise MembershipDensityGenerationError(
                "Every virtual node must have a "
                "non-empty ID."
            )

        result.append(identifier)

    if not result:
        raise MembershipDensityGenerationError(
            "Every constraint must contain at least "
            "one virtual node."
        )

    if len(set(result)) != len(result):
        raise MembershipDensityGenerationError(
            "Virtual-node IDs must be unique within "
            "a constraint."
        )

    return result


def membership_capacity(
    document: dict[str, Any],
) -> int:
    capacity = 0

    for constraint in _constraints(document):
        virtual_nodes = _virtual_node_ids(
            constraint
        )

        requirement_sets = (
            constraint.get("requirement_sets")
            or []
        )

        if not isinstance(
            requirement_sets,
            list,
        ):
            raise MembershipDensityGenerationError(
                "requirement_sets must be a list."
            )

        capacity += (
            len(requirement_sets)
            * len(virtual_nodes)
        )

    return capacity


def target_membership_count(
    *,
    maximum_membership_count: int,
    density_percent: int,
) -> int:
    if maximum_membership_count <= 0:
        raise MembershipDensityGenerationError(
            "Maximum membership count must be "
            "positive."
        )

    numerator = (
        maximum_membership_count
        * density_percent
    )

    if numerator % 100 != 0:
        raise MembershipDensityGenerationError(
            "The requested density does not produce "
            "an exact integer membership count: "
            f"maximum={maximum_membership_count}, "
            f"density_percent={density_percent}."
        )

    return numerator // 100


def balanced_membership_allocation(
    capacities: Sequence[int],
    target_count: int,
) -> tuple[int, ...]:
    if not capacities:
        raise MembershipDensityGenerationError(
            "At least one constraint is required."
        )

    if any(capacity <= 0 for capacity in capacities):
        raise MembershipDensityGenerationError(
            "Every constraint must have positive "
            "membership capacity."
        )

    if target_count < len(capacities):
        raise MembershipDensityGenerationError(
            "The density level would leave at least "
            "one requirement set empty."
        )

    if target_count > sum(capacities):
        raise MembershipDensityGenerationError(
            "The target membership count exceeds "
            "the available capacity."
        )

    allocation = [
        0
        for _ in capacities
    ]

    remaining = target_count

    maximum_layer = max(capacities)

    for local_index in range(
        maximum_layer
    ):
        for constraint_index, capacity in enumerate(
            capacities
        ):
            if remaining == 0:
                break

            if local_index < capacity:
                allocation[
                    constraint_index
                ] += 1

                remaining -= 1

        if remaining == 0:
            break

    if remaining != 0:
        raise MembershipDensityGenerationError(
            "Could not allocate the requested "
            "membership count."
        )

    if (
        max(allocation)
        - min(allocation)
        > 1
    ):
        raise MembershipDensityGenerationError(
            "Membership allocation is not balanced."
        )

    return tuple(allocation)


def apply_membership_density(
    document: dict[str, Any],
    density_percent: int,
) -> tuple[
    dict[str, Any],
    tuple[int, ...],
]:
    constraints = _constraints(document)

    node_ids = [
        _virtual_node_ids(constraint)
        for constraint in constraints
    ]

    capacities = tuple(
        len(values)
        for values in node_ids
    )

    maximum_count = sum(capacities)

    target_count = target_membership_count(
        maximum_membership_count=(
            maximum_count
        ),
        density_percent=density_percent,
    )

    allocation = (
        balanced_membership_allocation(
            capacities,
            target_count,
        )
    )

    for constraint, identifiers, count in zip(
        constraints,
        node_ids,
        allocation,
        strict=True,
    ):
        constraint["requirement_sets"] = [
            identifiers[:count]
        ]

    return document, allocation


def build_density_objectives_document(
    config: MembershipDensityConfig,
) -> tuple[
    dict[str, Any],
    tuple[int, ...],
]:
    validate_config(config)

    document = build_objectives_document(
        StructuralConfig(
            objective_id=config.objective_id,
            n_constraints=config.n_constraints,
            n_virtual_nodes=(
                config.n_virtual_nodes
            ),
            seed=config.seed,
            output_dir=config.output_dir,
        )
    )

    return apply_membership_density(
        document,
        config.membership_density_percent,
    )


def _fresh_ckg(
    output_dir: Path,
) -> CKGGraph:
    ckg = CKGGraph(
        output_dir=str(
            output_dir / "ckg_runtime"
        )
    )

    ckg.G.clear()
    ckg.objectives.clear()
    ckg.history.clear()
    ckg.session_coverage.clear()
    ckg.session_weighted_coverage.clear()
    ckg.session_resource_coverage.clear()

    return ckg


def generate_membership_density_instance(
    config: MembershipDensityConfig,
) -> MembershipDensityManifest:
    validate_config(config)

    output_dir = Path(
        config.output_dir
    )

    if (
        output_dir.exists()
        and any(output_dir.iterdir())
    ):
        raise MembershipDensityGenerationError(
            "Output directory is not empty: "
            f"{output_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    document, allocation = (
        build_density_objectives_document(
            config
        )
    )

    objectives_path = (
        output_dir / "objectives.yaml"
    )

    write_yaml(
        objectives_path,
        document,
    )

    ckg = _fresh_ckg(
        output_dir
    )

    ckg.bootstrap_objectives(
        str(objectives_path)
    )

    validate_reference_integrity(
        ckg,
        config.objective_id,
    )

    validate_graph_projection(
        ckg,
        config.objective_id,
    )

    counts = count_structure(
        ckg,
        config.objective_id,
    )

    maximum_count = (
        membership_capacity(document)
    )

    expected_count = (
        target_membership_count(
            maximum_membership_count=(
                maximum_count
            ),
            density_percent=(
                config.membership_density_percent
            ),
        )
    )

    expected_density = Fraction(
        config.membership_density_percent,
        100,
    )

    realised_density = Fraction(
        int(counts["membership_count"]),
        maximum_count,
    )

    if (
        counts["constraint_count"]
        != config.n_constraints
    ):
        raise MembershipDensityGenerationError(
            "Realised constraint count differs "
            "from requested value."
        )

    if (
        counts["virtual_node_count"]
        != config.n_virtual_nodes
    ):
        raise MembershipDensityGenerationError(
            "Realised virtual-node count differs "
            "from requested value."
        )

    if (
        counts["membership_count"]
        != expected_count
    ):
        raise MembershipDensityGenerationError(
            "Realised membership count differs "
            "from requested density."
        )

    if realised_density != expected_density:
        raise MembershipDensityGenerationError(
            "Realised density differs from the "
            "exact rational target."
        )

    if any(count <= 0 for count in allocation):
        raise MembershipDensityGenerationError(
            "Every requirement set must remain "
            "nonempty."
        )

    configuration_value = asdict(
        config
    )

    configuration_value[
        "output_dir"
    ] = "<excluded>"

    configuration_digest = (
        sha256_digest(
            configuration_value
        )
    )

    canonical_instance = {
        "generator_version": (
            GENERATOR_VERSION
        ),
        "document": document,
        "counts": {
            **counts,
            "maximum_membership_count": (
                maximum_count
            ),
            "allocation": list(allocation),
        },
        "configuration_digest": (
            configuration_digest
        ),
    }

    instance_digest = sha256_digest(
        canonical_instance
    )

    manifest = MembershipDensityManifest(
        generator_version=GENERATOR_VERSION,
        objective_id=config.objective_id,
        requested_constraint_count=(
            config.n_constraints
        ),
        realised_constraint_count=int(
            counts["constraint_count"]
        ),
        requested_virtual_node_count=(
            config.n_virtual_nodes
        ),
        realised_virtual_node_count=int(
            counts["virtual_node_count"]
        ),
        requested_membership_density_percent=(
            config.membership_density_percent
        ),
        realised_membership_density_percent=(
            int(
                realised_density
                * 100
            )
        ),
        requirement_set_count=int(
            counts["requirement_set_count"]
        ),
        requirement_membership_link_count=int(
            counts["membership_count"]
        ),
        maximum_membership_link_count=(
            maximum_count
        ),
        membership_density=float(
            realised_density
        ),
        graph_node_count=int(
            counts["graph_node_count"]
        ),
        graph_edge_count=int(
            counts["graph_edge_count"]
        ),
        seed=config.seed,
        configuration_digest=(
            configuration_digest
        ),
        instance_digest=instance_digest,
    )

    (
        output_dir / "manifest.json"
    ).write_text(
        json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return manifest
