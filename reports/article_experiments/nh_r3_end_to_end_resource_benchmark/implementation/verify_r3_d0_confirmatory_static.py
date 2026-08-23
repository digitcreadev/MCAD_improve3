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
PARENT_HEAD = "9ddfbbdbb62bffc9cf9e7201a804814a09931a70"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT_HEAD, "HEAD"],
        check=True,
    )

    contract = json.loads(
        (r3 / "config/r3_d0_confirmatory_static_activation_contract.json")
        .read_text(encoding="utf-8")
    )
    inference = json.loads(
        (r3 / "config/r3_d0_confirmatory_inference_protocol.json")
        .read_text(encoding="utf-8")
    )

    if contract.get("contract_version") != "mcad.nh_r3.d0.confirmatory_static_activation.v1":
        raise RuntimeError("unexpected D0 activation contract")
    if contract.get("parent_r3c5_head") != PARENT_HEAD:
        raise RuntimeError("D0 activation not bound to C5")
    if contract.get("r3c_readiness") != "PASS_READY_FOR_R3D_STATIC_ACTIVATION":
        raise RuntimeError("D0 activation missing C5 readiness")
    auth = contract.get("authorization") or {}
    for key in (
        "measurement_authorized",
        "backend_query_authorized",
        "docker_or_service_mutation_authorized",
        "confirmatory_claim_authorized",
        "effect_size_tuning_allowed",
        "scientific_redesign_allowed",
        "r3c_rerun_authorized",
    ):
        if auth.get(key) is not False:
            raise RuntimeError(f"D0 authorization boundary violated: {key}")

    if inference.get("contract_version") != "mcad.nh_r3.d0.confirmatory_inference_protocol.v1":
        raise RuntimeError("unexpected D0 inference protocol")
    if inference.get("frozen_before_test_measurement") is not True:
        raise RuntimeError("confirmatory inference not frozen before test measurement")
    primary_family = inference.get("primary_endpoint_family") or {}
    metrics = primary_family.get("metrics") or []
    if len(metrics) != 8 or len(set(metrics)) != 8:
        raise RuntimeError("primary confirmatory metric family must contain exactly 8 unique metrics")
    if primary_family.get("familywise_alpha") != 0.05:
        raise RuntimeError("confirmatory alpha changed")
    if primary_family.get("multiplicity") != "Holm step-down across all 8 frozen primary metrics":
        raise RuntimeError("confirmatory multiplicity procedure changed")
    if int((primary_family.get("permutation_test") or {}).get("replicates", -1)) != 100000:
        raise RuntimeError("permutation replicate count changed")
    if int((primary_family.get("confidence_interval") or {}).get("replicates", -1)) != 20000:
        raise RuntimeError("bootstrap replicate count changed")
    if (inference.get("secondary_break_even_family") or {}).get("confirmatory_p_value") is not False:
        raise RuntimeError("secondary ungated comparison improperly promoted")
    if (inference.get("integrity_and_rerun_rules") or {}).get("no_effect_based_reruns") is not True:
        raise RuntimeError("no-effect-based-rerun rule changed")
    if (inference.get("quota_fallback") or {}).get("effect_based_fallback_forbidden") is not True:
        raise RuntimeError("effect-based fallback unexpectedly allowed")

    impl = r3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        d0 = importlib.import_module("r3_d0_confirmatory_plan")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    primary = d0.summary(d0.build_plan(repo, "primary"))
    fallback = d0.summary(d0.build_plan(repo, "fallback"))

    expected_primary = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gated_arm_runs": 600,
        "ungated_arm_runs": 300,
        "gate_evaluations_planned": 14400,
        "mcad_api_restarts_planned": 900,
        "fresh_mcad_sessions_planned": 600,
    }
    expected_fallback = {
        "semantic_sessions": 120,
        "arm_runs": 360,
        "candidate_actions": 8640,
        "gated_arm_runs": 240,
        "ungated_arm_runs": 120,
        "gate_evaluations_planned": 5760,
        "mcad_api_restarts_planned": 360,
        "fresh_mcad_sessions_planned": 240,
    }
    for key, value in expected_primary.items():
        if int(primary[key]) != value:
            raise RuntimeError(f"primary static plan mismatch: {key}")
    for key, value in expected_fallback.items():
        if int(fallback[key]) != value:
            raise RuntimeError(f"fallback static plan mismatch: {key}")

    if primary["selection_role"] != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("primary selection role changed")
    if fallback["selection_role"] != "RESOURCE_CONSTRAINED_FALLBACK":
        raise RuntimeError("fallback selection role changed")
    if primary["unique_templates_lexicographic"] != fallback["unique_templates_lexicographic"]:
        raise RuntimeError("primary/fallback template set mismatch")
    if len(primary["unique_templates_lexicographic"]) != 7:
        raise RuntimeError("expected seven frozen templates")
    for p in (primary, fallback):
        if p["measurement_authorized"] is not False:
            raise RuntimeError("D0 plan unexpectedly authorizes measurement")
        if p["confirmatory_claim_authorized"] is not False:
            raise RuntimeError("D0 plan prematurely authorizes confirmatory claim")
        if p["effect_size_tuning_performed"] is not False:
            raise RuntimeError("D0 plan indicates effect-size tuning")

    print("r3c5_parent_head=" + PARENT_HEAD)
    print("primary_semantic_sessions=300")
    print("primary_arm_runs=900")
    print("primary_candidate_actions=21600")
    print("primary_gate_evaluations_planned=14400")
    print("primary_arm_position_balance=100_each")
    print("fallback_semantic_sessions=120")
    print("fallback_arm_runs=360")
    print("fallback_candidate_actions=8640")
    print("fallback_gate_evaluations_planned=5760")
    print("fallback_arm_position_balance=40_each")
    print("fallback_activation_authorized_now=false")
    print("confirmatory_inference_family_metrics=8")
    print("confirmatory_familywise_alpha=0.05")
    print("confirmatory_multiplicity=Holm")
    print("permutation_replicates=100000")
    print("bootstrap_replicates=20000")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("docker_commands_executed=false")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D0_CONFIRMATORY_STATIC_VERIFY=PASS_READY_FOR_D1_NO_MEASUREMENT")


if __name__ == "__main__":
    main()
