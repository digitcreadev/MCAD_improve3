from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import traceback
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Iterable, Mapping, Sequence

from backend.ckg.ckg_updater import CKGGraph


E3_EXECUTOR_VERSION = "mcad-sensitivity-e3-v2"

LEGACY_E22_VERSION = "mcad-sensitivity-e2.2-v1"
LEGACY_E21_VERSION = "mcad-sensitivity-e2.1-v1"

MEMBERSHIP_DENSITY_E22_VERSION = (
    "mcad-sensitivity-e2.2-membership-density-v1"
)
MEMBERSHIP_DENSITY_E21_VERSION = (
    "mcad-sensitivity-e2.1-membership-density-v1"
)

OBJECTIVE_COUNT_E22_VERSION = (
    "mcad-sensitivity-e2.2-objective-count-v1"
)

OBJECTIVE_COUNT_E21_VERSION = (
    "mcad-sensitivity-e2.1-objective-count-v1"
)

# Backward-compatible aliases retained for callers that
# imported the historical single-version constants.
EXPECTED_E22_VERSION = LEGACY_E22_VERSION
EXPECTED_E21_VERSION = LEGACY_E21_VERSION

SUPPORTED_GENERATOR_VERSION_PAIRS = {
    "constraint_count": (
        LEGACY_E22_VERSION,
        LEGACY_E21_VERSION,
    ),
    "virtual_node_count": (
        LEGACY_E22_VERSION,
        LEGACY_E21_VERSION,
    ),
    "membership_density": (
        MEMBERSHIP_DENSITY_E22_VERSION,
        MEMBERSHIP_DENSITY_E21_VERSION,
    ),
    "objective_count": (
        OBJECTIVE_COUNT_E22_VERSION,
        OBJECTIVE_COUNT_E21_VERSION,
    ),
}


class E3ExecutionError(RuntimeError):
    """Raised when an E3 controlled execution input is invalid."""


def _expected_generator_versions(
    factor: str,
) -> tuple[str, str]:
    try:
        return SUPPORTED_GENERATOR_VERSION_PAIRS[
            factor
        ]
    except KeyError as exc:
        raise E3ExecutionError(
            "Unsupported controlled-experiment factor: "
            f"{factor!r}."
        ) from exc


@dataclass(frozen=True)
class DiscoveredInstance:
    """Validated immutable description of one E2.2 campaign instance."""

    campaign_id: str
    factor: str
    factor_level: int
    replication_index: int
    seed: int
    objective_id: str
    relative_instance_dir: str
    canonical_instance_id: str

    requested_constraint_count: int
    realised_constraint_count: int
    requested_virtual_node_count: int
    realised_virtual_node_count: int

    configuration_digest: str
    instance_digest: str
    generator_version: str

    instance_dir: Path
    manifest_path: Path
    objectives_path: Path


@dataclass(frozen=True)
class ExecutionInputs:
    """Resolved and validated E3 execution inputs."""

    execution_spec_path: Path
    execution_spec: dict[str, Any]

    workload_path: Path
    workload: dict[str, Any]

    campaign_dir: Path
    campaign_manifest: dict[str, Any]

    output_dir: Path
    instances: tuple[DiscoveredInstance, ...]


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise E3ExecutionError(
            f"Missing {label}: {path}"
        )

    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise E3ExecutionError(
            f"Invalid JSON in {label} {path}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise E3ExecutionError(
            f"{label} must contain a JSON object: {path}"
        )

    return value


def _required_non_empty_string(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
) -> str:
    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise E3ExecutionError(
            f"{label}.{key} must be a non-empty string."
        )

    return value.strip()


def _required_integer(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
) -> int:
    value = mapping.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise E3ExecutionError(
            f"{label}.{key} must be an integer."
        )

    return value


def _csv_integer(
    row: Mapping[str, str],
    key: str,
    row_number: int,
) -> int:
    raw = row.get(key)

    if raw is None or not raw.strip():
        raise E3ExecutionError(
            f"instances.csv row {row_number}: "
            f"missing integer field {key!r}."
        )

    try:
        return int(raw)
    except ValueError as exc:
        raise E3ExecutionError(
            f"instances.csv row {row_number}: "
            f"{key!r} is not an integer: {raw!r}."
        ) from exc


def _csv_string(
    row: Mapping[str, str],
    key: str,
    row_number: int,
) -> str:
    raw = row.get(key)

    if raw is None or not raw.strip():
        raise E3ExecutionError(
            f"instances.csv row {row_number}: "
            f"missing string field {key!r}."
        )

    return raw.strip()


def _resolve_path(
    raw_path: str,
    *,
    relative_to: Path,
) -> Path:
    path = Path(raw_path).expanduser()

    if not path.is_absolute():
        path = relative_to / path

    return path.resolve()


def _canonical_instance_id(
    relative_instance_dir: str,
) -> str:
    path = Path(relative_instance_dir)

    parts = path.parts
    if parts and parts[0] == "instances":
        parts = parts[1:]

    if not parts:
        raise E3ExecutionError(
            "relative_instance_dir does not identify "
            f"an instance: {relative_instance_dir!r}"
        )

    return Path(*parts).as_posix()


def _normalise_selected_instances(
    raw_selection: Any,
) -> str | tuple[str, ...]:
    """
    Normalize the selection defined by execution_spec.schema.json.

    Semantics:
      - omitted instance_selection: execute every instance;
      - empty instance_selection object: execute every instance;
      - instance_selection.instance_ids: execute that subset.
    """
    if raw_selection is None or raw_selection == {}:
        return "all"

    if not isinstance(raw_selection, dict):
        raise E3ExecutionError(
            "execution_spec.instance_selection must be "
            "an object when provided."
        )

    values = raw_selection.get("instance_ids")

    if not isinstance(values, list) or not values:
        raise E3ExecutionError(
            "execution_spec.instance_selection.instance_ids "
            "must be a non-empty list."
        )

    selected: list[str] = []

    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise E3ExecutionError(
                "execution_spec.instance_selection."
                f"instance_ids[{index}] must be a "
                "non-empty string."
            )

        canonical = _canonical_instance_id(
            value.strip()
        )

        if canonical in selected:
            raise E3ExecutionError(
                "Duplicate selected instance: "
                f"{canonical}"
            )

        selected.append(canonical)

    return tuple(selected)


