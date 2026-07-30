from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence


ANALYZER_VERSION = (
    "mcad-sensitivity-sa3-clustered-precision-v2"
)

DEFAULT_LEVELS = (2, 4, 8, 12, 16)
DEFAULT_STEPS = (1, 2)


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


def parse_integer_sequence(
    value: str,
    *,
    field: str,
) -> tuple[int, ...]:
    try:
        parsed = tuple(
            int(item.strip())
            for item in value.split(",")
            if item.strip()
        )
    except ValueError as exc:
        raise PrecisionAnalysisError(
            f"Invalid integer sequence for {field}: "
            f"{value!r}"
        ) from exc

    if not parsed:
        raise PrecisionAnalysisError(
            f"{field} cannot be empty."
        )

    if len(set(parsed)) != len(parsed):
        raise PrecisionAnalysisError(
            f"{field} contains duplicate values."
        )

    return parsed


def linear_quantile(
    values: Sequence[float],
    probability: float,
) -> float:
    if not values:
        raise PrecisionAnalysisError(
            "Cannot calculate a quantile from "
            "an empty sequence."
        )

    if not 0.0 <= probability <= 1.0:
        raise PrecisionAnalysisError(
            "Quantile probability must lie "
            "between 0 and 1."
        )

    ordered = sorted(
        float(value)
        for value in values
    )

    if len(ordered) == 1:
        return ordered[0]

    position = probability * (
        len(ordered) - 1
    )

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return ordered[lower_index]

    fraction = position - lower_index

    return (
        ordered[lower_index]
        + fraction
        * (
            ordered[upper_index]
            - ordered[lower_index]
        )
    )


def percentile_interval(
    values: Sequence[float],
    confidence_level: float,
) -> tuple[float, float]:
    alpha = 1.0 - confidence_level

    return (
        linear_quantile(
            values,
            alpha / 2.0,
        ),
        linear_quantile(
            values,
            1.0 - alpha / 2.0,
        ),
    )


def relative_half_width(
    *,
    point_estimate: float,
    lower: float,
    upper: float,
) -> float:
    if (
        not math.isfinite(point_estimate)
        or point_estimate <= 0.0
    ):
        raise PrecisionAnalysisError(
            "Relative precision requires a positive "
            "finite point estimate."
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

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)


def validate_and_group(
    rows: Sequence[dict[str, str]],
    *,
    expected_cluster_count: int,
    expected_levels: Sequence[int],
    expected_steps: Sequence[int],
    measurements_per_cluster: int,
) -> tuple[
    dict[
        tuple[int, int],
        dict[int, tuple[float, ...]],
    ],
    dict[int, int],
]:
    if expected_cluster_count <= 1:
        raise PrecisionAnalysisError(
            "At least two structural-seed clusters "
            "are required."
        )

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
                "The combined timing CSV must contain "
                "measurement rows only; "
                f"row={row_index}."
            )

        if not truth_value(
            row.get("fresh_state")
        ):
            raise PrecisionAnalysisError(
                "Observation lacks fresh-state "
                f"evidence; row={row_index}."
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
                "Invalid timing observation at "
                f"row {row_index}: {exc}"
            ) from exc

        if (
            not math.isfinite(latency)
            or latency <= 0.0
        ):
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

    expected_replications = set(
        range(expected_cluster_count)
    )

    if (
        set(seed_by_replication)
        != expected_replications
    ):
        raise PrecisionAnalysisError(
            "Unexpected replication set: "
            f"expected="
            f"{sorted(expected_replications)}, "
            f"actual="
            f"{sorted(seed_by_replication)}."
        )

    if (
        len(set(seed_by_replication.values()))
        != expected_cluster_count
    ):
        raise PrecisionAnalysisError(
            "Structural seeds are not unique."
        )

    expected_cells = {
        (level, step)
        for level in expected_levels
        for step in expected_steps
    }

    if set(grouped_lists) != expected_cells:
        raise PrecisionAnalysisError(
            "Unexpected level-step cell set: "
            f"{sorted(grouped_lists)}."
        )

    grouped: dict[
        tuple[int, int],
        dict[int, tuple[float, ...]],
    ] = {}

    for cell, replication_groups in (
        grouped_lists.items()
    ):
        if (
            set(replication_groups)
            != expected_replications
        ):
            raise PrecisionAnalysisError(
                "A level-step cell does not contain "
                "every structural replication: "
                f"cell={cell}."
            )

        grouped[cell] = {}

        for replication, values in (
            replication_groups.items()
        ):
            if (
                len(values)
                != measurements_per_cluster
            ):
                raise PrecisionAnalysisError(
                    "Every structural-seed cluster must "
                    f"contain {measurements_per_cluster} "
                    "measurements: "
                    f"cell={cell}, "
                    f"replication={replication}, "
                    f"count={len(values)}."
                )

            grouped[cell][replication] = tuple(
                sorted(values)
            )

    return grouped, seed_by_replication


