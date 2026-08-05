#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]

E3 = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution"
)

PREREGISTRATION = (
    E3
    / "planning"
    / "virtual_node_count_stage10_preregistration.json"
)

AUTHORIZATION = (
    E3
    / "planning"
    / "virtual_node_count_stage10_timing_authorization.json"
)

FUNCTIONAL_AUDIT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "functional_completion"
    / "combined_60_functional_steps_audit.json"
)

PLAN = (
    E3
    / "planning"
    / "virtual_node_count_stage10_timing_execution_plan.json"
)

VALIDATION_JSON = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "timing_preparation"
    / "timing_runner_validation.json"
)

VALIDATION_MD = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "timing_preparation"
    / "timing_runner_validation.md"
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(
            f"[ERROR] Missing JSON artifact: {path}"
        )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise SystemExit(
            f"[ERROR] Expected JSON object: {path}"
        )

    return payload


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SystemExit(f"[ERROR] {message}")


def expected_run_stem(
    replication_index: int,
) -> str:
    if replication_index < 2:
        return (
            "virtual_node_count_"
            f"rep_{replication_index:03d}_strict_common"
        )

    return (
        "virtual_node_count_stage10_"
        f"rep_{replication_index:03d}_strict_common"
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
    )

    parser.add_argument(
        "--created-utc",
        required=True,
    )

    args = parser.parse_args()
    root = args.repo_root.resolve()

    preregistration = load_json(
        root / PREREGISTRATION
    )
    authorization = load_json(
        root / AUTHORIZATION
    )
    functional = load_json(
        root / FUNCTIONAL_AUDIT
    )

    campaign = preregistration.get(
        "campaign_contract",
        {},
    )
    timing = preregistration.get(
        "timing_protocol",
        {},
    )
    precision = preregistration.get(
        "precision_protocol",
        {},
    )

    runner_relative = Path(
        timing.get("runner_path", "")
    )
    analyzer_relative = Path(
        precision.get("analyzer_path", "")
    )

    runner_path = root / runner_relative
    analyzer_path = root / analyzer_relative

    require(
        runner_path.is_file(),
        f"Missing timing runner: {runner_path}",
    )
    require(
        analyzer_path.is_file(),
        f"Missing precision analyzer: {analyzer_path}",
    )

    runner_sha256 = sha256_file(runner_path)
    analyzer_sha256 = sha256_file(analyzer_path)

    require(
        runner_sha256
        == timing.get("runner_sha256"),
        "Timing runner SHA-256 differs from preregistration.",
    )
    require(
        analyzer_sha256
        == precision.get("analyzer_sha256"),
        "Precision analyzer SHA-256 differs from preregistration.",
    )

    help_result = subprocess.run(
        [
            sys.executable,
            str(runner_path),
            "--help",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    require(
        help_result.returncode == 0,
        (
            "Timing runner --help failed:\n"
            + help_result.stderr
        ),
    )

    cli_options = sorted(
        set(
            re.findall(
                r"--[a-zA-Z0-9][a-zA-Z0-9_-]*",
                help_result.stdout,
            )
        )
    )

    require(
        bool(cli_options),
        "No CLI options discovered in runner help.",
    )

    expected_campaign = (
        "virtual_node_count_stage10_c4"
    )

    require(
        campaign.get("campaign_id")
        == expected_campaign,
        "Unexpected campaign identifier.",
    )
    require(
        campaign.get("levels") == [6, 12, 24],
        "Unexpected virtual-node-count levels.",
    )
    require(
        campaign.get("stage10_replication_count")
        == 10,
        "Expected 10 Stage-10 replications.",
    )

    seeds = campaign.get("stage10_seeds")

    require(
        isinstance(seeds, list)
        and len(seeds) == 10,
        "Expected 10 Stage-10 structural seeds.",
    )

    require(
        timing.get("warmups_per_cell") == 10,
        "Expected 10 warmups per cell.",
    )
    require(
        timing.get("measurements_per_cell") == 100,
        "Expected 100 measurements per cell.",
    )
    require(
        timing.get("expected_cell_count") == 60,
        "Expected 60 timing cells.",
    )
    require(
        timing.get(
            "expected_warmup_observation_count"
        )
        == 600,
        "Expected 600 warmup observations.",
    )
    require(
        timing.get(
            "expected_measurement_observation_count"
        )
        == 6000,
        "Expected 6000 measurement observations.",
    )
    require(
        timing.get("order_seed_base") == 20260728,
        "Unexpected timing-order seed base.",
    )
    require(
        timing.get("reuse_successful") is True,
        "Successful-output reuse must be enabled.",
    )
    require(
        timing.get("fresh_ckg_state_required")
        is True,
        "Fresh CKG state must be required.",
    )
    require(
        timing.get(
            "functional_digest_check_required"
        )
        is True,
        "Functional digest check must be required.",
    )

    require(
        authorization.get("status")
        == "authorized",
        "Formal timing authorization is absent.",
    )
    require(
        authorization.get("campaign_id")
        == expected_campaign,
        "Authorization campaign mismatch.",
    )

    scope = authorization.get("scope", {})
    execution_state = authorization.get(
        "execution_state",
        {},
    )
    prohibitions = authorization.get(
        "prohibitions",
        {},
    )

    expected_scope = {
        "replication_count": 10,
        "timing_cell_count": 60,
        "warmup_runs_per_cell": 10,
        "measurement_runs_per_cell": 100,
        "expected_warmup_count": 600,
        "expected_measurement_count": 6000,
    }

    for key, expected_value in expected_scope.items():
        require(
            scope.get(key) == expected_value,
            (
                f"Authorization {key}: expected "
                f"{expected_value!r}, got "
                f"{scope.get(key)!r}."
            ),
        )

    require(
        execution_state
        == {
            "timing_execution_performed": False,
            "warmup_count_observed": 0,
            "measurement_count_observed": 0,
        },
        "Timing authorization execution state is not pristine.",
    )

    for field in (
        "functional_execution_rerun_authorized",
        "historical_prefix_rerun_authorized",
        "stage20_execution_authorized",
        "latency_claim_authorized",
        "scientific_freeze_authorized",
    ):
        require(
            prohibitions.get(field) is False,
            f"{field} must remain false.",
        )

    require(
        functional.get("status") == "pass",
        "Functional completion audit is not passing.",
    )
    require(
        functional.get("replication_count") == 10,
        "Expected 10 functional replications.",
    )
    require(
        functional.get("instance_count") == 30,
        "Expected 30 functional instances.",
    )
    require(
        functional.get("functional_step_count")
        == 60,
        "Expected 60 functional steps.",
    )
    require(
        functional.get(
            "all_replications_passed"
        )
        is True,
        "Not all functional replications passed.",
    )
    require(
        functional.get(
            "timing_execution_performed"
        )
        is False,
        "Functional audit already records timing execution.",
    )

    functional_runs = functional.get("runs")

    require(
        isinstance(functional_runs, list)
        and len(functional_runs) == 10,
        "Expected 10 functional run records.",
    )

    functional_by_replication = {
        int(item["replication_index"]): item
        for item in functional_runs
    }

    authorization_replications = {
        int(item["replication_index"]): item
        for item in authorization.get(
            "replications",
            []
        )
    }

    require(
        sorted(functional_by_replication)
        == list(range(10)),
        "Functional replication matrix is incomplete.",
    )
    require(
        sorted(authorization_replications)
        == list(range(10)),
        "Authorization replication matrix is incomplete.",
    )

    plan_replications: list[dict[str, Any]] = []

    for replication_index in range(10):
        functional_run = (
            functional_by_replication[
                replication_index
            ]
        )
        authorized_replication = (
            authorization_replications[
                replication_index
            ]
        )

        seed = int(seeds[replication_index])
        expected_stem = expected_run_stem(
            replication_index
        )

        source_run_path = Path(
            functional_run["run_path"]
        )

        require(
            source_run_path.name == expected_stem,
            (
                "Unexpected run path for replication "
                f"{replication_index}: {source_run_path}"
            ),
        )
        require(
            (root / source_run_path).is_dir(),
            f"Missing functional run: {source_run_path}",
        )
        require(
            functional_run.get("status") == "pass",
            (
                "Functional run is not passing: "
                f"replication {replication_index}"
            ),
        )
        require(
            functional_run.get(
                "selected_instance_count"
            )
            == 3,
            (
                "Expected 3 instances for replication "
                f"{replication_index}."
            ),
        )
        require(
            functional_run.get(
                "functional_step_count"
            )
            == 6,
            (
                "Expected 6 functional steps for "
                f"replication {replication_index}."
            ),
        )
        require(
            functional_run.get(
                "timing_artifact_count"
            )
            == 0,
            (
                "Unexpected pre-existing timing artifacts "
                f"for replication {replication_index}."
            ),
        )

        require(
            int(
                authorized_replication[
                    "structural_seed"
                ]
            )
            == seed,
            (
                "Authorization seed mismatch for "
                f"replication {replication_index}."
            ),
        )

        expected_order_seed = (
            20260728 + replication_index
        )

        require(
            int(
                authorized_replication[
                    "execution_order_seed"
                ]
            )
            == expected_order_seed,
            (
                "Execution-order seed mismatch for "
                f"replication {replication_index}."
            ),
        )

        digest = functional_run.get(
            "deterministic_execution_digest"
        )

        require(
            isinstance(digest, str)
            and bool(digest),
            (
                "Missing functional digest for "
                f"replication {replication_index}."
            ),
        )

        plan_replications.append(
            {
                "replication_index": (
                    replication_index
                ),
                "structural_seed": seed,
                "source_evidence_class": (
                    functional_run[
                        "evidence_class"
                    ]
                ),
                "source_functional_run_path": (
                    source_run_path.as_posix()
                ),
                "source_functional_digest": digest,
                "functional_digest_check_required": (
                    True
                ),
                "fresh_ckg_state_required": True,
                "reuse_successful": True,
                "factor_levels": [6, 12, 24],
                "steps_per_instance": 2,
                "timing_cell_count": 6,
                "warmups_per_cell": 10,
                "measurements_per_cell": 100,
                "expected_warmup_count": 60,
                "expected_measurement_count": 600,
                "execution_order_seed": (
                    expected_order_seed
                ),
                "logical_status": "ready",
                "runner_invocation_performed": False,
            }
        )

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()

    plan = {
        "schema_version": (
            "mcad-virtual-node-count-stage10-"
            "timing-execution-plan-v1"
        ),
        "status": "prepared",
        "created_utc": args.created_utc,
        "source_commit": source_commit,
        "campaign_id": expected_campaign,
        "factor": "virtual_node_count",
        "runner": {
            "path": runner_relative.as_posix(),
            "sha256": runner_sha256,
            "preregistered_sha256": (
                timing["runner_sha256"]
            ),
            "sha256_matches_preregistration": True,
            "help_exit_status": 0,
            "help_sha256": sha256_text(
                help_result.stdout
            ),
            "discovered_cli_options": cli_options,
        },
        "precision_analyzer": {
            "path": analyzer_relative.as_posix(),
            "sha256": analyzer_sha256,
            "preregistered_sha256": (
                precision["analyzer_sha256"]
            ),
            "sha256_matches_preregistration": True,
        },
        "scope": {
            "replication_count": 10,
            "factor_levels": [6, 12, 24],
            "steps_per_instance": 2,
            "timing_cell_count": 60,
            "warmups_per_cell": 10,
            "measurements_per_cell": 100,
            "expected_warmup_count": 600,
            "expected_measurement_count": 6000,
        },
        "protocol": {
            "fresh_ckg_state_required": True,
            "functional_digest_check_required": True,
            "reuse_successful": True,
            "reuse_successful_scope": (
                timing[
                    "reuse_successful_scope"
                ]
            ),
            "order_seed_base": 20260728,
            "order_seed_policy": (
                timing["order_seed_policy"]
            ),
        },
        "precision_protocol": {
            "analyzer_version": "v2",
            "cluster_unit": (
                precision["cluster_unit"]
            ),
            "bootstrap_repetitions": 10000,
            "bootstrap_seed_base": 20260728,
            "confidence_level": 0.95,
            "median_relative_half_width_target": (
                0.10
            ),
            "p95_relative_half_width_target": (
                0.15
            ),
            "all_cells_must_pass": True,
        },
        "replications": plan_replications,
        "execution_state": {
            "runner_invocation_performed": False,
            "timing_execution_performed": False,
            "warmup_count_observed": 0,
            "measurement_count_observed": 0,
            "timing_output_directories_created": False,
        },
        "prohibitions": {
            "functional_execution_rerun_authorized": (
                False
            ),
            "historical_prefix_rerun_authorized": (
                False
            ),
            "stage20_execution_authorized": False,
            "latency_claim_authorized": False,
            "scientific_freeze_authorized": False,
        },
        "next_stage": (
            "authorize_and_execute_stage10_formal_timing"
        ),
    }

    write_json(root / PLAN, plan)

    validation = {
        "schema_version": (
            "mcad-virtual-node-count-stage10-"
            "timing-runner-validation-v1"
        ),
        "status": "pass",
        "created_utc": args.created_utc,
        "source_commit": source_commit,
        "campaign_id": expected_campaign,
        "runner_path": runner_relative.as_posix(),
        "runner_sha256": runner_sha256,
        "runner_sha256_matches_preregistration": (
            True
        ),
        "runner_help_exit_status": 0,
        "runner_cli_option_count": len(
            cli_options
        ),
        "precision_analyzer_path": (
            analyzer_relative.as_posix()
        ),
        "precision_analyzer_sha256": (
            analyzer_sha256
        ),
        "precision_analyzer_sha256_matches_preregistration": (
            True
        ),
        "functional_audit_status": "pass",
        "replication_count": 10,
        "timing_cell_count": 60,
        "expected_warmup_count": 600,
        "expected_measurement_count": 6000,
        "functional_execution_rerun_performed": (
            False
        ),
        "timing_execution_performed": False,
        "timing_output_directories_created": False,
        "plan_path": PLAN.as_posix(),
        "plan_sha256": sha256_file(
            root / PLAN
        ),
        "next_stage": (
            "authorize_and_execute_stage10_formal_timing"
        ),
    }

    write_json(
        root / VALIDATION_JSON,
        validation,
    )

    summary = """# Virtual-node-count Stage-10 timing preparation

- Status: `PASS`
- Existing preregistered runner reused: `true`
- Runner SHA-256 matches preregistration: `true`
- Precision analyzer SHA-256 matches preregistration: `true`
- Replications prepared: `10`
- Timing cells prepared: `60`
- Expected warmups: `600`
- Expected measurements: `6000`
- Functional execution rerun: `false`
- Timing execution performed: `false`
- Timing output directories created: `false`

## Next stage

`authorize_and_execute_stage10_formal_timing`
"""

    summary_path = root / VALIDATION_MD
    summary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    summary_path.write_text(
        summary,
        encoding="utf-8",
    )

    print(
        "stage10_timing_runner_validation=PASS"
    )
    print(
        "runner_sha256_matches_preregistration=true"
    )
    print(
        "analyzer_sha256_matches_preregistration=true"
    )
    print("replication_count=10")
    print("timing_cell_count=60")
    print("expected_warmup_count=600")
    print("expected_measurement_count=6000")
    print(
        "functional_execution_rerun_performed=false"
    )
    print("timing_execution_performed=false")
    print(
        "timing_output_directories_created=false"
    )
    print(
        "next_stage="
        "authorize_and_execute_stage10_formal_timing"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