def _validate_workload_shape(
    workload: Mapping[str, Any],
) -> None:
    _required_non_empty_string(
        workload,
        "workload_id",
        "workload_spec",
    )
    _required_non_empty_string(
        workload,
        "objective_id",
        "workload_spec",
    )
    _required_non_empty_string(
        workload,
        "session_id",
        "workload_spec",
    )

    steps = workload.get("steps")

    if not isinstance(steps, list) or not steps:
        raise E3ExecutionError(
            "workload_spec.steps must be a non-empty list."
        )

    seen_step_ids: set[str] = set()
    previous_index = 0

    for position, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise E3ExecutionError(
                f"workload_spec.steps[{position - 1}] "
                "must be an object."
            )

        step_id = _required_non_empty_string(
            step,
            "step_id",
            f"workload_spec.steps[{position - 1}]",
        )

        step_index = _required_integer(
            step,
            "step_index",
            f"workload_spec.steps[{position - 1}]",
        )

        if step_id in seen_step_ids:
            raise E3ExecutionError(
                f"Duplicate workload step_id: {step_id}"
            )

        if step_index <= previous_index:
            raise E3ExecutionError(
                "workload step_index values must be "
                "strictly increasing."
            )

        query_spec = step.get("query_spec")
        if not isinstance(query_spec, dict) or not query_spec:
            raise E3ExecutionError(
                f"Workload step {step_id!r} must contain "
                "a non-empty query_spec object."
            )

        seen_step_ids.add(step_id)
        previous_index = step_index


def _load_instance_rows(
    instances_csv_path: Path,
) -> list[dict[str, str]]:
    if not instances_csv_path.is_file():
        raise E3ExecutionError(
            f"Missing E2.2 instance index: "
            f"{instances_csv_path}"
        )

    with instances_csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise E3ExecutionError(
                f"Empty CSV header: {instances_csv_path}"
            )

        required_columns = {
            "campaign_id",
            "factor",
            "factor_level",
            "replication_index",
            "seed",
            "objective_id",
            "relative_instance_dir",
            "requested_constraint_count",
            "realised_constraint_count",
            "requested_virtual_node_count",
            "realised_virtual_node_count",
            "configuration_digest",
            "instance_digest",
            "generator_version",
        }

        missing = required_columns - set(
            reader.fieldnames
        )

        if missing:
            raise E3ExecutionError(
                "instances.csv is missing required columns: "
                f"{sorted(missing)}"
            )

        rows = [dict(row) for row in reader]

    if not rows:
        raise E3ExecutionError(
            f"instances.csv contains no instances: "
            f"{instances_csv_path}"
        )

    return rows


def _validate_instance_manifest(
    *,
    manifest: Mapping[str, Any],
    row: Mapping[str, str],
    row_number: int,
) -> None:
    exact_string_fields = (
        "objective_id",
        "configuration_digest",
        "instance_digest",
        "generator_version",
    )

    exact_integer_fields = (
        "seed",
        "requested_constraint_count",
        "realised_constraint_count",
        "requested_virtual_node_count",
        "realised_virtual_node_count",
    )

    for field in exact_string_fields:
        csv_value = _csv_string(
            row,
            field,
            row_number,
        )
        manifest_value = _required_non_empty_string(
            manifest,
            field,
            "instance manifest",
        )

        if csv_value != manifest_value:
            raise E3ExecutionError(
                f"Instance row {row_number}: {field} "
                "differs between instances.csv and "
                "manifest.json."
            )

    for field in exact_integer_fields:
        csv_value = _csv_integer(
            row,
            field,
            row_number,
        )
        manifest_value = _required_integer(
            manifest,
            field,
            "instance manifest",
        )

        if csv_value != manifest_value:
            raise E3ExecutionError(
                f"Instance row {row_number}: {field} "
                "differs between instances.csv and "
                "manifest.json."
            )


