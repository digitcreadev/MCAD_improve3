#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
RESULT_DIR = R3 / "results/confirmatory_primary_20260823T224457Z"

EXPECTED_SOURCE_SHA = {
    R3 / "config/r3_d4_confirmatory_inference_freeze_contract.json":
        "eeae2cae1e6f9f942a8ead65598929bca7b8b0058e4a4ddca4037d36c64c91be",
    R3 / "implementation/r3_d4_confirmatory_inference.py":
        "6b85d01771891d04a232785c7b96bde3b0d6bbb01bcf2e81d7a41f186b22dc43",
    R3 / "implementation/verify_r3_d4_static.py":
        "26e6c30ab2acb9416d04399fa77397c9a33ae7acbf7dfa17b003f4a17e53a7fa",
}

EXPECTED_OUTPUT_SHA = {
    "confirmatory_analysis.json":
        "a2e4311ba5a9a5d6fbe6ce683fc406b0ff7d3fa8cca2496a0769bcb9f4710394",
    "confirmatory_arm_means.csv":
        "aae0a575bfce4984a65b932aba845d4c93f6604bf0c0f25b5841e9aef6e74b50",
    "confirmatory_primary_endpoint_family.csv":
        "172ee3c6debb2cce46fbf59d0a8cf8732d9d5bb9fac7b71aa8c3071c92abc246",
    "confirmatory_secondary_break_even.csv":
        "89f51a54dac1847be7c876dd8becedbad0d38121aeff63e4130409a4382019a1",
    "confirmatory_session_paired_metrics.csv":
        "59ee172b293d2f7494750cbd5fbab22f49f7cfb975a41a5ef93fc00d0486d31b",
    "confirmatory_stratum_diagnostics.csv":
        "e23a8404cad96f1059529a05a1e41abbf641ef6b58428868c576da5cdc90b528",
    "SHA256SUMS.txt":
        "15fa3164c070eddb177ae5c685a1e6e1e5ea8a0541aa669ef4d2c3e951e1b152",
}

PRIMARY_METRICS = (
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
)

EXPECTED_CONFIRMED = {
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
}

EXPECTED_NOT_CONFIRMED = {
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
}

