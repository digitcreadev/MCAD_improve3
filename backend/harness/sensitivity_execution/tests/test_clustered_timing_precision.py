from __future__ import annotations

import pytest

from backend.harness.sensitivity_execution.analyze_clustered_timing_precision import (
    PrecisionAnalysisError,
    cluster_bootstrap_cell,
    linear_quantile,
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


def test_linear_quantile() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert linear_quantile(
        values,
        0.50,
    ) == pytest.approx(2.5)

    assert linear_quantile(
        values,
        0.95,
    ) == pytest.approx(3.85)


def test_constant_clusters_have_zero_width() -> None:
    matrix = [
        [0.5] * 100
        for _ in range(10)
    ]

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


def test_cluster_bootstrap_point_estimates_match_pool() -> None:
    matrix = [
        [
            0.1
            + cluster_index * 0.01
            + observation_index * 0.0001
            for observation_index in range(100)
        ]
        for cluster_index in range(10)
    ]

    pooled = [
        value
        for cluster in matrix
        for value in cluster
    ]

    result = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=456,
        confidence_level=0.95,
    )

    assert result[
        "point_median_ms"
    ] == pytest.approx(
        linear_quantile(
            pooled,
            0.50,
        )
    )

    assert result[
        "point_p95_ms"
    ] == pytest.approx(
        linear_quantile(
            pooled,
            0.95,
        )
    )


def test_cluster_bootstrap_is_deterministic() -> None:
    matrix = [
        [
            0.1
            + cluster_index * 0.01
            + observation_index * 0.001
            for observation_index in range(100)
        ]
        for cluster_index in range(10)
    ]

    first = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=789,
        confidence_level=0.95,
    )

    second = cluster_bootstrap_cell(
        matrix,
        repetitions=1000,
        bootstrap_seed=789,
        confidence_level=0.95,
    )

    assert first == second


def test_cluster_bootstrap_rejects_wrong_cluster_count() -> None:
    matrix = [
        [1.0] * 100
        for _ in range(9)
    ]

    with pytest.raises(PrecisionAnalysisError):
        cluster_bootstrap_cell(
            matrix,
            repetitions=1000,
            bootstrap_seed=1,
            confidence_level=0.95,
        )


def test_cluster_bootstrap_rejects_wrong_cluster_size() -> None:
    matrix = [
        [1.0] * 100
        for _ in range(10)
    ]

    matrix[3] = [1.0] * 99

    with pytest.raises(PrecisionAnalysisError):
        cluster_bootstrap_cell(
            matrix,
            repetitions=1000,
            bootstrap_seed=1,
            confidence_level=0.95,
        )


def test_cluster_bootstrap_rejects_too_few_repetitions() -> None:
    matrix = [
        [1.0] * 100
        for _ in range(10)
    ]

    with pytest.raises(PrecisionAnalysisError):
        cluster_bootstrap_cell(
            matrix,
            repetitions=999,
            bootstrap_seed=1,
            confidence_level=0.95,
        )
