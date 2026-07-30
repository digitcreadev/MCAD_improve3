from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "mcad-sensitivity-e3-execution-v1"

FORBIDDEN_FIELDS = {
    "sat",
    "real",
    "real_node_ids",
    "ceval",
    "calculable_constraints",
    "phi",
    "phi_weighted",
    "phi_leq_t",
    "delta_phi_t",
    "metrics",
    "timeline",
    "audit",
    "status",
    "evaluator_latency_ms",
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


def reject_forbidden_fields(
    value: Mapping[str, Any],
    label: str,
) -> None:
    forbidden = sorted(FORBIDDEN_FIELDS & set(value))
    if forbidden:
        fail(f"{label} contains execution output fields: {forbidden}")


def validate_instance_selection(value: Any) -> None:
    selection = require_mapping(value, "instance_selection")
    reject_forbidden_fields(selection, "instance_selection")

    unknown = sorted(set(selection) - {"instance_ids"})
    if unknown:
        fail(
            "instance_selection contains unsupported fields: "
            f"{unknown}"
        )

    if "instance_ids" not in selection:
        fail("instance_selection.instance_ids is required")

    instance_ids = require_sequence(
        selection["instance_ids"],
        "instance_selection.instance_ids",
    )
    if not instance_ids:
        fail("instance_selection.instance_ids must not be empty")

    normalized: list[str] = []
    for index, instance_id in enumerate(instance_ids):
        normalized.append(
            require_non_empty_string(
                instance_id,
                f"instance_selection.instance_ids[{index}]",
            )
        )

    if len(normalized) != len(set(normalized)):
        fail("instance_selection.instance_ids must be unique")


def validate_execution_spec(
    execution_spec: Mapping[str, Any],
) -> None:
    reject_forbidden_fields(execution_spec, "execution_spec")

    allowed_fields = {
        "contract_version",
        "execution_id",
        "campaign_dir",
        "workload_path",
        "output_dir",
        "instance_selection",
        "overwrite",
        "continue_on_instance_failure",
    }
    unknown = sorted(set(execution_spec) - allowed_fields)
    if unknown:
        fail(f"execution_spec contains unsupported fields: {unknown}")

    if execution_spec.get("contract_version") != SCHEMA_VERSION:
        fail(
            "contract_version: expected "
            f"{SCHEMA_VERSION!r}, "
            f"got {execution_spec.get('contract_version')!r}"
        )

    require_non_empty_string(
        execution_spec.get("execution_id"),
        "execution_id",
    )
    require_non_empty_string(
        execution_spec.get("campaign_dir"),
        "campaign_dir",
    )
    require_non_empty_string(
        execution_spec.get("workload_path"),
        "workload_path",
    )
    require_non_empty_string(
        execution_spec.get("output_dir"),
        "output_dir",
    )

    overwrite = execution_spec.get("overwrite", False)
    if not isinstance(overwrite, bool):
        fail("overwrite must be a boolean")

    continue_on_failure = execution_spec.get(
        "continue_on_instance_failure",
        False,
    )
    if continue_on_failure is not False:
        fail("continue_on_instance_failure must be false")

    if "instance_selection" in execution_spec:
        validate_instance_selection(
            execution_spec["instance_selection"]
        )

    campaign_dir = Path(execution_spec["campaign_dir"])
    workload_path = Path(execution_spec["workload_path"])
    output_dir = Path(execution_spec["output_dir"])

    if output_dir == campaign_dir:
        fail("output_dir must be outside campaign_dir")

    try:
        output_dir.relative_to(campaign_dir)
    except ValueError:
        pass
    else:
        fail("output_dir must be outside campaign_dir")

    if workload_path == campaign_dir:
        fail("workload_path must identify a JSON file")


def load_execution_spec(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"execution spec does not exist: {path}")
    except json.JSONDecodeError as exc:
        fail(
            f"invalid JSON in {path}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )

    return require_mapping(raw, "execution_spec")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an MCAD E3 execution specification."
    )
    parser.add_argument(
        "execution_spec_path",
        type=Path,
        help="Path to execution_spec.json",
    )
    args = parser.parse_args()

    try:
        execution_spec = load_execution_spec(
            args.execution_spec_path
        )
        validate_execution_spec(execution_spec)
    except AssertionError as exc:
        print(f"[ERROR] Invalid E3 execution spec: {exc}")
        return 1

    selection = execution_spec.get("instance_selection")
    selected_count = (
        len(selection["instance_ids"])
        if isinstance(selection, dict)
        else "all"
    )

    print("[OK] E3 execution spec is valid.")
    print(f"[OK] execution_id={execution_spec['execution_id']}")
    print(f"[OK] campaign_dir={execution_spec['campaign_dir']}")
    print(f"[OK] workload_path={execution_spec['workload_path']}")
    print(f"[OK] output_dir={execution_spec['output_dir']}")
    print(f"[OK] selected_instances={selected_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