def _discover_all_instances(
    *,
    campaign_dir: Path,
    campaign_manifest: Mapping[str, Any],
) -> tuple[DiscoveredInstance, ...]:
    rows = _load_instance_rows(
        campaign_dir / "instances.csv"
    )

    campaign_id = _required_non_empty_string(
        campaign_manifest,
        "campaign_id",
        "campaign_manifest",
    )
    factor = _required_non_empty_string(
        campaign_manifest,
        "factor",
        "campaign_manifest",
    )

    campaign_generator_version = (
        _required_non_empty_string(
            campaign_manifest,
            "campaign_generator_version",
            "campaign_manifest",
        )
    )
    structural_generator_version = (
        _required_non_empty_string(
            campaign_manifest,
            "structural_generator_version",
            "campaign_manifest",
        )
    )

    (
        expected_campaign_generator_version,
        expected_structural_generator_version,
    ) = _expected_generator_versions(
        factor
    )

    if (
        campaign_generator_version
        != expected_campaign_generator_version
    ):
        raise E3ExecutionError(
            "Unsupported E2.2 campaign generator version "
            f"for factor {factor!r}: "
            f"expected="
            f"{expected_campaign_generator_version!r}, "
            f"actual={campaign_generator_version!r}."
        )

    if (
        structural_generator_version
        != expected_structural_generator_version
    ):
        raise E3ExecutionError(
            "Unsupported E2.1 structural generator version "
            f"for factor {factor!r}: "
            f"expected="
            f"{expected_structural_generator_version!r}, "
            f"actual={structural_generator_version!r}."
        )

    expected_count = _required_integer(
        campaign_manifest,
        "expected_instance_count",
        "campaign_manifest",
    )
    realised_count = _required_integer(
        campaign_manifest,
        "realised_instance_count",
        "campaign_manifest",
    )

    if expected_count != realised_count:
        raise E3ExecutionError(
            "Campaign expected_instance_count differs "
            "from realised_instance_count."
        )

    if realised_count != len(rows):
        raise E3ExecutionError(
            "campaign_manifest.realised_instance_count "
            "differs from instances.csv row count."
        )

    discovered: list[DiscoveredInstance] = []
    seen_ids: set[str] = set()
    seen_objectives: set[str] = set()
    seen_conditions: set[tuple[int, int, int]] = set()

    for row_number, row in enumerate(
        rows,
        start=2,
    ):
        row_campaign_id = _csv_string(
            row,
            "campaign_id",
            row_number,
        )
        row_factor = _csv_string(
            row,
            "factor",
            row_number,
        )

        if row_campaign_id != campaign_id:
            raise E3ExecutionError(
                f"instances.csv row {row_number}: "
                "campaign_id differs from campaign manifest."
            )

        if row_factor != factor:
            raise E3ExecutionError(
                f"instances.csv row {row_number}: "
                "factor differs from campaign manifest."
            )

        factor_level = _csv_integer(
            row,
            "factor_level",
            row_number,
        )
        replication_index = _csv_integer(
            row,
            "replication_index",
            row_number,
        )
        seed = _csv_integer(
            row,
            "seed",
            row_number,
        )

        relative_instance_dir = _csv_string(
            row,
            "relative_instance_dir",
            row_number,
        )
        canonical_instance_id = (
            _canonical_instance_id(
                relative_instance_dir
            )
        )

        objective_id = _csv_string(
            row,
            "objective_id",
            row_number,
        )

        condition_key = (
            factor_level,
            replication_index,
            seed,
        )

        if canonical_instance_id in seen_ids:
            raise E3ExecutionError(
                "Duplicate canonical instance identifier: "
                f"{canonical_instance_id}"
            )

        if objective_id in seen_objectives:
            raise E3ExecutionError(
                "Duplicate instance objective_id: "
                f"{objective_id}"
            )

        if condition_key in seen_conditions:
            raise E3ExecutionError(
                "Duplicate campaign condition: "
                f"{condition_key}"
            )

        instance_dir = (
            campaign_dir
            / relative_instance_dir
        ).resolve()

        try:
            instance_dir.relative_to(
                campaign_dir
            )
        except ValueError as exc:
            raise E3ExecutionError(
                "Instance path escapes campaign directory: "
                f"{relative_instance_dir}"
            ) from exc

        manifest_path = (
            instance_dir / "manifest.json"
        )
        objectives_path = (
            instance_dir / "objectives.yaml"
        )

        manifest = _read_json(
            manifest_path,
            "E2.1 instance manifest",
        )

        if not objectives_path.is_file():
            raise E3ExecutionError(
                "Missing E2.1 objectives file: "
                f"{objectives_path}"
            )

        _validate_instance_manifest(
            manifest=manifest,
            row=row,
            row_number=row_number,
        )

        generator_version = _csv_string(
            row,
            "generator_version",
            row_number,
        )

        if (
            generator_version
            != expected_structural_generator_version
        ):
            raise E3ExecutionError(
                f"Instance {canonical_instance_id}: "
                "unexpected generator version for "
                f"factor {factor!r}: "
                f"expected="
                f"{expected_structural_generator_version!r}, "
                f"actual={generator_version!r}."
            )

        discovered.append(
            DiscoveredInstance(
                campaign_id=campaign_id,
                factor=factor,
                factor_level=factor_level,
                replication_index=(
                    replication_index
                ),
                seed=seed,
                objective_id=objective_id,
                relative_instance_dir=(
                    relative_instance_dir
                ),
                canonical_instance_id=(
                    canonical_instance_id
                ),
                requested_constraint_count=(
                    _csv_integer(
                        row,
                        "requested_constraint_count",
                        row_number,
                    )
                ),
                realised_constraint_count=(
                    _csv_integer(
                        row,
                        "realised_constraint_count",
                        row_number,
                    )
                ),
                requested_virtual_node_count=(
                    _csv_integer(
                        row,
                        "requested_virtual_node_count",
                        row_number,
                    )
                ),
                realised_virtual_node_count=(
                    _csv_integer(
                        row,
                        "realised_virtual_node_count",
                        row_number,
                    )
                ),
                configuration_digest=(
                    _csv_string(
                        row,
                        "configuration_digest",
                        row_number,
                    )
                ),
                instance_digest=(
                    _csv_string(
                        row,
                        "instance_digest",
                        row_number,
                    )
                ),
                generator_version=(
                    generator_version
                ),
                instance_dir=instance_dir,
                manifest_path=manifest_path,
                objectives_path=objectives_path,
            )
        )

        seen_ids.add(canonical_instance_id)
        seen_objectives.add(objective_id)
        seen_conditions.add(condition_key)

    # Preserve the canonical E2.2 matrix order:
    # factor level, replication index, then seed.
    discovered.sort(
        key=lambda item: (
            item.factor_level,
            item.replication_index,
            item.seed,
            item.canonical_instance_id,
        )
    )

    return tuple(discovered)


def _select_instances(
    instances: Sequence[DiscoveredInstance],
    selection: str | Sequence[str],
) -> tuple[DiscoveredInstance, ...]:
    if selection == "all":
        return tuple(instances)

    requested = tuple(selection)
    by_id = {
        instance.canonical_instance_id: instance
        for instance in instances
    }

    unknown = [
        instance_id
        for instance_id in requested
        if instance_id not in by_id
    ]

    if unknown:
        raise E3ExecutionError(
            "Unknown selected instance identifiers: "
            f"{unknown}. Available identifiers: "
            f"{sorted(by_id)}"
        )

    # Follow campaign order, not the order supplied by the caller.
    selected_set = set(requested)

    return tuple(
        instance
        for instance in instances
        if instance.canonical_instance_id
        in selected_set
    )


def load_execution_inputs(
    execution_spec_path: str | Path,
) -> ExecutionInputs:
    spec_path = Path(
        execution_spec_path
    ).expanduser().resolve()

    execution_spec = _read_json(
        spec_path,
        "E3 execution spec",
    )

    contract_version = _required_non_empty_string(
        execution_spec,
        "contract_version",
        "execution_spec",
    )

    if (
        contract_version
        != "mcad-sensitivity-e3-execution-v1"
    ):
        raise E3ExecutionError(
            "Unsupported E3 execution contract version: "
            f"{contract_version!r}"
        )

    _required_non_empty_string(
        execution_spec,
        "execution_id",
        "execution_spec",
    )

    spec_dir = spec_path.parent

    campaign_dir = _resolve_path(
        _required_non_empty_string(
            execution_spec,
            "campaign_dir",
            "execution_spec",
        ),
        relative_to=spec_dir,
    )

    workload_path = _resolve_path(
        _required_non_empty_string(
            execution_spec,
            "workload_path",
            "execution_spec",
        ),
        relative_to=spec_dir,
    )

    output_dir = _resolve_path(
        _required_non_empty_string(
            execution_spec,
            "output_dir",
            "execution_spec",
        ),
        relative_to=spec_dir,
    )

    if not campaign_dir.is_dir():
        raise E3ExecutionError(
            f"Campaign directory does not exist: "
            f"{campaign_dir}"
        )

    workload = _read_json(
        workload_path,
        "E3 workload spec",
    )
    _validate_workload_shape(workload)

    campaign_manifest = _read_json(
        campaign_dir / "campaign_manifest.json",
        "E2.2 campaign manifest",
    )

    all_instances = _discover_all_instances(
        campaign_dir=campaign_dir,
        campaign_manifest=campaign_manifest,
    )

    selected_instances = _select_instances(
        all_instances,
        _normalise_selected_instances(
            execution_spec.get(
                "instance_selection"
            )
        ),
    )

    if not selected_instances:
        raise E3ExecutionError(
            "The execution selects no campaign instance."
        )

    return ExecutionInputs(
        execution_spec_path=spec_path,
        execution_spec=execution_spec,
        workload_path=workload_path,
        workload=workload,
        campaign_dir=campaign_dir,
        campaign_manifest=campaign_manifest,
        output_dir=output_dir,
        instances=selected_instances,
    )


