from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ORACLE_VERSION = (
    "mcad-sensitivity-sa4-membership-density-oracle-v1"
)


class DensityOracleError(RuntimeError):
    """Raised when membership-density evidence is invalid."""


@dataclass(frozen=True)
class DensityObservation:
    objective_id: str
    constraint_count: int
    virtual_node_count: int
    requirement_set_count: int
    membership_count: int
    maximum_membership_count: int
    membership_density: float
    membership_count_by_constraint: tuple[int, ...]
    virtual_node_count_by_constraint: tuple[int, ...]
    requirement_set_count_by_constraint: tuple[int, ...]
    unknown_references: tuple[str, ...]
    duplicate_memberships: tuple[str, ...]
    empty_requirement_sets: tuple[str, ...]
    duplicate_declared_virtual_nodes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def load_objectives_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DensityOracleError(
            f"Missing objectives document: {path}"
        )

    value = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(value, dict):
        raise DensityOracleError(
            f"Invalid objectives document root: {path}"
        )

    return value


def select_objective(
    document: Mapping[str, Any],
    objective_id: str | None = None,
) -> dict[str, Any]:
    objectives = document.get("objectives")

    if not isinstance(objectives, list):
        raise DensityOracleError(
            "Objectives document lacks an objectives list."
        )

    candidates = [
        objective
        for objective in objectives
        if isinstance(objective, dict)
    ]

    if objective_id is None:
        if len(candidates) != 1:
            raise DensityOracleError(
                "An explicit objective ID is required when "
                "the document does not contain exactly one "
                "objective."
            )

        return candidates[0]

    for objective in candidates:
        if objective.get("id") == objective_id:
            return objective

    raise DensityOracleError(
        f"Objective not found: {objective_id}"
    )


def virtual_node_id(value: Any) -> str:
    if isinstance(value, dict):
        identifier = value.get("id")
    else:
        identifier = value

    if not isinstance(identifier, str) or not identifier:
        raise DensityOracleError(
            f"Invalid virtual-node declaration: {value!r}"
        )

    return identifier


