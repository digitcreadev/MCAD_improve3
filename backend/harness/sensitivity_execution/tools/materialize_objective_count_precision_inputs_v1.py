#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_SOURCE_HEADER = [
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

OUTPUT_HEADER = [
    "factor_level",
    "formal_replication_index",
    "formal_structural_seed",
    "step_index",
    "wall_latency_ms",
]

EXPECTED_LEVELS = (1, 2, 5, 10, 20, 50)
EXPECTED_REPLICATIONS = tuple(range(10))

EXPECTED_ROWS_PER_REPLICATION = 21_120
EXPECTED_WARMUPS_PER_REPLICATION = 1_920
EXPECTED_MEASUREMENTS_PER_REPLICATION = 19_200

EXPECTED_STEP_COUNT = 32
MEASUREMENTS_PER_SEED_CELL = 100

EXPECTED_MEASUREMENT_ROWS = 192_000


class MaterializationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the preregistered SA5 objective-count "
            "Stage-10 precision input without statistical analysis."
        )
    )

    parser.add_argument("--timing-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preregistration-sha256", required=True)
    parser.add_argument("--source-commit", required=True)

    args = parser.parse_args()

    if not args.preregistration.is_file():
        raise MaterializationError(
            "Missing preregistration artifact."
        )

    if sha256(args.preregistration) != args.preregistration_sha256:
        raise MaterializationError(
            "Preregistration SHA-256 mismatch."
        )

    prereg = json.loads(
        args.preregistration.read_text(encoding="utf-8")
    )

    if prereg.get("status") != "preregistered_before_precision_analysis":
        raise MaterializationError(
            "Precision protocol is not preregistered."
        )

    if prereg.get("factor") != "objective_count":
        raise MaterializationError(
            "Unexpected preregistered factor."
        )

    if int(prereg.get("stage", -1)) != 10:
        raise MaterializationError(
            "Unexpected preregistered stage."
        )

    if args.output_dir.exists():
        raise MaterializationError(
            f"Output directory already exists: {args.output_dir}"
        )

    args.output_dir.mkdir(parents=True)

    observations_path = (
        args.output_dir
        / "objective_count_stage10_measurement_observations.csv"
    )

    timing_report_path = (
        args.output_dir
        / "objective_count_stage10_precision_timing_report.json"
    )

    materialization_path = (
        args.output_dir
        / "MATERIALIZATION.json"
    )

    source_files: list[dict[str, Any]] = []

    seed_by_replication: dict[int, int] = {}

    phase_counts: Counter[str] = Counter()
    measurement_counts: Counter[tuple[int, int, int]] = Counter()

    steps_by_replication_level: dict[
        tuple[int, int], set[int]
    ] = defaultdict(set)

    global_steps: set[int] = set()

    output_row_count = 0

    with observations_path.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as output_handle:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=OUTPUT_HEADER,
            lineterminator="\n",
        )

        writer.writeheader()

        for replication in EXPECTED_REPLICATIONS:
            rep = f"{replication:03d}"

            source_dir = (
                args.timing_root
                / (
                    f"objective_count_rep_{rep}_"
                    "portfolio_timing_stage10"
                )
            )

            source_path = (
                source_dir
                / "timing_observations.csv"
            )

            if not source_path.is_file():
                raise MaterializationError(
                    f"Missing source Timing CSV: {source_path}"
                )

            source_sha = sha256(source_path)

            source_files.append(
                {
                    "replication_index": replication,
                    "path": str(source_path),
                    "sha256": source_sha,
                }
            )

            total_rows = 0
            warmup_rows = 0
            measurement_rows = 0
            replication_seed: int | None = None

            with source_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as source_handle:
                reader = csv.DictReader(source_handle)

                if reader.fieldnames != EXPECTED_SOURCE_HEADER:
                    raise MaterializationError(
                        "Unexpected Timing CSV header: "
                        f"replication={replication}"
                    )

                for row in reader:
                    total_rows += 1

                    phase = row["phase"]

                    if phase not in {"warmup", "measurement"}:
                        raise MaterializationError(
                            f"Unexpected phase: {phase}"
                        )

                    phase_counts[phase] += 1

                    source_replication = int(
                        row["replication_index"]
                    )

                    if source_replication != replication:
                        raise MaterializationError(
                            "Replication contamination."
                        )

                    seed = int(row["seed"])
                    level = int(row["factor_level"])
                    step = int(row["step_index"])

                    if level not in EXPECTED_LEVELS:
                        raise MaterializationError(
                            f"Unexpected factor level: {level}"
                        )

                    if replication_seed is None:
                        replication_seed = seed
                    elif replication_seed != seed:
                        raise MaterializationError(
                            "Multiple seeds in one replication."
                        )

                    semantic_match = (
                        row["semantic_match"]
                        .strip()
                        .lower()
                    )

                    if semantic_match not in {"true", "1"}:
                        raise MaterializationError(
                            "Functional semantic mismatch "
                            "encountered in Timing evidence."
                        )

                    if phase == "warmup":
                        warmup_rows += 1
                        continue

                    measurement_rows += 1

                    latency_scalar = row["wall_latency_ms"]

                    # Deliberately do NOT parse, convert, compare,
                    # sort, aggregate, summarize, or otherwise
                    # interpret the latency scalar.
                    if (
                        latency_scalar == ""
                        or latency_scalar != latency_scalar.strip()
                    ):
                        raise MaterializationError(
                            "Missing or whitespace-altered "
                            "wall_latency_ms scalar."
                        )

                    writer.writerow(
                        {
                            "factor_level": row["factor_level"],
                            "formal_replication_index": (
                                row["replication_index"]
                            ),
                            "formal_structural_seed": row["seed"],
                            "step_index": row["step_index"],
                            "wall_latency_ms": latency_scalar,
                        }
                    )

                    output_row_count += 1

                    global_steps.add(step)

                    steps_by_replication_level[
                        (replication, level)
                    ].add(step)

                    measurement_counts[
                        (replication, level, step)
                    ] += 1

            if total_rows != EXPECTED_ROWS_PER_REPLICATION:
                raise MaterializationError(
                    "Unexpected source row count: "
                    f"replication={replication}, "
                    f"count={total_rows}"
                )

            if warmup_rows != EXPECTED_WARMUPS_PER_REPLICATION:
                raise MaterializationError(
                    "Unexpected warmup row count: "
                    f"replication={replication}, "
                    f"count={warmup_rows}"
                )

            if (
                measurement_rows
                != EXPECTED_MEASUREMENTS_PER_REPLICATION
            ):
                raise MaterializationError(
                    "Unexpected measurement row count: "
                    f"replication={replication}, "
                    f"count={measurement_rows}"
                )

            if replication_seed is None:
                raise MaterializationError(
                    "Replication exposes no structural seed."
                )

            seed_by_replication[replication] = replication_seed

    if output_row_count != EXPECTED_MEASUREMENT_ROWS:
        raise MaterializationError(
            "Unexpected total materialized observation count."
        )

    if len(seed_by_replication) != 10:
        raise MaterializationError(
            "Unexpected replication count."
        )

    if len(set(seed_by_replication.values())) != 10:
        raise MaterializationError(
            "Structural seeds are not unique."
        )

    if len(global_steps) != EXPECTED_STEP_COUNT:
        raise MaterializationError(
            "Unexpected canonical step count: "
            f"{len(global_steps)}"
        )

    frozen_steps = tuple(sorted(global_steps))

    for replication in EXPECTED_REPLICATIONS:
        for level in EXPECTED_LEVELS:
            actual_steps = steps_by_replication_level[
                (replication, level)
            ]

            if actual_steps != global_steps:
                raise MaterializationError(
                    "Canonical step set differs by "
                    "replication/factor level."
                )

            for step in frozen_steps:
                count = measurement_counts[
                    (replication, level, step)
                ]

                if count != MEASUREMENTS_PER_SEED_CELL:
                    raise MaterializationError(
                        "Unexpected measurement count in "
                        "replication/level/step cell: "
                        f"replication={replication}, "
                        f"level={level}, "
                        f"step={step}, "
                        f"count={count}"
                    )

    observations_sha = sha256(observations_path)

    timing_report = {
        "schema_version": (
            "mcad-sa5-objective-count-stage10-"
            "precision-input-timing-report-v1"
        ),
        "status": "precision_input_materialization_ready",
        "factor": "objective_count",
        "stage": 10,
        "source_commit": args.source_commit,
        "factor_levels": list(EXPECTED_LEVELS),
        "step_indices": list(frozen_steps),
        "totals": {
            "structural_seed_count": 10,
            "canonical_factor_level_count": 6,
            "canonical_step_count": 32,
            "canonical_cell_count": 192,
            "measurements_per_seed_and_cell": 100,
            "measurement_observation_count": (
                EXPECTED_MEASUREMENT_ROWS
            ),
        },
        "seed_by_replication": {
            str(replication): seed
            for replication, seed
            in sorted(seed_by_replication.items())
        },
        "observations": {
            "path": str(observations_path),
            "sha256": observations_sha,
            "columns": OUTPUT_HEADER,
        },
        "scientific_controls": {
            "source_latency_scalar_strings_copied": True,
            "latency_scalars_parsed": False,
            "latency_values_transformed": False,
            "latency_values_sorted": False,
            "latency_values_aggregated": False,
            "timing_values_interpreted": False,
            "precision_analysis_performed": False,
            "bootstrap_analysis_performed": False,
            "scientific_result_interpretation_performed": False,
            "scientific_freeze_performed": False,
            "manuscript_modified": False,
        },
    }

    write_json(
        timing_report_path,
        timing_report,
    )

    timing_report_sha = sha256(timing_report_path)

    materialization = {
        "schema_version": (
            "mcad-sa5-objective-count-stage10-"
            "precision-input-materialization-v1"
        ),
        "status": "materialization_complete_without_analysis",
        "created_at_utc": utc_now(),
        "source_commit": args.source_commit,
        "preregistration": {
            "path": str(args.preregistration),
            "sha256": args.preregistration_sha256,
        },
        "source_timing_files": source_files,
        "mapping": {
            "phase_filter": {
                "included": "measurement",
                "excluded": "warmup",
            },
            "factor_level": "factor_level",
            "replication_index": (
                "formal_replication_index"
            ),
            "seed": "formal_structural_seed",
            "step_index": "step_index",
            "wall_latency_ms": "wall_latency_ms",
        },
        "determinism": {
            "source_replication_order_preserved": True,
            "source_row_order_preserved": True,
            "latency_scalar_string_preserved": True,
            "pre_analysis_aggregation": False,
        },
        "structural_validation": {
            "replication_count": 10,
            "factor_levels": list(EXPECTED_LEVELS),
            "step_indices": list(frozen_steps),
            "step_count": len(frozen_steps),
            "measurement_rows": output_row_count,
            "measurements_per_seed_and_cell": (
                MEASUREMENTS_PER_SEED_CELL
            ),
            "all_replication_level_step_cells_complete": True,
            "unique_structural_seed_count": 10,
        },
        "outputs": {
            "observations_csv": {
                "path": str(observations_path),
                "sha256": observations_sha,
            },
            "timing_report_json": {
                "path": str(timing_report_path),
                "sha256": timing_report_sha,
            },
        },
        "scientific_controls": {
            "timing_scalar_strings_accessed_for_copy": True,
            "timing_values_accessed_for_analysis": False,
            "timing_values_interpreted": False,
            "precision_statistics_computed": False,
            "precision_analysis_performed": False,
            "bootstrap_analysis_performed": False,
            "scientific_result_interpretation_performed": False,
            "scientific_freeze_performed": False,
            "manuscript_modified": False,
        },
        "next_stage": (
            "merge_precision_inputs_before_"
            "precision_analysis_authorization"
        ),
    }

    write_json(
        materialization_path,
        materialization,
    )

    print("precision_input_adapter=PASS")
    print("canonical_replication_count=10")
    print("factor_level_count=6")
    print(f"canonical_step_count={len(frozen_steps)}")
    print(f"measurement_observation_count={output_row_count}")
    print("measurements_per_seed_and_cell=100")
    print(f"observations_sha256={observations_sha}")
    print(
        "timing_report_sha256="
        f"{timing_report_sha}"
    )
    print("latency_scalar_strings_copied=true")
    print("latency_scalars_parsed=false")
    print("timing_values_interpreted=false")
    print("precision_analysis_performed=false")
    print("bootstrap_analysis_performed=false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
