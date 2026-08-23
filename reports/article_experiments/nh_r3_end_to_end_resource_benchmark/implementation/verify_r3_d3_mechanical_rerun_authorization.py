#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
D3_HEAD = "6fedb3ecf8d38680203d1dc07d6d776e651d85e2"
ARCHIVE_SHA = "1c5bb0d802e1400a38c8bd57d629553f331821771d8bfbf83424caecd5d7fb37"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", D3_HEAD, "HEAD"],
        check=True,
    )

    freeze = json.loads(
        (repo / R3 / "results/d3_interrupted_attempt_20260823T211928Z/interruption_freeze.json")
        .read_text(encoding="utf-8")
    )
    auth = json.loads(
        (repo / R3 / "config/r3_d3_mechanical_rerun_authorization.json")
        .read_text(encoding="utf-8")
    )

    if freeze.get("contract_version") != "mcad.nh_r3.d3.interrupted_attempt_freeze.v1":
        raise RuntimeError("unexpected interruption freeze contract")
    if freeze.get("d3_execution_kit_head") != D3_HEAD:
        raise RuntimeError("interruption freeze not bound to D3 kit")
    attempt = freeze.get("attempt") or {}
    if int(attempt.get("partial_arm_receipts_present", -1)) != 297:
        raise RuntimeError("partial receipt count changed")
    if attempt.get("preserved_archive_sha256") != ARCHIVE_SHA:
        raise RuntimeError("preserved archive SHA changed")
    failure = freeze.get("failure_classification") or {}
    if failure.get("mechanical_external_failure") is not True:
        raise RuntimeError("mechanical failure classification missing")
    if failure.get("scientific_failure") is not False:
        raise RuntimeError("interruption incorrectly classified as scientific failure")
    if failure.get("effect_analysis_performed_before_freeze") is not False:
        raise RuntimeError("effect analysis flag violated")
    disposition = freeze.get("scientific_disposition") or {}
    if disposition.get("partial_attempt_excluded_from_final_inference") is not True:
        raise RuntimeError("partial attempt not excluded")
    if disposition.get("resume_from_arm_298_authorized") is not False:
        raise RuntimeError("partial resume unexpectedly authorized")
    if disposition.get("fallback_activation_authorized") is not False:
        raise RuntimeError("fallback unexpectedly authorized")

    if auth.get("contract_version") != "mcad.nh_r3.d3.mechanical_rerun_authorization.v1":
        raise RuntimeError("unexpected mechanical rerun authorization contract")
    if auth.get("parent_d3_execution_kit_head") != D3_HEAD:
        raise RuntimeError("rerun authorization not bound to D3 kit")
    if auth.get("interrupted_attempt_archive_sha256") != ARCHIVE_SHA:
        raise RuntimeError("rerun authorization archive binding changed")
    if auth.get("scientific_plan_changed") is not False:
        raise RuntimeError("scientific plan changed")
    if auth.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("effect-size tuning flag violated")
    if auth.get("interim_effect_analysis_performed") is not False:
        raise RuntimeError("interim effect-analysis flag violated")
    policy = auth.get("rerun_policy") or {}
    expected = {
        "mechanical_full_rerun_scientifically_authorized": True,
        "execution_authorized_now": False,
        "reuse_partial_receipts": False,
        "resume_partial_attempt": False,
        "use_same_primary_300_cohort": True,
        "use_same_primary_schedule": True,
        "use_same_d0_inference_protocol": True,
        "use_same_d1_executor": True,
        "repeat_fixed_7_template_warmup": True,
        "activate_fallback_120": False,
        "effect_based_rerun_or_fallback_forbidden": True,
    }
    for key, value in expected.items():
        if policy.get(key) is not value:
            raise RuntimeError(f"rerun policy mismatch: {key}")
    if policy.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("rerun scope changed")
    if (auth.get("protected_historical_runtime") or {}).get("mutation_authorized") is not False:
        raise RuntimeError("protected historical mutation unexpectedly authorized")
    if auth.get("next") != "R3-D3-R2_STABLE_HOST_RUNTIME_REBIND_AND_PREFLIGHT_NO_MEASUREMENT":
        raise RuntimeError("unexpected next station")

    print("d3_execution_kit_head=" + D3_HEAD)
    print("interrupted_attempt_partial_arm_receipts=297")
    print("interrupted_attempt_archive_sha256=" + ARCHIVE_SHA)
    print("mechanical_external_failure=true")
    print("partial_attempt_excluded_from_final_inference=true")
    print("mechanical_full_rerun_scientifically_authorized=true")
    print("execution_authorized_now=false")
    print("rerun_scope=FULL_PRIMARY_300_FROM_BLOCK_1")
    print("resume_partial_attempt=false")
    print("fallback_120_activated=false")
    print("effect_size_tuning_performed=false")
    print("interim_effect_analysis_performed=false")
    print("protected_historical_runtime_mutation_authorized=false")
    print("R3_D3_MECHANICAL_RERUN_AUTHORIZATION_STATIC_VERIFY=PASS")

if __name__ == "__main__":
    main()
