from __future__ import annotations

import pytest

from backend.harness.sensitivity_execution.analyze_clustered_timing_precision_v2 import (
    PrecisionAnalysisError,
    cluster_bootstrap_cell,
    linear_quantile,
    relative_half_width,
    stage_contract,
    validate_and_group,
)


def measurement_row(
    *,
    replication: int,
    seed: int,
    level: int,
    step: int,
    latency: float,
) -> dict[str, str]:
    return {
        "phase": "measurement",
        "fresh_state": "true",
        "semantic_match": "true",
        "formal_replication_index": str(
            replication
        ),
        "formal_structural_seed": str(seed),
        "factor_level": str(level),
        "step_index": str(step),
        "wall_latency_ms": str(latency),
    }


def test_relative_half_width() -> None:
    assert relative_half_width(
        point_estimate=10.0,
        lower=8.0,
        upper=12.0,
    ) == pytest.approx(0.2)


def test_linear_quantile() -> None:
    assert linear_quantile(
        [1.0, 2.0, 3.0, 4.0],
        0.50,
    ) == pytest.approx(2.5)


def test_stage_contracts() -> None:
    assert (
        stage_contract(10)["totals_key"]
        == "totals"
    )

    assert (
        stage_contract(20)["totals_key"]
        == "combined_totals"
    )

    assert (
        stage_contract(30)["extension_key"]
        == "post_stage30_review_required"
    )


def test_constant_twenty_cluster_bootstrap() -> None:
    clusters = [
        [0.5] * 100
        for _ in range(20)
    ]

    result = cluster_bootstrap_cell(
        clusters,
        expected_cluster_count=20,
        measurements_per_cluster=100,
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


def test_twenty_cluster_bootstrap_is_deterministic() -> None:
    clusters = [
        [
            0.1
            + cluster_index * 0.01
            + observation_index * 0.0001
            for observation_index in range(100)
        ]
        for cluster_index in range(20)
    ]

    first = cluster_bootstrap_cell(
        clusters,
        expected_cluster_count=20,
        measurements_per_cluster=100,
        repetitions=1000,
        bootstrap_seed=456,
        confidence_level=0.95,
    )

    second = cluster_bootstrap_cell(
        clusters,
        expected_cluster_count=20,
        measurements_per_cluster=100,
        repetitions=1000,
        bootstrap_seed=456,
        confidence_level=0.95,
    )

    assert first == second


def test_validate_twenty_clusters() -> None:
    rows = []

    for replication in range(20):
        for observation in range(3):
            rows.append(
                measurement_row(
                    replication=replication,
                    seed=1000 + replication,
                    level=2,
                    step=1,
                    latency=(
                        0.5
                        + replication * 0.01
                        + observation * 0.001
                    ),
                )
            )

    grouped, seed_map = validate_and_group(
        rows,
        expected_cluster_count=20,
        expected_levels=(2,),
        expected_steps=(1,),
        measurements_per_cluster=3,
    )

    assert len(seed_map) == 20
    assert len(grouped[(2, 1)]) == 20


def test_validate_rejects_missing_replication() -> None:
    rows = [
        measurement_row(
            replication=replication,
            seed=1000 + replication,
            level=2,
            step=1,
            latency=0.5,
        )
        for replication in range(19)
    ]

    with pytest.raises(
        PrecisionAnalysisError
    ):
        validate_and_group(
            rows,
            expected_cluster_count=20,
            expected_levels=(2,),
            expected_steps=(1,),
            measurements_per_cluster=1,
        )


def test_bootstrap_rejects_wrong_cluster_count() -> None:
    with pytest.raises(
        PrecisionAnalysisError
    ):
        cluster_bootstrap_cell(
            [[1.0] * 100 for _ in range(19)],
            expected_cluster_count=20,
            measurements_per_cluster=100,
            repetitions=1000,
            bootstrap_seed=1,
            confidence_level=0.95,
        )
