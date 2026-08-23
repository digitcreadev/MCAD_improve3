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
C3_HEAD = "266bc62593652547b3184969e4003fe2178843f8"

EXPECTED = {
    "c1_plan": "76d44e02ae57edd5caa570833e02f65bbabaf361c8e7da6c3c089f6cf065a551",
    "c2_executor": "c7c7d034aaba3d7ed967ad114e5a1a13cba92a98c68e82346586af1ea42ea7be",
    "c3_auth": "4e374d1d216037f8fda7ac021a12501fa12fe82d371f9d3345d6b0dcbfa895c8",
    "c3_verify": "a3bbf880430ce2d934e80845627641827c045b1f31c4db005ea4393f85bbd288",
    "c3_pre": "20290cc4d1701f178a3146b8f9876d0da936c334b5e37d863aac68355682d88c",
}

EXPECTED_TEMPLATES = (
    "AW_ATOM_COST",
    "AW_ATOM_MARGIN",
    "AW_ATOM_SALES",
    "AW_BAD_GRAIN_YEAR",
    "AW_DISTRACTOR_ACCESSORIES_SALES",
    "AW_MIX_ACCESSORIES_SALES_COST",
    "AW_PAIR_SALES_COST",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", C3_HEAD, "HEAD"], check=True)

    paths = {
        "c1_plan": r3 / "implementation/r3_c1_validation_plan.py",
        "c2_executor": r3 / "implementation/r3_c2_validation_executor.py",
        "c3_auth": r3 / "config/r3_c3_validation_measurement_authorization.json",
        "c3_verify": r3 / "implementation/verify_r3_c3_validation_authorization.py",
        "c3_pre": r3 / "runtime/r3_c3_one_shot_premeasurement_readonly.sh",
    }
    for key, path in paths.items():
        if sha256(path) != EXPECTED[key]:
            raise RuntimeError(f"frozen authority changed: {key}")

    contract_path = r3 / "config/r3_c4_validation_execution_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != "mcad.nh_r3.c4.validation_execution_kit.v1":
        raise RuntimeError("unexpected C4 execution contract")
    if contract.get("parent_c3_head") != C3_HEAD:
        raise RuntimeError("C4 contract not bound to C3")
    if contract.get("analysis_class") != "VALIDATION_CALIBRATION_NONCONFIRMATORY":
        raise RuntimeError("C4 analysis class changed")
    if contract["warmup"]["measured"] is not False:
        raise RuntimeError("warmup unexpectedly measured")
    if tuple(contract["warmup"]["unique_templates"]) != EXPECTED_TEMPLATES:
        raise RuntimeError("warmup template list changed")
    if contract["warmup"]["sqlserver_restart_after_warmup"] is not False:
        raise RuntimeError("SQL Server restart after warmup is forbidden")
    if contract["measurement"]["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("C4 cannot authorize confirmatory claims")
    if contract["measurement"]["effect_size_tuning_allowed"] is not False:
        raise RuntimeError("C4 effect-size tuning forbidden")
    if contract["runtime"]["historical_runtime_mutation_allowed"] is not False:
        raise RuntimeError("historical runtime mutation forbidden")
    if contract["integrity"]["negative_cgroup_delta_policy"] != "invalidate arm run; never clamp to zero":
        raise RuntimeError("negative cgroup policy changed")

    impl = r3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        c4 = importlib.import_module("r3_c4_validation_one_shot")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    dry = c4.dry_run(repo)
    expected = {
        "semantic_sessions": 40,
        "arm_runs": 120,
        "candidate_actions": 2880,
        "gate_evaluations_planned": 1920,
        "gated_arm_runs": 80,
        "ungated_arm_runs": 40,
        "mcad_api_restarts_planned": 120,
        "fresh_mcad_sessions_planned": 80,
    }
    for key, value in expected.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"C4 dry-run mismatch: {key}")
    if tuple(dry["warmup_templates"]) != EXPECTED_TEMPLATES:
        raise RuntimeError("C4 dry-run warmup template mismatch")
    if dry["warmup_measured"] is not False:
        raise RuntimeError("C4 dry-run warmup measured")
    if dry["validation_measured_execution_authorized"] is not True:
        raise RuntimeError("C3 authorization not visible to C4")
    if dry["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("C4 dry-run confirmatory boundary violated")
    if dry["measurement_executed"] is not False or dry["backend_query_executed"] is not False:
        raise RuntimeError("C4 dry-run executed work")

    print("c4_parent_c3_head=" + C3_HEAD)
    print("warmup_templates=7")
    print("warmup_measured=false")
    print("r3c_semantic_sessions=40")
    print("r3c_arm_runs=120")
    print("r3c_candidate_actions=2880")
    print("r3c_gate_evaluations_planned=1920")
    print("validation_measured_execution_authorized=true")
    print("confirmatory_claim_authorized=false")
    print("effect_size_tuning_performed=false")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("R3_C4_EXECUTION_KIT_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
