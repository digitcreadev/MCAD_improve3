from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import inspect
import json
import math
import platform
import random
import re
import shutil
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter_ns, process_time_ns
from typing import Any

import backend.harness.sensitivity_execution.execute_controlled_family as canonical_executor
from backend.harness.sensitivity_execution.execute_controlled_family import (
    _build_instance_ckg,
    load_execution_inputs,
)


TIMING_HARNESS_VERSION = "mcad-sensitivity-sa3-timing-v2"

VOLATILE_RESULT_KEYS = {
    "evaluator_latency_ms",
    "error",
    "traceback",
    "session_id",
    "qp_node_id",
}


class TimingHarnessError(RuntimeError):
    """Raised when the reset-safe timing protocol is violated."""


@dataclass(frozen=True, order=True)
class TimingCell:
    canonical_instance_id: str
    factor_level: int
    replication_index: int
    seed: int
    step_position: int
    step_index: int
    step_id: str

    @property
    def cell_id(self) -> str:
        return (
            f"{self.canonical_instance_id}"
            f"::step_{self.step_index:04d}"
        )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value)
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def source_identity(
    value: Any,
) -> dict[str, str]:
    if isinstance(value, Path):
        path = value.resolve()
    else:
        source_path = inspect.getsourcefile(value)

        if source_path is None:
            raise TimingHarnessError(
                "Cannot locate source file for "
                f"{value!r}."
            )

        path = Path(source_path).resolve()

    if not path.is_file():
        raise TimingHarnessError(
            f"Source file does not exist: {path}"
        )

    return {
        "path": str(path),
        "sha256": sha256_file(path),
    }


def validate_existing_bundle(
    *,
    output_dir: Path,
    manifest: Mapping[str, Any],
    current_input_digests: Mapping[str, str],
) -> None:
    if (
        manifest.get("input_digests")
        != dict(current_input_digests)
    ):
        raise TimingHarnessError(
            "Existing timing bundle was generated "
            "from different or modified inputs."
        )

    outputs = manifest.get("outputs")

    if not isinstance(outputs, Mapping):
        raise TimingHarnessError(
            "Existing timing manifest lacks outputs."
        )

    declared_outputs = (
        (
            "timing_observations_csv",
            "timing_observations_sha256",
        ),
        (
            "functional_references_json",
            "functional_references_sha256",
        ),
        (
            "timing_summary_json",
            "timing_summary_sha256",
        ),
    )

    for filename_key, digest_key in declared_outputs:
        filename = outputs.get(filename_key)
        expected_digest = outputs.get(digest_key)

        if (
            not isinstance(filename, str)
            or not isinstance(
                expected_digest,
                str,
            )
        ):
            raise TimingHarnessError(
                "Existing timing manifest contains "
                f"invalid declarations for {filename_key}."
            )

        path = output_dir / filename

        if not path.is_file():
            raise TimingHarnessError(
                f"Existing timing output is missing: {path}"
            )

        actual_digest = sha256_file(path)

        if actual_digest != expected_digest:
            raise TimingHarnessError(
                "Existing timing output digest mismatch: "
                f"{path}"
            )


def write_json(path: Path, value: Any) -> None:
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TimingHarnessError(
            f"Missing JSON file: {path}"
        )

    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(value, dict):
        raise TimingHarnessError(
            f"JSON root must be an object: {path}"
        )

    return value


def canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return canonicalize(asdict(value))

    if isinstance(value, Mapping):
        return {
            str(key): canonicalize(child)
            for key, child in sorted(
                value.items(),
                key=lambda item: str(item[0]),
            )
        }

    if isinstance(value, (list, tuple)):
        return [
            canonicalize(child)
            for child in value
        ]

    if isinstance(value, set):
        children = [
            canonicalize(child)
            for child in value
        ]

        return sorted(
            children,
            key=lambda child: json.dumps(
                child,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ),
        )

    if isinstance(value, Path):
        return str(value)

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            type(None),
        ),
    ):
        return value

    if hasattr(value, "_asdict"):
        return canonicalize(value._asdict())

    if hasattr(value, "__dict__"):
        return canonicalize(vars(value))

    return repr(value)


def functional_projection(value: Any) -> Any:
    canonical = canonicalize(value)

    def strip(child: Any) -> Any:
        if isinstance(child, dict):
            return {
                key: strip(grandchild)
                for key, grandchild in child.items()
                if key not in VOLATILE_RESULT_KEYS
            }

        if isinstance(child, list):
            return [
                strip(grandchild)
                for grandchild in child
            ]

        return child

    return strip(canonical)


