from __future__ import annotations

from collections import Counter

import pytest

from backend.harness.sensitivity_execution.run_timing_repetitions import (
    TimingHarnessError,
    canonicalize,
    counterbalanced_indices,
    functional_projection,
    percentile,
)


def test_counterbalanced_order_is_deterministic() -> None:
    first = counterbalanced_indices(
        10,
        3,
        20260728,
    )

    second = counterbalanced_indices(
        10,
        3,
        20260728,
    )

    assert first == second
    assert sorted(first) == list(range(10))


def test_every_cell_occupies_every_position_once() -> None:
    count = 10

    positions_by_cell = {
        cell: []
        for cell in range(count)
    }

    for round_index in range(count):
        order = counterbalanced_indices(
            count,
            round_index,
            20260728,
        )

        for position, cell in enumerate(order):
            positions_by_cell[cell].append(
                position
            )

    expected = list(range(count))

    for positions in positions_by_cell.values():
        assert sorted(positions) == expected


def test_invalid_counterbalance_arguments() -> None:
    with pytest.raises(TimingHarnessError):
        counterbalanced_indices(
            0,
            0,
            1,
        )

    with pytest.raises(TimingHarnessError):
        counterbalanced_indices(
            2,
            -1,
            1,
        )


def test_functional_projection_removes_volatile_fields() -> None:
    result = {
        "sat": True,
        "phi": 0.5,
        "session_id": "session-a",
        "qp_node_id": "qp-a",
        "evaluator_latency_ms": 12.3,
        "nested": {
            "error": "ignored",
            "real_node_ids": {"n2", "n1"},
        },
    }

    projected = functional_projection(result)

    assert projected["sat"] is True
    assert projected["phi"] == 0.5
    assert "session_id" not in projected
    assert "qp_node_id" not in projected
    assert "evaluator_latency_ms" not in projected
    assert "error" not in projected["nested"]
    assert projected["nested"]["real_node_ids"] == [
        "n1",
        "n2",
    ]


def test_canonicalize_is_deterministic() -> None:
    first = canonicalize(
        {
            "b": {3, 1, 2},
            "a": ["x", "y"],
        }
    )

    second = canonicalize(
        {
            "a": ["x", "y"],
            "b": {2, 3, 1},
        }
    )

    assert first == second


def test_percentile_linear_interpolation() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert percentile(values, 0.50) == 2.5
    assert percentile(values, 0.00) == 1.0
    assert percentile(values, 1.00) == 4.0


def test_percentile_rejects_empty_input() -> None:
    with pytest.raises(TimingHarnessError):
        percentile([], 0.50)


def test_every_cell_occupies_every_position_ten_times() -> None:
    count = 10
    rounds = 100

    positions_by_cell = {
        cell: []
        for cell in range(count)
    }

    for round_index in range(rounds):
        order = counterbalanced_indices(
            count,
            round_index,
            20260728,
        )

        for position, cell in enumerate(order):
            positions_by_cell[cell].append(
                position
            )

    expected = {
        position: 10
        for position in range(count)
    }

    for positions in positions_by_cell.values():
        assert dict(Counter(positions)) == expected