def weighted_kth(
    *,
    sorted_clusters: Sequence[
        Sequence[float]
    ],
    multiplicities: Sequence[int],
    support: Sequence[float],
    rank: int,
) -> float:
    total_count = sum(
        multiplicity * len(cluster)
        for cluster, multiplicity
        in zip(
            sorted_clusters,
            multiplicities,
            strict=True,
        )
    )

    if rank < 0 or rank >= total_count:
        raise PrecisionAnalysisError(
            "Weighted rank lies outside the "
            "bootstrap sample."
        )

    lower = 0
    upper = len(support) - 1

    while lower < upper:
        middle = (
            lower + upper
        ) // 2

        candidate = support[middle]

        cumulative_count = sum(
            multiplicity
            * bisect_right(
                cluster,
                candidate,
            )
            for cluster, multiplicity
            in zip(
                sorted_clusters,
                multiplicities,
                strict=True,
            )
        )

        if cumulative_count > rank:
            upper = middle
        else:
            lower = middle + 1

    return float(support[lower])


def weighted_linear_quantile(
    *,
    sorted_clusters: Sequence[
        Sequence[float]
    ],
    multiplicities: Sequence[int],
    support: Sequence[float],
    probability: float,
) -> float:
    sample_size = sum(
        multiplicity * len(cluster)
        for cluster, multiplicity
        in zip(
            sorted_clusters,
            multiplicities,
            strict=True,
        )
    )

    if sample_size <= 0:
        raise PrecisionAnalysisError(
            "Weighted bootstrap sample is empty."
        )

    position = probability * (
        sample_size - 1
    )

    lower_rank = math.floor(position)
    upper_rank = math.ceil(position)

    lower_value = weighted_kth(
        sorted_clusters=sorted_clusters,
        multiplicities=multiplicities,
        support=support,
        rank=lower_rank,
    )

    if lower_rank == upper_rank:
        return lower_value

    upper_value = weighted_kth(
        sorted_clusters=sorted_clusters,
        multiplicities=multiplicities,
        support=support,
        rank=upper_rank,
    )

    fraction = position - lower_rank

    return (
        lower_value
        + fraction
        * (upper_value - lower_value)
    )


