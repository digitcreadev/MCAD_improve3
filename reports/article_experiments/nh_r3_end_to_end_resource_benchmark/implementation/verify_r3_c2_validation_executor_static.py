#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
EXPECTED_HEAD = "082457760ba1602c5eda5f74a9cb653eed3552e1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", EXPECTED_HEAD, "HEAD"], check=True)

    contract_path = r3 / "config/r3_c2_validation_executor_contract.json"
    executor_path = r3 / "implementation/r3_c2_validation_executor.py"
    c1_contract = r3 / "config/r3_c1_validation_stage_contract.json"
    c1_schedule = r3 / "config/r3_c1_arm_order_schedule.csv"
    c1_plan_path = r3 / "implementation/r3_c1_validation_plan.py"
    b2e_path = r3 / "implementation/r3_dev_pilot_executor.py"
    b2k_path = r3 / "implementation/r3_isolated_executor_adapter.py"
    compose_path = r3 / "runtime/r3_isolated_runtime.compose.yml"

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["contract_version"] != "mcad.nh_r3.c2.validation_executor_preflight.v1.2":
        raise RuntimeError("unexpected C2 contract version")
    if contract["authorization"]["measurement_authorized"] is not False:
        raise RuntimeError("C2 measurement must remain unauthorized")
    if contract["authorization"]["backend_query_authorized"] is not False:
        raise RuntimeError("C2 backend queries must remain unauthorized")
    if contract["authorization"]["service_mutation_authorized"] is not False:
        raise RuntimeError("C2 service mutation must remain unauthorized")
    if contract["authorization"]["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("C2 confirmatory claims must remain unauthorized")
    if contract["executor_specialization"]["safe_pruning_semantics_reimplemented"] is not False:
        raise RuntimeError("C2 may not reimplement safe-pruning semantics")

    expected_blobs = contract["c1_authorities"]
    if git_blob_sha1(c1_contract) != expected_blobs["contract_git_blob"]:
        raise RuntimeError("C1 contract blob changed")
    if git_blob_sha1(c1_schedule) != expected_blobs["schedule_git_blob"]:
        raise RuntimeError("C1 schedule blob changed")
    if git_blob_sha1(c1_plan_path) != expected_blobs["validation_plan_git_blob"]:
        raise RuntimeError("C1 plan blob changed")
    if sha256(c1_schedule) != expected_blobs["schedule_sha256"]:
        raise RuntimeError("C1 schedule SHA changed")
    if sha256(c1_plan_path) != expected_blobs["validation_plan_sha256"]:
        raise RuntimeError("C1 plan SHA changed")

    op = contract["frozen_operational_authorities"]
    if git_blob_sha1(b2e_path) != op["b2e_executor_git_blob"]:
        raise RuntimeError("B2e executor blob changed")
    if git_blob_sha1(b2k_path) != op["b2k_isolated_adapter_git_blob"]:
        raise RuntimeError("B2k adapter blob changed")
    if git_blob_sha1(compose_path) != op["isolated_compose_git_blob"]:
        raise RuntimeError("isolated compose blob changed")

    tree = ast.parse(executor_path.read_text(encoding="utf-8"))
    function_names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required = {
        "validate_static_authorities",
        "validate_future_authorization",
        "dry_run",
        "run_validation",
        "main",
    }
    if not required <= function_names:
        raise RuntimeError(f"C2 executor missing functions: {sorted(required-function_names)}")

    implementation = r3 / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        c2 = importlib.import_module("r3_c2_validation_executor")
        c1 = importlib.import_module("r3_c1_validation_plan")
        frozen = importlib.import_module("r3_resource_runner")
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass

    plan = c1.build_plan(repo)
    if plan["semantic_sessions"] != 40 or len(plan["arm_runs"]) != 120 or len(plan["candidate_actions"]) != 2880:
        raise RuntimeError("C1 validation plan cardinality changed")

    # Recompute every scientific action from the frozen runner.
    for action in plan["candidate_actions"]:
        expected_gate = bool(frozen.frozen_gate_rule(str(action["arm"])))
        # r3_c1_validation_plan intentionally normalizes the original binding-row
        # fields class/operational_action into frozen_class/frozen_operational_action.
        # Reconstruct only that frozen scientific-rule input envelope here.
        rule_row = {
            "class": str(action["frozen_class"]),
            "operational_action": str(action["frozen_operational_action"]),
        }
        expected_full = bool(frozen.frozen_full_execute_rule(str(action["arm"]), rule_row))
        if bool(action["run_gate"]) != expected_gate:
            raise RuntimeError(
                f"C2/C1 gate action diverges from frozen scientific rule: "
                f"{action['session_id']}/{action['arm']}/candidate={action['candidate_index']}"
            )
        if bool(action["run_full_backend"]) != expected_full:
            raise RuntimeError(
                f"C2/C1 full-execute action diverges from frozen scientific rule: "
                f"{action['session_id']}/{action['arm']}/candidate={action['candidate_index']} "
                f"stored={bool(action['run_full_backend'])} expected={expected_full} "
                f"class={action['frozen_class']} action={action['frozen_operational_action']}"
            )

    dry = c2.dry_run(repo)
    expected = contract["validation_execution_plan"]
    checks = {
        "semantic_sessions": 40,
        "arm_runs": 120,
        "candidate_actions": 2880,
        "gate_evaluations_planned": 1920,
        "gated_arm_runs": 80,
        "ungated_arm_runs": 40,
        "mcad_api_restarts_planned": 120,
        "fresh_mcad_sessions_planned": 80,
    }
    for key, value in checks.items():
        if int(dry[key]) != value or int(expected[key]) != value:
            raise RuntimeError(f"C2 dry-run mismatch: {key}")
    if dry["historical_compose_targeted"] is not False:
        raise RuntimeError("historical compose routing leaked")
    if dry["isolated_project"] != "mcad-r3-rerun1":
        raise RuntimeError("isolated project changed")
    if dry["measurement_authorized"] is not False or dry["measurement_executed"] is not False:
        raise RuntimeError("C2 dry-run measurement flag violated")

    auth_path = r3 / "config/r3_c3_validation_measurement_authorization.json"
    if auth_path.exists():
        raise RuntimeError("future R3-C3 authorization unexpectedly exists during C2")

    print("r3c_semantic_sessions=40")
    print("r3c_arm_runs=120")
    print("r3c_candidate_actions=2880")
    print("r3c_gate_evaluations_planned=1920")
    print("r3c_gated_arms=80")
    print("r3c_ungated_arms=40")
    print("scientific_action_equivalence=PASS")
    print("isolated_routing_static_equivalence=PASS")
    print("future_measurement_authorization_present=false")
    print("measurement_executed=false")
    print("docker_command_executed=false")
    print("R3_C2_VALIDATION_EXECUTOR_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
