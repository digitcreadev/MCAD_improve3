from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np


ANALYZER_VERSION = (
    "mcad-sensitivity-sa3-clustered-precision-v1"
)

EXPECTED_LEVELS = (2, 4, 8, 12, 16)
EXPECTED_STEPS = (1, 2)


class PrecisionAnalysisError(RuntimeError):
    """Raised when clustered timing evidence is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PrecisionAnalysisError(
            f"Missing JSON file: {path}"
        )

    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(value, dict):
        raise PrecisionAnalysisError(
            f"JSON root must be an object: {path}"
        )

    return value


def write_json(
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def truth_value(value: Any) -> bool:
    return (
        str(value).strip().lower()
        in {"true", "1", "yes"}
    )


def linear_quantile(
    values: np.ndarray,
    probability: float,
    *,
    axis: int | tuple[int, ...] | None = None,
) -> np.ndarray | np.floating[Any]:
    try:
        return np.quantile(
            values,
            probability,
            axis=axis,
            method="linear",
        )
    except TypeError:
        return np.quantile(
            values,
            probability,
            axis=axis,
            interpolation="linear",
        )


def percentile_interval(
    values: np.ndarray,
    confidence_level: float,
) -> tuple[float, float]:
    alpha = 1.0 - confidence_level

    lower = float(
        linear_quantile(
            values,
            alpha / 2.0,
        )
    )

    upper = float(
        linear_quantile(
            values,
            1.0 - alpha / 2.0,
        )
    )

    return lower, upper


def relative_half_width(
    *,
    point_estimate: float,
    lower: float,
    upper: float,
) -> float:
    if not math.isfinite(point_estimate):
        raise PrecisionAnalysisError(
            "Point estimate is not finite."
        )

    if point_estimate <= 0.0:
        raise PrecisionAnalysisError(
            "Relative precision requires a positive "
            "point estimate."
        )

    if lower > upper:
        raise PrecisionAnalysisError(
            "Confidence-interval bounds are reversed."
        )

    return (
        upper - lower
    ) / (2.0 * point_estimate)


def read_measurements(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise PrecisionAnalysisError(
            f"Missing observations CSV: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise PrecisionAnalysisError(
            "Observations CSV is empty."
        )

    return rows


def validate_and_group(
    rows: Sequence[dict[str, str]],
) -> tuple[
    dict[
        tuple[int, int],
        dict[int, np.ndarray],
    ],
    dict[int, int],
]:
    grouped_lists: dict[
        tuple[int, int],
        dict[int, list[float]],
    ] = defaultdict(
        lambda: defaultdict(list)
    )

    seed_by_replication: dict[int, int] = {}

    for row_index, row in enumerate(
        rows,
        start=2,
    ):
        if row.get("phase") != "measurement":
            raise PrecisionAnalysisError(
                "Combined formal timing CSV must contain "
                "measurement rows only; "
                f"row={row_index}."
            )

        if not truth_value(
            row.get("fresh_state")
        ):
            raise PrecisionAnalysisError(
                "Observation lacks fresh-state evidence; "
                f"row={row_index}."
            )

        if not truth_value(
            row.get("semantic_match")
        ):
            raise PrecisionAnalysisError(
                "Observation contains a functional "
                f"mismatch; row={row_index}."
            )

        try:
            replication = int(
                row["formal_replication_index"]
            )
            seed = int(
                row["formal_structural_seed"]
            )
            level = int(
                row["factor_level"]
            )
            step = int(
                row["step_index"]
            )
            latency = float(
                row["wall_latency_ms"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PrecisionAnalysisError(
                "Invalid formal timing observation at "
                f"row {row_index}: {exc}"
            ) from exc

        if not math.isfinite(latency) or latency <= 0:
            raise PrecisionAnalysisError(
                "Latency must be positive and finite; "
                f"row={row_index}, value={latency}."
            )

        previous_seed = seed_by_replication.get(
            replication
        )

        if (
            previous_seed is not None
            and previous_seed != seed
        ):
            raise PrecisionAnalysisError(
                "A replication is associated with "
                "multiple structural seeds: "
                f"replication={replication}."
            )

        seed_by_replication[
            replication
        ] = seed

        grouped_lists[
            (level, step)
        ][replication].append(latency)

    expected_replications = set(range(10))

    if (
        set(seed_by_replication)
        != expected_replications
    ):
        raise PrecisionAnalysisError(
            "Expected formal replications 0 through 9; "
            f"actual={sorted(seed_by_replication)}."
        )

    if len(set(seed_by_replication.values())) != 10:
        raise PrecisionAnalysisError(
            "Structural seeds are not unique."
        )

    expected_cells = {
        (level, step)
        for level in EXPECTED_LEVELS
        for step in EXPECTED_STEPS
    }

    if set(grouped_lists) != expected_cells:
        raise PrecisionAnalysisError(
            "Unexpected level-step cell set: "
            f"{sorted(grouped_lists)}."
        )

    grouped_arrays: dict[
        tuple[int, int],
        dict[int, np.ndarray],
    ] = {}

    for cell, replication_groups in (
        grouped_lists.items()
    ):
        if (
            set(replication_groups)
            != expected_replications
        ):
            raise PrecisionAnalysisError(
                "Cell does not contain all ten "
                f"replications: cell={cell}."
            )

        grouped_arrays[cell] = {}

        for replication, values in (
            replication_groups.items()
        ):
            if len(values) != 100:
                raise PrecisionAnalysisError(
                    "Every seed-level-step cluster must "
                    "contain 100 measurements: "
                    f"cell={cell}, "
                    f"replication={replication}, "
                    f"count={len(values)}."
                )

            grouped_arrays[cell][
                replication
            ] = np.asarray(
                values,
                dtype=np.float64,
            )

    return grouped_arrays, seed_by_replication


def cluster_bootstrap_cell(
    cluster_matrix: np.ndarray,
    *,
    repetitions: int,
    bootstrap_seed: int,
    confidence_level: float,
    chunk_size: int = 500,
) -> dict[str, Any]:
    if (
        cluster_matrix.ndim != 2
        or cluster_matrix.shape != (10, 100)
    ):
        raise PrecisionAnalysisError(
            "Expected a 10 × 100 cluster matrix; "
            f"actual={cluster_matrix.shape}."
        )

    if repetitions < 1000:
        raise PrecisionAnalysisError(
            "At least 1,000 bootstrap repetitions "
            "are required."
        )

    if not (
        0.0 < confidence_level < 1.0
    ):
        raise PrecisionAnalysisError(
            "Confidence level must lie between 0 and 1."
        )

    pooled = cluster_matrix.reshape(-1)

    point_median = float(
        np.median(pooled)
    )

    point_p95 = float(
        linear_quantile(
            pooled,
            0.95,
        )
    )

    rng = np.random.default_rng(
        bootstrap_seed
    )

    bootstrap_medians = np.empty(
        repetitions,
        dtype=np.float64,
    )

    bootstrap_p95 = np.empty(
        repetitions,
        dtype=np.float64,
    )

    cluster_count = cluster_matrix.shape[0]

    for start in range(
        0,
        repetitions,
        chunk_size,
    ):
        stop = min(
            start + chunk_size,
            repetitions,
        )

        current_size = stop - start

        sampled_cluster_indices = (
            rng.integers(
                0,
                cluster_count,
                size=(
                    current_size,
                    cluster_count,
                ),
            )
        )

        sampled = cluster_matrix[
            sampled_cluster_indices
        ].reshape(
            current_size,
            -1,
        )

        bootstrap_medians[
            start:stop
        ] = np.median(
            sampled,
            axis=1,
        )

        bootstrap_p95[
            start:stop
        ] = linear_quantile(
            sampled,
            0.95,
            axis=1,
        )

    (
        median_ci_lower,
        median_ci_upper,
    ) = percentile_interval(
        bootstrap_medians,
        confidence_level,
    )

    (
        p95_ci_lower,
        p95_ci_upper,
    ) = percentile_interval(
        bootstrap_p95,
        confidence_level,
    )

    median_relative_half_width = (
        relative_half_width(
            point_estimate=point_median,
            lower=median_ci_lower,
            upper=median_ci_upper,
        )
    )

    p95_relative_half_width = (
        relative_half_width(
            point_estimate=point_p95,
            lower=p95_ci_lower,
            upper=p95_ci_upper,
        )
    )

    leave_one_out_medians = []
    leave_one_out_p95 = []

    for excluded_cluster in range(
        cluster_count
    ):
        retained = np.delete(
            cluster_matrix,
            excluded_cluster,
            axis=0,
        ).reshape(-1)

        leave_one_out_medians.append(
            float(np.median(retained))
        )

        leave_one_out_p95.append(
            float(
                linear_quantile(
                    retained,
                    0.95,
                )
            )
        )

    maximum_loo_median_relative_change = max(
        abs(value - point_median)
        / point_median
        for value in leave_one_out_medians
    )

    maximum_loo_p95_relative_change = max(
        abs(value - point_p95)
        / point_p95
        for value in leave_one_out_p95
    )

    return {
        "point_median_ms": point_median,
        "median_ci_lower_ms": (
            median_ci_lower
        ),
        "median_ci_upper_ms": (
            median_ci_upper
        ),
        "median_relative_half_width": (
            median_relative_half_width
        ),
        "point_p95_ms": point_p95,
        "p95_ci_lower_ms": p95_ci_lower,
        "p95_ci_upper_ms": p95_ci_upper,
        "p95_relative_half_width": (
            p95_relative_half_width
        ),
        "maximum_leave_one_seed_out_"
        "median_relative_change": (
            maximum_loo_median_relative_change
        ),
        "maximum_leave_one_seed_out_"
        "p95_relative_change": (
            maximum_loo_p95_relative_change
        ),
    }


def analyze_precision(
    rows: Sequence[dict[str, str]],
    *,
    bootstrap_repetitions: int,
    bootstrap_seed: int,
    confidence_level: float,
    median_target: float,
    p95_target: float,
) -> dict[str, Any]:
    grouped, seed_by_replication = (
        validate_and_group(rows)
    )

    cell_results = []

    for level, step in sorted(grouped):
        cluster_matrix = np.vstack(
            [
                grouped[
                    (level, step)
                ][replication]
                for replication in range(10)
            ]
        )

        cell_seed = (
            bootstrap_seed
            + level * 10_000
            + step * 100
        )

        statistics_record = (
            cluster_bootstrap_cell(
                cluster_matrix,
                repetitions=(
                    bootstrap_repetitions
                ),
                bootstrap_seed=cell_seed,
                confidence_level=(
                    confidence_level
                ),
            )
        )

        median_target_met = (
            statistics_record[
                "median_relative_half_width"
            ]
            <= median_target
        )

        p95_target_met = (
            statistics_record[
                "p95_relative_half_width"
            ]
            <= p95_target
        )

        cell_results.append(
            {
                "factor": "constraint_count",
                "factor_level": level,
                "step_index": step,
                "structural_seed_count": 10,
                "measurements_per_seed": 100,
                "observation_count": 1000,
                "bootstrap_repetitions": (
                    bootstrap_repetitions
                ),
                "bootstrap_seed": cell_seed,
                "confidence_level": (
                    confidence_level
                ),
                **statistics_record,
                "median_precision_target": (
                    median_target
                ),
                "p95_precision_target": (
                    p95_target
                ),
                "median_target_met": (
                    median_target_met
                ),
                "p95_target_met": (
                    p95_target_met
                ),
                "all_cell_targets_met": (
                    median_target_met
                    and p95_target_met
                ),
            }
        )

    all_median_targets_met = all(
        row["median_target_met"]
        for row in cell_results
    )

    all_p95_targets_met = all(
        row["p95_target_met"]
        for row in cell_results
    )

    all_precision_targets_met = (
        all_median_targets_met
        and all_p95_targets_met
    )

    failing_cells = [
        {
            "factor_level": row[
                "factor_level"
            ],
            "step_index": row["step_index"],
            "median_target_met": row[
                "median_target_met"
            ],
            "p95_target_met": row[
                "p95_target_met"
            ],
            "median_relative_half_width": (
                row[
                    "median_relative_half_width"
                ]
            ),
            "p95_relative_half_width": (
                row[
                    "p95_relative_half_width"
                ]
            ),
        }
        for row in cell_results
        if not row["all_cell_targets_met"]
    ]

    return {
        "seed_by_replication": {
            str(replication): seed
            for replication, seed in sorted(
                seed_by_replication.items()
            )
        },
        "cell_results": cell_results,
        "all_median_targets_met": (
            all_median_targets_met
        ),
        "all_p95_targets_met": (
            all_p95_targets_met
        ),
        "all_precision_targets_met": (
            all_precision_targets_met
        ),
        "failing_cell_count": len(
            failing_cells
        ),
        "failing_cells": failing_cells,
        "stage10_sufficient": (
            all_precision_targets_met
        ),
        "extension_to_stage20_required": (
            not all_precision_targets_met
        ),
    }


def write_intervals_csv(
    path: Path,
    rows: Sequence[dict[str, Any]],
) -> None:
    if not rows:
        raise PrecisionAnalysisError(
            "No interval rows to write."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(rows[0])

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
        writer.writerows(rows)


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate formal timing precision using "
            "a structural-seed cluster bootstrap."
        )
    )

    parser.add_argument(
        "--observations",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--timing-report",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--intervals-csv",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report-json",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report-md",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--bootstrap-repetitions",
        type=int,
        default=10_000,
    )

    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20260728,
    )

    parser.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
    )

    parser.add_argument(
        "--median-target",
        type=float,
        default=0.10,
    )

    parser.add_argument(
        "--p95-target",
        type=float,
        default=0.15,
    )

    args = parser.parse_args(argv)

    try:
        timing_report = load_json(
            args.timing_report
        )

        if (
            timing_report.get("status")
            != "stage10_formal_timing_execution_success"
        ):
            raise PrecisionAnalysisError(
                "Formal timing report does not have "
                "success status."
            )

        totals = timing_report.get("totals")

        if not isinstance(totals, dict):
            raise PrecisionAnalysisError(
                "Formal timing report lacks totals."
            )

        expected_totals = {
            "run_count": 10,
            "cell_count": 100,
            "measurement_observation_count": 10000,
            "functional_mismatch_count": 0,
            "exactly_balanced_run_count": 10,
        }

        for field, expected in (
            expected_totals.items()
        ):
            actual = totals.get(field)

            if actual != expected:
                raise PrecisionAnalysisError(
                    "Formal timing total mismatch for "
                    f"{field}: expected={expected}, "
                    f"actual={actual}."
                )

        rows = read_measurements(
            args.observations
        )

        if len(rows) != 10_000:
            raise PrecisionAnalysisError(
                "Expected exactly 10,000 formal "
                f"measurements; actual={len(rows)}."
            )

        analysis = analyze_precision(
            rows,
            bootstrap_repetitions=(
                args.bootstrap_repetitions
            ),
            bootstrap_seed=(
                args.bootstrap_seed
            ),
            confidence_level=(
                args.confidence_level
            ),
            median_target=args.median_target,
            p95_target=args.p95_target,
        )

        next_stage = (
            "SA4_membership_density_design"
            if analysis[
                "stage10_sufficient"
            ]
            else "SA3_stage_20_generation"
        )

        status = (
            "stage10_precision_targets_met"
            if analysis[
                "stage10_sufficient"
            ]
            else "stage10_precision_targets_not_met"
        )

        report = {
            "schema_version": (
                "mcad-sensitivity-sa3-stage10-"
                "precision-analysis-v1"
            ),
            "analyzer_version": (
                ANALYZER_VERSION
            ),
            "stage": (
                "SA3_stage_10_precision_analysis"
            ),
            "status": status,
            "scientific_freeze": False,
            "latency_claim_authorized": False,
            "bootstrap_contract": {
                "unit_of_resampling": (
                    "structural seed cluster"
                ),
                "within_cluster_measurements": (
                    "retained together"
                ),
                "bootstrap_repetitions": (
                    args.bootstrap_repetitions
                ),
                "bootstrap_seed": (
                    args.bootstrap_seed
                ),
                "confidence_level": (
                    args.confidence_level
                ),
                "interval_method": (
                    "percentile cluster bootstrap"
                ),
                "median_relative_half_width_target": (
                    args.median_target
                ),
                "p95_relative_half_width_target": (
                    args.p95_target
                ),
                "gate_rule": (
                    "Every level-step cell must meet "
                    "both precision targets."
                ),
            },
            "inputs": {
                "observations_path": str(
                    args.observations.resolve()
                ),
                "observations_sha256": (
                    sha256_file(
                        args.observations
                    )
                ),
                "timing_report_path": str(
                    args.timing_report.resolve()
                ),
                "timing_report_sha256": (
                    sha256_file(
                        args.timing_report
                    )
                ),
                "observation_count": len(rows),
            },
            **analysis,
            "next_stage": next_stage,
        }

        write_intervals_csv(
            args.intervals_csv,
            analysis["cell_results"],
        )

        report["outputs"] = {
            "intervals_csv": str(
                args.intervals_csv.resolve()
            ),
            "intervals_csv_sha256": (
                sha256_file(
                    args.intervals_csv
                )
            ),
        }

        write_json(
            args.report_json,
            report,
        )

        markdown_lines = [
            "# SA3 stage-10 precision analysis",
            "",
            "## Bootstrap contract",
            "",
            "- Resampling unit: structural seed",
            "- Seed clusters: `10`",
            "- Measurements per seed and cell: `100`",
            (
                "- Bootstrap repetitions: "
                f"`{args.bootstrap_repetitions}`"
            ),
            (
                "- Confidence level: "
                f"`{args.confidence_level:.0%}`"
            ),
            (
                "- Median precision target: "
                f"`{args.median_target:.0%}`"
            ),
            (
                "- p95 precision target: "
                f"`{args.p95_target:.0%}`"
            ),
            "",
            "## Cell results",
            "",
            (
                "| Level | Step | Median | "
                "Median RHW | p95 | p95 RHW | Pass |"
            ),
            "|---:|---:|---:|---:|---:|---:|---|",
        ]

        for row in analysis["cell_results"]:
            markdown_lines.append(
                f"| {row['factor_level']} "
                f"| {row['step_index']} "
                f"| {row['point_median_ms']:.6f} "
                f"| "
                f"{row['median_relative_half_width']:.2%} "
                f"| {row['point_p95_ms']:.6f} "
                f"| "
                f"{row['p95_relative_half_width']:.2%} "
                f"| {row['all_cell_targets_met']} |"
            )

        markdown_lines.extend(
            [
                "",
                "## Gate result",
                "",
                (
                    "- All median targets met: "
                    f"`{analysis['all_median_targets_met']}`"
                ),
                (
                    "- All p95 targets met: "
                    f"`{analysis['all_p95_targets_met']}`"
                ),
                (
                    "- Stage 10 sufficient: "
                    f"`{analysis['stage10_sufficient']}`"
                ),
                (
                    "- Extension to stage 20 required: "
                    f"`{analysis['extension_to_stage20_required']}`"
                ),
                (
                    f"- Next stage: `{next_stage}`"
                ),
                "",
                (
                    "Scientific freeze and final latency "
                    "claims remain disabled until the "
                    "complete sensitivity programme is "
                    "audited and frozen."
                ),
            ]
        )

        args.report_md.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.report_md.write_text(
            "\n".join(markdown_lines) + "\n",
            encoding="utf-8",
        )

        print(f"status={status}")

        for row in analysis["cell_results"]:
            print(
                f"level={row['factor_level']} "
                f"step={row['step_index']} "
                f"median_ms="
                f"{row['point_median_ms']:.6f} "
                f"median_rhw="
                f"{row['median_relative_half_width']:.6f} "
                f"median_pass="
                f"{str(row['median_target_met']).lower()} "
                f"p95_ms={row['point_p95_ms']:.6f} "
                f"p95_rhw="
                f"{row['p95_relative_half_width']:.6f} "
                f"p95_pass="
                f"{str(row['p95_target_met']).lower()}"
            )

        print(
            "all_median_targets_met="
            f"{str(analysis['all_median_targets_met']).lower()}"
        )
        print(
            "all_p95_targets_met="
            f"{str(analysis['all_p95_targets_met']).lower()}"
        )
        print(
            "all_precision_targets_met="
            f"{str(analysis['all_precision_targets_met']).lower()}"
        )
        print(
            "failing_cell_count="
            f"{analysis['failing_cell_count']}"
        )
        print(
            "stage10_sufficient="
            f"{str(analysis['stage10_sufficient']).lower()}"
        )
        print(
            "extension_to_stage20_required="
            f"{str(analysis['extension_to_stage20_required']).lower()}"
        )
        print(f"next_stage={next_stage}")
        print(
            f"report_json={args.report_json}"
        )
        print(
            f"intervals_csv={args.intervals_csv}"
        )

    except Exception as exc:
        print(
            "[ERROR] Clustered precision analysis "
            f"failed: {type(exc).__name__}: {exc}"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
