from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest
import yaml

from backend.ckg.ckg_updater import (
    CKGGraph,
)
from backend.harness.run_baselines_and_ablations import (
    _normalize_qp,
    load_yaml,
    policy_decision,
)
from backend.harness.run_robustness_benchmark import (
    _collect_mcad_explainability,
)


CONFIG_PATHS = [
    (
        "backend/harness/"
        "scenarios_robustness_foodmart.yaml"
    ),
    (
        "backend/harness/"
        "scenarios_robustness_adventureworks.yaml"
    ),
]


@pytest.fixture(autouse=True)
def isolated_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "MCAD_TMP_DIR",
        str(tmp_path / "runtime"),
    )


def decision_map(
    config_paths: list[str],
    tmp_path: Path,
) -> dict[
    tuple[str, str, int],
    bool,
]:
    expected: dict[
        tuple[str, str, int],
        bool,
    ] = {}

    for config_index, config_path in (
        enumerate(config_paths)
    ):
        cfg = load_yaml(config_path)
        objective_id = str(
            cfg["objective_id"]
        )
        dw_id = str(
            cfg.get("dw_id")
            or "UNKNOWN"
        )

        for scenario_index, scenario in (
            enumerate(
                cfg.get("scenarios")
                or []
            )
        ):
            ckg = CKGGraph(
                output_dir=str(
                    tmp_path
                    / f"policy_{config_index}_"
                      f"{scenario_index}"
                )
            )

            for step_index, step in (
                enumerate(
                    scenario.get("steps")
                    or [],
                    start=1,
                )
            ):
                qp = _normalize_qp(
                    step,
                    objective_id,
                )
                decision = policy_decision(
                    "mcad",
                    ckg,
                    objective_id,
                    qp,
                    rng=random.Random(0),
                    matched_random_allow_prob=0.0,
                    step_idx=step_index,
                )

                expected[
                    (
                        dw_id,
                        str(scenario["id"]),
                        step_index,
                    )
                ] = bool(
                    decision["allow"]
                )

    return expected


def explainability_map(
    config_paths: list[str],
) -> dict[
    tuple[str, str, int],
    dict[str, Any],
]:
    rows, _ = (
        _collect_mcad_explainability(
            config_paths
        )
    )

    return {
        (
            str(row["dw_id"]),
            str(row["scenario_id"]),
            int(row["step_idx"]),
        ): row
        for row in rows
    }


def test_explainability_decisions_match_policy(
    tmp_path: Path,
) -> None:
    expected = decision_map(
        CONFIG_PATHS,
        tmp_path,
    )
    actual = explainability_map(
        CONFIG_PATHS
    )

    assert len(expected) == 46
    assert len(actual) == 46

    assert {
        key: bool(row["mcad_allow"])
        for key, row in actual.items()
    } == expected


def test_partial_growth_steps_are_strict_blocks(
) -> None:
    rows = explainability_map(
        CONFIG_PATHS
    )

    target_steps = {
        (
            "FOODMART",
            "rb_fm_semantic_traps",
            3,
        ),
        (
            "FOODMART",
            "rb_fm_long_noisy_session",
            7,
        ),
        (
            "ADVENTUREWORKS",
            "rb_aw_semantic_traps",
            3,
        ),
        (
            "ADVENTUREWORKS",
            "rb_aw_long_noisy_session",
            7,
        ),
    }

    assert target_steps <= set(rows)

    for key in target_steps:
        row = rows[key]

        assert row["mcad_allow"] is False
        assert (
            row["primary_reason"]
            == "missing_requirement_set"
        )
        assert (
            row["explainable_block"]
            == 1
        )
        assert (
            row[
                "n_calculable_constraints"
            ]
            == 0
        )
        assert (
            row[
                "n_missing_requirements"
            ]
            > 0
        )


def test_all_mcad_blocks_are_explained(
) -> None:
    rows = list(
        explainability_map(
            CONFIG_PATHS
        ).values()
    )

    blocked = [
        row
        for row in rows
        if not bool(row["mcad_allow"])
    ]

    assert len(rows) == 46
    assert len(blocked) == 34

    assert all(
        row["explainable_block"] == 1
        for row in blocked
    )

    assert all(
        row["primary_reason"]
        != "unclassified_block"
        for row in blocked
    )


def test_oracle_labels_do_not_drive_mcad(
    tmp_path: Path,
) -> None:
    original = explainability_map(
        CONFIG_PATHS
    )

    mutated_paths: list[str] = []

    for index, config_path in enumerate(
        CONFIG_PATHS
    ):
        data = load_yaml(config_path)

        for scenario in (
            data.get("scenarios")
            or []
        ):
            for step in (
                scenario.get("steps")
                or []
            ):
                step["oracle_allow"] = (
                    not bool(
                        step.get(
                            "oracle_allow",
                            False,
                        )
                    )
                )

        output_path = (
            tmp_path
            / f"inverted_{index}.yaml"
        )

        output_path.write_text(
            yaml.safe_dump(
                data,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        mutated_paths.append(
            str(output_path)
        )

    mutated = explainability_map(
        mutated_paths
    )

    fields = (
        "mcad_allow",
        "sat",
        "primary_reason",
        "n_calculable_constraints",
        "n_missing_requirements",
        "induced_mask_size",
    )

    assert set(original) == set(mutated)

    for key in original:
        assert {
            field: original[key][field]
            for field in fields
        } == {
            field: mutated[key][field]
            for field in fields
        }