SOURCE_ARCHIVE_SHA = "8ac00f467d7fb2235e6a4df2850278e1893103279077178ffe610db995a91ff5"
R4_KIT_HEAD = "eae990ad9125896cb733261177a0d7dbb8ae934f"
PRESERVED_RESIDUE_SHA = "b8fdd1c5f55c10c2cb989fb4d43be6414b74020c34923b501366b5a30e19e974"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_exact_files(repo: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel, expected in EXPECTED_SOURCE_SHA.items():
        p = repo / rel
        if not p.is_file():
            raise RuntimeError(f"missing original D4 source: {rel}")
        actual = sha256(p)
        if actual != expected:
            raise RuntimeError(f"original D4 source changed: {rel} -> {actual}")
        hashes[str(rel)] = actual

    for name, expected in EXPECTED_OUTPUT_SHA.items():
        p = repo / RESULT_DIR / name
        if not p.is_file():
            raise RuntimeError(f"missing generated D4 output: {name}")
        actual = sha256(p)
        if actual != expected:
            raise RuntimeError(f"generated D4 output changed: {name} -> {actual}")
        hashes[str(RESULT_DIR / name)] = actual
    return hashes


def verify_manifest(repo: Path) -> None:
    manifest = repo / RESULT_DIR / "SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split("  ", 1)
        p = repo / RESULT_DIR / name
        if sha256(p) != expected:
            raise RuntimeError(f"generated output internal manifest mismatch: {name}")


def verify_analysis(repo: Path) -> dict[str, Any]:
    data = json.loads(
        (repo / RESULT_DIR / "confirmatory_analysis.json").read_text(encoding="utf-8")
    )

    if data.get("contract_version") != "mcad.nh_r3.d4.confirmatory_inference_analysis.v1":
        raise RuntimeError("unexpected confirmatory analysis contract")
    if data.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("unexpected analysis class")

    source = data.get("source") or {}
    if source.get("archive_sha256") != SOURCE_ARCHIVE_SHA:
        raise RuntimeError("source archive binding changed")
    if source.get("r4_execution_kit_head") != R4_KIT_HEAD:
        raise RuntimeError("R4 execution-kit binding changed")
    for key in (
        "interrupted_partial_receipts_reused",
        "resume_from_arm_298",
        "fallback_120_activated",
    ):
        if source.get(key) is not False:
            raise RuntimeError(f"source anti-redo boundary violated: {key}")

    integrity = data.get("measurement_integrity") or {}
    expected_integrity = {
        "status": "PASS",
        "semantic_sessions": 300,
        "arm_receipts": 900,
        "candidate_records": 21600,
        "gate_evaluations": 14400,
        "full_backend_executions": 14580,
        "fresh_gated_sessions": 600,
        "negative_cgroup_delta_arm_runs": 0,
        "warmup_templates_completed": 7,
    }
    for key, expected in expected_integrity.items():
        if integrity.get(key) != expected:
            raise RuntimeError(f"measurement integrity mismatch: {key}")

    protocol = data.get("frozen_inference_protocol") or {}
    if protocol.get("primary_comparison") != "SAFE_PRUNING - PERMISSIVE_GATED":
        raise RuntimeError("primary comparison changed")
    if tuple(protocol.get("primary_metrics") or []) != PRIMARY_METRICS:
        raise RuntimeError("frozen primary metric list changed")
    if int(protocol.get("sign_flip_replicates", -1)) != 100000:
        raise RuntimeError("sign-flip replicate count changed")
    if int(protocol.get("bootstrap_replicates", -1)) != 20000:
        raise RuntimeError("bootstrap replicate count changed")
    if float(protocol.get("holm_familywise_alpha", -1)) != 0.05:
        raise RuntimeError("Holm alpha changed")

    family = data.get("primary_endpoint_family") or {}
    results = family.get("results") or {}

    # Critical verifier-only recovery:
    # JSON object key order is NOT part of metric-family identity.
    actual_metric_family = set(results.keys())
    expected_metric_family = set(PRIMARY_METRICS)
    if actual_metric_family != expected_metric_family:
        raise RuntimeError(
            "D4 primary metric family changed: "
            + ",".join(sorted(actual_metric_family ^ expected_metric_family))
        )
    if len(results) != len(PRIMARY_METRICS):
        raise RuntimeError("D4 primary metric family cardinality changed")

    confirmed: set[str] = set()
    not_confirmed: set[str] = set()

    for metric in PRIMARY_METRICS:
        rec = results[metric]
        raw_p = float(rec["raw_one_sided_p"])
        holm_p = float(rec["holm_adjusted_one_sided_p"])
        mean_diff = float(rec["mean_difference_safe_minus_permissive"])
        flag = bool(rec["confirmatory_reduction_confirmed"])

        if not (0 < raw_p <= 1):
            raise RuntimeError(f"invalid raw p-value for {metric}")
        if not (0 < holm_p <= 1):
            raise RuntimeError(f"invalid Holm p-value for {metric}")
        if holm_p + 1e-15 < raw_p:
            raise RuntimeError(f"Holm p-value below raw p-value for {metric}")

        expected_flag = mean_diff < 0 and holm_p <= 0.05
        if flag != expected_flag:
            raise RuntimeError(f"claim rule mismatch for {metric}")

        (confirmed if flag else not_confirmed).add(metric)

    if confirmed != EXPECTED_CONFIRMED:
        raise RuntimeError("confirmed endpoint set changed")
    if not_confirmed != EXPECTED_NOT_CONFIRMED:
        raise RuntimeError("not-confirmed endpoint set changed")
    if int(family.get("confirmed_metric_count", -1)) != 6:
        raise RuntimeError("confirmed metric count changed")
    if family.get("all_8_confirmed") is not False:
        raise RuntimeError("all_8_confirmed unexpectedly true")
    if family.get("global_system_benefit_claim_authorized") is not False:
        raise RuntimeError("global system-benefit claim boundary violated")

    secondary = data.get("secondary_break_even_family") or {}
    if secondary.get("confirmatory_p_values_computed") is not False:
        raise RuntimeError("secondary confirmatory p-values unexpectedly computed")

    boundary = data.get("claim_boundary") or {}
    if boundary.get("global_system_benefit_claim_authorized") is not False:
        raise RuntimeError("global claim boundary violated")
    if boundary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("effect-size tuning flag violated")
    if boundary.get("posthoc_endpoint_selection_performed") is not False:
        raise RuntimeError("posthoc endpoint selection flag violated")
    if boundary.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback flag violated")

    if data.get("next") != (
        "R3-E0_XMLA_EMONDRIAN_END_TO_END_REPLICATION_STATIC_ACTIVATION_NO_MEASUREMENT"
    ):
        raise RuntimeError("unexpected D4 next stage")

    return {
        "confirmed_metrics": sorted(confirmed),
        "not_confirmed_metrics": sorted(not_confirmed),
        "confirmed_metric_count": 6,
        "all_8_confirmed": False,
        "global_system_benefit_claim_authorized": False,
        "secondary_confirmatory_p_values_computed": False,
    }


def make_receipt(repo: Path, receipt: Path) -> None:
    hashes = verify_exact_files(repo)
    verify_manifest(repo)
    facts = verify_analysis(repo)

    payload = {
        "contract_version": "mcad.nh_r3.d4.verifier_only_recovery_receipt.v1",
        "failure_class": "ORDER_ONLY_FALSE_NEGATIVE_IN_POST_GENERATION_VERIFIER",
        "verification_mode": "EXISTING_OUTPUTS_ONLY_NO_RECOMPUTATION",
        "original_inference_reexecuted": False,
        "generated_outputs_modified": False,
        "original_analysis_source_modified": False,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA,
        "r4_execution_kit_head": R4_KIT_HEAD,
        "preserved_pre_fix_residue_archive_sha256": PRESERVED_RESIDUE_SHA,
        "exact_file_sha256": hashes,
        **facts,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "backend_query_executed": False,
        "docker_or_service_mutation_performed": False,
        "measurement_performed": False,
        "next": "R3-E0_XMLA_EMONDRIAN_END_TO_END_REPLICATION_STATIC_ACTIVATION_NO_MEASUREMENT",
        "status": "PASS_EXISTING_D4_OUTPUTS_VERIFIED_AND_FROZEN",
    }
    receipt.parent.mkdir(parents=True, exist_ok=False)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--receipt")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    hashes = verify_exact_files(repo)
    verify_manifest(repo)
    facts = verify_analysis(repo)

    if args.receipt:
        receipt = Path(args.receipt).resolve()
        if receipt.exists():
            raise RuntimeError(f"receipt already exists: {receipt}")
        make_receipt(repo, receipt)

    print("original_d4_inference_reexecuted=false")
    print("generated_outputs_modified=false")
    print("metric_family_identity_order_insensitive=true")
    print("measurement_integrity=PASS")
    print("confirmed_metric_count=6")
    print("all_8_confirmed=false")
    print("confirmed_metrics=" + "|".join(facts["confirmed_metrics"]))
    print("not_confirmed_metrics=" + "|".join(facts["not_confirmed_metrics"]))
    print("global_system_benefit_claim_authorized=false")
    print("secondary_confirmatory_p_values_computed=false")
    print("exact_generated_output_files_verified=" + str(len(EXPECTED_OUTPUT_SHA)))
    print("R3_D4_VERIFIER_ONLY_EXISTING_OUTPUT_VERIFY=PASS")


if __name__ == "__main__":
    main()
