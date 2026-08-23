#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R2_HEAD = "0a02586b18fe0612d0e058e6029ddd24c536f52a"

EXPECTED_BLOBS = {
    "r2_contract": "52748f1c02cb1dafd0a6f05964ffe2a5af63c48e",
    "r2_receipt": "09a2ed82c0ffc86c567e543aaa9010c409f3ee88",
    "recovery_auth": "14fce8bcc4601947ce82d9dbe686c51286689206",
    "interruption_freeze": "67e256df516bd8079971c1dc645df408804cebe5",
    "d3_contract": "c4e45aa2a04bdb084a2c9a9047f074c31a5cf665",
}


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def check_blob(path: Path, expected: str, label: str) -> None:
    actual = git_blob_sha1(path)
    if actual != expected:
        raise RuntimeError(f"{label} changed: {actual}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", R2_HEAD, "HEAD"],
        check=True,
    )

    check_blob(
        repo / R3 / "config/r3_d3_r2_stable_host_runtime_rebind_contract.json",
        EXPECTED_BLOBS["r2_contract"], "R2 contract"
    )
    check_blob(
        repo / R3 / "results/d3_r2_stable_host_runtime_rebind_receipt.json",
        EXPECTED_BLOBS["r2_receipt"], "R2 runtime receipt"
    )
    check_blob(
        repo / R3 / "config/r3_d3_mechanical_rerun_authorization.json",
        EXPECTED_BLOBS["recovery_auth"], "mechanical rerun authorization"
    )
    check_blob(
        repo / R3 / "results/d3_interrupted_attempt_20260823T211928Z/interruption_freeze.json",
        EXPECTED_BLOBS["interruption_freeze"], "interruption freeze"
    )
    check_blob(
        repo / R3 / "config/r3_d3_primary_confirmatory_execution_contract.json",
        EXPECTED_BLOBS["d3_contract"], "D3 execution contract"
    )

    r2 = json.loads(
        (repo / R3 / "results/d3_r2_stable_host_runtime_rebind_receipt.json")
        .read_text(encoding="utf-8")
    )
    if r2.get("status") != "PASS_READY_FOR_R3_D3_R3":
        raise RuntimeError("R2 runtime receipt not ready for R3")
    if int((r2.get("host") or {}).get("idle_timeout_minutes", -1)) != 240:
        raise RuntimeError("R2 idle timeout binding changed")
    if r2.get("protected_historical_runtime_mutated") is not False:
        raise RuntimeError("R2 indicates historical runtime mutation")
    if r2.get("partial_attempt_reused") is not False:
        raise RuntimeError("R2 indicates partial attempt reuse")
    if r2.get("resume_from_arm_298") is not False:
        raise RuntimeError("R2 indicates partial resume")
    if r2.get("fallback_120_activated") is not False:
        raise RuntimeError("R2 indicates fallback activation")
    if r2.get("measurement_executed") is not False:
        raise RuntimeError("R2 unexpectedly executed measurement")
    if r2.get("backend_query_executed") is not False:
        raise RuntimeError("R2 unexpectedly executed backend query")

    auth = json.loads(
        (repo / R3 / "config/r3_d3_r3_replacement_primary_300_execution_authorization.json")
        .read_text(encoding="utf-8")
    )
    if auth.get("contract_version") != "mcad.nh_r3.d3.r3.replacement_primary_300_execution_authorization.v1":
        raise RuntimeError("unexpected R3 authorization contract")
    if auth.get("parent_r2_head") != R2_HEAD:
        raise RuntimeError("R3 authorization not bound to R2 head")
    if auth.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("R3 analysis class changed")

    execution = auth.get("replacement_execution") or {}
    expected = {
        "mechanical_full_rerun_scientifically_authorized": True,
        "replacement_primary_300_execution_authorized": True,
        "reuse_partial_receipts": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "no_interim_effect_looks": True,
        "no_effect_based_reruns": True,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "confirmatory_claim_authorized": False,
        "repeat_fixed_7_template_warmup": True,
    }
    for key, value in expected.items():
        if execution.get(key) is not value:
            raise RuntimeError(f"R3 execution authorization mismatch: {key}")
    if execution.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("R3 rerun scope changed")
    if execution.get("confirm_token") != "EXECUTE_AUTHORIZED_NH_R3_D3_REPLACEMENT_PRIMARY_300":
        raise RuntimeError("R3 replacement confirm token changed")

    ints = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fresh_gated_sessions_planned": 600,
    }
    for key, value in ints.items():
        if int(execution.get(key, -1)) != value:
            raise RuntimeError(f"R3 execution cardinality mismatch: {key}")

    boundary = auth.get("r3_wrapper_boundary") or {}
    for key in (
        "measurement_executed_in_r3",
        "backend_query_executed_in_r3",
        "docker_or_service_mutation_executed_in_r3",
        "effect_analysis_executed_in_r3",
    ):
        if boundary.get(key) is not False:
            raise RuntimeError(f"R3 wrapper boundary violated: {key}")
    if boundary.get("replacement_measurement_requires_subsequent_explicit_r4_command") is not True:
        raise RuntimeError("R4 explicit-command boundary missing")

    if auth.get("next") != "R3-D3-R4_EXECUTE_REPLACEMENT_PRIMARY_300_ONE_SHOT":
        raise RuntimeError("unexpected R3 next station")

    print("r2_parent_head=" + R2_HEAD)
    print("r2_runtime_receipt=PASS_READY_FOR_R3_D3_R3")
    print("codespace_idle_timeout_bound_minutes=240")
    print("replacement_primary_300_execution_authorized=true")
    print("rerun_scope=FULL_PRIMARY_300_FROM_BLOCK_1")
    print("reuse_partial_receipts=false")
    print("resume_from_arm_298=false")
    print("fallback_120_activated=false")
    print("semantic_sessions_authorized=300")
    print("arm_runs_authorized=900")
    print("candidate_actions_authorized=21600")
    print("gate_evaluations_planned=14400")
    print("full_backend_executions_planned=14580")
    print("fresh_gated_sessions_planned=600")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("docker_or_service_mutation_executed=false")
    print("effect_analysis_executed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D3_R3_REPLACEMENT_AUTHORIZATION_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
