#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "design_matrix.yaml"
METRICS_PATH = ROOT / "metrics_contract.yaml"
SPEC_PATH = ROOT / "SENSITIVITY_GENERATOR_DESIGN.md"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)

    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")

    return value


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_levels(
    axis_name: str,
    levels: list[Any],
) -> None:
    require(levels, f"{axis_name}: levels must not be empty")
    require(
        len(levels) == len(set(levels)),
        f"{axis_name}: levels must be unique",
    )

    numeric_levels = [
        float(value)
        for value in levels
    ]

    require(
        all(math.isfinite(value) for value in numeric_levels),
        f"{axis_name}: levels must be finite",
    )

    require(
        numeric_levels == sorted(numeric_levels),
        f"{axis_name}: levels must be sorted",
    )


def validate_noise_distribution(
    distribution: dict[str, Any],
) -> None:
    required_classes = {
        "wrong_measure",
        "wrong_context",
        "insufficient_grain",
        "invalid_aggregation",
        "invalid_unit",
        "invalid_time_window",
        "missing_cube",
        "redundant_contribution",
    }

    require(
        set(distribution) == required_classes,
        "baseline noise distribution must contain exactly "
        "the eight declared noise classes",
    )

    values = [
        float(value)
        for value in distribution.values()
    ]

    require(
        all(value >= 0.0 for value in values),
        "noise-distribution weights must be non-negative",
    )

    require(
        math.isclose(sum(values), 1.0, abs_tol=1e-9),
        "noise-distribution weights must sum to 1",
    )


def validate_design(design: dict[str, Any]) -> None:
    require(
        design.get("status") == "design_only",
        "design status must remain design_only during Phase E1",
    )

    baseline = design.get("baseline")
    axes = design.get("axes")
    smoke = design.get("smoke")

    require(
        isinstance(baseline, dict),
        "baseline must be a mapping",
    )
    require(
        isinstance(axes, dict),
        "axes must be a mapping",
    )
    require(
        isinstance(smoke, dict),
        "smoke must be a mapping",
    )

    expected_axes = {
        "objective_count",
        "constraint_count",
        "virtual_node_count",
        "contribution_density",
        "workload_noise",
    }

    require(
        set(axes) == expected_axes,
        "the design must contain exactly the five approved axes",
    )

    validate_noise_distribution(
        baseline.get("noise_distribution") or {}
    )

    primary_factors: set[str] = set()

    for axis_name, axis in axes.items():
        require(
            isinstance(axis, dict),
            f"{axis_name}: definition must be a mapping",
        )

        primary = axis.get("primary_factor")
        levels = axis.get("levels")
        fixed = axis.get("fixed")

        require(
            isinstance(primary, str) and primary,
            f"{axis_name}: primary_factor is required",
        )
        require(
            primary not in primary_factors,
            f"{axis_name}: primary factor {primary!r} is duplicated",
        )
        primary_factors.add(primary)

        require(
            isinstance(levels, list),
            f"{axis_name}: levels must be a list",
        )
        validate_levels(axis_name, levels)

        require(
            isinstance(fixed, dict) and fixed,
            f"{axis_name}: fixed controls are required",
        )

        require(
            primary not in fixed,
            f"{axis_name}: primary factor must not be fixed",
        )

        if axis_name in {
            "contribution_density",
            "workload_noise",
        }:
            tolerance = axis.get("tolerance")

            require(
                isinstance(tolerance, (int, float)),
                f"{axis_name}: tolerance is required",
            )
            require(
                0.0 < float(tolerance) < 0.1,
                f"{axis_name}: invalid tolerance",
            )

        if axis_name == "contribution_density":
            require(
                all(0.0 < float(level) <= 1.0 for level in levels),
                "contribution-density levels must be in ]0,1]",
            )

        if axis_name == "workload_noise":
            require(
                all(0.0 <= float(level) < 1.0 for level in levels),
                "noise-ratio levels must be in [0,1[",
            )

    smoke_axes = smoke.get("axes")

    require(
        isinstance(smoke_axes, dict),
        "smoke.axes must be a mapping",
    )
    require(
        set(smoke_axes) == expected_axes,
        "smoke must cover every approved axis",
    )

    for axis_name, smoke_axis in smoke_axes.items():
        smoke_levels = smoke_axis.get("levels")
        full_levels = axes[axis_name]["levels"]

        require(
            isinstance(smoke_levels, list) and smoke_levels,
            f"{axis_name}: smoke levels are required",
        )
        require(
            set(smoke_levels).issubset(set(full_levels)),
            f"{axis_name}: smoke levels must be a subset "
            "of full levels",
        )
        require(
            len(smoke_levels) >= 2,
            f"{axis_name}: smoke must test at least two levels",
        )

    required_manifest_fields = design.get(
        "required_manifest_fields"
    )

    require(
        isinstance(required_manifest_fields, list),
        "required_manifest_fields must be a list",
    )
    require(
        len(required_manifest_fields)
        == len(set(required_manifest_fields)),
        "manifest fields must be unique",
    )

    required_core_fields = {
        "instance_id",
        "axis",
        "requested_factor_value",
        "realised_factor_value",
        "seed",
        "configuration_digest",
        "instance_digest",
        "realised_density",
        "realised_noise_ratio",
    }

    require(
        required_core_fields.issubset(
            set(required_manifest_fields)
        ),
        "required core manifest fields are missing",
    )


