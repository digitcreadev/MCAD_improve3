#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"

PARENT = "45dc105e6e9c1ef800323af2a78987a2b8ddcf11"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

CONTRACT = R3 / "config/r3_e7_xmla_inference_engine_static_contract.json"
VECTORS = R3 / "config/r3_e7_xmla_inference_synthetic_test_vectors.json"
ENGINE = R3 / "implementation/r3_e7_xmla_inference_engine.py"
RECEIPT = R3 / "results/e7_xmla_inference_synthetic_test_receipt.json"

EXPECTED_BLOBS = {
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e6_xmla_replication_inference_protocol.json":
        "a49d00a38c2c62c6d7bff26a474d3e5662e8e301",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e6_xmla_replication_seed_manifest.json":
        "c0c412e83cffcddcda62d8354571fa9fea9c04ba",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/verify_r3_e6_xmla_replication_inference_static.py":
        "4519a226b7a5e8c54113603790a3adb24dede97a",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/r3_d4_confirmatory_inference.py":
        "9d957ef3e0fe76ff04517f6207d7e57a02d81564",
}

SHARED = ['full_backend_execution_count', 'backend_request_count_including_gate_probes', 'client_wall_ms', 'sqlserver_cpu_usage_usec_delta', 'sqlserver_io_rbytes_delta', 'sqlserver_io_wbytes_delta', 'response_bytes', 'time_to_analytical_objective_completion_ms']
XMLA_EXTRA = ['emondrian_cpu_usage_usec_delta', 'emondrian_io_rbytes_delta', 'emondrian_io_wbytes_delta']
SYN_NS_SHA = "f37c7d43e21dd56bb46c563ce4c58d12cbac6880f7d9d1d2876c215ad5ab4666"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_engine():
    spec = importlib.util.spec_from_file_location("r3_e7_engine", ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import E7 engine")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_lineage() -> None:
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git("rev-parse", f"{PARENT}^{{commit}}") != PARENT:
        raise RuntimeError("E6 parent missing")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", PARENT, "HEAD"], check=True)
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git("rev-parse", f"HEAD:{rel}")
        if actual != expected:
            raise RuntimeError(f"frozen authority changed: {rel} -> {actual}")


def verify_contract() -> None:
    c = load(CONTRACT)
    e6 = load(R3 / "config/r3_e6_xmla_replication_inference_protocol.json")
    r = load(RECEIPT)
    v = load(VECTORS)

    if c["parent_e6_head"] != PARENT:
        raise RuntimeError("E7 parent binding changed")
    if e6["next"] != "R3-E7_XMLA_INFERENCE_IMPLEMENTATION_SYNTHETIC_TESTS_NO_MEASURED_DATA":
        raise RuntimeError("E6 next-stage authority changed")
    prod = c["production_inference_defaults_frozen_from_e6"]
    fam = e6["shared_primary_replication_family"]
    if prod["shared_primary_metrics"] != SHARED or fam["metrics"] != SHARED:
        raise RuntimeError("shared primary family changed")
    if prod["permutation_replicates"] != fam["permutation_test"]["replicates"] != 100000:
        raise RuntimeError("permutation defaults changed")
    if prod["bootstrap_replicates"] != fam["confidence_interval"]["replicates"] != 20000:
        raise RuntimeError("bootstrap defaults changed")
    if prod["multiplicity"] != fam["multiplicity"]:
        raise RuntimeError("Holm multiplicity changed")
    if prod["xmla_specific_secondary_metrics"] != XMLA_EXTRA:
        raise RuntimeError("XMLA secondary diagnostics changed")
    if c["synthetic_test_scope"]["uses_e6_production_seed_streams"] is not False:
        raise RuntimeError("synthetic tests consume production seed streams")
    if v["namespace_sha256"] != SYN_NS_SHA:
        raise RuntimeError("synthetic namespace changed")
    if v["measured_data_used"] is not False:
        raise RuntimeError("synthetic vectors claim measured data")

    boundary = c["execution_boundary"]
    for key in [
        "bundle_read_allowed", "docker_allowed", "http_or_backend_query_allowed",
        "measured_receipt_ingestion_allowed", "real_p_value_computation_allowed",
        "real_confidence_interval_computation_allowed", "real_effect_analysis_allowed",
        "measurement_allowed", "historical_d4_recomputation_allowed",
        "historical_artifact_mutation_allowed",
    ]:
        if boundary[key] is not False:
            raise RuntimeError(f"E7 forbidden boundary enabled: {key}")
    for key in [
        "synthetic_p_value_computation_allowed",
        "synthetic_confidence_interval_computation_allowed",
        "synthetic_effect_analysis_allowed",
    ]:
        if boundary[key] is not True:
            raise RuntimeError(f"E7 synthetic boundary disabled: {key}")

    for key in [
        "bundle_read_performed", "docker_command_executed",
        "http_or_backend_query_executed", "measured_receipt_ingested",
        "real_p_value_computed", "real_confidence_interval_computed",
        "real_effect_analysis_performed", "measurement_performed",
        "global_system_benefit_claim_authorized", "backend_equivalence_claim_authorized",
        "effect_homogeneity_claim_authorized",
    ]:
        if r[key] is not False:
            raise RuntimeError(f"E7 receipt boundary changed: {key}")


def verify_engine_source_boundary() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    forbidden = {"requests", "urllib", "http", "socket", "docker", "tarfile"}
    bad = imports & forbidden
    if bad:
        raise RuntimeError(f"E7 engine imports forbidden runtime/network modules: {sorted(bad)}")
    for token in [
        "MCAD_R3_D3_REPLACEMENT_PRIMARY_RESULTS",
        "results/arm_runs",
        "docker compose",
        "docker run",
        "http://",
        "https://",
    ]:
        if token in source:
            raise RuntimeError(f"E7 engine contains forbidden measured/runtime token: {token}")
    if "--input" in source or "--receipts" in source or "--archive" in source:
        raise RuntimeError("E7 engine exposes a measured-data file CLI")


def verify_engine_self_tests() -> None:
    mod = import_engine()
    if tuple(mod.PRIMARY_METRICS) != tuple(SHARED):
        raise RuntimeError("engine primary metrics changed")
    if tuple(mod.XMLA_SECONDARY_METRICS) != tuple(XMLA_EXTRA):
        raise RuntimeError("engine XMLA metrics changed")
    if mod.PRODUCTION_SIGN_FLIP_REPLICATES != 100000:
        raise RuntimeError("engine production permutation default changed")
    if mod.PRODUCTION_BOOTSTRAP_REPLICATES != 20000:
        raise RuntimeError("engine production bootstrap default changed")
    if abs(mod.PRODUCTION_FAMILYWISE_ALPHA - 0.05) > 1e-15:
        raise RuntimeError("engine production alpha changed")
    if mod.SYNTHETIC_NAMESPACE_SHA256 != SYN_NS_SHA:
        raise RuntimeError("engine synthetic namespace changed")

    result_a = mod.run_synthetic_self_test()
    result_b = mod.run_synthetic_self_test()
    if result_a != result_b:
        raise RuntimeError("E7 synthetic self-test is not deterministic")
    if result_a["status"] != "PASS":
        raise RuntimeError("E7 synthetic self-test did not pass")
    if result_a["measured_data_used"] is not False:
        raise RuntimeError("E7 self-test used measured data")
    if result_a["real_effect_analysis_performed"] is not False:
        raise RuntimeError("E7 self-test claims real effect analysis")
    if result_a["synthetic_effect_analysis_performed"] is not True:
        raise RuntimeError("E7 self-test did not exercise synthetic analysis")
    if result_a["secondary_confirmatory_p_value_computed"] is not False:
        raise RuntimeError("E7 secondary diagnostic computed confirmatory p-value")

    try:
        mod.prove_measured_data_refusal()
    except RuntimeError as exc:
        if "measured XMLA receipt ingestion and real inference require a separate" not in str(exc):
            raise
    else:
        raise RuntimeError("E7 measured-data refusal disappeared")


def main() -> None:
    verify_lineage()
    verify_contract()
    verify_engine_source_boundary()
    verify_engine_self_tests()

    print("e6_parent_and_lineage=PASS")
    print("frozen_e6_protocol_seed_and_verifier_authorities=PASS")
    print("d4_reference_engine_not_recomputed=PASS")
    print("production_primary_family_8=PASS")
    print("production_permutation_replicates_100000=PASS")
    print("production_bootstrap_replicates_20000=PASS")
    print("holm_implementation_synthetic_vector=PASS")
    print("paired_sign_flip_synthetic_cases=PASS")
    print("stratified_bootstrap_synthetic_cases=PASS")
    print("synthetic_random_stream_determinism=PASS")
    print("synthetic_namespace_separate_from_production_seeds=PASS")
    print("xmla_secondary_confirmatory_p_values_computed=false")
    print("measured_data_cli_present=false")
    print("measured_receipt_ingested=false")
    print("real_p_value_computed=false")
    print("real_confidence_interval_computed=false")
    print("real_effect_analysis_performed=false")
    print("measurement_performed=false")
    print("R3_E7_XMLA_INFERENCE_SYNTHETIC_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
