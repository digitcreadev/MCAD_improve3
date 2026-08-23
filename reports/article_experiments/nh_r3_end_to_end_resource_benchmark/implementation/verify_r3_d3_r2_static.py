#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
PARENT = "af03ce42ec9e35293b438aa1924b7f8eb76c5449"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT, "HEAD"],
        check=True,
    )

    contract = json.loads(
        (repo / R3 / "config/r3_d3_r2_stable_host_runtime_rebind_contract.json")
        .read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.d3.r2.stable_host_runtime_rebind.v1":
        raise RuntimeError("unexpected R2 contract")
    if contract.get("parent_recovery_head") != PARENT:
        raise RuntimeError("R2 contract not bound to recovery checkpoint")

    host = contract.get("host") or {}
    if int(host.get("required_idle_timeout_minutes_for_this_rebind", -1)) != 240:
        raise RuntimeError("R2 host timeout requirement changed")
    if host.get("measurement_authorized_in_this_station") is not False:
        raise RuntimeError("R2 unexpectedly authorizes measurement")

    protected = contract.get("protected_historical_runtime") or {}
    if protected.get("must_remain_exited") is not True:
        raise RuntimeError("protected historical runtime exit preservation changed")
    for key in ("start_allowed", "restart_allowed", "mutation_allowed"):
        if protected.get(key) is not False:
            raise RuntimeError(f"protected historical runtime boundary violated: {key}")

    clone = contract.get("isolated_clone_rebind") or {}
    if clone.get("start_exact_existing_clone_containers_allowed") is not True:
        raise RuntimeError("exact isolated clone start not authorized")
    for key in ("recreate_allowed", "rebuild_allowed", "pull_allowed",
                "backend_query_allowed_in_this_station", "measurement_allowed_in_this_station"):
        if clone.get(key) is not False:
            raise RuntimeError(f"R2 isolated clone boundary violated: {key}")

    sci = contract.get("scientific_boundary") or {}
    expected = {
        "mechanical_full_rerun_scientifically_authorized": True,
        "full_rerun_execution_authorized_now": False,
        "reuse_partial_receipts": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "scientific_plan_changed": False,
        "effect_size_tuning_performed": False,
        "interim_effect_analysis_performed": False,
    }
    for key, value in expected.items():
        if sci.get(key) is not value:
            raise RuntimeError(f"R2 scientific boundary mismatch: {key}")
    if sci.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("R2 rerun scope changed")

    if contract.get("next") != "R3-D3-R3_REPLACEMENT_PRIMARY_300_EXECUTION_AUTHORIZATION_AND_PREMEASUREMENT_GATE":
        raise RuntimeError("unexpected R2 next station")

    print("parent_recovery_head=" + PARENT)
    print("codespace_idle_timeout_required_minutes=240")
    print("protected_historical_runtime_must_remain_exited=true")
    print("isolated_clone_exact_start_allowed=true")
    print("isolated_clone_recreate_allowed=false")
    print("backend_query_allowed=false")
    print("measurement_allowed=false")
    print("full_rerun_execution_authorized_now=false")
    print("rerun_scope=FULL_PRIMARY_300_FROM_BLOCK_1")
    print("fallback_120_activated=false")
    print("R3_D3_R2_STATIC_VERIFY=PASS")

if __name__ == "__main__":
    main()
