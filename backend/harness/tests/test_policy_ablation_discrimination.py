from __future__ import annotations

import random
from pathlib import Path

import yaml

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.run_baselines_and_ablations import (
    _normalize_qp,
    policy_decision,
)


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "backend" / "harness" / "scenarios.yaml"


def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def find_scenario(config: dict, scenario_id: str) -> dict:
    return next(
        scenario
        for scenario in config["scenarios"]
        if scenario["id"] == scenario_id
    )


def decide(policy: str, scenario: dict, objective_id: str) -> dict:
    step = scenario["steps"][0]
    qp = _normalize_qp(step, objective_id)

    return policy_decision(
        policy=policy,
        ckg=CKGGraph(
            output_dir=f"results_policy_tmp/tests/{policy}"
        ),
        objective_id=objective_id,
        qp=qp,
        rng=random.Random(20260720),
        matched_random_allow_prob=0.5,
        step_idx=1,
    )


def test_no_sat_is_discriminative() -> None:
    config = load_config()
    objective_id = config["objective_id"]

    scenario = find_scenario(
        config,
        "adversarial_missing_cube_sat_witness",
    )

    mcad = decide("mcad", scenario, objective_id)
    ablation = decide("ablation_no_sat", scenario, objective_id)

    assert mcad["sat"] is False
    assert mcad["allow"] is False

    assert ablation["sat"] is False
    assert ablation["allow"] is True
    assert ablation["real_nv_ids"]
    assert ablation["ceval_ids"] == ["c1"]


def test_no_real_is_discriminative() -> None:
    config = load_config()
    objective_id = config["objective_id"]

    scenario = find_scenario(
        config,
        "border_growth_partial_1998_only",
    )

    mcad = decide("mcad", scenario, objective_id)
    ablation = decide("ablation_no_real", scenario, objective_id)

    assert mcad["allow"] is False
    assert ablation["allow"] is True


def test_ceval_intersection_is_discriminative() -> None:
    config = load_config()
    objective_id = config["objective_id"]

    scenario = find_scenario(
        config,
        "border_growth_partial_1998_only",
    )

    mcad = decide("mcad", scenario, objective_id)
    ablation = decide(
        "ablation_ceval_any_intersection",
        scenario,
        objective_id,
    )

    assert mcad["allow"] is False
    assert ablation["allow"] is True
