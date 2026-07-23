#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.ckg.ckg_updater import CKGGraph, _node


GENERATOR_VERSION = "mcad-sensitivity-e2.1-v1"


@dataclass(frozen=True)
class StructuralConfig:
    objective_id: str
    n_constraints: int
    n_virtual_nodes: int
    seed: int
    output_dir: str


@dataclass(frozen=True)
class StructuralManifest:
    generator_version: str
    objective_id: str
    requested_constraint_count: int
    realised_constraint_count: int
    requested_virtual_node_count: int
    realised_virtual_node_count: int
    requirement_set_count: int
    requirement_membership_link_count: int
    membership_density: float
    graph_node_count: int
    graph_edge_count: int
    seed: int
    configuration_digest: str
    instance_digest: str


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def distribute_virtual_nodes(
    n_constraints: int,
    n_virtual_nodes: int,
) -> list[int]:
    if n_constraints < 1:
        raise ValueError("n_constraints must be >= 1")

    if n_virtual_nodes < n_constraints:
        raise ValueError(
            "n_virtual_nodes must be >= n_constraints "
            "so each constraint has at least one NV"
        )

    base = n_virtual_nodes // n_constraints
    remainder = n_virtual_nodes % n_constraints

    return [
        base + (1 if index < remainder else 0)
        for index in range(n_constraints)
    ]


def build_objectives_document(
    config: StructuralConfig,
) -> dict[str, Any]:
    rng = random.Random(config.seed)

    distribution = distribute_virtual_nodes(
        config.n_constraints,
        config.n_virtual_nodes,
    )

    measures = [
        "Sales",
        "Cost",
        "Margin",
        "Quantity",
        "StockoutRate",
        "ReturnRate",
        "GrowthRate",
        "Profit",
    ]

    aggregators = [
        "SUM",
        "AVG",
        "MIN",
        "MAX",
    ]

    units = [
        "USD",
        "PERCENT",
        "COUNT",
    ]

    constraints: list[dict[str, Any]] = []
    kpis: list[str] = []

    for constraint_index, nv_count in enumerate(
        distribution,
        start=1,
    ):
        constraint_id = (
            f"{config.objective_id}_C{constraint_index:04d}"
        )
        kpi_id = (
            f"{config.objective_id}_KPI{constraint_index:04d}"
        )
        kpis.append(kpi_id)

        virtual_nodes: list[dict[str, Any]] = []
        requirement_set: list[str] = []

        measure = measures[
            (constraint_index - 1) % len(measures)
        ]
        aggregator = aggregators[
            (constraint_index - 1) % len(aggregators)
        ]
        unit = units[
            (constraint_index - 1) % len(units)
        ]

        for nv_index in range(1, nv_count + 1):
            nv_id = (
                f"{config.objective_id}"
                f"_C{constraint_index:04d}"
                f"_NV{nv_index:04d}"
            )

            requirement_set.append(nv_id)

            year = 2000 + rng.randint(0, 20)
            region = f"Region_{rng.randint(1, 10):02d}"

            virtual_nodes.append(
                {
                    "id": nv_id,
                    "fact": "SyntheticFact",
                    "grain": [
                        "Time.Month",
                        "Geography.Region",
                    ],
                    "measure": measure,
                    "aggregator": aggregator,
                    "unit": unit,
                    "slicers": {
                        "Geography.Region": region,
                        "Time.Year": str(year),
                    },
                    "window_start": f"{year}-01-01",
                    "window_end": f"{year}-12-31",
                }
            )

        constraints.append(
            {
                "id": constraint_id,
                "kpi_id": kpi_id,
                "description": (
                    f"Synthetic constraint {constraint_index}"
                ),
                "weight": 1.0,
                "virtual_nodes": virtual_nodes,
                "requirement_sets": [
                    requirement_set,
                ],
            }
        )

    document = {
        "objectives": [
            {
                "id": config.objective_id,
                "name": config.objective_id,
                "description": (
                    "Synthetic sensitivity structural objective"
                ),
                "kpis": kpis,
                "constraints": constraints,
            }
        ]
    }

    return document


def write_yaml(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            value,
            handle,
            allow_unicode=True,
            sort_keys=False,
        )


def count_structure(
    ckg: CKGGraph,
    objective_id: str,
) -> dict[str, int | float]:
    objective = ckg.objectives.get(objective_id)

    if not objective:
        raise ValueError(
            f"Objective not loaded: {objective_id}"
        )

    constraints = objective.get("constraints") or {}

    virtual_node_count = 0
    requirement_set_count = 0
    membership_count = 0
    maximum_membership_count = 0

    for constraint in constraints.values():
        nv_ids = list(
            constraint.get("virtual_nodes") or []
        )
        requirement_sets = list(
            constraint.get("requirement_sets") or []
        )

        virtual_node_count += len(nv_ids)
        requirement_set_count += len(requirement_sets)

        for requirement_set in requirement_sets:
            membership_count += len(requirement_set)

        maximum_membership_count += (
            len(requirement_sets) * len(nv_ids)
        )

    density = (
        membership_count / maximum_membership_count
        if maximum_membership_count
        else 0.0
    )

    return {
        "constraint_count": len(constraints),
        "virtual_node_count": virtual_node_count,
        "requirement_set_count": requirement_set_count,
        "membership_count": membership_count,
        "membership_density": round(density, 6),
        "graph_node_count": ckg.G.number_of_nodes(),
        "graph_edge_count": ckg.G.number_of_edges(),
    }


