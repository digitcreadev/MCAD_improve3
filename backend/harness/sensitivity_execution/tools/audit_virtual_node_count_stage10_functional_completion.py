#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]

E3 = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution"
)

RUNS = E3 / "runs"

PREREGISTRATION = (
    E3
    / "planning"
    / "virtual_node_count_stage10_preregistration.json"
)

COMMON_WORKLOAD_AUDIT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "common_workloads"
    / "stage10_common_workload_audit.json"
)

NEW_EXECUTION_REPORT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "functional_execution"
    / "new_replications_functional_execution_report.json"
)

REPORT = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "functional_completion"
    / "combined_60_functional_steps_audit.json"
)

SUMMARY = (
    E3
    / "audits"
    / "virtual_node_count_stage10"
    / "functional_completion"
    / "combined_60_functional_steps_audit.md"
)

EXPECTED_LEVELS = [6, 12, 24]

EXPECTED_SEEDS = {
    0: 101,
    1: 202,
    2: 1198202409,
    3: 796786883,
    4: 1126922093,
    5: 809989256,
    6: 618554674,
    7: 1363159082,
    8: 874332939,
    9: 1767972531,
}


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


def write_json(path: Path, payload: Any) -> None:
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise SystemExit(f"[ERROR] {message}")


def run_stem(replication: int) -> str:
    if replication < 2:
        return (
            "virtual_node_count_"
            f"rep_{replication:03d}_strict_common"
        )

    return (
        "virtual_node_count_stage10_"
        f"rep_{replication:03d}_strict_common"
    )


def validate_csv_statuses(
    rows: list[dict[str, str]],
    path: Path,
) -> None:
    if not rows:
        raise SystemExit(
            f"[ERROR] Empty instance-results CSV: {path}"
        )

    status_fields = [
        field
        for field in rows[0]
        if field.lower() in {
            "status",
            "result",
            "execution_status",
        }
    ]

    accepted = {
        "pass",
        "passed",
        "success",
        "successful",
        "ok",
        "completed",
    }

    for field in status_fields:
        for index, row in enumerate(rows, start=1):
            value = str(row.get(field, "")).lower()

            if value and value not in accepted:
                raise SystemExit(
                    "[ERROR] Non-success CSV status: "
                    f"{path}:{index}:{field}={value!r}"
                )


