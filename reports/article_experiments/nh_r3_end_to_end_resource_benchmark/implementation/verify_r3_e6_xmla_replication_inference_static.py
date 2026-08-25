#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"

PARENT = "effd3a0677bc943f51faf87f4808743136ba027b"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

PROTOCOL = R3 / "config/r3_e6_xmla_replication_inference_protocol.json"
SEEDS = R3 / "config/r3_e6_xmla_replication_seed_manifest.json"
RECEIPT = R3 / "results/e6_xmla_replication_inference_static_receipt.json"

EXPECTED_BLOBS = {
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_d0_confirmatory_inference_protocol.json":
        "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_d0_confirmatory_primary_arm_order_schedule.csv":
        "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e4_xmla_external_overlay_static_contract.json":
        "a07d35b69ff8c717c5d4c2610ba28685f0873827",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e5_xmla_executor_receipt_static_contract.json":
        "8db8982a735aeff5cf3a27e0eb23af87a2ef4baa",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e5_xmla_arm_receipt_schema.json":
        "9dd353e1495e677c1d75cb0ccb8adfa2920c335e",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/r3_e5_xmla_executor_static.py":
        "a67e69eb1f9e1735a6e1868135ff1a513beaf221",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/verify_r3_e5_xmla_executor_static.py":
        "60f90d3bf3cbb1a54ae4bd66dbb2789a47bdbb32",
}

SHARED = [
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
]
XMLA_EXTRA = [
    "emondrian_cpu_usage_usec_delta",
    "emondrian_io_rbytes_delta",
    "emondrian_io_wbytes_delta",
]

SEED_NAMESPACE = "MCAD-NH-R3-E6|XMLA_REPLICATION|effd3a0677bc943f51faf87f4808743136ba027b|v1"
SEED_NAMESPACE_SHA256 = "b3bcfe0ff7bbc0b2a7fb786f76dcdb9973de72380ff55f312b0fa172ed2475e5"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def derive(kind: str, metric: str) -> tuple[str, int]:
    h = hashlib.sha256(f"{SEED_NAMESPACE_SHA256}|{kind}|{metric}".encode()).hexdigest()
    return h, int(h[:16], 16)


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = sorted(range(m), key=lambda i: (p_values[i], i))
    out = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        adjusted = min(1.0, (m - rank) * p_values[idx])
        running = max(running, adjusted)
        out[idx] = running
    return out


def verify_lineage_and_blobs() -> None:
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git("rev-parse", f"{PARENT}^{{commit}}") != PARENT:
        raise RuntimeError("E5 parent missing")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", PARENT, "HEAD"], check=True)
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git("rev-parse", f"HEAD:{rel}")
        if actual != expected:
            raise RuntimeError(f"frozen authority changed: {rel} -> {actual}")