def percentile(
    values: Sequence[float],
    probability: float,
) -> float:
    if not values:
        raise TimingHarnessError(
            "Cannot calculate a percentile "
            "from an empty sequence."
        )

    ordered = sorted(float(value) for value in values)

    if len(ordered) == 1:
        return ordered[0]

    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + fraction
        * (ordered[upper] - ordered[lower])
    )


def descriptive_statistics(
    values: Sequence[float],
) -> dict[str, Any]:
    data = [
        float(value)
        for value in values
    ]

    if not data:
        return {
            "count": 0,
            "mean_ms": None,
            "median_ms": None,
            "stdev_ms": None,
            "minimum_ms": None,
            "maximum_ms": None,
            "p95_ms": None,
            "p99_ms": None,
        }

    return {
        "count": len(data),
        "mean_ms": statistics.fmean(data),
        "median_ms": statistics.median(data),
        "stdev_ms": (
            statistics.stdev(data)
            if len(data) > 1
            else 0.0
        ),
        "minimum_ms": min(data),
        "maximum_ms": max(data),
        "p95_ms": percentile(data, 0.95),
        "p99_ms": percentile(data, 0.99),
    }


def counterbalanced_indices(
    count: int,
    round_index: int,
    order_seed: int,
) -> list[int]:
    if count <= 0:
        raise TimingHarnessError(
            "count must be positive."
        )

    if round_index < 0:
        raise TimingHarnessError(
            "round_index must be non-negative."
        )

    base = list(range(count))

    random.Random(order_seed).shuffle(base)

    shift = round_index % count

    ordered = (
        base[shift:]
        + base[:shift]
    )

    cycle = round_index // count

    if cycle % 2 == 1:
        ordered = list(reversed(ordered))

    return ordered


def parse_integer_attribute(
    instance: Any,
    attribute_name: str,
    pattern: str,
) -> int:
    value = getattr(
        instance,
        attribute_name,
        None,
    )

    if value is not None:
        return int(value)

    match = re.search(
        pattern,
        str(instance.canonical_instance_id),
    )

    if match is None:
        raise TimingHarnessError(
            f"Cannot infer {attribute_name} from "
            f"{instance.canonical_instance_id!r}."
        )

    return int(match.group(1))


def build_cells(inputs: Any) -> list[TimingCell]:
    raw_steps = inputs.workload.get("steps")

    if not isinstance(raw_steps, list) or not raw_steps:
        raise TimingHarnessError(
            "The workload must contain at least one step."
        )

    cells: list[TimingCell] = []

    for instance in inputs.instances:
        level = parse_integer_attribute(
            instance,
            "factor_level",
            r"level_(\d+)",
        )

        replication = parse_integer_attribute(
            instance,
            "replication_index",
            r"rep_(\d+)",
        )

        seed = parse_integer_attribute(
            instance,
            "seed",
            r"seed_(\d+)",
        )

        for step_position, raw_step in enumerate(
            raw_steps
        ):
            cells.append(
                TimingCell(
                    canonical_instance_id=str(
                        instance.canonical_instance_id
                    ),
                    factor_level=level,
                    replication_index=replication,
                    seed=seed,
                    step_position=step_position,
                    step_index=int(
                        raw_step["step_index"]
                    ),
                    step_id=str(
                        raw_step["step_id"]
                    ),
                )
            )

    return sorted(cells)


def stable_session_id(
    inputs: Any,
    instance: Any,
) -> str:
    base = str(
        inputs.workload["session_id"]
    )

    safe_instance = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        str(instance.canonical_instance_id),
    )

    return (
        f"{base}__TIMING__{safe_instance}"
    )


