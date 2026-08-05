from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.sensitivity_generator.structural_generator import (
    count_structure,
    sha256_digest,
    validate_graph_projection,
    validate_reference_integrity,
    write_yaml,
)

GENERATOR_VERSION = "mcad-sensitivity-e2.1-objective-count-v2"
SESSION_SUPPORT_POLICY = "union_requirement_sets"
CONSTRAINTS_PER_OBJECTIVE = 8
VIRTUAL_NODES_PER_CONSTRAINT = 4
VIRTUAL_NODES_PER_OBJECTIVE = 32
REQUIREMENT_SET_LOCAL_INDICES = ((0, 1), (1, 2))
USEFUL_LOCAL_INDICES = (0, 1, 2)
IRRELEVANT_LOCAL_INDICES = (3,)


@dataclass(frozen=True)
class ObjectiveCountV2Config:
    instance_id: str
    objective_count: int
    selected_objective_index: int
    constraints_per_objective: int
    virtual_nodes_per_objective: int
    seed: int
    output_dir: str


@dataclass(frozen=True)
class ObjectiveCountV2StructuralManifest:
    generator_version: str
    objective_id: str
    selected_objective_id: str
    selected_objective_index: int
    objective_ids: tuple[str, ...]
    requested_objective_count: int
    realised_objective_count: int
    objective_count: int
    requested_constraint_count: int
    realised_constraint_count: int
    selected_objective_constraint_count: int
    requested_virtual_node_count: int
    realised_virtual_node_count: int
    total_constraint_count: int
    useful_virtual_node_count: int
    irrelevant_virtual_node_count: int
    total_virtual_node_count: int
    requirement_set_count: int
    requirement_membership_link_count: int
    maximum_membership_link_count: int
    membership_density: float
    realised_density: float
    graph_node_count: int
    graph_edge_count: int
    session_support_policy: str
    seed: int
    selected_objective_shape_digest: str
    configuration_digest: str
    instance_digest: str


def _identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        raise ValueError("instance_id must contain an alphanumeric character.")
    return cleaned