def _clear_ckg_runtime_state(
    ckg: CKGGraph,
) -> None:
    """
    Remove constructor bootstrap state before loading an E2.1 instance.

    This reproduces the clean-state convention used by the
    structural-family generator.
    """
    required_attributes = (
        "G",
        "objectives",
        "history",
        "session_coverage",
        "session_weighted_coverage",
        "session_resource_coverage",
    )

    for attribute_name in required_attributes:
        if not hasattr(ckg, attribute_name):
            raise E3ExecutionError(
                "CKGGraph is missing required runtime "
                f"attribute {attribute_name!r}."
            )

        value = getattr(ckg, attribute_name)

        clear = getattr(value, "clear", None)
        if not callable(clear):
            raise E3ExecutionError(
                "CKGGraph runtime attribute "
                f"{attribute_name!r} is not clearable."
            )

        clear()


def _build_instance_ckg(
    *,
    instance: DiscoveredInstance,
    runtime_output_dir: Path,
) -> CKGGraph:
    """
    Create one fully isolated CKG for a controlled instance.

    No evaluator logic is duplicated here. The function only controls
    lifecycle, state isolation, and objective bootstrap.
    """
    runtime_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ckg = CKGGraph(
        output_dir=str(runtime_output_dir)
    )

    _clear_ckg_runtime_state(ckg)

    ckg.bootstrap_objectives(
        str(instance.objectives_path)
    )

    objective_ids = set(ckg.objectives)

    if objective_ids != {instance.objective_id}:
        raise E3ExecutionError(
            "Bootstrapped objective set differs from the "
            f"instance manifest for "
            f"{instance.canonical_instance_id!r}: "
            f"expected={[instance.objective_id]!r}, "
            f"actual={sorted(objective_ids)!r}."
        )

    if len(ckg.G) == 0:
        raise E3ExecutionError(
            "Bootstrapped CKG is empty for instance "
            f"{instance.canonical_instance_id!r}."
        )

    if ckg.history:
        raise E3ExecutionError(
            "Freshly bootstrapped CKG contains history for "
            f"instance {instance.canonical_instance_id!r}."
        )

    for attribute_name in (
        "session_coverage",
        "session_weighted_coverage",
        "session_resource_coverage",
    ):
        value = getattr(ckg, attribute_name)

        if value:
            raise E3ExecutionError(
                "Freshly bootstrapped CKG contains session "
                f"state in {attribute_name!r} for instance "
                f"{instance.canonical_instance_id!r}."
            )

    return ckg


def _print_bootstrap_summary(
    inputs: ExecutionInputs,
) -> None:
    print("[OK] E3 Phase B CKG bootstrap started.")

    bootstrap_root = (
        inputs.output_dir
        / "_runtime"
        / "instances"
    )

    for instance in inputs.instances:
        runtime_output_dir = (
            bootstrap_root
            / instance.canonical_instance_id
        )

        ckg = _build_instance_ckg(
            instance=instance,
            runtime_output_dir=runtime_output_dir,
        )

        objective = ckg.objectives[
            instance.objective_id
        ]

        constraints = objective.get(
            "constraints",
            {},
        )

        if not isinstance(constraints, dict):
            raise E3ExecutionError(
                "Bootstrapped objective constraints must "
                "be represented as a mapping for instance "
                f"{instance.canonical_instance_id!r}."
            )

        print(
            "[BOOTSTRAP] "
            f"id={instance.canonical_instance_id} "
            f"objective_id={instance.objective_id} "
            f"graph_nodes={len(ckg.G)} "
            f"objective_count={len(ckg.objectives)} "
            f"constraint_count={len(constraints)} "
            f"runtime_dir={runtime_output_dir}"
        )

    print(
        "[OK] E3 Phase B CKG bootstrap succeeded "
        f"for {len(inputs.instances)} instance(s)."
    )


def _print_discovery_summary(
    inputs: ExecutionInputs,
) -> None:
    execution_id = inputs.execution_spec[
        "execution_id"
    ]
    campaign_id = inputs.campaign_manifest[
        "campaign_id"
    ]
    workload_id = inputs.workload[
        "workload_id"
    ]

    print("[OK] E3 Phase A input discovery succeeded.")
    print(f"[OK] executor_version={E3_EXECUTOR_VERSION}")
    print(f"[OK] execution_id={execution_id}")
    print(f"[OK] campaign_id={campaign_id}")
    print(f"[OK] workload_id={workload_id}")
    print(f"[OK] campaign_dir={inputs.campaign_dir}")
    print(f"[OK] workload_path={inputs.workload_path}")
    print(f"[OK] output_dir={inputs.output_dir}")
    print(
        f"[OK] selected_instance_count="
        f"{len(inputs.instances)}"
    )

    for instance in inputs.instances:
        print(
            "[INSTANCE] "
            f"id={instance.canonical_instance_id} "
            f"level={instance.factor_level} "
            f"replication={instance.replication_index} "
            f"seed={instance.seed} "
            f"objective_id={instance.objective_id}"
        )


@dataclass(frozen=True)
class InstanceExecutionResult:
    """Completed or failed execution of one controlled instance."""

    instance: DiscoveredInstance
    session_id: str
    output_dir: Path
    status: str
    metrics: dict[str, Any]
    semantic_digest: str


INSTANCE_RESULT_COLUMNS = (
    "execution_id",
    "campaign_id",
    "factor",
    "factor_level",
    "replication_index",
    "seed",
    "canonical_instance_id",
    "objective_id",
    "session_id",
    "status",
    "step_count",
    "successful_step_count",
    "failed_step_count",
    "sat_fail_count",
    "real_empty_count",
    "ceval_empty_count",
    "phi_final",
    "phi_weighted_final",
    "auc_phi",
    "evaluator_latency_p50_ms",
    "evaluator_latency_p95_ms",
    "evaluator_latency_p99_ms",
    "configuration_digest",
    "instance_digest",
    "semantic_digest",
)


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _semantic_digest(value: Any) -> str:
    return hashlib.sha256(
        _stable_json_bytes(value)
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _write_json(
    path: Path,
    value: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(columns),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    column: row.get(column, "")
                    for column in columns
                }
            )