def evaluate_cell_once(
    *,
    inputs: Any,
    instance: Any,
    cell: TimingCell,
    runtime_root: Path,
    measure: bool,
) -> dict[str, Any]:
    prefix = (
        f"cell_{cell.factor_level:06d}_"
        f"step_{cell.step_index:04d}_"
    )

    with tempfile.TemporaryDirectory(
        prefix=prefix,
        dir=runtime_root,
    ) as temporary:
        runtime_dir = (
            Path(temporary) / "ckg"
        )

        ckg = _build_instance_ckg(
            instance=instance,
            runtime_output_dir=runtime_dir,
        )

        session_id = stable_session_id(
            inputs,
            instance,
        )

        target_result: Any = None
        latency_ns: int | None = None
        cpu_latency_ns: int | None = None

        steps = inputs.workload["steps"]

        for step_position in range(
            cell.step_position + 1
        ):
            raw_step = steps[step_position]

            qp = {
                "objective_id": (
                    instance.objective_id
                ),
                "query_spec": dict(
                    raw_step["query_spec"]
                ),
            }

            is_target = (
                step_position
                == cell.step_position
            )

            if is_target and measure:
                cpu_started = process_time_ns()
                wall_started = perf_counter_ns()

                target_result = ckg.evaluate_step(
                    session_id=session_id,
                    objective_id=(
                        instance.objective_id
                    ),
                    step_idx=int(
                        raw_step["step_index"]
                    ),
                    qp=qp,
                )

                latency_ns = (
                    perf_counter_ns()
                    - wall_started
                )

                cpu_latency_ns = (
                    process_time_ns()
                    - cpu_started
                )

            else:
                result = ckg.evaluate_step(
                    session_id=session_id,
                    objective_id=(
                        instance.objective_id
                    ),
                    step_idx=int(
                        raw_step["step_index"]
                    ),
                    qp=qp,
                )

                if is_target:
                    target_result = result

        if target_result is None:
            raise TimingHarnessError(
                f"No result produced for {cell.cell_id}."
            )

        projection = functional_projection(
            target_result
        )

        return {
            "projection": projection,
            "semantic_digest": (
                sha256_payload(projection)
            ),
            "latency_ns": latency_ns,
            "cpu_latency_ns": cpu_latency_ns,
            "fresh_state": True,
            "prefix_step_count": (
                cell.step_position
            ),
        }


def capture_input_digests(
    execution_spec_path: Path,
    inputs: Any,
) -> dict[str, str]:
    paths: set[Path] = {
        execution_spec_path.resolve(),
    }

    execution_spec = inputs.execution_spec

    workload_path = Path(
        execution_spec["workload_path"]
    ).resolve()

    campaign_dir = Path(
        execution_spec["campaign_dir"]
    ).resolve()

    paths.update(
        {
            workload_path,
            campaign_dir / "campaign_spec.json",
            campaign_dir / "campaign_manifest.json",
            campaign_dir / "instances.csv",
        }
    )

    for instance in inputs.instances:
        objectives_path = Path(
            instance.objectives_path
        ).resolve()

        paths.add(objectives_path)
        paths.add(
            objectives_path.parent
            / "manifest.json"
        )

    missing = [
        path
        for path in paths
        if not path.is_file()
    ]

    if missing:
        raise TimingHarnessError(
            f"Missing immutable input files: {missing}"
        )

    return {
        str(path): sha256_file(path)
        for path in sorted(paths)
    }


