from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

OPERATOR_REGISTRY_VERSION = "mcad-sa5-objective-count-noise-operators-v1"

NOISE_CLASS_ORDER = (
    "wrong_measure",
    "wrong_context",
    "insufficient_grain",
    "invalid_aggregation",
    "invalid_unit",
    "invalid_time_window",
    "missing_cube",
    "redundant_contribution",
)

NON_REDUNDANT_NOISE_CLASSES = tuple(
    item for item in NOISE_CLASS_ORDER if item != "redundant_contribution"
)

SEMANTIC_PROJECTION_FIELDS = (
    "cube",
    "measures",
    "group_by",
    "slicers",
    "aggregators",
    "units",
    "window_start",
    "window_end",
    "time_members",
)

WORKLOAD_LENGTH = 32
NOISE_STEP_COUNT = 8
CONTRIBUTIVE_STEP_COUNT = 24
SUPPORT_ORDINAL_COUNT = 24


@dataclass(frozen=True)
class NoiseSchedule:
    seed: int
    noise_positions: tuple[int, ...]
    contributive_positions: tuple[int, ...]
    redundant_contribution_position: int
    redundant_source_step_index: int
    redundant_source_support_ordinal: int
    class_by_position: dict[int, str]
    target_support_ordinal_by_class: dict[str, int]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def semantic_projection(query_spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: copy.deepcopy(query_spec.get(field))
        for field in SEMANTIC_PROJECTION_FIELDS
    }


def support_query_from_virtual_node(
    virtual_node: Mapping[str, Any],
    *,
    support_ordinal: int,
    constraint_index: int,
    local_virtual_node_index: int,
) -> dict[str, Any]:
    query = {
        "cube": str(virtual_node.get("fact") or ""),
        "measures": [str(virtual_node.get("measure") or "")],
        "group_by": list(virtual_node.get("grain") or []),
        "slicers": dict(virtual_node.get("slicers") or {}),
        "aggregators": [str(virtual_node.get("aggregator") or "")],
        "units": [str(virtual_node.get("unit") or "")],
        "window_start": str(virtual_node.get("window_start") or ""),
        "window_end": str(virtual_node.get("window_end") or ""),
        "time_members": [],
        "mcad_support_coordinate": {
            "support_ordinal": support_ordinal,
            "constraint_index": constraint_index,
            "local_virtual_node_index": local_virtual_node_index,
            "virtual_node_id": str(virtual_node.get("id") or ""),
        },
    }
    if not query["cube"] or not query["measures"][0]:
        raise ValueError("Virtual node cannot produce a canonical support query.")
    return query


def selected_noise_positions(seed: int) -> tuple[int, ...]:
    ranked = sorted(
        range(1, WORKLOAD_LENGTH + 1),
        key=lambda position: (
            hashlib.sha256(
                (
                    "mcad-sa5-noise-position-v2"
                    f"|{seed}|{position}"
                ).encode("utf-8")
            ).hexdigest(),
            position,
        ),
    )
    return tuple(sorted(ranked[:NOISE_STEP_COUNT]))


def ranked_non_redundant_classes(seed: int) -> tuple[str, ...]:
    return tuple(
        sorted(
            NON_REDUNDANT_NOISE_CLASSES,
            key=lambda noise_class: (
                hashlib.sha256(
                    (
                        "mcad-sa5-noise-class-v3"
                        f"|{seed}|{noise_class}"
                    ).encode("utf-8")
                ).hexdigest(),
                noise_class,
            ),
        )
    )


def target_support_ordinals(seed: int) -> dict[str, int]:
    unused = set(range(SUPPORT_ORDINAL_COUNT))
    result: dict[str, int] = {}
    for noise_class in NON_REDUNDANT_NOISE_CLASSES:
        selected = min(
            unused,
            key=lambda support_ordinal: (
                hashlib.sha256(
                    (
                        "mcad-sa5-noise-target-v3"
                        f"|{seed}|{noise_class}|{support_ordinal}"
                    ).encode("utf-8")
                ).hexdigest(),
                support_ordinal,
            ),
        )
        result[noise_class] = selected
        unused.remove(selected)
    return result


