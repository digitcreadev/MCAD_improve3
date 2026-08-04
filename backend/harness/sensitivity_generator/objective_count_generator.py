
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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

GENERATOR_VERSION = "mcad-sensitivity-e2.1-objective-count-v1"


@dataclass(frozen=True)
class ObjectiveCountConfig:
    instance_id: str
    objective_count: int
    selected_objective_index: int
    constraints_per_objective: int
    virtual_nodes_per_objective: int
    seed: int
    output_dir: str


@dataclass(frozen=True)
class ObjectiveCountStructuralManifest:
    generator_version: str
    objective_id: str
    selected_objective_id: str
    selected_objective_index: int
    objective_ids: tuple[str, ...]
    requested_objective_count: int
    realised_objective_count: int
    requested_constraint_count: int
    realised_constraint_count: int
    requested_virtual_node_count: int
    realised_virtual_node_count: int
    total_constraint_count: int
    total_virtual_node_count: int
    requirement_set_count: int
    requirement_membership_link_count: int
    membership_density: float
    graph_node_count: int
    graph_edge_count: int
    seed: int
    selected_objective_shape_digest: str
    configuration_digest: str
    instance_digest: str


def _identifier(value: str) -> str:
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
            "instance_id must contain an "
            "alphanumeric character."
        )

    return cleaned


