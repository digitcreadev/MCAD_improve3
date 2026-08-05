from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "mcad-sensitivity-e3-workload-v1"

FORBIDDEN_INPUT_FIELDS = {
    "sat",
    "real",
    "real_node_ids",
    "ceval",
    "calculable_constraints",
    "phi",
    "phi_weighted",
    "phi_leq_t",
    "delta_phi_t",
    "phi_weighted_leq_t",
    "delta_phi_weighted_t",
    "covered_constraints",
    "evaluator_latency_ms",
    "status",
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")



CONTROLLED_NOISE_METADATA_FIELD = "mcad_controlled_noise"
CONTROLLED_NOISE_OPERATOR_REGISTRY_VERSION = (
    "mcad-sa5-objective-count-noise-operators-v1"
)
CONTROLLED_NOISE_CLASSES = {
    "wrong_measure",
    "wrong_context",
    "insufficient_grain",
    "invalid_aggregation",
    "invalid_unit",
    "invalid_time_window",
    "missing_cube",
    "redundant_contribution",
}

def fail(message: str) -> None:
    raise AssertionError(message)


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value


def require_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        fail(f"{label} must be an array")
    return value


def require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty string")
    return value


def require_string_list(
    value: Any,
    label: str,
    *,
    non_empty: bool = False,
) -> list[str]:
    items = require_sequence(value, label)

    if non_empty and not items:
        fail(f"{label} must not be empty")

    result: list[str] = []
    for index, item in enumerate(items):
        result.append(
            require_non_empty_string(item, f"{label}[{index}]")
        )
    return result


def reject_forbidden_fields(
    value: Mapping[str, Any],
    label: str,
) -> None:
    forbidden = sorted(FORBIDDEN_INPUT_FIELDS & set(value))
    if forbidden:
        fail(f"{label} contains evaluator output fields: {forbidden}")


def controlled_noise_class(
    query_spec: Mapping[str, Any],
    label: str,
) -> str | None:
    raw = query_spec.get(CONTROLLED_NOISE_METADATA_FIELD)
    if raw is None:
        return None

    metadata = require_mapping(
        raw,
        f"{label}.{CONTROLLED_NOISE_METADATA_FIELD}",
    )
    noise_class = require_non_empty_string(
        metadata.get("noise_class"),
        f"{label}.{CONTROLLED_NOISE_METADATA_FIELD}.noise_class",
    )
    if noise_class not in CONTROLLED_NOISE_CLASSES:
        fail(
            f"{label}.{CONTROLLED_NOISE_METADATA_FIELD}.noise_class "
            f"is unsupported: {noise_class!r}"
        )
    registry_version = require_non_empty_string(
        metadata.get("operator_registry_version"),
        (
            f"{label}.{CONTROLLED_NOISE_METADATA_FIELD}."
            "operator_registry_version"
        ),
    )
    if registry_version != CONTROLLED_NOISE_OPERATOR_REGISTRY_VERSION:
        fail(
            f"{label}.{CONTROLLED_NOISE_METADATA_FIELD}."
            "operator_registry_version: expected "
            f"{CONTROLLED_NOISE_OPERATOR_REGISTRY_VERSION!r}, "
            f"got {registry_version!r}"
        )
    return noise_class


def validate_query_spec(
    query_spec: Mapping[str, Any],
    *,
    step_index: int,
) -> None:
    label = f"steps[{step_index}].query_spec"

    reject_forbidden_fields(query_spec, label)
    noise_class = controlled_noise_class(query_spec, label)

    cube = query_spec.get("cube")
    if noise_class == "missing_cube":
        if cube != "":
            fail(
                f"{label}.cube must be empty for controlled "
                "missing_cube noise"
            )
    else:
        require_non_empty_string(
            cube,
            f"{label}.cube",
        )
    require_string_list(
        query_spec.get("measures"),
        f"{label}.measures",
        non_empty=True,
    )

    for field in (
        "group_by",
        "aggregators",
        "units",
        "time_members",
    ):
        if field in query_spec:
            require_string_list(
                query_spec[field],
                f"{label}.{field}",
            )

    if "slicers" in query_spec:
        slicers = require_mapping(
            query_spec["slicers"],
            f"{label}.slicers",
        )
        for dimension, member in slicers.items():
            require_non_empty_string(
                dimension,
                f"{label}.slicers dimension",
            )
            require_non_empty_string(
                member,
                f"{label}.slicers[{dimension!r}]",
            )

    for field in ("window_start", "window_end"):
        if field in query_spec:
            value = require_non_empty_string(
                query_spec[field],
                f"{label}.{field}",
            )
            if not DATE_PATTERN.fullmatch(value):
                fail(
                    f"{label}.{field} must use YYYY-MM-DD format"
                )

    has_reversed_window = (
        "window_start" in query_spec
        and "window_end" in query_spec
        and query_spec["window_start"] > query_spec["window_end"]
    )

    if noise_class == "invalid_time_window":
        if not has_reversed_window:
            fail(
                f"{label} must contain a reversed window for "
                "controlled invalid_time_window noise"
            )
    elif has_reversed_window:
        fail(
            f"{label}.window_start must not be after window_end"
        )


def validate_workload_spec(
    workload: Mapping[str, Any],
) -> None:
    reject_forbidden_fields(workload, "workload")

    if workload.get("contract_version") != SCHEMA_VERSION:
        fail(
            "contract_version: expected "
            f"{SCHEMA_VERSION!r}, "
            f"got {workload.get('contract_version')!r}"
        )

    require_non_empty_string(
        workload.get("workload_id"),
        "workload_id",
    )
    require_non_empty_string(
        workload.get("objective_id"),
        "objective_id",
    )
    require_non_empty_string(
        workload.get("session_id"),
        "session_id",
    )

    steps = require_sequence(workload.get("steps"), "steps")
    if not steps:
        fail("steps must not be empty")

    seen_step_ids: set[str] = set()
    seen_step_indices: set[int] = set()
    previous_step_index: int | None = None

    for position, raw_step in enumerate(steps):
        step = require_mapping(
            raw_step,
            f"steps[{position}]",
        )

        reject_forbidden_fields(
            step,
            f"steps[{position}]",
        )

        step_index = step.get("step_index")
        if (
            not isinstance(step_index, int)
            or isinstance(step_index, bool)
            or step_index < 1
        ):
            fail(
                f"steps[{position}].step_index "
                "must be an integer greater than or equal to 1"
            )

        if step_index in seen_step_indices:
            fail(f"duplicate step_index: {step_index}")

        if (
            previous_step_index is not None
            and step_index <= previous_step_index
        ):
            fail(
                "step_index values must be strictly increasing"
            )

        step_id = require_non_empty_string(
            step.get("step_id"),
            f"steps[{position}].step_id",
        )
        if step_id in seen_step_ids:
            fail(f"duplicate step_id: {step_id!r}")

        query_spec = require_mapping(
            step.get("query_spec"),
            f"steps[{position}].query_spec",
        )
        validate_query_spec(
            query_spec,
            step_index=position,
        )

        seen_step_indices.add(step_index)
        seen_step_ids.add(step_id)
        previous_step_index = step_index


def load_workload_spec(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"workload file does not exist: {path}")
    except json.JSONDecodeError as exc:
        fail(
            f"invalid JSON in {path}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )

    return require_mapping(raw, "workload")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an MCAD E3 workload specification."
    )
    parser.add_argument(
        "workload_path",
        type=Path,
        help="Path to workload_spec.json",
    )
    args = parser.parse_args()

    try:
        workload = load_workload_spec(args.workload_path)
        validate_workload_spec(workload)
    except AssertionError as exc:
        print(f"[ERROR] Invalid E3 workload: {exc}")
        return 1

    print("[OK] E3 workload is valid.")
    print(f"[OK] workload_id={workload['workload_id']}")
    print(f"[OK] objective_id={workload['objective_id']}")
    print(f"[OK] session_id={workload['session_id']}")
    print(f"[OK] step_count={len(workload['steps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
