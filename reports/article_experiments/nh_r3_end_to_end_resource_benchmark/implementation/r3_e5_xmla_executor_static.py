#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_E4_HEAD = "e34ba8e6e0c1267974305053557c6a28acfe2c11"

ARMS = ("UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING")
SHARED_METRICS = (
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
)
XMLA_METRICS = (
    "emondrian_cpu_usage_usec_delta",
    "emondrian_io_rbytes_delta",
    "emondrian_io_wbytes_delta",
)

CONTRACT_REL = R3_REL / "config/r3_e5_xmla_executor_receipt_static_contract.json"
SCHEDULE_REL = R3_REL / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def read_schedule(repo: Path) -> list[dict[str, str]]:
    path = repo / SCHEDULE_REL
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def schedule_summary(repo: Path) -> dict[str, Any]:
    rows = read_schedule(repo)
    if len(rows) != 300:
        raise RuntimeError(f"frozen primary schedule row count changed: {len(rows)}")
    session_ids = [r["session_id"] for r in rows]
    if len(set(session_ids)) != 300:
        raise RuntimeError("frozen primary schedule session ids are not unique")

    strata = Counter((r["topology"], r["pattern"]) for r in rows)
    if len(strata) != 20 or set(strata.values()) != {15}:
        raise RuntimeError(f"frozen 20x15 stratification changed: {dict(strata)}")

    for row in rows:
        if row["selection_role"] != "CONFIRMATORY_PRIMARY":
            raise RuntimeError("selection role changed")
        ordered = (row["arm_1"], row["arm_2"], row["arm_3"])
        if set(ordered) != set(ARMS) or len(set(ordered)) != 3:
            raise RuntimeError(f"arm permutation changed for {row['session_id']}")

    return {
        "semantic_sessions": 300,
        "strata": 20,
        "sessions_per_stratum": 15,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "candidates_per_arm_run": 24,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fixed_warmup_template_count": 7,
    }


def validate_static_authorities(repo: Path) -> dict[str, Any]:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT_E4_HEAD, "HEAD"],
        check=True,
    )

    contract = json.loads((repo / CONTRACT_REL).read_text(encoding="utf-8"))
    if contract["contract_version"] != "mcad.nh_r3.e5.xmla_executor_receipt_static.v1":
        raise RuntimeError("unexpected E5 contract")
    if contract["parent_e4_head"] != PARENT_E4_HEAD:
        raise RuntimeError("E5 parent binding changed")

    return schedule_summary(repo)


def dry_run(repo: Path) -> dict[str, Any]:
    counts = validate_static_authorities(repo)
    return {
        "contract_version": "mcad.nh_r3.e5.xmla_executor_dry_run.v1",
        "stage": "R3-E_XMLA_EMONDRIAN_END_TO_END_REPLICATION",
        "scientific_role": "SECONDARY_END_TO_END_CONFIRMATION",
        "backend_id": "adventureworks_xmla",
        "adapter": "xmla_mondrian",
        **counts,
        "shared_primary_metrics": list(SHARED_METRICS),
        "xmla_specific_additional_metrics": list(XMLA_METRICS),
        "xmla_specific_confirmatory_p_values_authorized": False,
        "expected_future_arm_receipts": 900,
        "measurement_authorized": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "http_request_executed": False,
        "docker_command_executed": False,
        "database_restore_performed": False,
        "effect_analysis_performed": False,
        "global_system_benefit_claim_authorized": False,
    }


def prove_measurement_refusal(repo: Path) -> None:
    validate_static_authorities(repo)
    raise RuntimeError(
        "R3-E5 is a static executor/receipt contract only; "
        "no R3-E materialization or measured-execution authorization exists"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/workspaces/MCAD_improve3")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prove-measurement-refusal", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()

    if args.prove_measurement_refusal:
        try:
            prove_measurement_refusal(repo)
        except RuntimeError as exc:
            expected = (
                "R3-E5 is a static executor/receipt contract only; "
                "no R3-E materialization or measured-execution authorization exists"
            )
            if str(exc) != expected:
                raise
            print(f"authorization_refusal_reason={exc}")
            print("http_request_executed=false")
            print("docker_command_executed=false")
            print("backend_query_executed=false")
            print("measurement_executed=false")
            print("R3_E5_MEASUREMENT_REFUSAL_PROBE=PASS")
            return
        raise RuntimeError("measurement refusal probe unexpectedly did not refuse")

    result = dry_run(repo)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("R3_E5_XMLA_EXECUTOR_DRY_RUN=PASS_NO_BACKEND_IO")


if __name__ == "__main__":
    main()