def _positive(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a strictly positive integer.")


def _validate(config: ObjectiveCountV2Config) -> None:
    _identifier(config.instance_id)
    _positive("objective_count", config.objective_count)
    _positive("constraints_per_objective", config.constraints_per_objective)
    _positive("virtual_nodes_per_objective", config.virtual_nodes_per_objective)
    _positive("seed", config.seed)

    if config.constraints_per_objective != CONSTRAINTS_PER_OBJECTIVE:
        raise ValueError(
            "objective-count v2 requires exactly 8 constraints per objective."
        )
    if config.virtual_nodes_per_objective != VIRTUAL_NODES_PER_OBJECTIVE:
        raise ValueError(
            "objective-count v2 requires exactly 32 virtual nodes per objective."
        )
    if (
        isinstance(config.selected_objective_index, bool)
        or not isinstance(config.selected_objective_index, int)
        or not 0 <= config.selected_objective_index < config.objective_count
    ):
        raise ValueError(
            "selected_objective_index must identify one generated objective."
        )
    if not str(config.output_dir).strip():
        raise ValueError("output_dir must not be empty.")


def _objective_id(config: ObjectiveCountV2Config, index: int) -> str:
    return (
        f"O_{_identifier(config.instance_id).upper()}_"
        f"OBJ{index + 1:04d}"
    )


def _normalise_ids(value: Any, objective_id: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalise_ids(item, objective_id)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalise_ids(item, objective_id) for item in value]
    if isinstance(value, str):
        return value.replace(objective_id, "<SELECTED_OBJECTIVE>")
    return value


def _prepare_output(output_dir: Path) -> None:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ValueError(
                "Objective-count v2 structural output directory must be absent "
                f"or empty: {output_dir}"
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=False)


def _context_pairs(seed: int, constraint_index: int) -> list[tuple[int, str]]:
    candidates = [
        (year, f"Region_{region_index:02d}")
        for year in range(2000, 2021)
        for region_index in range(1, 11)
    ]
    return sorted(
        candidates,
        key=lambda pair: (
            hashlib.sha256(
                (
                    "mcad-sa5-objective-count-context-v2"
                    f"|{seed}|{constraint_index}|{pair[0]}|{pair[1]}"
                ).encode("utf-8")
            ).hexdigest(),
            pair,
        ),
    )[:VIRTUAL_NODES_PER_CONSTRAINT]


def _build_objective(
    *,
    objective_id: str,
    seed: int,
) -> dict[str, Any]:
    measures = (
        "Sales",
        "Cost",
        "Margin",
        "Quantity",
        "StockoutRate",
        "ReturnRate",
        "GrowthRate",
        "Profit",
    )
    aggregators = ("SUM", "AVG", "MIN", "MAX")
    units = ("USD", "PERCENT", "COUNT")

    constraints: list[dict[str, Any]] = []
    kpis: list[str] = []

    for constraint_index in range(1, CONSTRAINTS_PER_OBJECTIVE + 1):
        constraint_id = f"{objective_id}_C{constraint_index:04d}"
        kpi_id = f"{objective_id}_KPI{constraint_index:04d}"
        kpis.append(kpi_id)

        measure = measures[(constraint_index - 1) % len(measures)]
        aggregator = aggregators[(constraint_index - 1) % len(aggregators)]
        unit = units[(constraint_index - 1) % len(units)]

        virtual_nodes: list[dict[str, Any]] = []
        contexts = _context_pairs(seed, constraint_index)

        for local_index, (year, region) in enumerate(contexts):
            nv_id = f"{constraint_id}_NV{local_index + 1:04d}"
            virtual_nodes.append(
                {
                    "id": nv_id,
                    "fact": "SyntheticFact",
                    "grain": ["Time.Month", "Geography.Region"],
                    "measure": measure,
                    "aggregator": aggregator,
                    "unit": unit,
                    "slicers": {
                        "Geography.Region": region,
                        "Time.Year": str(year),
                    },
                    "window_start": f"{year}-01-01",
                    "window_end": f"{year}-12-31",
                    "sa5_local_virtual_node_index": local_index,
                    "sa5_support_coordinate": (
                        (constraint_index - 1) * len(USEFUL_LOCAL_INDICES)
                        + local_index
                        if local_index in USEFUL_LOCAL_INDICES
                        else None
                    ),
                    "sa5_useful_for_session_support": (
                        local_index in USEFUL_LOCAL_INDICES
                    ),
                }
            )

        requirement_sets = [
            [virtual_nodes[index]["id"] for index in local_indices]
            for local_indices in REQUIREMENT_SET_LOCAL_INDICES
        ]

        constraints.append(
            {
                "id": constraint_id,
                "kpi_id": kpi_id,
                "description": f"Synthetic constraint {constraint_index}",
                "weight": 1.0,
                "virtual_nodes": virtual_nodes,
                "requirement_sets": requirement_sets,
            }
        )

    return {
        "id": objective_id,
        "name": objective_id,
        "description": "Synthetic SA5 objective-count v2 objective",
        "session_support_policy": SESSION_SUPPORT_POLICY,
        "kpis": kpis,
        "constraints": constraints,
    }


def build_objectives_document_v2(
    config: ObjectiveCountV2Config,
) -> dict[str, Any]:
    _validate(config)
    objectives = []
    for index in range(config.objective_count):
        objectives.append(
            _build_objective(
                objective_id=_objective_id(config, index),
                seed=config.seed + index * 1_000_003,
            )
        )
    return {"objectives": objectives}


def generate_objective_count_instance_v2(
    config: ObjectiveCountV2Config,
) -> ObjectiveCountV2StructuralManifest:
    _validate(config)
    output_dir = Path(config.output_dir)
    _prepare_output(output_dir)

    document = build_objectives_document_v2(config)
    objective_ids = tuple(str(item["id"]) for item in document["objectives"])
    selected_id = objective_ids[config.selected_objective_index]
    objectives_path = output_dir / "objectives.yaml"
    write_yaml(objectives_path, document)

    ckg = CKGGraph(output_dir=str(output_dir / "ckg_runtime"))
    ckg.G.clear()
    ckg.objectives.clear()
    ckg.history.clear()
    ckg.session_coverage.clear()
    ckg.session_weighted_coverage.clear()
    ckg.session_resource_coverage.clear()
    ckg.bootstrap_objectives(str(objectives_path))

    if set(ckg.objectives) != set(objective_ids):
        raise ValueError("Realised objective identifiers differ from generated set.")

    counts_by_objective: dict[str, dict[str, int | float]] = {}
    maximum_membership_count = 0
    for objective_id in objective_ids:
        validate_reference_integrity(ckg, objective_id)
        validate_graph_projection(ckg, objective_id)
        counts = count_structure(ckg, objective_id)
        counts_by_objective[objective_id] = counts
        if counts["constraint_count"] != CONSTRAINTS_PER_OBJECTIVE:
            raise ValueError("Per-objective constraint baseline changed.")
        if counts["virtual_node_count"] != VIRTUAL_NODES_PER_OBJECTIVE:
            raise ValueError("Per-objective virtual-node baseline changed.")
        if counts["requirement_set_count"] != 16:
            raise ValueError("Per-objective requirement-set count changed.")
        if counts["membership_count"] != 32:
            raise ValueError("Per-objective membership-link count changed.")
        if counts["membership_density"] != 0.5:
            raise ValueError("Per-objective membership density changed.")
        for constraint in (ckg.objectives[objective_id].get("constraints") or {}).values():
            maximum_membership_count += len(
                constraint.get("requirement_sets") or []
            ) * len(constraint.get("virtual_nodes") or [])

    selected_counts = counts_by_objective[selected_id]
    total_constraints = sum(
        int(item["constraint_count"]) for item in counts_by_objective.values()
    )
    total_virtual_nodes = sum(
        int(item["virtual_node_count"]) for item in counts_by_objective.values()
    )
    requirement_sets = sum(
        int(item["requirement_set_count"]) for item in counts_by_objective.values()
    )
    memberships = sum(
        int(item["membership_count"]) for item in counts_by_objective.values()
    )
    density = memberships / maximum_membership_count if maximum_membership_count else 0.0

    configuration = asdict(config)
    configuration["output_dir"] = "<excluded>"
    configuration_digest = sha256_digest(configuration)
    selected_objective = document["objectives"][config.selected_objective_index]
    selected_shape_digest = sha256_digest(
        _normalise_ids(selected_objective, selected_id)
    )
    instance_digest = sha256_digest(
        {
            "document": document,
            "configuration_digest": configuration_digest,
            "selected_objective_shape_digest": selected_shape_digest,
            "total_constraint_count": total_constraints,
            "total_virtual_node_count": total_virtual_nodes,
            "requirement_set_count": requirement_sets,
            "membership_count": memberships,
            "maximum_membership_count": maximum_membership_count,
            "realised_density": round(density, 6),
            "session_support_policy": SESSION_SUPPORT_POLICY,
        }
    )

    manifest = ObjectiveCountV2StructuralManifest(
        generator_version=GENERATOR_VERSION,
        objective_id=selected_id,
        selected_objective_id=selected_id,
        selected_objective_index=config.selected_objective_index,
        objective_ids=objective_ids,
        requested_objective_count=config.objective_count,
        realised_objective_count=len(ckg.objectives),
        objective_count=len(ckg.objectives),
        requested_constraint_count=config.constraints_per_objective,
        realised_constraint_count=int(selected_counts["constraint_count"]),
        selected_objective_constraint_count=int(selected_counts["constraint_count"]),
        requested_virtual_node_count=config.virtual_nodes_per_objective,
        realised_virtual_node_count=int(selected_counts["virtual_node_count"]),
        total_constraint_count=total_constraints,
        useful_virtual_node_count=len(objective_ids) * 24,
        irrelevant_virtual_node_count=len(objective_ids) * 8,
        total_virtual_node_count=total_virtual_nodes,
        requirement_set_count=requirement_sets,
        requirement_membership_link_count=memberships,
        maximum_membership_link_count=maximum_membership_count,
        membership_density=round(density, 6),
        realised_density=round(density, 6),
        graph_node_count=ckg.G.number_of_nodes(),
        graph_edge_count=ckg.G.number_of_edges(),
        session_support_policy=SESSION_SUPPORT_POLICY,
        seed=config.seed,
        selected_objective_shape_digest=selected_shape_digest,
        configuration_digest=configuration_digest,
        instance_digest=instance_digest,
    )

    (output_dir / "manifest.json").write_text(
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