def cluster_bootstrap_cell(
    cluster_matrix: Sequence[
        Sequence[float]
    ],
    *,
    expected_cluster_count: int,
    measurements_per_cluster: int,
    repetitions: int,
    bootstrap_seed: int,
    confidence_level: float,
) -> dict[str, Any]:
    if (
        len(cluster_matrix)
        != expected_cluster_count
    ):
        raise PrecisionAnalysisError(
            "Unexpected structural-seed cluster count: "
            f"expected={expected_cluster_count}, "
            f"actual={len(cluster_matrix)}."
        )

    sorted_clusters = [
        tuple(
            sorted(
                float(value)
                for value in cluster
            )
        )
        for cluster in cluster_matrix
    ]

    if any(
        len(cluster)
        != measurements_per_cluster
        for cluster in sorted_clusters
    ):
        raise PrecisionAnalysisError(
            "A structural-seed cluster has an "
            "unexpected measurement count."
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
            "Confidence level must lie between "
            "0 and 1."
        )

    pooled = [
        value
        for cluster in sorted_clusters
        for value in cluster
    ]

    support = sorted(set(pooled))

    point_median = linear_quantile(
        pooled,
        0.50,
    )

    point_p95 = linear_quantile(
        pooled,
        0.95,
    )

    rng = random.Random(
        bootstrap_seed
    )

    bootstrap_medians: list[float] = []
    bootstrap_p95: list[float] = []

    cluster_count = len(
        sorted_clusters
    )

    for _ in range(repetitions):
        multiplicities = [
            0
            for _ in range(cluster_count)
        ]

        for _ in range(cluster_count):
            selected_cluster = rng.randrange(
                cluster_count
            )

            multiplicities[
                selected_cluster
            ] += 1

        bootstrap_medians.append(
            weighted_linear_quantile(
                sorted_clusters=(
                    sorted_clusters
                ),
                multiplicities=(
                    multiplicities
                ),
                support=support,
                probability=0.50,
            )
        )

        bootstrap_p95.append(
            weighted_linear_quantile(
                sorted_clusters=(
                    sorted_clusters
                ),
                multiplicities=(
                    multiplicities
                ),
                support=support,
                probability=0.95,
            )
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

    median_rhw = relative_half_width(
        point_estimate=point_median,
        lower=median_ci_lower,
        upper=median_ci_upper,
    )

    p95_rhw = relative_half_width(
        point_estimate=point_p95,
        lower=p95_ci_lower,
        upper=p95_ci_upper,
    )

    leave_one_out_medians = []
    leave_one_out_p95 = []

    for excluded_cluster in range(
        cluster_count
    ):
        retained = [
            value
            for cluster_index, cluster
            in enumerate(sorted_clusters)
            if cluster_index
            != excluded_cluster
            for value in cluster
        ]

        leave_one_out_medians.append(
            linear_quantile(
                retained,
                0.50,
            )
        )

        leave_one_out_p95.append(
            linear_quantile(
                retained,
                0.95,
            )
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
            median_rhw
        ),
        "point_p95_ms": point_p95,
        "p95_ci_lower_ms": p95_ci_lower,
        "p95_ci_upper_ms": p95_ci_upper,
        "p95_relative_half_width": (
            p95_rhw
        ),
        "maximum_leave_one_seed_out_"
        "median_relative_change": max(
            abs(value - point_median)
            / point_median
            for value
            in leave_one_out_medians
        ),
        "maximum_leave_one_seed_out_"
        "p95_relative_change": max(
            abs(value - point_p95)
            / point_p95
            for value
            in leave_one_out_p95
        ),
    }