def write_observations_csv(
    path: Path,
    observations: Sequence[
        Mapping[str, Any]
    ],
) -> None:
    fieldnames = [
        "phase",
        "phase_round",
        "order_position",
        "observation_index",
        "cell_id",
        "canonical_instance_id",
        "factor_level",
        "replication_index",
        "seed",
        "step_position",
        "step_index",
        "step_id",
        "prefix_step_count",
        "fresh_state",
        "wall_latency_ns",
        "wall_latency_ms",
        "cpu_latency_ns",
        "cpu_latency_ms",
        "semantic_digest",
        "semantic_match",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for observation in observations:
            writer.writerow(
                {
                    key: observation.get(key)
                    for key in fieldnames
                }
            )


def build_summary(
    *,
    cells: Sequence[TimingCell],
    observations: Sequence[
        Mapping[str, Any]
    ],
    measurements: int,
) -> dict[str, Any]:
    measured = [
        observation
        for observation in observations
        if observation["phase"] == "measurement"
    ]

    by_level: dict[
        int,
        list[float],
    ] = defaultdict(list)

    by_level_step: dict[
        tuple[int, str],
        list[float],
    ] = defaultdict(list)

    by_cell_positions: dict[
        str,
        list[int],
    ] = defaultdict(list)

    for observation in measured:
        latency = float(
            observation["wall_latency_ms"]
        )
        level = int(
            observation["factor_level"]
        )
        step_id = str(
            observation["step_id"]
        )

        by_level[level].append(latency)

        by_level_step[
            (level, step_id)
        ].append(latency)

        by_cell_positions[
            str(observation["cell_id"])
        ].append(
            int(observation["order_position"])
        )

    level_summaries = [
        {
            "factor_level": level,
            **descriptive_statistics(values),
        }
        for level, values in sorted(
            by_level.items()
        )
    ]

    level_step_summaries = [
        {
            "factor_level": level,
            "step_id": step_id,
            **descriptive_statistics(values),
        }
        for (
            level,
            step_id,
        ), values in sorted(
            by_level_step.items()
        )
    ]

    order_balance = []

    expected_positions = list(
        range(len(cells))
    )

    quotient, remainder = divmod(
        measurements,
        len(cells),
    )

    for cell in cells:
        positions = sorted(
            by_cell_positions[cell.cell_id]
        )

        counts = Counter(positions)

        position_counts = {
            str(position): counts.get(
                position,
                0,
            )
            for position in expected_positions
        }

        count_values = list(
            position_counts.values()
        )

        exact_full_balance = (
            remainder == 0
            and all(
                count == quotient
                for count in count_values
            )
        )

        near_balance = (
            max(count_values)
            - min(count_values)
            <= 1
        )

        order_balance.append(
            {
                "cell_id": cell.cell_id,
                "position_count": len(positions),
                "unique_position_count": len(
                    set(positions)
                ),
                "position_counts": position_counts,
                "expected_repetitions_per_position": (
                    quotient
                    if remainder == 0
                    else None
                ),
                "maximum_position_count_difference": (
                    max(count_values)
                    - min(count_values)
                ),
                "near_balance": near_balance,
                "exact_full_balance": (
                    exact_full_balance
                ),
            }
        )

    return {
        "measurement_observation_count": (
            len(measured)
        ),
        "level_summaries": level_summaries,
        "level_step_summaries": (
            level_step_summaries
        ),
        "order_balance": order_balance,
        "all_cells_exactly_balanced": all(
            item["exact_full_balance"]
            for item in order_balance
        ),
    }


def run_timing_harness(
    *,
    execution_spec_path: Path,
    output_dir: Path,
    warmups: int,
    measurements: int,
    order_seed: int,
    reuse_successful: bool,
) -> dict[str, Any]:
    if warmups < 0:
        raise TimingHarnessError(
            "warmups must be non-negative."
        )

    if measurements <= 0:
        raise TimingHarnessError(
            "measurements must be positive."
        )

    execution_spec_path = (
        execution_spec_path.resolve()
    )
    output_dir = output_dir.resolve()

    inputs = load_execution_inputs(
        execution_spec_path
    )

    input_digests_before = (
        capture_input_digests(
            execution_spec_path,
            inputs,
        )
    )

    source_identities = {
        "timing_harness": source_identity(
            Path(__file__)
        ),
        "canonical_executor": source_identity(
            canonical_executor
        ),
        "ckg_graph": source_identity(
            canonical_executor.CKGGraph
        ),
    }

    configuration = {
        "timing_harness_version": (
            TIMING_HARNESS_VERSION
        ),
        "source_identities": source_identities,
        "execution_spec_path": str(
            execution_spec_path
        ),
        "execution_spec_sha256": (
            input_digests_before[
                str(execution_spec_path)
            ]
        ),
        "warmups": warmups,
        "measurements": measurements,
        "order_seed": order_seed,
    }

    configuration_digest = (
        sha256_payload(configuration)
    )

    manifest_path = (
        output_dir / "timing_manifest.json"
    )

    if output_dir.exists() and any(
        output_dir.iterdir()
    ):
        if (
            reuse_successful
            and manifest_path.is_file()
        ):
            existing = read_json(
                manifest_path
            )

            if (
                existing.get("status") == "success"
                and existing.get(
                    "configuration_digest"
                )
                == configuration_digest
            ):
                validate_existing_bundle(
                    output_dir=output_dir,
                    manifest=existing,
                    current_input_digests=(
                        input_digests_before
                    ),
                )

                print(
                    "[INFO] Existing successful timing "
                    "bundle reused after integrity "
                    "validation."
                )
                return existing

        raise TimingHarnessError(
            "Timing output directory already exists "
            f"and is non-empty: {output_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    runtime_root = (
        output_dir / "_runtime"
    )

    runtime_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    cells = build_cells(inputs)

    instance_by_id = {
        str(instance.canonical_instance_id):
        instance
        for instance in inputs.instances
    }

    references: dict[str, dict[str, Any]] = {}

    print("=== FUNCTIONAL REFERENCES ===")

    for cell in cells:
        instance = instance_by_id[
            cell.canonical_instance_id
        ]

        result = evaluate_cell_once(
            inputs=inputs,
            instance=instance,
            cell=cell,
            runtime_root=runtime_root,
            measure=False,
        )

        references[cell.cell_id] = {
            "semantic_digest": (
                result["semantic_digest"]
            ),
            "projection": result["projection"],
        }

        print(
            f"reference cell={cell.cell_id} "
            f"digest={result['semantic_digest']}"
        )

    observations: list[
        dict[str, Any]
    ] = []

    observation_index = 0
    functional_mismatch_count = 0

    phases = (
        ("warmup", warmups),
        ("measurement", measurements),
    )

    for phase, round_count in phases:
        print()
        print(
            f"=== {phase.upper()} ROUNDS ==="
        )

        for phase_round in range(
            round_count
        ):
            order = counterbalanced_indices(
                len(cells),
                phase_round,
                order_seed,
            )

            for order_position, cell_index in enumerate(
                order
            ):
                cell = cells[cell_index]

                instance = instance_by_id[
                    cell.canonical_instance_id
                ]

                result = evaluate_cell_once(
                    inputs=inputs,
                    instance=instance,
                    cell=cell,
                    runtime_root=runtime_root,
                    measure=True,
                )

                semantic_match = (
                    result["semantic_digest"]
                    == references[
                        cell.cell_id
                    ]["semantic_digest"]
                )

                if not semantic_match:
                    functional_mismatch_count += 1

                observation_index += 1

                latency_ns = int(
                    result["latency_ns"]
                )

                cpu_latency_ns = int(
                    result["cpu_latency_ns"]
                )

                observations.append(
                    {
                        "phase": phase,
                        "phase_round": phase_round,
                        "order_position": (
                            order_position
                        ),
                        "observation_index": (
                            observation_index
                        ),
                        "cell_id": cell.cell_id,
                        "canonical_instance_id": (
                            cell.canonical_instance_id
                        ),
                        "factor_level": (
                            cell.factor_level
                        ),
                        "replication_index": (
                            cell.replication_index
                        ),
                        "seed": cell.seed,
                        "step_position": (
                            cell.step_position
                        ),
                        "step_index": (
                            cell.step_index
                        ),
                        "step_id": cell.step_id,
                        "prefix_step_count": (
                            result[
                                "prefix_step_count"
                            ]
                        ),
                        "fresh_state": True,
                        "wall_latency_ns": (
                            latency_ns
                        ),
                        "wall_latency_ms": (
                            latency_ns
                            / 1_000_000.0
                        ),
                        "cpu_latency_ns": (
                            cpu_latency_ns
                        ),
                        "cpu_latency_ms": (
                            cpu_latency_ns
                            / 1_000_000.0
                        ),
                        "semantic_digest": (
                            result[
                                "semantic_digest"
                            ]
                        ),
                        "semantic_match": (
                            semantic_match
                        ),
                    }
                )

            print(
                f"phase={phase} "
                f"round={phase_round + 1}/"
                f"{round_count} "
                f"observations={observation_index}"
            )

    if functional_mismatch_count != 0:
        raise TimingHarnessError(
            "Functional evaluator results changed "
            "across timing repetitions: "
            f"mismatches={functional_mismatch_count}"
        )

    input_digests_after = (
        capture_input_digests(
            execution_spec_path,
            inputs,
        )
    )

    if input_digests_before != input_digests_after:
        raise TimingHarnessError(
            "Immutable E2/E3 inputs changed during "
            "timing repetitions."
        )

    observations_path = (
        output_dir / "timing_observations.csv"
    )

    references_path = (
        output_dir / "functional_references.json"
    )

    summary_path = (
        output_dir / "timing_summary.json"
    )

    write_observations_csv(
        observations_path,
        observations,
    )

    write_json(
        references_path,
        {
            "schema_version": (
                "mcad-sensitivity-sa3-"
                "functional-references-v1"
            ),
            "references": references,
        },
    )

    summary = build_summary(
        cells=cells,
        observations=observations,
        measurements=measurements,
    )

    write_json(
        summary_path,
        {
            "schema_version": (
                "mcad-sensitivity-sa3-"
                "timing-summary-v1"
            ),
            **summary,
        },
    )

    shutil.rmtree(
        runtime_root,
        ignore_errors=True,
    )

    reference_count = len(cells)

    warmup_count = (
        len(cells) * warmups
    )

    measurement_count = (
        len(cells) * measurements
    )

    fresh_ckg_build_count = (
        reference_count
        + warmup_count
        + measurement_count
    )

    manifest = {
        "schema_version": (
            "mcad-sensitivity-sa3-"
            "timing-manifest-v1"
        ),
        "timing_harness_version": (
            TIMING_HARNESS_VERSION
        ),
        "status": "success",
        "configuration": configuration,
        "configuration_digest": (
            configuration_digest
        ),
        "source_identities": source_identities,
        "execution_id": (
            inputs.execution_spec[
                "execution_id"
            ]
        ),
        "campaign_id": (
            inputs.campaign_manifest[
                "campaign_id"
            ]
        ),
        "workload_id": (
            inputs.workload["workload_id"]
        ),
        "cell_count": len(cells),
        "instance_count": len(
            inputs.instances
        ),
        "step_count_per_instance": len(
            inputs.workload["steps"]
        ),
        "reference_count": reference_count,
        "warmup_observation_count": (
            warmup_count
        ),
        "measurement_observation_count": (
            measurement_count
        ),
        "fresh_ckg_build_count": (
            fresh_ckg_build_count
        ),
        "fresh_state_per_observation": True,
        "cross_repetition_state_reuse": False,
        "prefix_replay_preserves_session_state": True,
        "timed_scope": (
            "production CKGGraph.evaluate_step "
            "target call only"
        ),
        "clock": "time.perf_counter_ns",
        "functional_mismatch_count": (
            functional_mismatch_count
        ),
        "warmups_excluded_from_summary": True,
        "order_policy": (
            "deterministic shuffled base order "
            "with cyclic rotation by round"
        ),
        "all_cells_exactly_balanced": (
            summary[
                "all_cells_exactly_balanced"
            ]
        ),
        "input_digests": (
            input_digests_before
        ),
        "environment": {
            "python_version": (
                sys.version
            ),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "outputs": {
            "timing_observations_csv": (
                observations_path.name
            ),
            "functional_references_json": (
                references_path.name
            ),
            "timing_summary_json": (
                summary_path.name
            ),
            "timing_observations_sha256": (
                sha256_file(
                    observations_path
                )
            ),
            "functional_references_sha256": (
                sha256_file(
                    references_path
                )
            ),
            "timing_summary_sha256": (
                sha256_file(summary_path)
            ),
        },
        "scientific_freeze": False,
        "latency_claim_authorized": False,
    }

    write_json(
        manifest_path,
        manifest,
    )

    return manifest


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run reset-safe temporal repetitions "
            "through the production MCAD evaluator."
        )
    )

    parser.add_argument(
        "execution_spec_path",
        type=Path,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--warmups",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--measurements",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--order-seed",
        type=int,
        default=20260728,
    )

    parser.add_argument(
        "--reuse-successful",
        action="store_true",
    )

    args = parser.parse_args(argv)

    try:
        manifest = run_timing_harness(
            execution_spec_path=(
                args.execution_spec_path
            ),
            output_dir=args.output_dir,
            warmups=args.warmups,
            measurements=args.measurements,
            order_seed=args.order_seed,
            reuse_successful=(
                args.reuse_successful
            ),
        )

    except Exception as exc:
        print(
            f"[ERROR] Timing harness failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    print()
    print(
        "[OK] Reset-safe timing repetitions "
        "completed."
    )
    print(
        f"[OK] execution_id="
        f"{manifest['execution_id']}"
    )
    print(
        f"[OK] cell_count="
        f"{manifest['cell_count']}"
    )
    print(
        "[OK] warmup_observation_count="
        f"{manifest['warmup_observation_count']}"
    )
    print(
        "[OK] measurement_observation_count="
        f"{manifest['measurement_observation_count']}"
    )
    print(
        "[OK] fresh_ckg_build_count="
        f"{manifest['fresh_ckg_build_count']}"
    )
    print(
        "[OK] functional_mismatch_count="
        f"{manifest['functional_mismatch_count']}"
    )
    print(
        "[OK] all_cells_exactly_balanced="
        f"{str(manifest['all_cells_exactly_balanced']).lower()}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
