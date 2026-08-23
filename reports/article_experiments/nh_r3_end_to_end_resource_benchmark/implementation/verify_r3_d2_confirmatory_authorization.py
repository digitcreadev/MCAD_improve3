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
D1_HEAD = "f567b869a7cea486a780b35bf4acc873245fda88"

EXPECTED = {
    "d1_contract_blob": "879cfbd3be42831fa74cc43737ca6cf23454fee4",
    "d1_contract_sha": "ebb654a6ededd99edf6c86aa2841aacfbb1504857db457173fee1bfb5b7749ae",
    "d1_executor_blob": "ee0fb893a35086d01a69ee4eb8d70166ba2bb7b0",
    "d1_executor_sha": "b4e024ab12940a9824f39188e8b79e0974f166d7b98ac04ab7afe70082a012ae",
    "d1_verify_blob": "c877c781e8dc67de5eb89c9682a9941a6add003f",
    "d1_verify_sha": "cb6728c73de26128ccbd52071f4396ac32f1ee5356e2461b1620e666fda6e513",
    "d1_preflight_blob": "9d45411272403731724263f3c86ef404e63fc3ce",
    "d1_preflight_sha": "20cc626dbd3f141685b4a12a9832ad70e75091344d47398034823a8ea19afc34",
    "d0_inference_blob": "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb",
    "primary_schedule_blob": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def check_identity(path: Path, blob: str, sha: str | None, label: str) -> None:
    actual_blob = git_blob_sha1(path)
    if actual_blob != blob:
        raise RuntimeError(f"{label} git blob changed: {actual_blob}")
    if sha is not None:
        actual_sha = sha256(path)
        if actual_sha != sha:
            raise RuntimeError(f"{label} sha256 changed: {actual_sha}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", D1_HEAD, "HEAD"],
        check=True,
    )

    check_identity(
        r3 / "config/r3_d1_confirmatory_executor_contract.json",
        EXPECTED["d1_contract_blob"], EXPECTED["d1_contract_sha"], "D1 contract"
    )
    check_identity(
        r3 / "implementation/r3_d1_confirmatory_executor.py",
        EXPECTED["d1_executor_blob"], EXPECTED["d1_executor_sha"], "D1 executor"
    )
    check_identity(
        r3 / "implementation/verify_r3_d1_confirmatory_executor_static.py",
        EXPECTED["d1_verify_blob"], EXPECTED["d1_verify_sha"], "D1 static verifier"
    )
    check_identity(
        r3 / "runtime/r3_d1_isolated_runtime_preflight_readonly.sh",
        EXPECTED["d1_preflight_blob"], EXPECTED["d1_preflight_sha"], "D1 runtime preflight"
    )
    check_identity(
        r3 / "config/r3_d0_confirmatory_inference_protocol.json",
        EXPECTED["d0_inference_blob"], None, "D0 inference protocol"
    )
    check_identity(
        r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv",
        EXPECTED["primary_schedule_blob"], None, "D0 primary schedule"
    )

    auth_path = r3 / "config/r3_d2_confirmatory_measurement_authorization.json"
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.d2.confirmatory_measurement_authorization.v1":
        raise RuntimeError("unexpected D2 authorization contract")
    if data.get("d0_head") != D0_HEAD:
        raise RuntimeError("D2 authorization not bound to D0")
    if data.get("d1_head") != D1_HEAD:
        raise RuntimeError("D2 authorization not bound to D1")
    if data.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("D2 analysis class changed")

    auth = data.get("authorization") or {}
    required = {
        "primary_300_measured_execution_authorized": True,
        "fallback_120_activated": False,
        "fallback_activation_from_observed_effects_forbidden": True,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "confirmatory_claim_authorized": False,
        "no_interim_effect_looks": True,
        "no_effect_based_reruns": True,
        "automatic_rerun": False,
    }
    for key, value in required.items():
        if auth.get(key) is not value:
            raise RuntimeError(f"D2 authorization field mismatch: {key}")

    primary = data.get("primary_execution") or {}
    expected_ints = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "gated_arm_runs": 600,
        "ungated_arm_runs": 300,
        "mcad_api_restarts_planned": 900,
        "fresh_gated_sessions_planned": 600,
    }
    for key, value in expected_ints.items():
        if int(primary.get(key, -1)) != value:
            raise RuntimeError(f"D2 primary execution mismatch: {key}")
    if primary.get("confirm_token") != "EXECUTE_AUTHORIZED_NH_R3_D_CONFIRMATORY_PRIMARY_300":
        raise RuntimeError("D2 confirm token changed")

    impl = r3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        d1 = importlib.import_module("r3_d1_confirmatory_executor")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    executor_auth = d1.validate_future_authorization(repo)
    if executor_auth.get("d1_head") != D1_HEAD:
        raise RuntimeError("D1 executor did not read D2 authorization bound to D1")

    dry = d1.dry_run(repo)
    expected_dry = {
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
    for key, value in expected_dry.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"D1 executor dry-run diverges after D2 authorization: {key}")
    if dry.get("fallback_activation_authorized_now") is not False:
        raise RuntimeError("fallback activated after D2 authorization")
    if dry.get("measurement_executed") is not False:
        raise RuntimeError("D2 static verification executed measurement")
    if dry.get("backend_query_executed") is not False:
        raise RuntimeError("D2 static verification executed backend query")

    print("d1_parent_head=" + D1_HEAD)
    print("d0_head=" + D0_HEAD)
    print("primary_semantic_sessions=300")
    print("primary_arm_runs=900")
    print("primary_candidate_actions=21600")
    print("primary_gate_evaluations_planned=14400")
    print("primary_full_backend_executions_planned=14580")
    print("fallback_120_activated=false")
    print("primary_300_measured_execution_authorized=true")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("docker_command_executed=false")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D2_CONFIRMATORY_AUTHORIZATION_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