def build_noise_schedule(seed: int) -> NoiseSchedule:
    noise_positions = selected_noise_positions(seed)
    contributive_positions = tuple(
        position
        for position in range(1, WORKLOAD_LENGTH + 1)
        if position not in set(noise_positions)
    )
    if len(contributive_positions) != CONTRIBUTIVE_STEP_COUNT:
        raise ValueError("Invalid contributive position count.")

    first_contributive_position = contributive_positions[0]
    eligible_redundant_positions = tuple(
        position
        for position in noise_positions
        if position > first_contributive_position
    )
    if not eligible_redundant_positions:
        raise ValueError("No valid redundant-contribution position.")

    redundant_position = min(eligible_redundant_positions)
    redundant_source_step_index = max(
        position
        for position in contributive_positions
        if position < redundant_position
    )
    redundant_source_support_ordinal = contributive_positions.index(
        redundant_source_step_index
    )

    class_by_position: dict[int, str] = {
        redundant_position: "redundant_contribution"
    }
    remaining_positions = tuple(
        position for position in noise_positions if position != redundant_position
    )
    for position, noise_class in zip(
        remaining_positions,
        ranked_non_redundant_classes(seed),
        strict=True,
    ):
        class_by_position[position] = noise_class

    if set(class_by_position.values()) != set(NOISE_CLASS_ORDER):
        raise ValueError("Noise schedule does not assign all classes exactly once.")

    return NoiseSchedule(
        seed=seed,
        noise_positions=noise_positions,
        contributive_positions=contributive_positions,
        redundant_contribution_position=redundant_position,
        redundant_source_step_index=redundant_source_step_index,
        redundant_source_support_ordinal=redundant_source_support_ordinal,
        class_by_position=dict(sorted(class_by_position.items())),
        target_support_ordinal_by_class=target_support_ordinals(seed),
    )


def _metadata(
    *,
    noise_class: str,
    source_projection: Mapping[str, Any],
    mutated_projection: Mapping[str, Any],
    target_support_ordinal: int | None,
    source_step_index: int | None,
    changed_fields: Sequence[str],
) -> dict[str, Any]:
    return {
        "noise_class": noise_class,
        "operator_registry_version": OPERATOR_REGISTRY_VERSION,
        "target_support_ordinal": target_support_ordinal,
        "source_step_index": source_step_index,
        "changed_fields": list(changed_fields),
        "source_semantic_digest": sha256_payload(source_projection),
        "mutated_semantic_digest": sha256_payload(mutated_projection),
    }


def apply_noise_operator(
    noise_class: str,
    source_query: Mapping[str, Any],
    *,
    target_support_ordinal: int | None = None,
    source_step_index: int | None = None,
) -> dict[str, Any]:
    if noise_class not in NOISE_CLASS_ORDER:
        raise ValueError(f"Unknown SA5 noise class: {noise_class!r}")

    source_projection = semantic_projection(source_query)
    query = copy.deepcopy(source_projection)
    changed_fields: tuple[str, ...]

    if noise_class == "wrong_measure":
        query["measures"] = ["__MCAD_SA5_WRONG_MEASURE__"]
        changed_fields = ("measures",)
    elif noise_class == "wrong_context":
        slicers = dict(query.get("slicers") or {})
        slicers["Geography.Region"] = "__MCAD_SA5_WRONG_CONTEXT__"
        query["slicers"] = slicers
        changed_fields = ("slicers",)
    elif noise_class == "insufficient_grain":
        query["group_by"] = ["Geography.Region"]
        changed_fields = ("group_by",)
    elif noise_class == "invalid_aggregation":
        query["aggregators"] = ["__MCAD_SA5_INVALID_AGGREGATION__"]
        changed_fields = ("aggregators",)
    elif noise_class == "invalid_unit":
        query["units"] = ["__MCAD_SA5_INVALID_UNIT__"]
        changed_fields = ("units",)
    elif noise_class == "invalid_time_window":
        query["window_start"], query["window_end"] = (
            query.get("window_end"),
            query.get("window_start"),
        )
        changed_fields = ("window_start", "window_end")
    elif noise_class == "missing_cube":
        query["cube"] = ""
        changed_fields = ("cube",)
    else:
        if source_step_index is None:
            raise ValueError(
                "redundant_contribution requires source_step_index provenance."
            )
        changed_fields = ()

    mutated_projection = semantic_projection(query)
    query["mcad_controlled_noise"] = _metadata(
        noise_class=noise_class,
        source_projection=source_projection,
        mutated_projection=mutated_projection,
        target_support_ordinal=target_support_ordinal,
        source_step_index=source_step_index,
        changed_fields=changed_fields,
    )
    return query


def changed_semantic_fields(
    source_query: Mapping[str, Any],
    mutated_query: Mapping[str, Any],
) -> tuple[str, ...]:
    source = semantic_projection(source_query)
    mutated = semantic_projection(mutated_query)
    return tuple(
        field
        for field in SEMANTIC_PROJECTION_FIELDS
        if source.get(field) != mutated.get(field)
    )