def _percentile(
    values: Sequence[float],
    probability: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(float(value) for value in values)

    if len(ordered) == 1:
        return round(ordered[0], 6)

    position = probability * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )
    fraction = position - lower_index

    value = (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )

    return round(value, 6)


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0

    return round(
        sum(float(value) for value in values)
        / float(len(values)),
        6,
    )


def _instance_session_id(
    workload_session_id: str,
    instance: DiscoveredInstance,
) -> str:
    return (
        f"{workload_session_id}::"
        f"{instance.canonical_instance_id}"
    )


def _instance_output_dir(
    execution_output_dir: Path,
    instance: DiscoveredInstance,
) -> Path:
    return (
        execution_output_dir
        / "instances"
        / Path(instance.canonical_instance_id)
    )


def _e2_input_paths(
    inputs: ExecutionInputs,
) -> tuple[Path, ...]:
    paths: list[Path] = [
        inputs.campaign_dir / "campaign_manifest.json",
        inputs.campaign_dir / "instances.csv",
    ]

    campaign_spec = (
        inputs.campaign_dir / "campaign_spec.json"
    )
    if campaign_spec.is_file():
        paths.append(campaign_spec)

    for instance in inputs.instances:
        paths.extend(
            [
                instance.manifest_path,
                instance.objectives_path,
            ]
        )

    unique = {
        path.resolve()
        for path in paths
    }

    return tuple(
        sorted(
            unique,
            key=lambda item: item.as_posix(),
        )
    )


def _capture_input_digests(
    inputs: ExecutionInputs,
) -> dict[str, str]:
    result: dict[str, str] = {}

    for path in _e2_input_paths(inputs):
        try:
            key = path.relative_to(
                inputs.campaign_dir
            ).as_posix()
        except ValueError:
            key = path.as_posix()

        result[key] = _file_sha256(path)

    return result