def validate_metrics(metrics: dict[str, Any]) -> None:
    require(
        metrics.get("missing_value_policy", {}).get(
            "representation"
        ) == "",
        "missing-value representation must be the empty string",
    )

    decision_metrics = metrics.get("decision_metrics")
    goal_metrics = metrics.get("goal_progress_metrics")
    runtime_metrics = metrics.get("runtime_metrics")

    require(
        isinstance(decision_metrics, dict),
        "decision_metrics must be defined",
    )
    require(
        isinstance(goal_metrics, dict),
        "goal_progress_metrics must be defined",
    )
    require(
        isinstance(runtime_metrics, dict),
        "runtime_metrics must be defined",
    )

    expected_decision_metrics = {
        "precision",
        "recall",
        "specificity",
        "f1",
        "balanced_accuracy",
        "matthews_correlation_coefficient",
        "false_allow_rate",
        "false_block_rate",
    }

    require(
        set(decision_metrics) == expected_decision_metrics,
        "decision metric registry is incomplete",
    )

    require(
        goal_metrics["time_to_0_8"].get(
            "requires_companion_metric"
        ) == "reach_rate_0_8",
        "time_to_0_8 must require reach_rate_0_8",
    )

    require(
        goal_metrics["time_to_0_9"].get(
            "requires_companion_metric"
        ) == "reach_rate_0_9",
        "time_to_0_9 must require reach_rate_0_9",
    )

    require(
        runtime_metrics["warm_latency_ms"].get(
            "missing_when"
        ),
        "warm latency must define its missing-value condition",
    )


def main() -> int:
    for path in (DESIGN_PATH, METRICS_PATH, SPEC_PATH):
        if not path.is_file():
            print(
                f"[ERROR] Required design file missing: {path}",
                file=sys.stderr,
            )
            return 1

    try:
        design = load_yaml(DESIGN_PATH)
        metrics = load_yaml(METRICS_PATH)

        validate_design(design)
        validate_metrics(metrics)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("[OK] Phase E1 design specification is valid.")
    print(
        f"[OK] design_digest={canonical_digest(design)}"
    )
    print(
        f"[OK] metrics_digest={canonical_digest(metrics)}"
    )
    print(f"[OK] axes={len(design['axes'])}")
    print(
        "[OK] axis_names="
        + ",".join(sorted(design["axes"]))
    )
    print(
        "[OK] status=design_only; no experimental "
        "result is authorised yet."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
