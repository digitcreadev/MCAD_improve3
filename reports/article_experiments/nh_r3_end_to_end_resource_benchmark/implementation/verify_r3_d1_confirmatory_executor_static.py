#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
D0_HEAD = "f610dd5d1a61830385bb11f537eb1d740bb0ccc6"

EXPECTED_BLOBS = {
    "d0_contract": "6c608b951bca9b262cc69bb7964a48cec79c62b1",
    "d0_inference": "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb",
    "d0_plan": "54750b314717dc370ca65f84ca765c338b4abb2c",
    "primary_schedule": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    "fallback_schedule": "bae0fd86e18236296c94b5b404203f06f4ad55b5",
    "b2e": "5eeaf00e00dfd6561959c81941acc902acf8b509",
    "b2k": "41792ef397834dcea7369882c6273e693d2608e9",
    "compose": "f807f35039d89ac5dae153fb3fa36d99f4a33e53",
}


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", D0_HEAD, "HEAD"],
        check=True,
    )

    paths = {
        "d0_contract": r3 / "config/r3_d0_confirmatory_static_activation_contract.json",
        "d0_inference": r3 / "config/r3_d0_confirmatory_inference_protocol.json",
        "d0_plan": r3 / "implementation/r3_d0_confirmatory_plan.py",
        "primary_schedule": r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv",
        "fallback_schedule": r3 / "config/r3_d0_confirmatory_fallback_arm_order_schedule.csv",
        "b2e": r3 / "implementation/r3_dev_pilot_executor.py",
        "b2k": r3 / "implementation/r3_isolated_executor_adapter.py",
        "compose": r3 / "runtime/r3_isolated_runtime.compose.yml",
    }
    for key, path in paths.items():
        actual = git_blob_sha1(path)
        if actual != EXPECTED_BLOBS[key]:
            raise RuntimeError(f"frozen authority changed: {key} -> {actual}")

    contract = json.loads(
        (r3 / "config/r3_d1_confirmatory_executor_contract.json").read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.d1.confirmatory_executor_preflight.v1":
        raise RuntimeError("unexpected D1 contract")
    if contract.get("parent_d0_head") != D0_HEAD:
        raise RuntimeError("D1 not bound to D0 head")
    if contract.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("D1 analysis class changed")
    if (contract.get("fallback_firewall") or {}).get("fallback_activation_authorized_now") is not False:
        raise RuntimeError("fallback unexpectedly activated")
    auth = contract.get("d1_authorization") or {}
    for key in (
        "measurement_authorized",
        "backend_query_authorized",
        "docker_mutation_authorized",
        "service_mutation_authorized",
        "confirmatory_claim_authorized",
        "effect_size_tuning_allowed",
        "scientific_redesign_allowed",
        "r3c_rerun_authorized",
    ):
        if auth.get(key) is not False:
            raise RuntimeError(f"D1 authorization boundary violated: {key}")

    impl = r3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        d1 = importlib.import_module("r3_d1_confirmatory_executor")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    dry = d1.dry_run(repo)
    expected = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "gated_arm_runs": 600,
        "ungated_arm_runs": 300,
        "mcad_api_restarts_planned": 900,
        "fresh_mcad_sessions_planned": 600,
    }
    for key, value in expected.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"D1 dry-run mismatch: {key}")
    if dry.get("selection_role") != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("D1 primary role changed")
    if dry.get("historical_compose_targeted") is not False:
        raise RuntimeError("D1 historical compose routing leak")
    if dry.get("fallback_activation_authorized_now") is not False:
        raise RuntimeError("D1 fallback activated")
    if dry.get("measurement_executed") is not False:
        raise RuntimeError("D1 dry-run executed measurement")
    if dry.get("backend_query_executed") is not False:
        raise RuntimeError("D1 dry-run executed backend query")
    if dry.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("D1 prematurely authorized claim")

    auth_path = repo / R3_REL / "config/r3_d2_confirmatory_measurement_authorization.json"
    if auth_path.exists():
        raise RuntimeError("D2 measurement authorization must not exist during D1")

    print("d0_parent_head=" + D0_HEAD)
    print("primary_semantic_sessions=300")
    print("primary_arm_runs=900")
    print("primary_candidate_actions=21600")
    print("primary_gate_evaluations_planned=14400")
    print("primary_full_backend_executions_planned=14580")
    print("primary_gated_arm_runs=600")
    print("primary_ungated_arm_runs=300")
    print("primary_mcad_api_restarts_planned=900")
    print("primary_fresh_gated_sessions_planned=600")
    print("fallback_activation_authorized_now=false")
    print("future_D2_authorization_present=false")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("docker_command_executed=false")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D1_CONFIRMATORY_EXECUTOR_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