def _prepare_output_directory(
    inputs: ExecutionInputs,
) -> None:
    output_dir = inputs.output_dir
    overwrite = bool(
        inputs.execution_spec.get(
            "overwrite",
            False,
        )
    )

    try:
        output_dir.relative_to(
            inputs.campaign_dir
        )
    except ValueError:
        pass
    else:
        raise E3ExecutionError(
            "E3 output directory must be outside "
            "the immutable E2 campaign tree."
        )

    if output_dir.exists():
        has_content = any(
            output_dir.iterdir()
        )

        if has_content and not overwrite:
            raise E3ExecutionError(
                "Output directory already exists and is "
                "not empty. Set execution_spec.overwrite=true "
                f"to replace it: {output_dir}"
            )

        if has_content and overwrite:
            shutil.rmtree(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


def _project_cumulative_phi(
    evaluator_value: Any,
    previous_value: float,
) -> float:
    if evaluator_value is None:
        return round(
            float(previous_value),
            6,
        )

    value = float(evaluator_value)

    if value < 0.0 or value > 1.0:
        raise E3ExecutionError(
            "Evaluator returned cumulative phi outside "
            f"[0, 1]: {value}"
        )

    if value + 1e-12 < previous_value:
        raise E3ExecutionError(
            "Evaluator returned a decreasing cumulative phi: "
            f"previous={previous_value}, current={value}"
        )

    return round(value, 6)


def _semantic_step_projection(
    timeline_entry: Mapping[str, Any],
) -> dict[str, Any]:
    excluded = {
        "evaluator_latency_ms",
        "error",
        "traceback",
    }

    return {
        key: value
        for key, value in timeline_entry.items()
        if key not in excluded
    }


def _build_instance_metrics(
    timeline: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    successful = [
        step
        for step in timeline
        if step.get("status") == "success"
    ]
    failed = [
        step
        for step in timeline
        if step.get("status") == "failed"
    ]

    latencies = [
        float(step["evaluator_latency_ms"])
        for step in successful
    ]

    phi_curve = [
        float(step["phi_leq_t"])
        for step in successful
    ]
    weighted_curve = [
        float(step["phi_weighted_leq_t"])
        for step in successful
    ]

    return {
        "step_count": len(timeline),
        "successful_step_count": len(successful),
        "failed_step_count": len(failed),
        "sat_fail_count": sum(
            1
            for step in successful
            if not bool(step.get("sat"))
        ),
        "real_empty_count": sum(
            1
            for step in successful
            if not list(
                step.get("real_node_ids") or []
            )
        ),
        "ceval_empty_count": sum(
            1
            for step in successful
            if not list(
                step.get(
                    "calculable_constraints"
                )
                or []
            )
        ),
        "phi_final": round(
            phi_curve[-1] if phi_curve else 0.0,
            6,
        ),
        "phi_weighted_final": round(
            (
                weighted_curve[-1]
                if weighted_curve
                else 0.0
            ),
            6,
        ),
        "auc_phi": _mean(phi_curve),
        "evaluator_latency_p50_ms": _percentile(
            latencies,
            0.50,
        ),
        "evaluator_latency_p95_ms": _percentile(
            latencies,
            0.95,
        ),
        "evaluator_latency_p99_ms": _percentile(
            latencies,
            0.99,
        ),
    }


def _base_instance_manifest(
    *,
    inputs: ExecutionInputs,
    instance: DiscoveredInstance,
    session_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": (
            "mcad-sensitivity-e3-instance-execution-v1"
        ),
        "executor_version": E3_EXECUTOR_VERSION,
        "execution_id": inputs.execution_spec[
            "execution_id"
        ],
        "campaign_id": instance.campaign_id,
        "factor": instance.factor,
        "factor_level": instance.factor_level,
        "replication_index": (
            instance.replication_index
        ),
        "seed": instance.seed,
        "canonical_instance_id": (
            instance.canonical_instance_id
        ),
        "relative_instance_dir": (
            instance.relative_instance_dir
        ),
        "objective_id": instance.objective_id,
        "workload_id": inputs.workload[
            "workload_id"
        ],
        "workload_objective_binding": (
            inputs.workload["objective_id"]
        ),
        "session_id": session_id,
        "configuration_digest": (
            instance.configuration_digest
        ),
        "instance_digest": (
            instance.instance_digest
        ),
        "structural_generator_version": (
            instance.generator_version
        ),
        "campaign_generator_version": (
            inputs.campaign_manifest[
                "campaign_generator_version"
            ]
        ),
        "evaluator_component": "CKGGraph",
        "evaluator_entrypoint": (
            "backend.ckg.ckg_updater."
            "CKGGraph.evaluate_step"
        ),
        "commit_entrypoint": (
            "backend.ckg.ckg_updater."
            "CKGGraph.update_from_step"
        ),
        "invocation_mode": "local-python",
    }


def _execute_instance(
    *,
    inputs: ExecutionInputs,
    instance: DiscoveredInstance,
) -> InstanceExecutionResult:
    instance_output_dir = _instance_output_dir(
        inputs.output_dir,
        instance,
    )
    runtime_output_dir = (
        instance_output_dir / "runtime"
    )

    instance_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    session_id = _instance_session_id(
        str(inputs.workload["session_id"]),
        instance,
    )

    manifest = _base_instance_manifest(
        inputs=inputs,
        instance=instance,
        session_id=session_id,
    )

    timeline: list[dict[str, Any]] = []
    previous_phi = 0.0
    previous_weighted_phi = 0.0

    audit: dict[str, Any] = {
        "schema_version": (
            "mcad-sensitivity-e3-instance-audit-v1"
        ),
        "execution_id": inputs.execution_spec[
            "execution_id"
        ],
        "canonical_instance_id": (
            instance.canonical_instance_id
        ),
        "objective_id": instance.objective_id,
        "session_id": session_id,
        "fresh_runtime_state": True,
        "fresh_session": True,
        "cross_instance_state_reuse": False,
        "evaluator_reimplementation": False,
        "backend_http_api_used": False,
        "evaluator_entrypoint_preserved": True,
        "step_order_preserved": True,
        "source_instance_digest": (
            instance.instance_digest
        ),
        "status": "running",
    }

    try:
        ckg = _build_instance_ckg(
            instance=instance,
            runtime_output_dir=runtime_output_dir,
        )

        for raw_step in inputs.workload["steps"]:
            step_index = int(
                raw_step["step_index"]
            )
            step_id = str(
                raw_step["step_id"]
            )
            query_spec = dict(
                raw_step["query_spec"]
            )

            qp = {
                "objective_id": instance.objective_id,
                "query_spec": query_spec,
            }

            started_ns = perf_counter_ns()

            try:
                evaluator_result = ckg.evaluate_step(
                    session_id=session_id,
                    objective_id=instance.objective_id,
                    step_idx=step_index,
                    qp=qp,
                )
            except Exception as exc:
                latency_ms = round(
                    (
                        perf_counter_ns()
                        - started_ns
                    )
                    / 1_000_000.0,
                    6,
                )

                failed_step = {
                    "step_index": step_index,
                    "step_id": step_id,
                    "session_id": session_id,
                    "objective_id": (
                        instance.objective_id
                    ),
                    "query_spec": query_spec,
                    "sat": False,
                    "real_node_ids": [],
                    "calculable_constraints": [],
                    "phi": 0.0,
                    "phi_weighted": 0.0,
                    "phi_leq_t": previous_phi,
                    "delta_phi_t": 0.0,
                    "phi_weighted_leq_t": (
                        previous_weighted_phi
                    ),
                    "delta_phi_weighted_t": 0.0,
                    "evaluator_latency_ms": (
                        latency_ms
                    ),
                    "status": "failed",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "traceback": traceback.format_exc(),
                }
                timeline.append(failed_step)
                raise

            latency_ms = round(
                (
                    perf_counter_ns()
                    - started_ns
                )
                / 1_000_000.0,
                6,
            )

            if not isinstance(
                evaluator_result,
                dict,
            ):
                raise E3ExecutionError(
                    "CKGGraph.evaluate_step() must "
                    "return a dictionary."
                )

            projected_phi = (
                _project_cumulative_phi(
                    evaluator_result.get(
                        "phi_leq_t"
                    ),
                    previous_phi,
                )
            )
            projected_weighted_phi = (
                _project_cumulative_phi(
                    evaluator_result.get(
                        "phi_weighted_leq_t"
                    ),
                    previous_weighted_phi,
                )
            )

            timeline_entry = {
                "step_index": step_index,
                "step_id": step_id,
                "session_id": session_id,
                "objective_id": (
                    instance.objective_id
                ),
                "query_spec": query_spec,
                **evaluator_result,
                "phi_leq_t": projected_phi,
                "delta_phi_t": round(
                    projected_phi
                    - previous_phi,
                    6,
                ),
                "phi_weighted_leq_t": (
                    projected_weighted_phi
                ),
                "delta_phi_weighted_t": round(
                    projected_weighted_phi
                    - previous_weighted_phi,
                    6,
                ),
                "evaluator_latency_ms": (
                    latency_ms
                ),
                "status": "success",
            }

            ckg.update_from_step(
                timeline_entry,
                step_idx=step_index,
                session_id=session_id,
            )

            timeline.append(
                timeline_entry
            )
            previous_phi = projected_phi
            previous_weighted_phi = (
                projected_weighted_phi
            )

        metrics = _build_instance_metrics(
            timeline
        )

        semantic_payload = {
            "manifest": manifest,
            "timeline": [
                _semantic_step_projection(step)
                for step in timeline
            ],
            "metrics": {
                key: value
                for key, value in metrics.items()
                if not key.startswith(
                    "evaluator_latency_"
                )
            },
        }
        semantic_digest = _semantic_digest(
            semantic_payload
        )

        manifest.update(
            {
                "status": "success",
                "step_count": len(timeline),
                "semantic_digest": (
                    semantic_digest
                ),
                "required_outputs": [
                    "execution_manifest.json",
                    "timeline.json",
                    "metrics.json",
                    "audit.json",
                ],
            }
        )

        audit.update(
            {
                "status": "success",
                "history_entry_count": len(
                    ckg.history
                ),
                "timeline_step_count": len(
                    timeline
                ),
                "all_steps_committed": (
                    len(ckg.history)
                    == len(timeline)
                ),
                "cumulative_phi_in_range": all(
                    0.0
                    <= float(
                        step["phi_leq_t"]
                    )
                    <= 1.0
                    for step in timeline
                ),
                "cumulative_phi_monotone": all(
                    float(
                        timeline[index][
                            "phi_leq_t"
                        ]
                    )
                    >= float(
                        timeline[index - 1][
                            "phi_leq_t"
                        ]
                    )
                    for index in range(
                        1,
                        len(timeline),
                    )
                ),
                "semantic_digest": (
                    semantic_digest
                ),
            }
        )

        _write_json(
            instance_output_dir
            / "timeline.json",
            {
                "schema_version": (
                    "mcad-sensitivity-e3-timeline-v1"
                ),
                "execution_id": (
                    inputs.execution_spec[
                        "execution_id"
                    ]
                ),
                "canonical_instance_id": (
                    instance.canonical_instance_id
                ),
                "objective_id": (
                    instance.objective_id
                ),
                "session_id": session_id,
                "steps": timeline,
            },
        )
        _write_json(
            instance_output_dir
            / "metrics.json",
            {
                "schema_version": (
                    "mcad-sensitivity-e3-metrics-v1"
                ),
                "execution_id": (
                    inputs.execution_spec[
                        "execution_id"
                    ]
                ),
                "canonical_instance_id": (
                    instance.canonical_instance_id
                ),
                "objective_id": (
                    instance.objective_id
                ),
                **metrics,
            },
        )
        _write_json(
            instance_output_dir
            / "audit.json",
            audit,
        )
        _write_json(
            instance_output_dir
            / "execution_manifest.json",
            manifest,
        )

        return InstanceExecutionResult(
            instance=instance,
            session_id=session_id,
            output_dir=instance_output_dir,
            status="success",
            metrics=metrics,
            semantic_digest=semantic_digest,
        )

    except Exception as exc:
        metrics = _build_instance_metrics(
            timeline
        )

        semantic_payload = {
            "manifest": manifest,
            "timeline": [
                _semantic_step_projection(step)
                for step in timeline
            ],
            "metrics": {
                key: value
                for key, value in metrics.items()
                if not key.startswith(
                    "evaluator_latency_"
                )
            },
            "failure": (
                f"{type(exc).__name__}: {exc}"
            ),
        }
        semantic_digest = _semantic_digest(
            semantic_payload
        )

        manifest.update(
            {
                "status": "failed",
                "step_count": len(timeline),
                "semantic_digest": (
                    semantic_digest
                ),
                "failure": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }
        )

        audit.update(
            {
                "status": "failed",
                "failure": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
                "traceback": traceback.format_exc(),
                "semantic_digest": (
                    semantic_digest
                ),
            }
        )

        _write_json(
            instance_output_dir
            / "timeline.json",
            {
                "schema_version": (
                    "mcad-sensitivity-e3-timeline-v1"
                ),
                "execution_id": (
                    inputs.execution_spec[
                        "execution_id"
                    ]
                ),
                "canonical_instance_id": (
                    instance.canonical_instance_id
                ),
                "objective_id": (
                    instance.objective_id
                ),
                "session_id": session_id,
                "steps": timeline,
            },
        )
        _write_json(
            instance_output_dir
            / "metrics.json",
            {
                "schema_version": (
                    "mcad-sensitivity-e3-metrics-v1"
                ),
                "execution_id": (
                    inputs.execution_spec[
                        "execution_id"
                    ]
                ),
                "canonical_instance_id": (
                    instance.canonical_instance_id
                ),
                "objective_id": (
                    instance.objective_id
                ),
                **metrics,
            },
        )
        _write_json(
            instance_output_dir
            / "audit.json",
            audit,
        )
        _write_json(
            instance_output_dir
            / "execution_manifest.json",
            manifest,
        )

        raise E3ExecutionError(
            "Controlled execution failed for instance "
            f"{instance.canonical_instance_id!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _instance_result_row(
    *,
    execution_id: str,
    result: InstanceExecutionResult,
) -> dict[str, Any]:
    instance = result.instance

    return {
        "execution_id": execution_id,
        "campaign_id": instance.campaign_id,
        "factor": instance.factor,
        "factor_level": instance.factor_level,
        "replication_index": (
            instance.replication_index
        ),
        "seed": instance.seed,
        "canonical_instance_id": (
            instance.canonical_instance_id
        ),
        "objective_id": instance.objective_id,
        "session_id": result.session_id,
        "status": result.status,
        **result.metrics,
        "configuration_digest": (
            instance.configuration_digest
        ),
        "instance_digest": (
            instance.instance_digest
        ),
        "semantic_digest": (
            result.semantic_digest
        ),
    }


def _build_campaign_metrics(
    results: Sequence[InstanceExecutionResult],
) -> dict[str, Any]:
    rows = [
        result.metrics
        for result in results
    ]

    return {
        "instance_count": len(results),
        "successful_instance_count": sum(
            1
            for result in results
            if result.status == "success"
        ),
        "failed_instance_count": sum(
            1
            for result in results
            if result.status == "failed"
        ),
        "step_count": sum(
            int(row["step_count"])
            for row in rows
        ),
        "successful_step_count": sum(
            int(row["successful_step_count"])
            for row in rows
        ),
        "failed_step_count": sum(
            int(row["failed_step_count"])
            for row in rows
        ),
        "sat_fail_count": sum(
            int(row["sat_fail_count"])
            for row in rows
        ),
        "real_empty_count": sum(
            int(row["real_empty_count"])
            for row in rows
        ),
        "ceval_empty_count": sum(
            int(row["ceval_empty_count"])
            for row in rows
        ),
        "mean_phi_final": _mean(
            [
                float(row["phi_final"])
                for row in rows
            ]
        ),
        "mean_phi_weighted_final": _mean(
            [
                float(
                    row["phi_weighted_final"]
                )
                for row in rows
            ]
        ),
        "mean_auc_phi": _mean(
            [
                float(row["auc_phi"])
                for row in rows
            ]
        ),
        "mean_evaluator_latency_p50_ms": _mean(
            [
                float(
                    row[
                        "evaluator_latency_p50_ms"
                    ]
                )
                for row in rows
            ]
        ),
        "mean_evaluator_latency_p95_ms": _mean(
            [
                float(
                    row[
                        "evaluator_latency_p95_ms"
                    ]
                )
                for row in rows
            ]
        ),
        "mean_evaluator_latency_p99_ms": _mean(
            [
                float(
                    row[
                        "evaluator_latency_p99_ms"
                    ]
                )
                for row in rows
            ]
        ),
    }


def execute_controlled_family(
    execution_spec_path: str | Path,
) -> dict[str, Any]:
    inputs = load_execution_inputs(
        execution_spec_path
    )

    _prepare_output_directory(
        inputs
    )

    input_digests_before = (
        _capture_input_digests(inputs)
    )

    _write_json(
        inputs.output_dir
        / "execution_spec.json",
        inputs.execution_spec,
    )

    results: list[InstanceExecutionResult] = []

    for instance in inputs.instances:
        result = _execute_instance(
            inputs=inputs,
            instance=instance,
        )
        results.append(result)

    input_digests_after = (
        _capture_input_digests(inputs)
    )

    if (
        input_digests_before
        != input_digests_after
    ):
        raise E3ExecutionError(
            "Immutable E2 inputs changed during "
            "controlled execution."
        )

    execution_id = str(
        inputs.execution_spec["execution_id"]
    )

    result_rows = [
        _instance_result_row(
            execution_id=execution_id,
            result=result,
        )
        for result in results
    ]

    campaign_metrics = (
        _build_campaign_metrics(results)
    )

    campaign_semantic_payload = {
        "execution_id": execution_id,
        "executor_version": E3_EXECUTOR_VERSION,
        "campaign_id": inputs.campaign_manifest[
            "campaign_id"
        ],
        "workload_id": inputs.workload[
            "workload_id"
        ],
        "instance_results": [
            {
                key: value
                for key, value in row.items()
                if not key.startswith(
                    "evaluator_latency_"
                )
            }
            for row in result_rows
        ],
        "input_digests": (
            input_digests_before
        ),
    }

    execution_digest = _semantic_digest(
        campaign_semantic_payload
    )

    campaign_metrics_payload = {
        "schema_version": (
            "mcad-sensitivity-e3-campaign-metrics-v1"
        ),
        "execution_id": execution_id,
        "campaign_id": inputs.campaign_manifest[
            "campaign_id"
        ],
        "factor": inputs.campaign_manifest[
            "factor"
        ],
        **campaign_metrics,
    }

    execution_manifest = {
        "schema_version": (
            "mcad-sensitivity-e3-execution-manifest-v1"
        ),
        "executor_version": E3_EXECUTOR_VERSION,
        "execution_id": execution_id,
        "status": "success",
        "campaign_id": inputs.campaign_manifest[
            "campaign_id"
        ],
        "factor": inputs.campaign_manifest[
            "factor"
        ],
        "workload_id": inputs.workload[
            "workload_id"
        ],
        "workload_objective_binding": (
            inputs.workload["objective_id"]
        ),
        "selected_instance_count": len(
            inputs.instances
        ),
        "successful_instance_count": len(
            results
        ),
        "failed_instance_count": 0,
        "instance_order": [
            instance.canonical_instance_id
            for instance in inputs.instances
        ],
        "evaluator_entrypoint": (
            "backend.ckg.ckg_updater."
            "CKGGraph.evaluate_step"
        ),
        "commit_entrypoint": (
            "backend.ckg.ckg_updater."
            "CKGGraph.update_from_step"
        ),
        "fresh_runtime_state_per_instance": True,
        "fresh_session_per_instance": True,
        "cross_instance_state_reuse": False,
        "e2_inputs_unchanged": True,
        "input_digests": input_digests_before,
        "deterministic_execution_digest": (
            execution_digest
        ),
        "required_outputs": [
            "execution_spec.json",
            "execution_manifest.json",
            "instance_results.csv",
            "campaign_metrics.json",
        ],
    }

    _write_csv(
        inputs.output_dir
        / "instance_results.csv",
        result_rows,
        INSTANCE_RESULT_COLUMNS,
    )
    _write_json(
        inputs.output_dir
        / "campaign_metrics.json",
        campaign_metrics_payload,
    )
    _write_json(
        inputs.output_dir
        / "execution_manifest.json",
        execution_manifest,
    )

    return {
        "execution_manifest": (
            execution_manifest
        ),
        "campaign_metrics": (
            campaign_metrics_payload
        ),
        "instance_results": result_rows,
    }


def _print_discovery(
    inputs: ExecutionInputs,
) -> None:
    print(
        "[OK] E3 execution inputs discovered."
    )
    print(
        "[OK] execution_id="
        f"{inputs.execution_spec['execution_id']}"
    )
    print(
        "[OK] campaign_id="
        f"{inputs.campaign_manifest['campaign_id']}"
    )
    print(
        "[OK] selected_instance_count="
        f"{len(inputs.instances)}"
    )

    for instance in inputs.instances:
        print(
            "[INSTANCE] "
            f"id={instance.canonical_instance_id} "
            f"level={instance.factor_level} "
            f"rep={instance.replication_index} "
            f"seed={instance.seed} "
            f"objective={instance.objective_id}"
        )


def _bootstrap_selected_instances(
    inputs: ExecutionInputs,
) -> None:
    print(
        "[OK] Bootstrapping selected instances."
    )
    print(
        "[OK] selected_instance_count="
        f"{len(inputs.instances)}"
    )

    for instance in inputs.instances:
        runtime_dir = (
            inputs.output_dir
            / "_bootstrap_probe"
            / Path(
                instance.canonical_instance_id
            )
        )

        ckg = _build_instance_ckg(
            instance=instance,
            runtime_output_dir=runtime_dir,
        )

        objective = ckg.objectives[
            instance.objective_id
        ]
        constraint_count = len(
            objective.get(
                "constraints",
                {},
            )
        )

        print(
            "[BOOTSTRAP] "
            f"id={instance.canonical_instance_id} "
            f"graph_nodes={len(ckg.G)} "
            "objective_count="
            f"{len(ckg.objectives)} "
            "constraint_count="
            f"{constraint_count}"
        )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute an MCAD E3 controlled family "
            "through the production CKG evaluator."
        )
    )
    parser.add_argument(
        "execution_spec_path",
        type=Path,
        help="Path to execution_spec.json",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help=(
            "Validate and display selected instances "
            "without bootstrapping or executing them."
        ),
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help=(
            "Bootstrap each selected instance without "
            "executing workload steps."
        ),
    )

    args = parser.parse_args(argv)

    if (
        args.discover_only
        and args.bootstrap_only
    ):
        parser.error(
            "--discover-only and --bootstrap-only "
            "are mutually exclusive."
        )

    try:
        inputs = load_execution_inputs(
            args.execution_spec_path
        )

        if args.discover_only:
            _print_discovery(inputs)
            return 0

        if args.bootstrap_only:
            _bootstrap_selected_instances(
                inputs
            )
            return 0

        result = execute_controlled_family(
            args.execution_spec_path
        )

    except E3ExecutionError as exc:
        print(
            f"[ERROR] E3 controlled execution failed: "
            f"{exc}"
        )
        return 1

    manifest = result[
        "execution_manifest"
    ]
    metrics = result[
        "campaign_metrics"
    ]

    print(
        "[OK] E3 controlled execution completed."
    )
    print(
        "[OK] execution_id="
        f"{manifest['execution_id']}"
    )
    print(
        "[OK] selected_instance_count="
        f"{manifest['selected_instance_count']}"
    )
    print(
        "[OK] step_count="
        f"{metrics['step_count']}"
    )
    print(
        "[OK] output_dir="
        f"{load_execution_inputs(args.execution_spec_path).output_dir}"
    )
    print(
        "[OK] deterministic_execution_digest="
        f"{manifest['deterministic_execution_digest']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
