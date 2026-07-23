from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from backend.harness.sensitivity_design.validate_design import (
    validate_design,
    validate_metrics,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    with (ROOT / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_current_design_is_valid() -> None:
    validate_design(load("design_matrix.yaml"))
    validate_metrics(load("metrics_contract.yaml"))


def test_primary_factor_cannot_also_be_fixed() -> None:
    design = load("design_matrix.yaml")
    broken = copy.deepcopy(design)

    axis = broken["axes"]["objective_count"]
    axis["fixed"][axis["primary_factor"]] = 5

    with pytest.raises(
        ValueError,
        match="primary factor must not be fixed",
    ):
        validate_design(broken)


def test_noise_weights_must_sum_to_one() -> None:
    design = load("design_matrix.yaml")
    broken = copy.deepcopy(design)

    broken["baseline"]["noise_distribution"][
        "missing_cube"
    ] = 0.50

    with pytest.raises(
        ValueError,
        match="must sum to 1",
    ):
        validate_design(broken)


def test_smoke_levels_must_belong_to_full_matrix() -> None:
    design = load("design_matrix.yaml")
    broken = copy.deepcopy(design)

    broken["smoke"]["axes"]["objective_count"][
        "levels"
    ] = [1, 999]

    with pytest.raises(
        ValueError,
        match="subset of full levels",
    ):
        validate_design(broken)


def test_missing_metrics_are_not_zero_filled() -> None:
    metrics = load("metrics_contract.yaml")

    assert (
        metrics["missing_value_policy"]["representation"]
        == ""
    )
    assert (
        metrics["runtime_metrics"]["warm_latency_ms"][
            "missing_when"
        ]
    )
