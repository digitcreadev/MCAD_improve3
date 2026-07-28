from __future__ import annotations

from pathlib import Path

import pytest

from backend.harness.sensitivity_generator.oracles.membership_density_oracle import (
    DensityOracleError,
    analyze_objectives_document,
    assert_valid_density,
    expected_membership_count,
    non_membership_semantic_digest,
    validate_density_family,
)


LEVEL_ALLOCATIONS = {
    25: (2, 2, 1, 1),
    50: (3, 3, 3, 3),
    75: (5, 5, 4, 4),
    100: (6, 6, 6, 6),
}


def make_document(
    allocations: tuple[int, ...],
) -> dict:
    constraints = []

    for constraint_index, membership_count in enumerate(
        allocations,
        start=1,
    ):
        virtual_nodes = [
            {
                "id": (
                    f"C{constraint_index}_NV"
                    f"{node_index}"
                ),
                "fact": "SyntheticFact",
                "grain": ["Time.Month"],
                "measure": "Sales",
                "aggregator": "SUM",
                "unit": "USD",
            }
            for node_index in range(1, 7)
        ]

        constraints.append(
            {
                "id": f"C{constraint_index}",
                "kpi_id": f"KPI{constraint_index}",
                "weight": 1.0,
                "virtual_nodes": virtual_nodes,
                "requirement_sets": [
                    [
                        node["id"]
                        for node
                        in virtual_nodes[
                            :membership_count
                        ]
                    ]
                ],
            }
        )

    return {
        "objectives": [
            {
                "id": "O_TEST",
                "name": "O_TEST",
                "constraints": constraints,
            }
        ]
    }


def test_formula_uses_local_capacity_not_global_product() -> None:
    observation = analyze_objectives_document(
        make_document(
            LEVEL_ALLOCATIONS[100]
        )
    )

    assert observation.constraint_count == 4
    assert observation.virtual_node_count == 24
    assert observation.requirement_set_count == 4
    assert observation.maximum_membership_count == 24
    assert observation.maximum_membership_count != 96
    assert observation.membership_count == 24
    assert observation.membership_density == 1.0


@pytest.mark.parametrize(
    ("density_percent", "expected_count"),
    (
        (25, 6),
        (50, 12),
        (75, 18),
        (100, 24),
    ),
)
def test_exact_membership_counts(
    density_percent: int,
    expected_count: int,
) -> None:
    assert expected_membership_count(
        24,
        density_percent,
    ) == expected_count

    observation = assert_valid_density(
        make_document(
            LEVEL_ALLOCATIONS[
                density_percent
            ]
        ),
        density_percent=density_percent,
    )

    assert (
        observation.membership_count
        == expected_count
    )


def test_non_exact_density_is_rejected() -> None:
    with pytest.raises(DensityOracleError):
        expected_membership_count(
            10,
            25,
        )


def test_unknown_reference_is_rejected() -> None:
    document = make_document(
        LEVEL_ALLOCATIONS[100]
    )

    document["objectives"][0][
        "constraints"
    ][0]["requirement_sets"][0][0] = "UNKNOWN"

    with pytest.raises(DensityOracleError):
        assert_valid_density(
            document,
            density_percent=100,
        )


def test_duplicate_membership_is_rejected() -> None:
    document = make_document(
        LEVEL_ALLOCATIONS[100]
    )

    requirement_set = document[
        "objectives"
    ][0]["constraints"][0]["requirement_sets"][0]

    requirement_set[1] = requirement_set[0]

    with pytest.raises(DensityOracleError):
        assert_valid_density(
            document,
            density_percent=100,
        )


def test_non_membership_digest_ignores_only_memberships() -> None:
    low = make_document(
        LEVEL_ALLOCATIONS[25]
    )

    high = make_document(
        LEVEL_ALLOCATIONS[100]
    )

    assert (
        non_membership_semantic_digest(low)
        == non_membership_semantic_digest(high)
    )

    high["objectives"][0][
        "constraints"
    ][0]["virtual_nodes"][0]["unit"] = "EUR"

    assert (
        non_membership_semantic_digest(low)
        != non_membership_semantic_digest(high)
    )


def test_complete_density_family_is_nested_and_balanced() -> None:
    documents = {
        level: make_document(allocation)
        for level, allocation
        in LEVEL_ALLOCATIONS.items()
    }

    result = validate_density_family(
        documents,
        required_levels=(25, 50, 75, 100),
    )

    assert result["levels"] == [
        25,
        50,
        75,
        100,
    ]

    assert result[
        "nested_membership_sets"
    ] is True

    assert result[
        "balanced_allocation"
    ] is True

    assert result[
        "one_factor_at_a_time"
    ] is True


def test_oracle_source_does_not_import_generators() -> None:
    source = (
        Path(
            "backend/harness/"
            "sensitivity_generator/oracles/"
            "membership_density_oracle.py"
        )
        .read_text(encoding="utf-8")
    )

    assert "structural_generator" not in source
    assert "controlled_families" not in source