def _positive(
    name: str,
    value: int,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(
            f"{name} must be a strictly positive integer."
        )


def _validate(
    config: ObjectiveCountConfig,
) -> None:
    _identifier(config.instance_id)
    _positive(
        "objective_count",
        config.objective_count,
    )
    _positive(
        "constraints_per_objective",
        config.constraints_per_objective,
    )
    _positive(
        "virtual_nodes_per_objective",
        config.virtual_nodes_per_objective,
    )
    _positive("seed", config.seed)

    if (
        isinstance(
            config.selected_objective_index,
            bool,
        )
        or not isinstance(
            config.selected_objective_index,
            int,
        )
        or not (
            0
            <= config.selected_objective_index
            < config.objective_count
        )
    ):
        raise ValueError(
            "selected_objective_index must identify "
            "one generated objective."
        )

    if (
        config.virtual_nodes_per_objective
        < config.constraints_per_objective
    ):
        raise ValueError(
            "virtual_nodes_per_objective must be "
            "at least constraints_per_objective."
        )

    if not str(config.output_dir).strip():
        raise ValueError(
            "output_dir must not be empty."
        )


def _objective_id(
    config: ObjectiveCountConfig,
    index: int,
) -> str:
    return (
        f"O_{_identifier(config.instance_id).upper()}_"
        f"OBJ{index + 1:04d}"
    )


def _normalise_ids(
    value: Any,
    objective_id: str,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalise_ids(
                item,
                objective_id,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _normalise_ids(
                item,
                objective_id,
            )
            for item in value
        ]

    if isinstance(value, str):
        return value.replace(
            objective_id,
            "<SELECTED_OBJECTIVE>",
        )

    return value


def _prepare_output(
    output_dir: Path,
) -> None:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ValueError(
                "Objective-count structural output "
                "directory must be absent or empty: "
                f"{output_dir}"
            )
    else:
        output_dir.mkdir(
            parents=True,
            exist_ok=False,
        )


def _build_document(
    config: ObjectiveCountConfig,
) -> dict[str, Any]:
    objectives: list[dict[str, Any]] = []

    for index in range(
        config.objective_count
    ):
        objective_id = _objective_id(
            config,
            index,
        )

        generated = build_objectives_document(
            StructuralConfig(
                objective_id=objective_id,
                n_constraints=(
                    config.constraints_per_objective
                ),
                n_virtual_nodes=(
                    config.virtual_nodes_per_objective
                ),
                seed=(
                    config.seed
                    + index * 1_000_003
                ),
                output_dir="<not-written>",
            )
        ).get("objectives")

        if (
            not isinstance(generated, list)
            or len(generated) != 1
            or not isinstance(generated[0], dict)
        ):
            raise ValueError(
                "Legacy structural generator did not "
                "return exactly one objective."
            )

        objectives.append(generated[0])

    return {"objectives": objectives}


def generate_objective_count_instance(
    config: ObjectiveCountConfig,
) -> ObjectiveCountStructuralManifest:
    _validate(config)

    output_dir = Path(config.output_dir)
    _prepare_output(output_dir)

    document = _build_document(config)

    objective_ids = tuple(
        str(item["id"])
        for item in document["objectives"]
    )

    selected_id = objective_ids[
        config.selected_objective_index
    ]

    objectives_path = (
        output_dir / "objectives.yaml"
    )

    write_yaml(
        objectives_path,
        document,
    )

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

    ckg.bootstrap_objectives(
        str(objectives_path)
    )

    if set(ckg.objectives) != set(objective_ids):
        raise ValueError(
            "Realised objective identifiers differ "
            "from the generated set."
        )

    counts_by_objective: dict[
        str,
        dict[str, int | float],
    ] = {}

    maximum_membership_count = 0

    for objective_id in objective_ids:
        validate_reference_integrity(
            ckg,
            objective_id,
        )
        validate_graph_projection(
            ckg,
            objective_id,
        )

        counts = count_structure(
            ckg,
            objective_id,
        )

        counts_by_objective[
            objective_id
        ] = counts

        if (
            counts["constraint_count"]
            != config.constraints_per_objective
        ):
            raise ValueError(
                "Per-objective constraint baseline changed."
            )

        if (
            counts["virtual_node_count"]
            != config.virtual_nodes_per_objective
        ):
            raise ValueError(
                "Per-objective virtual-node baseline changed."
            )

        for constraint in (
            ckg.objectives[
                objective_id
            ].get("constraints") or {}
        ).values():
            maximum_membership_count += (
                len(
                    constraint.get(
                        "requirement_sets"
                    ) or []
                )
                * len(
                    constraint.get(
                        "virtual_nodes"
                    ) or []
                )
            )

    selected_counts = counts_by_objective[
        selected_id
    ]

    total_constraints = sum(
        int(item["constraint_count"])
        for item in counts_by_objective.values()
    )

    total_virtual_nodes = sum(
        int(item["virtual_node_count"])
        for item in counts_by_objective.values()
    )

    requirement_sets = sum(
        int(item["requirement_set_count"])
        for item in counts_by_objective.values()
    )

    memberships = sum(
        int(item["membership_count"])
        for item in counts_by_objective.values()
    )

    density = (
        memberships / maximum_membership_count
        if maximum_membership_count
        else 0.0
    )

    configuration = asdict(config)
    configuration["output_dir"] = "<excluded>"

    configuration_digest = sha256_digest(
        configuration
    )

    selected_objective = document[
        "objectives"
    ][config.selected_objective_index]

    selected_shape_digest = sha256_digest(
        _normalise_ids(
            selected_objective,
            selected_id,
        )
    )

    instance_digest = sha256_digest(
        {
            "document": document,
            "configuration_digest": (
                configuration_digest
            ),
            "selected_objective_shape_digest": (
                selected_shape_digest
            ),
            "total_constraint_count": (
                total_constraints
            ),
            "total_virtual_node_count": (
                total_virtual_nodes
            ),
            "requirement_set_count": (
                requirement_sets
            ),
            "membership_count": memberships,
            "membership_density": round(
                density,
                6,
            ),
        }
    )

    manifest = ObjectiveCountStructuralManifest(
        generator_version=GENERATOR_VERSION,
        objective_id=selected_id,
        selected_objective_id=selected_id,
        selected_objective_index=(
            config.selected_objective_index
        ),
        objective_ids=objective_ids,
        requested_objective_count=(
            config.objective_count
        ),
        realised_objective_count=len(
            ckg.objectives
        ),
        requested_constraint_count=(
            config.constraints_per_objective
        ),
        realised_constraint_count=int(
            selected_counts["constraint_count"]
        ),
        requested_virtual_node_count=(
            config.virtual_nodes_per_objective
        ),
        realised_virtual_node_count=int(
            selected_counts["virtual_node_count"]
        ),
        total_constraint_count=(
            total_constraints
        ),
        total_virtual_node_count=(
            total_virtual_nodes
        ),
        requirement_set_count=(
            requirement_sets
        ),
        requirement_membership_link_count=(
            memberships
        ),
        membership_density=round(
            density,
            6,
        ),
        graph_node_count=(
            ckg.G.number_of_nodes()
        ),
        graph_edge_count=(
            ckg.G.number_of_edges()
        ),
        seed=config.seed,
        selected_objective_shape_digest=(
            selected_shape_digest
        ),
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
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return manifest
