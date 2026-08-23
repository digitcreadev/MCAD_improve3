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
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
C1_HEAD = "082457760ba1602c5eda5f74a9cb653eed3552e1"
C2_HEAD = "31941cc21a099ae931a2b5f6dd0c0f34c8d2a4de"

EXPECTED = {
    "c2_contract_sha256": "568ed447fe8d71f614db06978f932313c633d9a957184a699bbbfd86be944e91",
    "c2_executor_sha256": "c7c7d034aaba3d7ed967ad114e5a1a13cba92a98c68e82346586af1ea42ea7be",
    "c2_static_verifier_sha256": "5ff3d3554e3110c97a23015c2c60151a86407649cd70d26f31f0facab5e2f22d",
    "c2_runtime_preflight_sha256": "2a60cef2ffaa8e0b53ce07f7b6b1708276c076818abedee57565f3ad6a28ee43",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def import_c2(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        return importlib.import_module("r3_c2_validation_executor")
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", C2_HEAD, "HEAD"], check=True)

    c2_contract = r3 / "config/r3_c2_validation_executor_contract.json"
    c2_executor = r3 / "implementation/r3_c2_validation_executor.py"
    c2_verifier = r3 / "implementation/verify_r3_c2_validation_executor_static.py"
    c2_preflight = r3 / "runtime/r3_c2_isolated_runtime_preflight_readonly.sh"
    auth_path = r3 / "config/r3_c3_validation_measurement_authorization.json"

    for path, key in (
        (c2_contract, "c2_contract_sha256"),
        (c2_executor, "c2_executor_sha256"),
        (c2_verifier, "c2_static_verifier_sha256"),
        (c2_preflight, "c2_runtime_preflight_sha256"),
    ):
        actual = sha256(path)
        if actual != EXPECTED[key]:
            raise RuntimeError(f"{path.name}: frozen C2 authority changed")

    data = json.loads(auth_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.c3.validation_measurement_authorization.v1":
        raise RuntimeError("unexpected C3 authorization contract version")
    if data.get("c1_head") != C1_HEAD or data.get("c2_head") != C2_HEAD:
        raise RuntimeError("C3 authorization not bound to frozen C1/C2 checkpoints")
    if data.get("analysis_class") != "VALIDATION_CALIBRATION_NONCONFIRMATORY":
        raise RuntimeError("C3 analysis class changed")

    scope = data.get("validation_scope")
    if not isinstance(scope, dict):
        raise RuntimeError("C3 validation scope missing")
    expected_scope = {
        "semantic_sessions": 40,
        "arm_runs": 120,
        "candidate_actions": 2880,
        "gate_evaluations_planned": 1920,
        "gated_arm_runs": 80,
        "ungated_arm_runs": 40,
        "mcad_api_restarts_planned": 120,
        "fresh_mcad_sessions_planned": 80,
    }
    for key, value in expected_scope.items():
        if int(scope.get(key, -1)) != value:
            raise RuntimeError(f"C3 scope mismatch: {key}")
    if scope.get("selection_role") != "CALIBRATION_NO_EFFECT_TUNING":
        raise RuntimeError("C3 selection role changed")
    for key in (
        "effect_size_tuning_allowed",
        "cohort_change_allowed",
        "arm_order_change_allowed",
        "completion_boundary_change_allowed",
        "live_gate_may_relabel_frozen_action",
    ):
        if scope.get(key) is not False:
            raise RuntimeError(f"C3 forbidden scope flag changed: {key}")

    auth = data.get("authorization")
    if not isinstance(auth, dict):
        raise RuntimeError("C3 authorization payload missing")
    if auth.get("validation_measured_execution_authorized") is not True:
        raise RuntimeError("C3 measured validation authorization missing")
    if auth.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("C3 cannot authorize confirmatory claims")
    if auth.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("C3 effect-size tuning flag violated")
    if auth.get("scientific_redesign_performed") is not False:
        raise RuntimeError("C3 scientific redesign flag violated")
    if auth.get("runtime_project") != "mcad-r3-rerun1":
        raise RuntimeError("C3 runtime project changed")
    if auth.get("explicit_confirm_token") != "EXECUTE_AUTHORIZED_NH_R3_C_VALIDATION_40":
        raise RuntimeError("C3 confirmation token changed")

    c2 = import_c2(repo)
    dry = c2.dry_run(repo)
    for key, value in expected_scope.items():
        if key in dry and int(dry[key]) != value:
            raise RuntimeError(f"C2 dry-run/C3 scope mismatch: {key}")
    if dry["measurement_executed"] is not False:
        raise RuntimeError("C2 dry-run unexpectedly measured")
    if dry["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("C2 dry-run confirmatory boundary changed")

    validated = c2.validate_future_authorization(repo)
    if validated != data:
        raise RuntimeError("C2 authorization reader did not accept exact C3 authorization")
    if c2.CONFIRM_TOKEN != "EXECUTE_AUTHORIZED_NH_R3_C_VALIDATION_40":
        raise RuntimeError("C2 executor confirmation token changed")

    boundary = data.get("measurement_boundary")
    if not isinstance(boundary, dict):
        raise RuntimeError("C3 measurement boundary missing")
    for key in (
        "R3_C3_performs_measurement",
        "R3_C3_performs_backend_query",
        "R3_C3_performs_service_mutation",
        "R3_C3_performs_docker_mutation",
    ):
        if boundary.get(key) is not False:
            raise RuntimeError(f"C3 premeasurement boundary violated: {key}")

    print("c3_authorization_contract=PASS")
    print("c3_bound_to_c1_head=" + C1_HEAD)
    print("c3_bound_to_c2_head=" + C2_HEAD)
    print("r3c_semantic_sessions=40")
    print("r3c_arm_runs=120")
    print("r3c_candidate_actions=2880")
    print("r3c_gate_evaluations_planned=1920")
    print("validation_measured_execution_authorized=true")
    print("confirmatory_claim_authorized=false")
    print("effect_size_tuning_performed=false")
    print("scientific_redesign_performed=false")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("docker_mutation_performed=false")
    print("R3_C3_VALIDATION_AUTHORIZATION_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
