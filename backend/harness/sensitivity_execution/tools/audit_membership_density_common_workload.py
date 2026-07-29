from __future__ import annotations

import argparse
import json
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.harness.sensitivity_execution.execute_controlled_family import (
    _discover_all_instances,
)
from backend.harness.sensitivity_generator.oracles.membership_density_oracle import (
    assert_valid_density,
    load_objectives_yaml,
    non_membership_semantic_digest,
    normalized_membership_edges,
)


AUDITOR_VERSION = (
    "mcad-sensitivity-sa4-membership-density-"
    "common-workload-auditor-v2"
)

EXPECTED_FACTOR = "membership_density"

EXPECTED_CAMPAIGN_GENERATOR_VERSION = (
    "mcad-sensitivity-e2.2-membership-density-v1"
)

EXPECTED_STRUCTURAL_GENERATOR_VERSION = (
    "mcad-sensitivity-e2.1-membership-density-v1"
)

DEFAULT_REQUIRED_LEVELS = (25, 50, 75, 100)

TARGET_MEMBERSHIP_COUNTS = {
    25: 6,
    50: 12,
    75: 18,
    100: 24,
}


# Copied from the validated historical workload contract.
# It is defined locally because importing the historical
# audit script executes that script and produces unrelated
# constraint-count reports.
SEMANTIC_FIELDS = (
    "fact",
    "grain",
    "measure",
    "aggregator",
    "unit",
    "slicers",
    "window_start",
    "window_end",
)


def workload_query_spec(
    semantic_node: dict[str, Any],
) -> dict[str, Any]:
    year = (
        semantic_node
        .get("slicers", {})
        .get("Time.Year")
    )

    query_spec = {
        "cube": semantic_node["fact"],
        "measures": [
            semantic_node["measure"]
        ],
        "group_by": list(
            semantic_node["grain"]
        ),
        "slicers": deepcopy(
            semantic_node["slicers"]
        ),
        "aggregators": [
            semantic_node["aggregator"]
        ],
        "units": [
            semantic_node["unit"]
        ],
        "window_start": (
            semantic_node["window_start"]
        ),
        "window_end": (
            semantic_node["window_end"]
        ),
    }

    if year is not None:
        query_spec["time_members"] = [
            str(year)
        ]

    return query_spec


class MembershipDensityWorkloadAuditError(
    RuntimeError
):
    """Raised when an SA4 workload invariant is violated."""


@dataclass(frozen=True)
class InstanceSemanticObservation:
    canonical_instance_id: str
    objective_id: str
    factor_level: int
    replication_index: int
    seed: int
    non_membership_semantic_digest: str
    semantic_nodes: Mapping[str, Mapping[str, Any]]
    membership_edges: frozenset[
        tuple[int, int, int]
    ]