def analyze_objectives_document(
    document: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> DensityObservation:
    objective = select_objective(
        document,
        objective_id,
    )

    selected_objective_id = objective.get("id")

    if not isinstance(selected_objective_id, str):
        raise DensityOracleError(
            "Selected objective lacks a valid ID."
        )

    constraints = objective.get("constraints")

    if not isinstance(constraints, list):
        raise DensityOracleError(
            "Objective lacks a constraints list."
        )

    virtual_node_count = 0
    requirement_set_count = 0
    membership_count = 0
    maximum_membership_count = 0

    memberships_by_constraint: list[int] = []
    virtual_nodes_by_constraint: list[int] = []
    requirement_sets_by_constraint: list[int] = []

    unknown_references: list[str] = []
    duplicate_memberships: list[str] = []
    empty_requirement_sets: list[str] = []
    duplicate_declared_virtual_nodes: list[str] = []

    globally_declared: set[str] = set()

    for constraint_index, constraint in enumerate(
        constraints
    ):
        if not isinstance(constraint, dict):
            raise DensityOracleError(
                "Invalid constraint declaration at "
                f"index {constraint_index}."
            )

        constraint_id = str(
            constraint.get(
                "id",
                f"constraint-{constraint_index}",
            )
        )

        raw_virtual_nodes = (
            constraint.get("virtual_nodes") or []
        )

        if not isinstance(raw_virtual_nodes, list):
            raise DensityOracleError(
                f"Invalid virtual_nodes for {constraint_id}."
            )

        declared_ids = [
            virtual_node_id(value)
            for value in raw_virtual_nodes
        ]

        local_duplicates = sorted(
            {
                identifier
                for identifier in declared_ids
                if declared_ids.count(identifier) > 1
            }
        )

        for identifier in local_duplicates:
            duplicate_declared_virtual_nodes.append(
                f"{constraint_id}:{identifier}"
            )

        for identifier in declared_ids:
            if identifier in globally_declared:
                duplicate_declared_virtual_nodes.append(
                    f"global:{identifier}"
                )

            globally_declared.add(identifier)

        declared_set = set(declared_ids)

        raw_requirement_sets = (
            constraint.get("requirement_sets") or []
        )

        if not isinstance(raw_requirement_sets, list):
            raise DensityOracleError(
                f"Invalid requirement_sets for {constraint_id}."
            )

        local_membership_count = 0

        for requirement_set_index, requirement_set in enumerate(
            raw_requirement_sets
        ):
            if not isinstance(requirement_set, list):
                raise DensityOracleError(
                    "Requirement set must be a list: "
                    f"{constraint_id}[{requirement_set_index}]"
                )

            members = [
                str(member)
                for member in requirement_set
            ]

            if not members:
                empty_requirement_sets.append(
                    f"{constraint_id}[{requirement_set_index}]"
                )

            repeated = sorted(
                {
                    member
                    for member in members
                    if members.count(member) > 1
                }
            )

            for member in repeated:
                duplicate_memberships.append(
                    f"{constraint_id}"
                    f"[{requirement_set_index}]:{member}"
                )

            missing = sorted(
                set(members) - declared_set
            )

            for member in missing:
                unknown_references.append(
                    f"{constraint_id}"
                    f"[{requirement_set_index}]:{member}"
                )

            local_membership_count += len(members)

        local_virtual_node_count = len(
            declared_ids
        )

        local_requirement_set_count = len(
            raw_requirement_sets
        )

        virtual_node_count += (
            local_virtual_node_count
        )

        requirement_set_count += (
            local_requirement_set_count
        )

        membership_count += (
            local_membership_count
        )

        maximum_membership_count += (
            local_requirement_set_count
            * local_virtual_node_count
        )

        memberships_by_constraint.append(
            local_membership_count
        )

        virtual_nodes_by_constraint.append(
            local_virtual_node_count
        )

        requirement_sets_by_constraint.append(
            local_requirement_set_count
        )

    density = (
        Fraction(
            membership_count,
            maximum_membership_count,
        )
        if maximum_membership_count
        else Fraction(0, 1)
    )

    return DensityObservation(
        objective_id=selected_objective_id,
        constraint_count=len(constraints),
        virtual_node_count=virtual_node_count,
        requirement_set_count=requirement_set_count,
        membership_count=membership_count,
        maximum_membership_count=(
            maximum_membership_count
        ),
        membership_density=float(density),
        membership_count_by_constraint=tuple(
            memberships_by_constraint
        ),
        virtual_node_count_by_constraint=tuple(
            virtual_nodes_by_constraint
        ),
        requirement_set_count_by_constraint=tuple(
            requirement_sets_by_constraint
        ),
        unknown_references=tuple(
            sorted(unknown_references)
        ),
        duplicate_memberships=tuple(
            sorted(duplicate_memberships)
        ),
        empty_requirement_sets=tuple(
            sorted(empty_requirement_sets)
        ),
        duplicate_declared_virtual_nodes=tuple(
            sorted(
                duplicate_declared_virtual_nodes
            )
        ),
    )


def expected_membership_count(
    maximum_membership_count: int,
    density_percent: int,
) -> int:
    if maximum_membership_count <= 0:
        raise DensityOracleError(
            "Maximum membership count must be positive."
        )

    if not 1 <= density_percent <= 100:
        raise DensityOracleError(
            "Density percentage must lie between "
            "1 and 100."
        )

    numerator = (
        maximum_membership_count
        * density_percent
    )

    if numerator % 100 != 0:
        raise DensityOracleError(
            "Density level does not produce an exact "
            "integer membership count: "
            f"maximum={maximum_membership_count}, "
            f"percentage={density_percent}."
        )

    return numerator // 100


def assert_valid_density(
    document: Mapping[str, Any],
    *,
    density_percent: int,
    objective_id: str | None = None,
    require_nonempty_sets: bool = True,
) -> DensityObservation:
    observation = analyze_objectives_document(
        document,
        objective_id=objective_id,
    )

    integrity_failures = {
        "unknown_references": (
            observation.unknown_references
        ),
        "duplicate_memberships": (
            observation.duplicate_memberships
        ),
        "duplicate_declared_virtual_nodes": (
            observation.duplicate_declared_virtual_nodes
        ),
    }

    if require_nonempty_sets:
        integrity_failures[
            "empty_requirement_sets"
        ] = observation.empty_requirement_sets

    active_failures = {
        key: value
        for key, value in integrity_failures.items()
        if value
    }

    if active_failures:
        raise DensityOracleError(
            "Reference-integrity failure: "
            f"{active_failures}"
        )

    expected_count = expected_membership_count(
        observation.maximum_membership_count,
        density_percent,
    )

    if observation.membership_count != expected_count:
        raise DensityOracleError(
            "Realised membership count differs from "
            "the density contract: "
            f"expected={expected_count}, "
            f"actual={observation.membership_count}."
        )

    expected_density = Fraction(
        density_percent,
        100,
    )

    realised_density = Fraction(
        observation.membership_count,
        observation.maximum_membership_count,
    )

    if realised_density != expected_density:
        raise DensityOracleError(
            "Realised density differs from the exact "
            "rational target."
        )

    if (
        require_nonempty_sets
        and any(
            count <= 0
            for count
            in observation.membership_count_by_constraint
        )
    ):
        raise DensityOracleError(
            "Every constraint must retain at least one "
            "membership link."
        )

    return observation


def normalized_non_membership_payload(
    document: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> dict[str, Any]:
    objective = copy.deepcopy(
        select_objective(
            document,
            objective_id,
        )
    )

    constraints = objective.get("constraints")

    if not isinstance(constraints, list):
        raise DensityOracleError(
            "Objective lacks a constraints list."
        )

    normalized_constraints = []

    for constraint_index, constraint in enumerate(
        constraints
    ):
        if not isinstance(constraint, dict):
            raise DensityOracleError(
                f"Invalid constraint {constraint_index}."
            )

        virtual_nodes = (
            constraint.get("virtual_nodes") or []
        )

        normalized_virtual_nodes = []

        for value in virtual_nodes:
            if isinstance(value, dict):
                normalized_virtual_nodes.append(
                    {
                        key: child
                        for key, child in value.items()
                        if key != "id"
                    }
                )
            else:
                normalized_virtual_nodes.append(
                    {"declaration_type": "identifier"}
                )

        excluded = {
            "id",
            "kpi_id",
            "description",
            "virtual_nodes",
            "requirement_sets",
        }

        normalized_constraints.append(
            {
                "constraint_index": (
                    constraint_index
                ),
                "payload": {
                    key: value
                    for key, value
                    in constraint.items()
                    if key not in excluded
                },
                "virtual_nodes": (
                    normalized_virtual_nodes
                ),
                "requirement_set_count": len(
                    constraint.get(
                        "requirement_sets"
                    )
                    or []
                ),
            }
        )

    objective_excluded = {
        "id",
        "name",
        "description",
        "constraints",
    }

    return {
        "objective_payload": {
            key: value
            for key, value in objective.items()
            if key not in objective_excluded
        },
        "constraints": normalized_constraints,
    }


def non_membership_semantic_digest(
    document: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> str:
    return sha256_json(
        normalized_non_membership_payload(
            document,
            objective_id=objective_id,
        )
    )


def normalized_membership_edges(
    document: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> frozenset[tuple[int, int, int]]:
    objective = select_objective(
        document,
        objective_id,
    )

    constraints = objective.get("constraints")

    if not isinstance(constraints, list):
        raise DensityOracleError(
            "Objective lacks a constraints list."
        )

    edges: set[tuple[int, int, int]] = set()

    for constraint_index, constraint in enumerate(
        constraints
    ):
        virtual_nodes = (
            constraint.get("virtual_nodes") or []
        )

        declared_ids = [
            virtual_node_id(value)
            for value in virtual_nodes
        ]

        local_index = {
            identifier: index
            for index, identifier
            in enumerate(declared_ids)
        }

        requirement_sets = (
            constraint.get("requirement_sets") or []
        )

        for requirement_set_index, requirement_set in enumerate(
            requirement_sets
        ):
            for member in requirement_set:
                member_id = str(member)

                if member_id not in local_index:
                    raise DensityOracleError(
                        "Cannot normalize an unknown "
                        f"membership reference: {member_id}"
                    )

                edges.add(
                    (
                        constraint_index,
                        requirement_set_index,
                        local_index[member_id],
                    )
                )

    return frozenset(edges)


def validate_density_family(
    documents_by_level: Mapping[
        int,
        Mapping[str, Any],
    ],
    *,
    required_levels: Sequence[int],
) -> dict[str, Any]:
    observed_levels = sorted(
        documents_by_level
    )

    if observed_levels != sorted(required_levels):
        raise DensityOracleError(
            "Unexpected density-level set: "
            f"expected={sorted(required_levels)}, "
            f"actual={observed_levels}."
        )

    observations: dict[
        int,
        DensityObservation,
    ] = {}

    digests: dict[int, str] = {}
    edges: dict[
        int,
        frozenset[tuple[int, int, int]],
    ] = {}

    for level in observed_levels:
        document = documents_by_level[level]

        observations[level] = assert_valid_density(
            document,
            density_percent=level,
        )

        digests[level] = (
            non_membership_semantic_digest(
                document
            )
        )

        edges[level] = normalized_membership_edges(
            document
        )

    if len(set(digests.values())) != 1:
        raise DensityOracleError(
            "Non-membership semantics vary across "
            "density levels."
        )

    baseline = observations[
        observed_levels[0]
    ]

    for level in observed_levels[1:]:
        observation = observations[level]

        structural_signature = (
            observation.constraint_count,
            observation.virtual_node_count,
            observation.requirement_set_count,
            observation.maximum_membership_count,
            observation.virtual_node_count_by_constraint,
            observation.requirement_set_count_by_constraint,
        )

        baseline_signature = (
            baseline.constraint_count,
            baseline.virtual_node_count,
            baseline.requirement_set_count,
            baseline.maximum_membership_count,
            baseline.virtual_node_count_by_constraint,
            baseline.requirement_set_count_by_constraint,
        )

        if structural_signature != baseline_signature:
            raise DensityOracleError(
                "A non-density structural dimension "
                f"changed at level {level}."
            )

    previous_edges: frozenset[
        tuple[int, int, int]
    ] | None = None

    for level in observed_levels:
        current_edges = edges[level]

        if (
            previous_edges is not None
            and not previous_edges.issubset(
                current_edges
            )
        ):
            raise DensityOracleError(
                "Membership sets are not nested across "
                f"density levels at level {level}."
            )

        previous_edges = current_edges

        counts = (
            observations[level]
            .membership_count_by_constraint
        )

        if max(counts) - min(counts) > 1:
            raise DensityOracleError(
                "Membership allocation is not balanced "
                f"at level {level}: {counts}."
            )

    return {
        "oracle_version": ORACLE_VERSION,
        "levels": observed_levels,
        "non_membership_semantic_digest": next(
            iter(digests.values())
        ),
        "observations": {
            str(level): (
                observations[level].to_dict()
            )
            for level in observed_levels
        },
        "nested_membership_sets": True,
        "balanced_allocation": True,
        "one_factor_at_a_time": True,
    }