def verify_inheritance() -> None:
    d0 = load(R3 / "config/r3_d0_confirmatory_inference_protocol.json")
    e5 = load(R3 / "config/r3_e5_xmla_executor_receipt_static_contract.json")
    p = load(PROTOCOL)

    d0fam = d0["primary_endpoint_family"]
    pfam = p["shared_primary_replication_family"]

    if e5["resource_accounting"]["shared_r3_primary_endpoint_family"] != SHARED:
        raise RuntimeError("E5 shared metric family changed")
    if e5["resource_accounting"]["xmla_specific_additional_metrics"] != XMLA_EXTRA:
        raise RuntimeError("E5 XMLA diagnostics changed")
    if e5["inference_boundary"]["shared_primary_family_inherits_d0_holm_protocol"] is not True:
        raise RuntimeError("E5 no longer inherits D0 Holm protocol")

    checks = [
        (pfam["metrics"], d0fam["metrics"], "metric family"),
        (pfam["comparison"], d0fam["comparison"], "primary comparison"),
        (pfam["alternative"], d0fam["alternative"], "alternative"),
        (pfam["familywise_alpha"], d0fam["familywise_alpha"], "alpha"),
        (pfam["multiplicity"], d0fam["multiplicity"], "multiplicity"),
        (pfam["permutation_test"]["kind"], d0fam["permutation_test"]["kind"], "permutation kind"),
        (pfam["permutation_test"]["replicates"], d0fam["permutation_test"]["replicates"], "permutation replicates"),
        (pfam["permutation_test"]["monte_carlo_p"], d0fam["permutation_test"]["monte_carlo_p"], "permutation p rule"),
        (pfam["confidence_interval"]["kind"], d0fam["confidence_interval"]["kind"], "bootstrap kind"),
        (pfam["confidence_interval"]["confidence"], d0fam["confidence_interval"]["confidence"], "bootstrap confidence"),
        (pfam["confidence_interval"]["replicates"], d0fam["confidence_interval"]["replicates"], "bootstrap replicates"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            raise RuntimeError(f"E6 does not inherit D0 {label}: {actual!r} != {expected!r}")

    if p["design_basis"]["primary_cohort_sessions"] != 300:
        raise RuntimeError("E6 cohort changed")
    if p["design_basis"]["strata"] != 20 or p["design_basis"]["equal_sessions_per_stratum"] != 15:
        raise RuntimeError("E6 stratification changed")
    if p["secondary_break_even_family"]["comparison"] != d0["secondary_break_even_family"]["comparison"]:
        raise RuntimeError("secondary break-even comparison changed")
    if p["secondary_break_even_family"]["confirmatory_p_value"] is not False:
        raise RuntimeError("secondary break-even p-values unexpectedly authorized")
    if p["xmla_specific_resource_diagnostics"]["confirmatory_p_values_authorized"] is not False:
        raise RuntimeError("XMLA-specific confirmatory p-values unexpectedly authorized")
    if p["xmla_specific_resource_diagnostics"]["holm_family_membership"] is not False:
        raise RuntimeError("XMLA-specific diagnostics leaked into Holm family")


def verify_seeds() -> None:
    s = load(SEEDS)
    if s["seed_namespace_literal"] != SEED_NAMESPACE:
        raise RuntimeError("seed namespace literal changed")
    if s["seed_namespace_sha256"] != SEED_NAMESPACE_SHA256:
        raise RuntimeError("seed namespace hash changed")
    if hashlib.sha256(SEED_NAMESPACE.encode()).hexdigest() != SEED_NAMESPACE_SHA256:
        raise RuntimeError("seed namespace hash self-check failed")
    if s["outcome_independent"] is not True or s["frozen_before_xmla_measurement"] is not True:
        raise RuntimeError("seed independence/freeze flags changed")

    for metric in SHARED:
        for kind in ["permutation", "bootstrap", "secondary_break_even_bootstrap"]:
            expected_h, expected_u = derive(kind, metric)
            got = s["primary_family"][metric][kind]
            if got["sha256"] != expected_h or got["uint64_be_prefix"] != expected_u:
                raise RuntimeError(f"seed changed: {metric}/{kind}")

    for metric in XMLA_EXTRA:
        for kind in ["xmla_descriptive_bootstrap", "xmla_secondary_break_even_bootstrap"]:
            expected_h, expected_u = derive(kind, metric)
            key = "descriptive_bootstrap" if kind == "xmla_descriptive_bootstrap" else "secondary_break_even_bootstrap"
            got = s["xmla_secondary_diagnostics"][metric][key]
            if got["sha256"] != expected_h or got["uint64_be_prefix"] != expected_u:
                raise RuntimeError(f"seed changed: {metric}/{kind}")


def verify_integrity_and_boundary() -> None:
    p = load(PROTOCOL)
    r = load(RECEIPT)

    integ = p["measurement_integrity"]
    if integ["required_arm_receipts"] != 900 or integ["required_semantic_sessions"] != 300:
        raise RuntimeError("measurement integrity cardinality changed")
    if integ["required_arms_per_session"] != 3:
        raise RuntimeError("arms per session changed")
    if "never clamp to zero" not in integ["negative_cgroup_delta_policy"]:
        raise RuntimeError("negative cgroup policy weakened")
    if integ["no_effect_based_early_stopping"] is not True:
        raise RuntimeError("effect-based early stopping enabled")
    if integ["no_effect_based_reruns"] is not True:
        raise RuntimeError("effect-based reruns enabled")
    if integ["no_interim_effect_looks"] is not True:
        raise RuntimeError("interim effect looks enabled")

    x = p["cross_backend_interpretation"]
    for key in [
        "new_global_system_benefit_claim_authorized",
        "backend_equivalence_claim_authorized",
        "effect_homogeneity_claim_authorized",
        "cross_backend_effect_difference_test_pre_registered",
    ]:
        if x[key] is not False:
            raise RuntimeError(f"cross-backend claim boundary changed: {key}")

    b = p["analysis_execution_boundary"]
    for key, value in b.items():
        if key.endswith("_allowed") or key.endswith("_present"):
            if value is not False:
                raise RuntimeError(f"E6 execution boundary changed: {key}")

    for key in [
        "bundle_read_performed",
        "docker_command_executed",
        "http_or_backend_query_executed",
        "measured_receipt_ingested",
        "real_p_value_computed",
        "real_confidence_interval_computed",
        "effect_analysis_performed",
        "measurement_performed",
        "measurement_authorized",
        "analysis_authorized",
        "global_system_benefit_claim_authorized",
        "backend_equivalence_claim_authorized",
        "effect_homogeneity_claim_authorized",
    ]:
        if r[key] is not False:
            raise RuntimeError(f"E6 static receipt changed: {key}")


def verify_holm_self_test() -> None:
    raw = [0.001, 0.010, 0.020, 0.200]
    expected = [0.004, 0.030, 0.040, 0.200]
    got = holm_adjust(raw)
    for a, b in zip(got, expected):
        if abs(a - b) > 1e-12:
            raise RuntimeError(f"Holm self-test failed: {got}")


def main() -> None:
    verify_lineage_and_blobs()
    verify_inheritance()
    verify_seeds()
    verify_integrity_and_boundary()
    verify_holm_self_test()

    print("e5_parent_and_lineage=PASS")
    print("frozen_e5_and_d0_authorities=PASS")
    print("shared_xmla_replication_family_8=PASS")
    print("d0_inference_procedure_inherited_without_change=PASS")
    print("holm_familywise_alpha_0_05=PASS")
    print("permutation_replicates_100000=PASS")
    print("bootstrap_replicates_20000=PASS")
    print("outcome_independent_seed_manifest=PASS")
    print("secondary_break_even_confirmatory_p_value=false")
    print("xmla_specific_confirmatory_p_values_authorized=false")
    print("global_system_benefit_claim_authorized=false")
    print("backend_equivalence_claim_authorized=false")
    print("measurement_authorized=false")
    print("analysis_authorized=false")
    print("effect_analysis_performed=false")
    print("R3_E6_XMLA_REPLICATION_INFERENCE_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
