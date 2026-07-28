from __future__ import annotations

import numpy as np
import pytest

from backend.harness.sensitivity_execution.analyze_clustered_timing_precision import (
    PrecisionAnalysisError,
    cluster_bootstrap_cell,
    relative_half_width,
)


def test_relative_half_width() -> None:
    value = relative_half_width(
        point_estimate=10.0,
        lower=8.0,
        upper=12.0,
    )

    assert value == pytest.approx(0.2)


def test_relative_half_width_rejects_zero_point() -> None:
    with pytest.raises(PrecisionAnalysisError):
        relative_half_width(
            point_estimate=0.0,
            lower=0.0,
            upper=1.0,
        )


def test_constant_clusters_have_zero_width() -> None:
    matrix = np.full(
        (10, 100),
        0.5,
        dtype=np.float64,
    )

    result = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=123,
        confidence_level=0.95,
    )

    assert result["point_median_ms"] == 0.5
    assert result["point_p95_ms"] == 0.5

    assert (
        result["median_relative_half_width"]
        == pytest.approx(0.0)
    )

    assert (
        result["p95_relative_half_width"]
        == pytest.approx(0.0)
    )


def test_cluster_bootstrap_is_deterministic() -> None:
    matrix = np.vstack(
        [
            np.linspace(
                0.1 + index * 0.01,
                0.2 + index * 0.01,
                100,
            )
            for index in range(10)
        ]
    )

    first = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=456,
        confidence_level=0.95,
    )

    second = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=456,
        confidence_level=0.95,
    )

    assert first == second


def test_cluster_bootstrap_rejects_wrong_shape() -> None:
    matrix = np.ones(
        (9, 100),
        dtype=np.float64,
    )

    with pytest.raises(PrecisionAnalysisError):
        cluster_bootstrap_cell(
            matrix,
            repetitions=1000,
            bootstrap_seed=1,
            confidence_level=0.95,
        )


def test_cluster_bootstrap_rejects_too_few_repetitions() -> None:
    matrix = np.ones(
        (10, 100),
        dtype=np.float64,
    )

    with pytest.raises(PrecisionAnalysisError):
        cluster_bootstrap_cell(
            matrix,
            repetitions=999,
            bootstrap_seed=1,
            confidence_level=0.95,
        )
