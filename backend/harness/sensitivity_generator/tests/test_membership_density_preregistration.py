from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PREREGISTRATION = (
    Path(__file__).resolve().parents[1]
    / "families"
    / "membership_density_preregistration.json"
)

EXPECTED_SEEDS = [
    101,
    202,
    1198202409,
    796786883,
    1126922093,
    809989256,
    618554674,
    1363159082,
    874332939,
    1767972531,
]

EXPECTED_SEED_DIGEST = (
    "451262bdcb669f38f98b4d15bbf32df7"
    "68a31f2d0c790c6c1d43d57f8ad195a7"
)


def load_preregistration() -> dict[str, Any]:
    value = json.loads(
        PREREGISTRATION.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(value, dict)

    return value


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_preregistration_is_frozen() -> None:
    value = load_preregistration()

    assert value["status"] == "frozen"

    assert (
        value["safety_state"][
            "preregistration_frozen"
        ]
        is True
    )

    assert (
        value["safety_state"][
            "canonical_campaign_generation_authorized"
        ]
        is True
    )


def test_exact_structural_seed_schedule() -> None:
    value = load_preregistration()

    seeds = value["campaign"][
        "structural_seeds"
    ]

    assert seeds == EXPECTED_SEEDS
    assert len(seeds) == 10
    assert len(set(seeds)) == 10

    assert canonical_digest(seeds) == (
        EXPECTED_SEED_DIGEST
    )

    assert (
        value["seed_schedule_provenance"][
            "selected_seed_digest"
        ]
        == EXPECTED_SEED_DIGEST
    )


def test_campaign_matrix_is_exact() -> None:
    value = load_preregistration()

    campaign = value["campaign"]

    assert campaign["levels"] == [
        25,
        50,
        75,
        100,
    ]

    assert (
        campaign["structural_seed_count"]
        == 10
    )

    assert (
        campaign["expected_instance_count"]
        == (
            len(campaign["levels"])
            * len(campaign["structural_seeds"])
        )
        == 40
    )

    assert (
        campaign["baseline_constraint_count"]
        == 4
    )

    assert (
        campaign["baseline_virtual_node_count"]
        == 24
    )


def test_additional_seeds_are_not_an_alternative() -> None:
    value = load_preregistration()

    disambiguation = value[
        "disambiguation"
    ]

    assert disambiguation[
        "stage10_equals_all_seeds_1_to_10"
    ] is True

    assert disambiguation[
        "additional_equals_all_seeds_11_to_20"
    ] is True

    assert disambiguation[
        "stage20_equals_all_seeds_1_to_20"
    ] is True

    assert disambiguation[
        "stage20_equals_stage10_plus_additional"
    ] is True

    assert disambiguation[
        "additional_seeds_are_continuation"
    ] is True

    assert disambiguation[
        "alternative_seed_schedule"
    ] is False


def test_execution_has_not_started() -> None:
    value = load_preregistration()

    safety = value["safety_state"]

    assert safety[
        "canonical_campaign_generated"
    ] is False

    assert safety[
        "controlled_execution_started"
    ] is False

    assert safety[
        "timing_execution_started"
    ] is False

    assert safety[
        "latency_claim_authorized"
    ] is False

    assert safety[
        "scientific_freeze"
    ] is False

    assert value["next_stage"] == (
        "SA4_membership_density_"
        "canonical_campaign_generation"
    )