def _read_json(
    path: Path,
    *,
    label: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise MembershipDensityWorkloadAuditError(
            f"Missing {label}: {path}"
        )

    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise MembershipDensityWorkloadAuditError(
            f"Invalid JSON in {label}: {path}"
        ) from exc

    if not isinstance(value, dict):
        raise MembershipDensityWorkloadAuditError(
            f"{label} must contain a JSON object."
        )

    return value


def _canonical_json_bytes(
    value: Any,
) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_payload(
    value: Any,
) -> str:
    return sha256(
        _canonical_json_bytes(value)
    ).hexdigest()


def _objective(
    document: Mapping[str, Any],
) -> Mapping[str, Any]:
    objectives = document.get("objectives")

    if (
        not isinstance(objectives, list)
        or len(objectives) != 1
        or not isinstance(objectives[0], Mapping)
    ):
        raise MembershipDensityWorkloadAuditError(
            "Expected exactly one objective."
        )

    return objectives[0]


def _collection_values(
    value: Any,
    *,
    label: str,
) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        collection = value
    elif isinstance(value, Mapping):
        collection = list(value.values())
    else:
        raise MembershipDensityWorkloadAuditError(
            f"{label} must be a list or mapping."
        )

    if not all(
        isinstance(item, Mapping)
        for item in collection
    ):
        raise MembershipDensityWorkloadAuditError(
            f"{label} contains an invalid item."
        )

    return list(collection)


def _virtual_nodes(
    document: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    objective = _objective(document)

    constraints = _collection_values(
        objective.get("constraints"),
        label="objective.constraints",
    )

    result: list[Mapping[str, Any]] = []

    for constraint_index, constraint in enumerate(
        constraints,
        start=1,
    ):
        nodes = _collection_values(
            constraint.get("virtual_nodes"),
            label=(
                "objective.constraints"
                f"[{constraint_index}].virtual_nodes"
            ),
        )

        result.extend(nodes)

    return result


def _semantic_projection(
    node: Mapping[str, Any],
) -> dict[str, Any]:
    missing = [
        field
        for field in SEMANTIC_FIELDS
        if field not in node
    ]

    if missing:
        raise MembershipDensityWorkloadAuditError(
            "Virtual node lacks workload semantic "
            f"fields: {missing}"
        )

    return {
        field: node[field]
        for field in SEMANTIC_FIELDS
    }


def _semantic_node_map(
    document: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Group virtual nodes by canonical query specification.

    Structural virtual-node identity and multiplicity are
    preserved inside each query-equivalence class.
    """
    result: dict[str, dict[str, Any]] = {}
    seen_virtual_node_ids: set[str] = set()

    for node in _virtual_nodes(document):
        projection = _semantic_projection(node)

        semantic_id = _sha256_payload(
            projection
        )

        query_spec = workload_query_spec(
            projection
        )

        if not isinstance(query_spec, dict):
            raise MembershipDensityWorkloadAuditError(
                "workload_query_spec must return a mapping."
            )

        query_spec_digest = _sha256_payload(
            query_spec
        )

        raw_virtual_node_id = node.get("id")

        if (
            not isinstance(
                raw_virtual_node_id,
                str,
            )
            or not raw_virtual_node_id.strip()
        ):
            raise MembershipDensityWorkloadAuditError(
                "Every virtual node must expose a "
                "non-empty string id."
            )

        virtual_node_id = (
            raw_virtual_node_id.strip()
        )

        if (
            virtual_node_id
            in seen_virtual_node_ids
        ):
            raise MembershipDensityWorkloadAuditError(
                "Duplicate virtual-node identifier "
                f"detected: {virtual_node_id}."
            )

        seen_virtual_node_ids.add(
            virtual_node_id
        )

        existing = result.get(
            query_spec_digest
        )

        if existing is None:
            result[
                query_spec_digest
            ] = {
                # Legacy alias retained for downstream
                # readers that previously consumed
                # semantic_id as the workload key.
                "semantic_id": (
                    query_spec_digest
                ),
                "equivalence_class_id": (
                    query_spec_digest
                ),
                "query_spec_digest": (
                    query_spec_digest
                ),
                "semantic_ids": [
                    semantic_id
                ],
                "semantic_projections": [
                    projection
                ],
                "equivalent_virtual_node_ids": [
                    virtual_node_id
                ],
                "equivalence_class_size": 1,
                "query_spec": query_spec,
            }

            continue

        if (
            _canonical_json_bytes(
                existing["query_spec"]
            )
            != _canonical_json_bytes(
                query_spec
            )
        ):
            raise MembershipDensityWorkloadAuditError(
                "Canonical query-spec digest collision "
                f"detected: {query_spec_digest}."
            )

        if (
            semantic_id
            in existing["semantic_ids"]
        ):
            semantic_index = (
                existing["semantic_ids"].index(
                    semantic_id
                )
            )

            if (
                _canonical_json_bytes(
                    existing[
                        "semantic_projections"
                    ][semantic_index]
                )
                != _canonical_json_bytes(
                    projection
                )
            ):
                raise (
                    MembershipDensityWorkloadAuditError(
                        "Semantic digest collision "
                        f"detected: {semantic_id}."
                    )
                )
        else:
            existing[
                "semantic_ids"
            ].append(
                semantic_id
            )

            existing[
                "semantic_projections"
            ].append(
                projection
            )

        existing[
            "equivalent_virtual_node_ids"
        ].append(
            virtual_node_id
        )

        existing[
            "equivalence_class_size"
        ] = len(
            existing[
                "equivalent_virtual_node_ids"
            ]
        )

    for record in result.values():
        semantic_pairs = sorted(
            zip(
                record["semantic_ids"],
                record[
                    "semantic_projections"
                ],
                strict=True,
            ),
            key=lambda item: item[0],
        )

        record["semantic_ids"] = [
            semantic_id
            for semantic_id, _
            in semantic_pairs
        ]

        record[
            "semantic_projections"
        ] = [
            projection
            for _, projection
            in semantic_pairs
        ]

        record[
            "equivalent_virtual_node_ids"
        ] = sorted(
            record[
                "equivalent_virtual_node_ids"
            ]
        )

        record[
            "equivalence_class_size"
        ] = len(
            record[
                "equivalent_virtual_node_ids"
            ]
        )

        if (
            record[
                "equivalence_class_size"
            ]
            < 1
        ):
            raise MembershipDensityWorkloadAuditError(
                "A query-equivalence class must "
                "contain at least one virtual node."
            )

    return result



def _validate_nested_membership_edges(
    edges_by_level: Mapping[
        int,
        frozenset[tuple[int, int, int]],
    ],
    required_levels: Sequence[int],
) -> None:
    ordered_levels = tuple(
        sorted(required_levels)
    )

    for lower, upper in zip(
        ordered_levels,
        ordered_levels[1:],
        strict=False,
    ):
        lower_edges = edges_by_level[lower]
        upper_edges = edges_by_level[upper]

        if not lower_edges < upper_edges:
            raise MembershipDensityWorkloadAuditError(
                "Membership edges are not strictly nested: "
                f"level_{lower} is not a strict subset "
                f"of level_{upper}."
            )


def _observe_instance(
    instance: Any,
) -> InstanceSemanticObservation:
    document = load_objectives_yaml(
        instance.objectives_path
    )

    assert_valid_density(
        document,
        density_percent=instance.factor_level,
    )

    semantic_nodes = _semantic_node_map(
        document
    )

    membership_edges = normalized_membership_edges(
        document
    )

    expected_membership_count = (
        TARGET_MEMBERSHIP_COUNTS.get(
            instance.factor_level
        )
    )

    if expected_membership_count is None:
        raise MembershipDensityWorkloadAuditError(
            "Unsupported density level: "
            f"{instance.factor_level}."
        )

    if (
        len(membership_edges)
        != expected_membership_count
    ):
        raise MembershipDensityWorkloadAuditError(
            "Unexpected membership-link count: "
            f"level={instance.factor_level}, "
            f"expected={expected_membership_count}, "
            f"actual={len(membership_edges)}."
        )

    return InstanceSemanticObservation(
        canonical_instance_id=(
            instance.canonical_instance_id
        ),
        objective_id=instance.objective_id,
        factor_level=instance.factor_level,
        replication_index=(
            instance.replication_index
        ),
        seed=instance.seed,
        non_membership_semantic_digest=(
            non_membership_semantic_digest(
                document
            )
        ),
        semantic_nodes=semantic_nodes,
        membership_edges=membership_edges,
    )


def _audit_replication(
    observations: Sequence[
        InstanceSemanticObservation
    ],
    *,
    required_levels: Sequence[int],
) -> dict[str, Any]:
    ordered = sorted(
        observations,
        key=lambda item: item.factor_level,
    )

    replication_indices = {
        item.replication_index
        for item in ordered
    }

    seeds = {
        item.seed
        for item in ordered
    }

    observed_levels = tuple(
        item.factor_level
        for item in ordered
    )

    required_level_tuple = tuple(
        required_levels
    )

    if len(replication_indices) != 1:
        raise MembershipDensityWorkloadAuditError(
            "Replication audit received mixed "
            "replication indices."
        )

    if len(seeds) != 1:
        raise MembershipDensityWorkloadAuditError(
            "Structural seed varies within a "
            "replication."
        )

    if observed_levels != required_level_tuple:
        raise MembershipDensityWorkloadAuditError(
            "Replication does not contain the exact "
            "density-level matrix: "
            f"expected={required_level_tuple}, "
            f"actual={observed_levels}."
        )

    non_membership_digests = {
        item.non_membership_semantic_digest
        for item in ordered
    }

    if len(non_membership_digests) != 1:
        raise MembershipDensityWorkloadAuditError(
            "Non-membership semantics vary across "
            "density levels."
        )

    query_spec_id_sets = [
        set(item.semantic_nodes)
        for item in ordered
    ]

    reference_query_spec_ids = (
        query_spec_id_sets[0]
    )

    if any(
        value
        != reference_query_spec_ids
        for value
        in query_spec_id_sets[1:]
    ):
        raise MembershipDensityWorkloadAuditError(
            "Canonical query-specification sets vary "
            "across density levels."
        )

    comparable_fields = (
        "equivalence_class_id",
        "query_spec_digest",
        "semantic_ids",
        "semantic_projections",
        "equivalence_class_size",
        "query_spec",
    )

    for query_spec_id in sorted(
        reference_query_spec_ids
    ):
        serialized_records = {
            _canonical_json_bytes(
                {
                    field: item.semantic_nodes[
                        query_spec_id
                    ][field]
                    for field
                    in comparable_fields
                }
            )
            for item in ordered
        }

        if len(serialized_records) != 1:
            raise MembershipDensityWorkloadAuditError(
                "A query-equivalence class varies "
                "across density levels: "
                f"query_spec_digest={query_spec_id}."
            )

    structural_counts = [
        sum(
            int(
                record[
                    "equivalence_class_size"
                ]
            )
            for record
            in item.semantic_nodes.values()
        )
        for item in ordered
    ]

    if len(set(structural_counts)) != 1:
        raise MembershipDensityWorkloadAuditError(
            "Structural virtual-node multiplicity "
            "varies across density levels."
        )

    structural_virtual_node_count = (
        structural_counts[0]
    )

    if structural_virtual_node_count != 24:
        raise MembershipDensityWorkloadAuditError(
            "SA4 requires exactly 24 structural "
            "virtual nodes per instance: "
            f"actual={structural_virtual_node_count}."
        )

    edges_by_level = {
        item.factor_level: item.membership_edges
        for item in ordered
    }

    _validate_nested_membership_edges(
        edges_by_level,
        required_levels,
    )

    replication_index = next(
        iter(replication_indices)
    )

    seed = next(iter(seeds))

    reference = ordered[0]

    # The workload is ordered by canonical query-spec
    # digest. Query-equivalent virtual nodes share one
    # step, while their identifiers and multiplicity
    # remain explicit in the equivalence-class metadata.
    steps = []

    for position, query_spec_id in enumerate(
        sorted(reference.semantic_nodes),
        start=1,
    ):
        reference_class = (
            reference.semantic_nodes[
                query_spec_id
            ]
        )

        equivalent_ids_by_level = {
            str(item.factor_level): list(
                item.semantic_nodes[
                    query_spec_id
                ][
                    "equivalent_virtual_node_ids"
                ]
            )
            for item in ordered
        }

        expected_class_size = int(
            reference_class[
                "equivalence_class_size"
            ]
        )

        if any(
            len(node_ids)
            != expected_class_size
            for node_ids
            in equivalent_ids_by_level.values()
        ):
            raise MembershipDensityWorkloadAuditError(
                "Query-equivalence class multiplicity "
                "varies across density levels: "
                f"query_spec_digest={query_spec_id}."
            )

        steps.append(
            {
                "step_position": position,
                "step_index": position,
                "step_id": f"Q{position:03d}",
                # Backward-compatible alias. In v2 the
                # workload key is the canonical
                # query-specification digest.
                "semantic_id": query_spec_id,
                "equivalence_class_id": (
                    query_spec_id
                ),
                "query_spec_digest": (
                    reference_class[
                        "query_spec_digest"
                    ]
                ),
                "semantic_ids": list(
                    reference_class[
                        "semantic_ids"
                    ]
                ),
                "semantic_projections": list(
                    reference_class[
                        "semantic_projections"
                    ]
                ),
                "equivalence_class_size": (
                    expected_class_size
                ),
                (
                    "equivalent_"
                    "virtual_node_ids_by_level"
                ): equivalent_ids_by_level,
                "query_spec": (
                    reference_class[
                        "query_spec"
                    ]
                ),
            }
        )

    instance_ids_by_level = {
        str(item.factor_level): (
            item.canonical_instance_id
        )
        for item in ordered
    }

    objective_ids_by_level = {
        str(item.factor_level): (
            item.objective_id
        )
        for item in ordered
    }

    membership_counts_by_level = {
        str(level): len(
            edges_by_level[level]
        )
        for level in required_levels
    }

    equivalence_class_size_histogram: dict[
        str,
        int,
    ] = {}

    for step in steps:
        key = str(
            step[
                "equivalence_class_size"
            ]
        )

        equivalence_class_size_histogram[
            key
        ] = (
            equivalence_class_size_histogram.get(
                key,
                0,
            )
            + 1
        )

    query_equivalence_class_count = len(
        steps
    )

    query_equivalent_virtual_node_count = (
        structural_virtual_node_count
        - query_equivalence_class_count
    )

    blueprint_payload = {
        "schema_version": (
            "mcad-sensitivity-sa4-membership-density-"
            "replication-workload-blueprint-v2"
        ),
        "strategy": (
            "one_workload_per_structural_seed_"
            "shared_across_density_levels"
        ),
        "workload_equivalence_key": (
            "canonical_query_spec_digest"
        ),
        "workload_step_count_basis": (
            "unique_canonical_query_specs"
        ),
        "equivalence_class_metadata_required": True,
        "replication_index": replication_index,
        "seed": seed,
        "levels": list(required_levels),
        "instance_ids_by_level": (
            instance_ids_by_level
        ),
        "objective_ids_by_level": (
            objective_ids_by_level
        ),
        "structural_virtual_node_count": (
            structural_virtual_node_count
        ),
        "query_equivalence_class_count": (
            query_equivalence_class_count
        ),
        "step_count": len(steps),
        "steps": steps,
        "objective_binding_mode": (
            "instance_objective_rebound_by_e3"
        ),
    }

    blueprint_digest = _sha256_payload(
        blueprint_payload
    )

    return {
        "replication_index": replication_index,
        "seed": seed,
        "levels": list(required_levels),
        "instance_ids_by_level": (
            instance_ids_by_level
        ),
        "objective_ids_by_level": (
            objective_ids_by_level
        ),
        # Backward-compatible structural count.
        "semantic_node_count": (
            structural_virtual_node_count
        ),
        "structural_virtual_node_count": (
            structural_virtual_node_count
        ),
        # In v2 this count is the number of unique
        # canonical query specifications.
        "strict_common_semantic_node_count": (
            query_equivalence_class_count
        ),
        "strict_common_query_spec_count": (
            query_equivalence_class_count
        ),
        "query_equivalence_class_count": (
            query_equivalence_class_count
        ),
        "query_equivalent_virtual_node_count": (
            query_equivalent_virtual_node_count
        ),
        "equivalence_class_size_histogram": (
            equivalence_class_size_histogram
        ),
        "workload_equivalence_key": (
            "canonical_query_spec_digest"
        ),
        "workload_step_count_basis": (
            "unique_canonical_query_specs"
        ),
        "equivalence_class_metadata_preserved": True,
        "non_membership_semantic_digest": (
            next(iter(non_membership_digests))
        ),
        "membership_counts_by_level": (
            membership_counts_by_level
        ),
        "membership_edges_strictly_nested": True,
        "semantic_sets_exactly_equal": True,
        "query_spec_sets_exactly_equal": True,
        "query_specs_identical": True,
        "workload_blueprint": (
            blueprint_payload
        ),
        "workload_blueprint_digest": (
            blueprint_digest
        ),
    }



def audit_membership_density_campaign(
    campaign_dir: str | Path,
    *,
    required_levels: Sequence[int] = (
        DEFAULT_REQUIRED_LEVELS
    ),
) -> dict[str, Any]:
    root = Path(
        campaign_dir
    ).expanduser().resolve()

    required_level_tuple = tuple(
        int(level)
        for level in required_levels
    )

    if (
        required_level_tuple
        != tuple(
            sorted(
                set(required_level_tuple)
            )
        )
    ):
        raise MembershipDensityWorkloadAuditError(
            "required_levels must be sorted and unique."
        )

    if required_level_tuple != (
        DEFAULT_REQUIRED_LEVELS
    ):
        raise MembershipDensityWorkloadAuditError(
            "SA4 v2 requires the exact levels "
            "25, 50, 75 and 100."
        )

    campaign_manifest = _read_json(
        root / "campaign_manifest.json",
        label="campaign manifest",
    )

    if (
        campaign_manifest.get("factor")
        != EXPECTED_FACTOR
    ):
        raise MembershipDensityWorkloadAuditError(
            "Campaign factor must be "
            f"{EXPECTED_FACTOR!r}."
        )

    if (
        campaign_manifest.get(
            "campaign_generator_version"
        )
        != EXPECTED_CAMPAIGN_GENERATOR_VERSION
    ):
        raise MembershipDensityWorkloadAuditError(
            "Unexpected campaign generator version."
        )

    if (
        campaign_manifest.get(
            "structural_generator_version"
        )
        != EXPECTED_STRUCTURAL_GENERATOR_VERSION
    ):
        raise MembershipDensityWorkloadAuditError(
            "Unexpected structural generator version."
        )

    instances = _discover_all_instances(
        campaign_dir=root,
        campaign_manifest=campaign_manifest,
    )

    by_replication: dict[
        int,
        list[InstanceSemanticObservation],
    ] = defaultdict(list)

    for instance in instances:
        observation = _observe_instance(
            instance
        )

        by_replication[
            observation.replication_index
        ].append(observation)

    if not by_replication:
        raise MembershipDensityWorkloadAuditError(
            "Campaign contains no structural "
            "replications."
        )

    replication_audits = [
        _audit_replication(
            by_replication[
                replication_index
            ],
            required_levels=(
                required_level_tuple
            ),
        )
        for replication_index in sorted(
            by_replication
        )
    ]

    seeds = [
        audit["seed"]
        for audit in replication_audits
    ]

    if len(seeds) != len(set(seeds)):
        raise MembershipDensityWorkloadAuditError(
            "Structural seeds are not unique across "
            "replications."
        )

    query_spec_sets = [
        {
            step[
                "query_spec_digest"
            ]
            for step in audit[
                "workload_blueprint"
            ]["steps"]
        }
        for audit in replication_audits
    ]

    global_common = set.intersection(
        *query_spec_sets
    )

    global_union = set.union(
        *query_spec_sets
    )

    global_exact_equality = all(
        query_spec_set
        == query_spec_sets[0]
        for query_spec_set
        in query_spec_sets[1:]
    )

    partition_step_count_histogram: dict[
        str,
        int,
    ] = {}

    structural_node_count_histogram: dict[
        str,
        int,
    ] = {}

    for replication in replication_audits:
        step_key = str(
            replication[
                "workload_blueprint"
            ]["step_count"]
        )

        partition_step_count_histogram[
            step_key
        ] = (
            partition_step_count_histogram.get(
                step_key,
                0,
            )
            + 1
        )

        structural_key = str(
            replication[
                "structural_virtual_node_count"
            ]
        )

        structural_node_count_histogram[
            structural_key
        ] = (
            structural_node_count_histogram.get(
                structural_key,
                0,
            )
            + 1
        )

    query_equivalence_replications = [
        replication[
            "replication_index"
        ]
        for replication
        in replication_audits
        if (
            replication[
                "query_equivalent_virtual_node_count"
            ]
            > 0
        )
    ]

    audit_payload = {
        "schema_version": (
            "mcad-sensitivity-sa4-membership-density-"
            "common-workload-audit-v2"
        ),
        "auditor_version": AUDITOR_VERSION,
        "status": "success",
        "campaign_id": campaign_manifest.get(
            "campaign_id"
        ),
        "campaign_digest": campaign_manifest.get(
            "campaign_digest"
        ),
        "factor": EXPECTED_FACTOR,
        "required_levels": list(
            required_level_tuple
        ),
        "replication_count": (
            len(replication_audits)
        ),
        "instance_count": len(instances),
        "workload_strategy": (
            "one_workload_per_structural_seed_"
            "shared_across_density_levels"
        ),
        "workload_equivalence_key": (
            "canonical_query_spec_digest"
        ),
        "workload_step_count_basis": (
            "unique_canonical_query_specs"
        ),
        "equivalence_class_metadata_required": True,
        "execution_partition_required": True,
        "replications": replication_audits,
        "partition_step_count_histogram": (
            partition_step_count_histogram
        ),
        "structural_virtual_node_count_histogram": (
            structural_node_count_histogram
        ),
        "query_equivalence_replication_indices": (
            query_equivalence_replications
        ),
        "global_diagnostics": {
            "strict_common_query_spec_count": (
                len(global_common)
            ),
            "query_spec_union_count": (
                len(global_union)
            ),
            "exact_query_spec_set_equality": (
                global_exact_equality
            ),
            # Legacy aliases retained for v1 readers.
            "strict_common_semantic_node_count": (
                len(global_common)
            ),
            "semantic_union_count": (
                len(global_union)
            ),
            "exact_semantic_set_equality": (
                global_exact_equality
            ),
            "global_workload_authorized": False,
        },
        "invariants": {
            "factor_profile_valid": True,
            "exact_level_matrix_per_replication": True,
            "one_seed_per_replication": True,
            "structural_virtual_node_count_fixed": True,
            "non_membership_semantics_fixed": True,
            "query_spec_sets_fixed": True,
            "query_specs_fixed": True,
            "query_equivalent_nodes_grouped": True,
            "equivalence_class_metadata_preserved": True,
            "membership_counts_exact": True,
            "membership_edges_strictly_nested": True,
            "cross_replication_workload_reuse": False,
        },
        "canonical_campaign_execution_authorized": True,
        "controlled_execution_started": False,
        "timing_execution_started": False,
        "latency_claim_authorized": False,
        "scientific_freeze": False,
    }

    audit_payload["audit_digest"] = (
        _sha256_payload(audit_payload)
    )

    return audit_payload



def write_audit_bundle(
    *,
    campaign_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    output_root = Path(
        output_dir
    ).expanduser().resolve()

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit = audit_membership_density_campaign(
        campaign_dir
    )

    audit_path = (
        output_root
        / "membership_density_common_workload_audit.json"
    )

    blueprint_path = (
        output_root
        / "replication_workload_blueprints.json"
    )

    audit_path.write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    blueprint_payload = {
        "schema_version": (
            "mcad-sensitivity-sa4-membership-density-"
            "replication-workload-blueprints-v2"
        ),
        "auditor_version": AUDITOR_VERSION,
        "campaign_id": audit["campaign_id"],
        "campaign_digest": audit[
            "campaign_digest"
        ],
        "strategy": audit[
            "workload_strategy"
        ],
        "execution_partition_required": True,
        "replications": [
            {
                "replication_index": item[
                    "replication_index"
                ],
                "seed": item["seed"],
                "workload_blueprint": item[
                    "workload_blueprint"
                ],
                "workload_blueprint_digest": item[
                    "workload_blueprint_digest"
                ],
            }
            for item in audit["replications"]
        ],
    }

    blueprint_payload["bundle_digest"] = (
        _sha256_payload(blueprint_payload)
    )

    blueprint_path.write_text(
        json.dumps(
            blueprint_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit an SA4 membership-density campaign "
            "and construct deterministic per-seed "
            "workload blueprints."
        )
    )

    parser.add_argument(
        "--campaign-dir",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    arguments = parser.parse_args()

    audit = write_audit_bundle(
        campaign_dir=arguments.campaign_dir,
        output_dir=arguments.output_dir,
    )

    print("[OK] membership-density workload audit passed.")
    print(
        f"[OK] campaign_id={audit['campaign_id']}"
    )
    print(
        f"[OK] replication_count="
        f"{audit['replication_count']}"
    )
    print(
        f"[OK] instance_count="
        f"{audit['instance_count']}"
    )
    print(
        f"[OK] audit_digest="
        f"{audit['audit_digest']}"
    )
    print(
        "[OK] workload_strategy="
        f"{audit['workload_strategy']}"
    )
    print(
        "[OK] execution_partition_required=true"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