def validate_reference_integrity(
    ckg: CKGGraph,
    objective_id: str,
) -> None:
    objective = ckg.objectives.get(objective_id)

    if not objective:
        raise ValueError(
            f"Objective not found: {objective_id}"
        )

    constraints = objective.get("constraints") or {}

    seen_constraint_ids: set[str] = set()
    seen_nv_ids: set[str] = set()

    for constraint_id, constraint in constraints.items():
        if constraint_id in seen_constraint_ids:
            raise ValueError(
                f"Duplicate constraint id: {constraint_id}"
            )

        seen_constraint_ids.add(constraint_id)

        declared_nv_ids = list(
            constraint.get("virtual_nodes") or []
        )

        if not declared_nv_ids:
            raise ValueError(
                f"Constraint without NV: {constraint_id}"
            )

        declared_nv_set = set(declared_nv_ids)

        if len(declared_nv_set) != len(declared_nv_ids):
            raise ValueError(
                f"Duplicate NV in constraint: {constraint_id}"
            )

        for nv_id in declared_nv_ids:
            if nv_id in seen_nv_ids:
                raise ValueError(
                    f"Globally duplicated NV id: {nv_id}"
                )

            seen_nv_ids.add(nv_id)

        for requirement_set in (
            constraint.get("requirement_sets") or []
        ):
            missing = (
                set(requirement_set)
                - declared_nv_set
            )

            if missing:
                raise ValueError(
                    f"Unknown requirement-set NVs in "
                    f"{constraint_id}: {sorted(missing)}"
                )


def validate_graph_projection(
    ckg: CKGGraph,
    objective_id: str,
) -> None:
    objective = ckg.objectives[objective_id]
    objective_node = _node("objective", objective_id)

    if not ckg.G.has_node(objective_node):
        raise ValueError(
            f"Missing objective graph node: {objective_node}"
        )

    for constraint_id, constraint in (
        objective.get("constraints") or {}
    ).items():
        constraint_node = _node(
            "constraint",
            constraint_id,
        )

        if not ckg.G.has_node(constraint_node):
            raise ValueError(
                f"Missing constraint node: "
                f"{constraint_node}"
            )

        edge_data = ckg.G.get_edge_data(
            objective_node,
            constraint_node,
        )

        if not edge_data or (
            edge_data.get("rel")
            != "HAS_CONSTRAINT"
        ):
            raise ValueError(
                f"Missing HAS_CONSTRAINT edge for "
                f"{constraint_id}"
            )

        for nv_id in (
            constraint.get("virtual_nodes") or []
        ):
            nv_node = _node("nv", nv_id)

            if not ckg.G.has_node(nv_node):
                raise ValueError(
                    f"Missing NV node: {nv_node}"
                )

            edge_data = ckg.G.get_edge_data(
                constraint_node,
                nv_node,
            )

            if not edge_data or (
                edge_data.get("rel")
                != "REQUIRES_NV"
            ):
                raise ValueError(
                    f"Missing REQUIRES_NV edge for "
                    f"{constraint_id} -> {nv_id}"
                )


def generate_structural_instance(
    config: StructuralConfig,
) -> StructuralManifest:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    document = build_objectives_document(config)

    yaml_path = output_dir / "objectives.yaml"
    write_yaml(yaml_path, document)

    ckg = CKGGraph(
        output_dir=str(
            output_dir / "ckg_runtime"
        )
    )

    # Replace the automatically bootstrapped catalogue
    # with the generated canonical instance.
    ckg.G.clear()
    ckg.objectives.clear()
    ckg.history.clear()
    ckg.session_coverage.clear()
    ckg.session_weighted_coverage.clear()
    ckg.session_resource_coverage.clear()

    ckg.bootstrap_objectives(str(yaml_path))

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

    if (
        counts["constraint_count"]
        != config.n_constraints
    ):
        raise ValueError(
            "Realised constraint count differs "
            "from requested value"
        )

    if (
        counts["virtual_node_count"]
        != config.n_virtual_nodes
    ):
        raise ValueError(
            "Realised NV count differs "
            "from requested value"
        )

    configuration_value = asdict(config)
    configuration_value["output_dir"] = "<excluded>"

    configuration_digest = sha256_digest(
        configuration_value
    )

    canonical_instance = {
        "document": document,
        "counts": counts,
        "configuration_digest": configuration_digest,
    }

    instance_digest = sha256_digest(
        canonical_instance
    )

    manifest = StructuralManifest(
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
        requirement_set_count=int(
            counts["requirement_set_count"]
        ),
        requirement_membership_link_count=int(
            counts["membership_count"]
        ),
        membership_density=float(
            counts["membership_density"]
        ),
        graph_node_count=int(
            counts["graph_node_count"]
        ),
        graph_edge_count=int(
            counts["graph_edge_count"]
        ),
        seed=config.seed,
        configuration_digest=configuration_digest,
        instance_digest=instance_digest,
    )

    manifest_path = output_dir / "manifest.json"

    manifest_path.write_text(
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