def validate_run(
    root: Path,
    replication: int,
) -> dict[str, Any]:
    stem = run_stem(replication)
    run_dir = root / RUNS / stem

    required_top = {
        "campaign_metrics": (
            run_dir / "campaign_metrics.json"
        ),
        "execution_manifest": (
            run_dir / "execution_manifest.json"
        ),
        "execution_spec": (
            run_dir / "execution_spec.json"
        ),
        "instance_results": (
            run_dir / "instance_results.csv"
        ),
    }

    for path in required_top.values():
        require(
            path.is_file(),
            f"Missing run artifact: {path}",
        )

    manifest = load_json(
        required_top["execution_manifest"]
    )
    metrics = load_json(
        required_top["campaign_metrics"]
    )
    execution_spec = load_json(
        required_top["execution_spec"]
    )

    require(
        int(manifest.get("selected_instance_count", -1))
        == 3,
        f"{stem}: selected_instance_count must be 3.",
    )

    require(
        int(metrics.get("step_count", -1)) == 6,
        f"{stem}: campaign step_count must be 6.",
    )

    if "successful_instance_count" in metrics:
        require(
            int(metrics["successful_instance_count"]) == 3,
            f"{stem}: successful_instance_count must be 3.",
        )

    if "failed_instance_count" in metrics:
        require(
            int(metrics["failed_instance_count"]) == 0,
            f"{stem}: failed_instance_count must be 0.",
        )

    digest = manifest.get(
        "deterministic_execution_digest"
    )

    require(
        isinstance(digest, str) and bool(digest),
        f"{stem}: missing deterministic digest.",
    )

    selection = (
        execution_spec
        .get("instance_selection", {})
        .get("instance_ids", [])
    )

    require(
        isinstance(selection, list)
        and len(selection) == 3,
        f"{stem}: execution spec must select 3 instances.",
    )

    with required_top["instance_results"].open(
        newline="",
        encoding="utf-8",
    ) as stream:
        rows = list(csv.DictReader(stream))

    require(
        len(rows) == 3,
        f"{stem}: instance_results must contain 3 rows.",
    )

    validate_csv_statuses(
        rows,
        required_top["instance_results"],
    )

    instance_dirs = sorted(
        path.parent
        for path in run_dir.glob(
            "instances/level_*/"
            "rep_*_seed_*/execution_manifest.json"
        )
    )

    require(
        len(instance_dirs) == 3,
        f"{stem}: expected 3 instance directories.",
    )

    observed_levels: list[int] = []
    observed_seeds: set[int] = set()
    observed_replications: set[int] = set()

    instance_reports = []

    pattern = re.compile(
        r"rep_(\d+)_seed_(\d+)$"
    )

    for instance_dir in instance_dirs:
        level_match = re.fullmatch(
            r"level_(\d+)",
            instance_dir.parent.name,
        )
        instance_match = pattern.fullmatch(
            instance_dir.name
        )

        require(
            level_match is not None,
            f"Invalid level directory: {instance_dir}",
        )
        require(
            instance_match is not None,
            f"Invalid instance directory: {instance_dir}",
        )

        level = int(level_match.group(1))
        observed_replication = int(
            instance_match.group(1)
        )
        observed_seed = int(
            instance_match.group(2)
        )

        observed_levels.append(level)
        observed_replications.add(
            observed_replication
        )
        observed_seeds.add(observed_seed)

        artifacts = {
            "audit": instance_dir / "audit.json",
            "execution_manifest": (
                instance_dir / "execution_manifest.json"
            ),
            "metrics": instance_dir / "metrics.json",
            "timeline": instance_dir / "timeline.json",
        }

        for path in artifacts.values():
            require(
                path.is_file(),
                f"Missing instance artifact: {path}",
            )

        audit = load_json(artifacts["audit"])

        status = audit.get("status")

        if isinstance(status, str):
            require(
                status.lower()
                in {
                    "pass",
                    "passed",
                    "success",
                    "successful",
                    "ok",
                    "completed",
                },
                f"Non-passing audit status: {artifacts['audit']}",
            )

        instance_reports.append(
            {
                "factor_level": level,
                "replication_index": (
                    observed_replication
                ),
                "seed": observed_seed,
                "relative_instance_dir": (
                    instance_dir
                    .relative_to(run_dir)
                    .as_posix()
                ),
                "audit_sha256": sha256_file(
                    artifacts["audit"]
                ),
                "execution_manifest_sha256": (
                    sha256_file(
                        artifacts["execution_manifest"]
                    )
                ),
                "metrics_sha256": sha256_file(
                    artifacts["metrics"]
                ),
                "timeline_sha256": sha256_file(
                    artifacts["timeline"]
                ),
            }
        )

    require(
        sorted(observed_levels) == EXPECTED_LEVELS,
        f"{stem}: levels differ from 6,12,24.",
    )

    require(
        observed_replications == {replication},
        f"{stem}: replication contamination.",
    )

    require(
        observed_seeds
        == {EXPECTED_SEEDS[replication]},
        f"{stem}: seed contamination.",
    )

    timing_artifacts = [
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if (
            path.is_file()
            and "timing" in path.name.lower()
        )
    ]

    require(
        not timing_artifacts,
        f"{stem}: unexpected timing artifacts.",
    )

    return {
        "replication_index": replication,
        "seed": EXPECTED_SEEDS[replication],
        "evidence_class": (
            "historical_prefix_reused"
            if replication < 2
            else "stage10_new_functional_execution"
        ),
        "run_path": (
            run_dir.relative_to(root).as_posix()
        ),
        "selected_instance_count": 3,
        "functional_step_count": 6,
        "deterministic_execution_digest": digest,
        "campaign_metrics_sha256": sha256_file(
            required_top["campaign_metrics"]
        ),
        "execution_manifest_sha256": sha256_file(
            required_top["execution_manifest"]
        ),
        "execution_spec_sha256": sha256_file(
            required_top["execution_spec"]
        ),
        "instance_results_sha256": sha256_file(
            required_top["instance_results"]
        ),
        "timing_artifact_count": 0,
        "instances": sorted(
            instance_reports,
            key=lambda item: item["factor_level"],
        ),
        "status": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()

    preregistration = load_json(
        root / PREREGISTRATION
    )
    common_audit = load_json(
        root / COMMON_WORKLOAD_AUDIT
    )
    new_report = load_json(
        root / NEW_EXECUTION_REPORT
    )

    campaign_contract = preregistration.get(
        "campaign_contract",
        {},
    )

    require(
        campaign_contract.get(
            "expected_stage10_instance_count"
        )
        == 30,
        "Preregistration must expect 30 instances.",
    )

    require(
        campaign_contract.get(
            "expected_stage10_functional_step_count"
        )
        == 60,
        "Preregistration must expect 60 steps.",
    )

    require(
        campaign_contract.get(
            "stage10_replication_count"
        )
        == 10,
        "Preregistration must expect 10 replications.",
    )

    require(
        common_audit.get("status") == "pass",
        "Common-workload audit is not passing.",
    )

    require(
        common_audit.get(
            "historical_prefix_audit_matches"
        )
        is True,
        "Historical audit compatibility missing.",
    )

    require(
        common_audit.get(
            "historical_prefix_workload_matches"
        )
        is True,
        "Historical workload compatibility missing.",
    )

    require(
        new_report.get("status") == "pass",
        "New functional execution report is not passing.",
    )

    require(
        new_report.get(
            "executed_replication_count"
        )
        == 8,
        "Expected 8 newly executed replications.",
    )

    require(
        new_report.get("executed_instance_count")
        == 24,
        "Expected 24 newly executed instances.",
    )

    require(
        new_report.get(
            "executed_functional_step_count"
        )
        == 48,
        "Expected 48 newly executed steps.",
    )

    require(
        new_report.get(
            "historical_prefix",
            {},
        ).get("rerun_performed")
        is False,
        "Historical prefix was marked as rerun.",
    )

    # rep_000 and rep_001 are validated directly from their
    # authoritative historical run directories by validate_run().
    # Only a Stage-10-named duplicate directory would indicate a rerun.
    for replication in (0, 1):
        forbidden_stage10_dir = (
            root
            / RUNS
            / (
                "virtual_node_count_stage10_"
                f"rep_{replication:03d}_strict_common"
            )
        )

        require(
            not forbidden_stage10_dir.exists(),
            "Historical prefix appears to have been "
            f"rerun: {forbidden_stage10_dir}",
        )

    runs = [
        validate_run(root, replication)
        for replication in range(10)
    ]

    total_instances = sum(
        item["selected_instance_count"]
        for item in runs
    )

    total_steps = sum(
        item["functional_step_count"]
        for item in runs
    )

    require(
        total_instances == 30,
        f"Combined instance count is {total_instances}, not 30.",
    )

    require(
        total_steps == 60,
        f"Combined functional step count is {total_steps}, not 60.",
    )

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
    ).strip()

    report = {
        "schema_version": (
            "mcad-virtual-node-count-stage10-"
            "functional-completion-audit-v1"
        ),
        "status": "pass",
        "campaign_id": (
            "virtual_node_count_stage10_c4"
        ),
        "factor": "virtual_node_count",
        "source_commit": source_commit,
        "replication_count": 10,
        "instance_count": total_instances,
        "functional_step_count": total_steps,
        "expected_replication_count": 10,
        "expected_instance_count": 30,
        "expected_functional_step_count": 60,
        "all_replications_passed": True,
        "historical_prefix": {
            "replications": [0, 1],
            "instance_count": 6,
            "functional_step_count": 12,
            "reused": True,
            "rerun_performed": False,
            "rerun_required": False,
        },
        "new_functional_execution": {
            "replications": list(range(2, 10)),
            "instance_count": 24,
            "functional_step_count": 48,
            "all_passed": True,
        },
        "timing_execution_performed": False,
        "timing_artifact_count": 0,
        "latency_claim_authorized": False,
        "source_artifacts": {
            "preregistration": {
                "path": PREREGISTRATION.as_posix(),
                "sha256": sha256_file(
                    root / PREREGISTRATION
                ),
            },
            "common_workload_audit": {
                "path": COMMON_WORKLOAD_AUDIT.as_posix(),
                "sha256": sha256_file(
                    root / COMMON_WORKLOAD_AUDIT
                ),
            },
            "new_execution_report": {
                "path": NEW_EXECUTION_REPORT.as_posix(),
                "sha256": sha256_file(
                    root / NEW_EXECUTION_REPORT
                ),
            },
        },
        "runs": runs,
        "next_stage": (
            "prepare_stage10_formal_timing_authorization"
        ),
    }

    write_json(root / REPORT, report)

    summary = """# Virtual-node-count Stage-10 functional completion

- Status: `PASS`
- Replications: `10`
- Instances: `30`
- Functional steps: `60`
- Historical prefix: `6 instances / 12 steps`, reused
- Historical prefix rerun: `false`
- New evidence: `24 instances / 48 steps`
- Timing execution performed: `false`
- Latency claim authorized: `false`

## Next stage

`prepare_stage10_formal_timing_authorization`
"""

    summary_path = root / SUMMARY
    summary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    summary_path.write_text(
        summary,
        encoding="utf-8",
    )

    print(
        "virtual_node_count_stage10_"
        "functional_completion_audit=PASS"
    )
    print("replication_count=10")
    print("instance_count=30")
    print("functional_step_count=60")
    print("historical_prefix_instance_count=6")
    print("historical_prefix_step_count=12")
    print("historical_prefix_rerun_performed=false")
    print("new_instance_count=24")
    print("new_functional_step_count=48")
    print("timing_execution_performed=false")
    print(
        "next_stage="
        "prepare_stage10_formal_timing_authorization"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