def analyze_precision(
    rows: Sequence[dict[str, str]],
    *,
    expected_cluster_count: int,
    expected_levels: Sequence[int],
    expected_steps: Sequence[int],
    measurements_per_cluster: int,
    bootstrap_repetitions: int,
    bootstrap_seed: int,
    confidence_level: float,
    median_target: float,
    p95_target: float,
) -> dict[str, Any]:
    grouped, seed_by_replication = (
        validate_and_group(
            rows,
            expected_cluster_count=(
                expected_cluster_count
            ),
            expected_levels=expected_levels,
            expected_steps=expected_steps,
            measurements_per_cluster=(
                measurements_per_cluster
            ),
        )
    )

    cell_results = []

    for level, step in sorted(grouped):
        cluster_groups = [
            grouped[
                (level, step)
            ][replication]
            for replication in range(
                expected_cluster_count
            )
        ]

        cell_seed = (
            bootstrap_seed
            + level * 10_000
            + step * 100
        )

        statistics_record = (
            cluster_bootstrap_cell(
                cluster_groups,
                expected_cluster_count=(
                    expected_cluster_count
                ),
                measurements_per_cluster=(
                    measurements_per_cluster
                ),
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
                "structural_seed_count": (
                    expected_cluster_count
                ),
                "measurements_per_seed": (
                    measurements_per_cluster
                ),
                "observation_count": (
                    expected_cluster_count
                    * measurements_per_cluster
                ),
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
            "factor_level": (
                row["factor_level"]
            ),
            "step_index": (
                row["step_index"]
            ),
            "median_target_met": (
                row["median_target_met"]
            ),
            "p95_target_met": (
                row["p95_target_met"]
            ),
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
        "stage_sufficient": (
            all_precision_targets_met
        ),
        "extension_required": (
            not all_precision_targets_met
        ),
    }


def stage_contract(
    stage_size: int,
) -> dict[str, Any]:
    contracts = {
        10: {
            "timing_status": (
                "stage10_formal_timing_execution_success"
            ),
            "totals_key": "totals",
            "analysis_stage": (
                "SA3_stage_10_precision_analysis"
            ),
            "success_status": (
                "stage10_precision_targets_met"
            ),
            "failure_status": (
                "stage10_precision_targets_not_met"
            ),
            "sufficient_key": (
                "stage10_sufficient"
            ),
            "extension_key": (
                "extension_to_stage20_required"
            ),
            "success_next_stage": (
                "SA4_membership_density_design"
            ),
            "extension_next_stage": (
                "SA3_stage_20_generation"
            ),
        },
        20: {
            "timing_status": (
                "stage20_formal_timing_execution_success"
            ),
            "totals_key": "combined_totals",
            "analysis_stage": (
                "SA3_stage_20_precision_analysis"
            ),
            "success_status": (
                "stage20_precision_targets_met"
            ),
            "failure_status": (
                "stage20_precision_targets_not_met"
            ),
            "sufficient_key": (
                "stage20_sufficient"
            ),
            "extension_key": (
                "extension_to_stage30_required"
            ),
            "success_next_stage": (
                "SA4_membership_density_design"
            ),
            "extension_next_stage": (
                "SA3_stage_30_generation"
            ),
        },
        30: {
            "timing_status": (
                "stage30_formal_timing_execution_success"
            ),
            "totals_key": "combined_totals",
            "analysis_stage": (
                "SA3_stage_30_precision_analysis"
            ),
            "success_status": (
                "stage30_precision_targets_met"
            ),
            "failure_status": (
                "stage30_precision_targets_not_met"
            ),
            "sufficient_key": (
                "stage30_sufficient"
            ),
            "extension_key": (
                "post_stage30_review_required"
            ),
            "success_next_stage": (
                "SA4_membership_density_design"
            ),
            "extension_next_stage": (
                "SA3_stage_30_precision_limit_review"
            ),
        },
    }

    try:
        return contracts[stage_size]
    except KeyError as exc:
        raise PrecisionAnalysisError(
            "Supported stage sizes are 10, 20 and 30."
        ) from exc


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate timing precision using a "
            "structural-seed cluster bootstrap."
        )
    )

    parser.add_argument(
        "--stage-size",
        type=int,
        choices=(10, 20, 30),
        required=True,
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
        "--levels",
        default="2,4,8,12,16",
    )

    parser.add_argument(
        "--steps",
        default="1,2",
    )

    parser.add_argument(
        "--measurements-per-cluster",
        type=int,
        default=100,
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
        levels = parse_integer_sequence(
            args.levels,
            field="levels",
        )

        steps = parse_integer_sequence(
            args.steps,
            field="steps",
        )

        contract = stage_contract(
            args.stage_size
        )

        timing_report = load_json(
            args.timing_report
        )

        if (
            timing_report.get("status")
            != contract["timing_status"]
        ):
            raise PrecisionAnalysisError(
                "Timing report status does not match "
                f"stage {args.stage_size}: "
                f"expected={contract['timing_status']!r}, "
                f"actual={timing_report.get('status')!r}."
            )

        totals = timing_report.get(
            contract["totals_key"]
        )

        if not isinstance(totals, dict):
            raise PrecisionAnalysisError(
                "Timing report lacks the expected "
                f"totals section: "
                f"{contract['totals_key']}."
            )

        expected_cell_count = (
            args.stage_size
            * len(levels)
            * len(steps)
        )

        expected_measurement_count = (
            expected_cell_count
            * args.measurements_per_cluster
        )

        expected_totals = {
            "run_count": args.stage_size,
            "successful_run_count": (
                args.stage_size
            ),
            "cell_count": (
                expected_cell_count
            ),
            "measurement_observation_count": (
                expected_measurement_count
            ),
            "functional_mismatch_count": 0,
            "exactly_balanced_run_count": (
                args.stage_size
            ),
        }

        for field, expected in (
            expected_totals.items()
        ):
            actual = totals.get(field)

            if actual != expected:
                raise PrecisionAnalysisError(
                    "Timing total mismatch for "
                    f"{field}: expected={expected}, "
                    f"actual={actual}."
                )

        reported_seed_count = totals.get(
            "structural_seed_count"
        )

        if (
            reported_seed_count is not None
            and reported_seed_count
            != args.stage_size
        ):
            raise PrecisionAnalysisError(
                "Timing report structural-seed count "
                f"differs from stage size: "
                f"expected={args.stage_size}, "
                f"actual={reported_seed_count}."
            )

        rows = read_measurements(
            args.observations
        )

        if len(rows) != expected_measurement_count:
            raise PrecisionAnalysisError(
                "Unexpected formal measurement count: "
                f"expected={expected_measurement_count}, "
                f"actual={len(rows)}."
            )

        analysis = analyze_precision(
            rows,
            expected_cluster_count=(
                args.stage_size
            ),
            expected_levels=levels,
            expected_steps=steps,
            measurements_per_cluster=(
                args.measurements_per_cluster
            ),
            bootstrap_repetitions=(
                args.bootstrap_repetitions
            ),
            bootstrap_seed=(
                args.bootstrap_seed
            ),
            confidence_level=(
                args.confidence_level
            ),
            median_target=(
                args.median_target
            ),
            p95_target=(
                args.p95_target
            ),
        )

        stage_sufficient = bool(
            analysis["stage_sufficient"]
        )

        extension_required = bool(
            analysis["extension_required"]
        )

        status = (
            contract["success_status"]
            if stage_sufficient
            else contract["failure_status"]
        )

        next_stage = (
            contract["success_next_stage"]
            if stage_sufficient
            else contract[
                "extension_next_stage"
            ]
        )

        report = {
            "schema_version": (
                "mcad-sensitivity-sa3-"
                f"stage{args.stage_size}-"
                "precision-analysis-v2"
            ),
            "analyzer_version": (
                ANALYZER_VERSION
            ),
            "analyzer_source": {
                "path": str(
                    Path(__file__).resolve()
                ),
                "sha256": sha256_file(
                    Path(__file__)
                ),
            },
            "stage": (
                contract["analysis_stage"]
            ),
            "status": status,
            "stage_size": args.stage_size,
            "structural_seed_count": (
                args.stage_size
            ),
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
            "seed_by_replication": (
                analysis[
                    "seed_by_replication"
                ]
            ),
            "cell_results": (
                analysis["cell_results"]
            ),
            "all_median_targets_met": (
                analysis[
                    "all_median_targets_met"
                ]
            ),
            "all_p95_targets_met": (
                analysis[
                    "all_p95_targets_met"
                ]
            ),
            "all_precision_targets_met": (
                analysis[
                    "all_precision_targets_met"
                ]
            ),
            "failing_cell_count": (
                analysis[
                    "failing_cell_count"
                ]
            ),
            "failing_cells": (
                analysis["failing_cells"]
            ),
            contract["sufficient_key"]: (
                stage_sufficient
            ),
            contract["extension_key"]: (
                extension_required
            ),
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
            (
                "# SA3 stage-"
                f"{args.stage_size} precision analysis"
            ),
            "",
            "## Bootstrap contract",
            "",
            (
                "- Structural seed clusters: "
                f"`{args.stage_size}`"
            ),
            (
                "- Measurements per seed and cell: "
                f"`{args.measurements_per_cluster}`"
            ),
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
                    "- Stage sufficient: "
                    f"`{stage_sufficient}`"
                ),
                (
                    "- Extension required: "
                    f"`{extension_required}`"
                ),
                f"- Next stage: `{next_stage}`",
                "",
                (
                    "Scientific freeze and final latency "
                    "claims remain disabled."
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
            f"{contract['sufficient_key']}="
            f"{str(stage_sufficient).lower()}"
        )

        print(
            f"{contract['extension_key']}="
            f"{str(extension_required).lower()}"
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
