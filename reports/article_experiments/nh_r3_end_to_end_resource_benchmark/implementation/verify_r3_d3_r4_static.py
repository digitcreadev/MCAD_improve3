#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R3_HEAD = "41b2369a83a3073d986691bdf7293d322d8d7851"


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", R3_HEAD, "HEAD"],
        check=True,
    )

    contract = json.loads(
        (repo / R3 / "config/r3_d3_r4_replacement_execution_contract.json")
        .read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.d3.r4.replacement_primary_300_execution_kit.v1":
        raise RuntimeError("unexpected R4 contract")
    if contract.get("parent_r3_head") != R3_HEAD:
        raise RuntimeError("R4 contract not bound to R3 authorization head")

    frozen = contract.get("frozen_authorities") or {}
    expected_blobs = {
        "r3_replacement_authorization_git_blob": (
            repo / R3 / "config/r3_d3_r3_replacement_primary_300_execution_authorization.json",
            "904a345e1174afc2a482c459dbbba2909905329c",
        ),
        "r2_runtime_receipt_git_blob": (
            repo / R3 / "results/d3_r2_stable_host_runtime_rebind_receipt.json",
            "09a2ed82c0ffc86c567e543aaa9010c409f3ee88",
        ),
        "d3_primary_driver_git_blob": (
            repo / R3 / "implementation/r3_d3_primary_confirmatory_one_shot.py",
            "5563c6324f527a776ffb1ff29f4de0c07a8d744e",
        ),
        "d3_execution_contract_git_blob": (
            repo / R3 / "config/r3_d3_primary_confirmatory_execution_contract.json",
            "c4e45aa2a04bdb084a2c9a9047f074c31a5cf665",
        ),
        "interruption_freeze_git_blob": (
            repo / R3 / "results/d3_interrupted_attempt_20260823T211928Z/interruption_freeze.json",
            "67e256df516bd8079971c1dc645df408804cebe5",
        ),
    }
    for field, (path, expected) in expected_blobs.items():
        if frozen.get(field) != expected:
            raise RuntimeError(f"R4 frozen authority field changed: {field}")
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"R4 authority blob changed: {path} -> {actual}")

    execution = contract.get("replacement_execution") or {}
    expected_bool = {
        "authorized": True,
        "repeat_fixed_7_template_warmup": True,
        "reuse_partial_receipts": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "no_interim_effect_looks": True,
        "effect_analysis_in_execution_wrapper": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "confirmatory_claim_authorized_during_execution": False,
    }
    for key, value in expected_bool.items():
        if execution.get(key) is not value:
            raise RuntimeError(f"R4 execution boundary mismatch: {key}")
    if execution.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("R4 rerun scope changed")
    if execution.get("external_confirm_token") != "EXECUTE_AUTHORIZED_NH_R3_D3_REPLACEMENT_PRIMARY_300":
        raise RuntimeError("R4 external confirm token changed")

    expected_int = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fresh_gated_sessions_planned": 600,
    }
    for key, value in expected_int.items():
        if int(execution.get(key, -1)) != value:
            raise RuntimeError(f"R4 execution cardinality mismatch: {key}")

    impl = repo / R3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        r4 = importlib.import_module("r3_d3_r4_replacement_primary_one_shot")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    dry = r4.dry_run(repo)
    for key, value in expected_int.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"R4 dry-run mismatch: {key}")
    if dry.get("replacement_primary_300_execution_authorized") is not True:
        raise RuntimeError("R4 dry-run authorization missing")
    if dry.get("reuse_partial_receipts") is not False:
        raise RuntimeError("R4 dry-run partial reuse")
    if dry.get("resume_from_arm_298") is not False:
        raise RuntimeError("R4 dry-run partial resume")
    if dry.get("fallback_120_activated") is not False:
        raise RuntimeError("R4 dry-run fallback activation")
    if dry.get("measurement_executed") is not False:
        raise RuntimeError("R4 static verify executed measurement")
    if dry.get("backend_query_executed") is not False:
        raise RuntimeError("R4 static verify executed backend query")
    if dry.get("effect_analysis_performed") is not False:
        raise RuntimeError("R4 static verify executed effect analysis")

    print("r3_parent_head=" + R3_HEAD)
    print("replacement_primary_300_execution_authorized=true")
    print("rerun_scope=FULL_PRIMARY_300_FROM_BLOCK_1")
    print("semantic_sessions=300")
    print("arm_runs=900")
    print("candidate_actions=21600")
    print("gate_evaluations_planned=14400")
    print("full_backend_executions_planned=14580")
    print("fresh_gated_sessions_planned=600")
    print("reuse_partial_receipts=false")
    print("resume_from_arm_298=false")
    print("fallback_120_activated=false")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("effect_analysis_performed=false")
    print("R3_D3_R4_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
