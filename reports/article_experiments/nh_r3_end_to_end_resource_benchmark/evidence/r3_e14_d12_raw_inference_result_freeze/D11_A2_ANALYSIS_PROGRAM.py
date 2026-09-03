#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

PRIMARY_METRICS = [
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
]

XMLA_DIAGNOSTICS = [
    "emondrian_cpu_usage_usec_delta",
    "emondrian_io_rbytes_delta",
    "emondrian_io_wbytes_delta",
]

ARMS = [
    "UNGATED_EXECUTE_ADMISSIBLE",
    "PERMISSIVE_GATED",
    "SAFE_PRUNING",
]

EXPECTED_RUN_ID = "r3e_e14_d8_a3_replacement_primary300_20260903T105543Z"

EXPECTED_RUNTIME_IDENTITY = {
    "project_name": "mcad-r3e-xmla1",
    "sqlserver_container_id": "d2261a8631dc101de0db0ae125e1fa639852678ccbf5ef88057decd5a34d9ce0",
    "sqlserver_image_id": "sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89",
    "emondrian_container_id": "01091951115bfc8a924fbc3e54b57531b235ad5b5c3c3c1abb042318e4a24c6b",
    "emondrian_image_id": "sha256:77d2d5395e902b28368bdc0357d9a1a6d928c415af160425248df5d2d0697a69",
    "mcad_api_container_id": "7af54b420f9348163d0a68ebc19804cd9b367d5771ad6cb85861ae97936a4dff",
    "mcad_api_image_id": "sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840",
    "mcad_proxy_container_id": "21924b8ec521a0c769120d403c6b46e911341e9aeed77df391e313a21b7bdccc",
    "mcad_proxy_image_id": "sha256:492ebe93459255dd81a836503dc376e46c4b29a12eb3f5f549d83943e93fe14a",
}

C_GROUP_METRICS = [
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "emondrian_cpu_usage_usec_delta",
    "emondrian_io_rbytes_delta",
    "emondrian_io_wbytes_delta",
]

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def atomic_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def import_e7(path: Path):
    spec = importlib.util.spec_from_file_location("frozen_r3_e7", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen E7 engine")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def parse_schedule(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    expected_header = [
        "block_index", "session_id", "topology", "pattern",
        "selection_role", "arm_1", "arm_2", "arm_3",
    ]
    if not rows:
        raise RuntimeError("schedule empty")
    if list(rows[0].keys()) != expected_header:
        raise RuntimeError("schedule header mismatch")
    if len(rows) != 300:
        raise RuntimeError(f"schedule row count {len(rows)} != 300")
    sessions = [r["session_id"] for r in rows]
    if len(set(sessions)) != 300:
        raise RuntimeError("schedule session ids not unique")
    strata = Counter((r["topology"], r["pattern"]) for r in rows)
    if len(strata) != 20 or set(strata.values()) != {15}:
        raise RuntimeError(f"schedule strata mismatch: {len(strata)} / {sorted(set(strata.values()))}")
    for i, row in enumerate(rows, start=1):
        if int(row["block_index"]) != i:
            raise RuntimeError(f"schedule block_index mismatch at {i}")
        if row["selection_role"] != "CONFIRMATORY_PRIMARY":
            raise RuntimeError(f"schedule selection_role mismatch at {i}")
        if set([row["arm_1"], row["arm_2"], row["arm_3"]]) != set(ARMS):
            raise RuntimeError(f"schedule arms mismatch at {i}")
    return rows

def validate_static(repo: Path) -> dict[str, Any]:
    r3 = repo / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
    e6 = load_json(r3 / "config/r3_e6_xmla_replication_inference_protocol.json")
    seeds = load_json(r3 / "config/r3_e6_xmla_replication_seed_manifest.json")
    d10 = load_json(r3 / "config/r3_e14_d10_inference_authorization.json")
    schema = load_json(r3 / "config/r3_e5_xmla_arm_receipt_schema.json")
    schedule = parse_schedule(r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv")
    e7 = import_e7(r3 / "implementation/r3_e7_xmla_inference_engine.py")

    if e6["shared_primary_replication_family"]["metrics"] != PRIMARY_METRICS:
        raise RuntimeError("E6 primary metrics mismatch")
    if d10["primary_replication_family"]["metrics"] != PRIMARY_METRICS:
        raise RuntimeError("D10 primary metrics mismatch")
    if e6["shared_primary_replication_family"]["permutation_test"]["replicates"] != 100000:
        raise RuntimeError("permutation replicate mismatch")
    if e6["shared_primary_replication_family"]["confidence_interval"]["replicates"] != 20000:
        raise RuntimeError("bootstrap replicate mismatch")
    if e6["shared_primary_replication_family"]["familywise_alpha"] != 0.05:
        raise RuntimeError("alpha mismatch")
    if e6["measurement_integrity"]["required_arm_receipts"] != 900:
        raise RuntimeError("receipt count mismatch")
    if len(e6["measurement_integrity"]["requirements"]) != 11:
        raise RuntimeError("integrity requirement count mismatch")
    if seeds["frozen_before_xmla_measurement"] is not True or seeds["outcome_independent"] is not True:
        raise RuntimeError("seed freeze mismatch")
    if set(seeds["primary_family"]) != set(PRIMARY_METRICS):
        raise RuntimeError("seed primary family mismatch")
    if schema["$id"] != "mcad.nh_r3.e5.xmla_arm_receipt.schema.v1":
        raise RuntimeError("schema id mismatch")
    if len(schedule) != 300:
        raise RuntimeError("schedule size mismatch")
    if tuple(PRIMARY_METRICS) != tuple(e7.PRIMARY_METRICS):
        raise RuntimeError("E7 primary metrics mismatch")
    if e7.PRODUCTION_SIGN_FLIP_REPLICATES != 100000:
        raise RuntimeError("E7 permutation default mismatch")
    if e7.PRODUCTION_BOOTSTRAP_REPLICATES != 20000:
        raise RuntimeError("E7 bootstrap default mismatch")
    if e7.PRODUCTION_FAMILYWISE_ALPHA != 0.05:
        raise RuntimeError("E7 alpha mismatch")
    required_fns = [
        "analyze_primary_pair",
        "analyze_secondary_pair",
        "holm_adjust",
        "sign_flip_test",
        "stratified_percentile_bootstrap",
    ]
    for name in required_fns:
        if not callable(getattr(e7, name, None)):
            raise RuntimeError(f"E7 function missing: {name}")

    return {
        "static_check": "PASS",
        "schedule_sessions": 300,
        "schedule_strata": 20,
        "sessions_per_stratum": 15,
        "primary_metric_count": 8,
        "permutation_replicates": 100000,
        "bootstrap_replicates": 20000,
        "familywise_alpha": 0.05,
        "measured_archive_opened": False,
        "measured_receipt_ingested": False,
        "effect_computation_executed": False,
        "result_interpretation_executed": False,
    }

def is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)

def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))

def validate_receipt_shape(r: dict[str, Any], schema: dict[str, Any]) -> None:
    required = set(schema["required"])
    properties = set(schema["properties"])
    if set(r) != properties:
        missing = sorted(properties - set(r))
        extra = sorted(set(r) - properties)
        raise RuntimeError(f"receipt keys mismatch missing={missing} extra={extra}")
    if required != properties:
        raise RuntimeError("frozen schema required/properties mismatch")
    if r["receipt_version"] != "mcad.nh_r3.e5.xmla_arm_receipt.v1":
        raise RuntimeError("receipt_version mismatch")
    if r["run_id"] != EXPECTED_RUN_ID:
        raise RuntimeError("run_id mismatch")
    if not isinstance(r["session_id"], str) or not r["session_id"]:
        raise RuntimeError("session_id invalid")
    if not is_int(r["block_index"]) or not (1 <= r["block_index"] <= 300):
        raise RuntimeError("block_index invalid")
    if not isinstance(r["topology"], str) or not r["topology"]:
        raise RuntimeError("topology invalid")
    if not isinstance(r["pattern"], str) or not r["pattern"]:
        raise RuntimeError("pattern invalid")
    if r["selection_role"] != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("selection_role mismatch")
    if r["arm"] not in ARMS:
        raise RuntimeError("arm invalid")
    if not is_int(r["arm_position"]) or not (1 <= r["arm_position"] <= 3):
        raise RuntimeError("arm_position invalid")
    if r["candidate_actions"] != 24:
        raise RuntimeError("candidate_actions mismatch")
    for key in [
        "gate_evaluations",
        "full_backend_execution_count",
        "backend_request_count_including_gate_probes",
        "response_bytes",
    ]:
        if not is_int(r[key]) or r[key] < 0:
            raise RuntimeError(f"{key} invalid")
    for key in ["client_wall_ms", "time_to_analytical_objective_completion_ms"]:
        if not is_number(r[key]) or float(r[key]) < 0:
            raise RuntimeError(f"{key} invalid")
    for key in C_GROUP_METRICS:
        if not is_int(r[key]):
            raise RuntimeError(f"{key} invalid type")
    if not is_int(r["completion_candidate_index"]) or not (0 <= r["completion_candidate_index"] <= 23):
        raise RuntimeError("completion_candidate_index invalid")
    if r["completion_candidate_reached"] is not True:
        raise RuntimeError("completion_candidate_reached false")
    if r["runtime_identity"] != EXPECTED_RUNTIME_IDENTITY:
        raise RuntimeError("runtime_identity mismatch")
    flags = r["integrity_flags"]
    if set(flags) != {
        "negative_cgroup_delta_detected",
        "secret_value_recorded",
        "historical_runtime_targeted",
        "completion_candidate_unique",
    }:
        raise RuntimeError("integrity_flags keys mismatch")
    if flags["negative_cgroup_delta_detected"] is not False:
        raise RuntimeError("negative_cgroup_delta_detected true")
    if flags["secret_value_recorded"] is not False:
        raise RuntimeError("secret_value_recorded true")
    if flags["historical_runtime_targeted"] is not False:
        raise RuntimeError("historical_runtime_targeted true")
    if flags["completion_candidate_unique"] is not True:
        raise RuntimeError("completion_candidate_unique false")
    for key in C_GROUP_METRICS:
        if r[key] < 0:
            raise RuntimeError(f"negative cgroup delta value for {key}")
    for key in PRIMARY_METRICS:
        if key not in r or r[key] is None or not is_number(r[key]):
            raise RuntimeError(f"missing/nonfinite primary metric {key}")

def load_arm_receipts_from_d9(d9: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_manifest = {}
    for line in (d9 / "RAW_SOURCE_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, path = line.split(None, 1)
        path = path.strip()
        if path.startswith("arm_runs/"):
            raw_manifest[path] = digest
    if len(raw_manifest) != 900:
        raise RuntimeError(f"arm raw source manifest count {len(raw_manifest)} != 900")

    parts = sorted(d9.glob("ARM_RUNS.tar.gz.part-*"))
    if not parts:
        raise RuntimeError("ARM_RUNS archive parts missing")
    compressed = b"".join(p.read_bytes() for p in parts)
    receipts = []
    seen_hashes = {}

    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as gz:
        with tarfile.open(fileobj=gz, mode="r|") as tf:
            for member in tf:
                if not member.isfile():
                    raise RuntimeError(f"non-file archive member {member.name}")
                if member.name not in raw_manifest:
                    raise RuntimeError(f"unexpected archive member {member.name}")
                if member.name in seen_hashes:
                    raise RuntimeError(f"duplicate archive member {member.name}")
                f = tf.extractfile(member)
                if f is None:
                    raise RuntimeError(f"cannot extract {member.name}")
                data = f.read()
                digest = sha_bytes(data)
                if digest != raw_manifest[member.name]:
                    raise RuntimeError(f"archive member hash mismatch {member.name}")
                seen_hashes[member.name] = digest
                receipts.append(json.loads(data.decode("utf-8")))

    if seen_hashes != raw_manifest:
        raise RuntimeError("archive membership/hash set mismatch")
    if len(receipts) != 900:
        raise RuntimeError(f"receipt count {len(receipts)} != 900")

    return receipts, {
        "archive_part_count": len(parts),
        "archive_member_count": 900,
        "archive_member_hashes_verified": 900,
    }

def validate_integrity(
    receipts: list[dict[str, Any]],
    schema: dict[str, Any],
    schedule: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str], dict[str, Any]]:
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for r in receipts:
        validate_receipt_shape(r, schema)
        key = (r["session_id"], r["arm"])
        if key in by_pair:
            raise RuntimeError(f"duplicate session-arm receipt {key}")
        by_pair[key] = r

    expected_pairs = set()
    strata = []
    for row in schedule:
        sid = row["session_id"]
        strata.append(f'{row["topology"]}|{row["pattern"]}')
        for pos in range(1, 4):
            arm = row[f"arm_{pos}"]
            expected_pairs.add((sid, arm))
            r = by_pair.get((sid, arm))
            if r is None:
                raise RuntimeError(f"missing session-arm receipt {(sid, arm)}")
            if r["block_index"] != int(row["block_index"]):
                raise RuntimeError(f"block_index mismatch for {(sid, arm)}")
            if r["topology"] != row["topology"]:
                raise RuntimeError(f"topology mismatch for {(sid, arm)}")
            if r["pattern"] != row["pattern"]:
                raise RuntimeError(f"pattern mismatch for {(sid, arm)}")
            if r["selection_role"] != row["selection_role"]:
                raise RuntimeError(f"selection_role mismatch for {(sid, arm)}")
            if r["arm_position"] != pos:
                raise RuntimeError(f"arm_position mismatch for {(sid, arm)}")

    if set(by_pair) != expected_pairs:
        raise RuntimeError("session-arm pair set mismatch")
    if len(by_pair) != 900:
        raise RuntimeError("session-arm pair count mismatch")

    strata_counts = Counter(strata)
    if len(strata_counts) != 20 or set(strata_counts.values()) != {15}:
        raise RuntimeError("stratum count mismatch")

    integrity = {
        "contract_version": "mcad.nh_r3.e14.d11.measurement_integrity_receipt.v1",
        "classification": "PASS_ALL_11_FROZEN_E6_INTEGRITY_REQUIREMENTS",
        "run_id": EXPECTED_RUN_ID,
        "arm_receipts": 900,
        "semantic_sessions": 300,
        "arms_per_session": 3,
        "candidate_actions_per_receipt": 24,
        "frozen_requirement_count": 11,
        "all_frozen_session_ids_present": True,
        "arm_positions_match_frozen_schedule": True,
        "completion_candidate_reached_all": True,
        "completion_candidate_unique_all": True,
        "secret_value_recorded_false_all": True,
        "historical_runtime_targeted_false_all": True,
        "runtime_identity_exact_match_all": True,
        "negative_cgroup_delta_detected_false_all": True,
        "negative_cgroup_delta_values_present": False,
        "missing_primary_metric_values": 0,
        "imputation_performed": False,
        "posthoc_outlier_exclusion_performed": False,
        "effect_computation_started_before_integrity_pass": False,
        "result_interpretation_executed": False,
    }
    return by_pair, strata, integrity

def run_analysis(repo: Path, d9: Path, output: Path, analysis_id: str) -> None:
    r3 = repo / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
    schema = load_json(r3 / "config/r3_e5_xmla_arm_receipt_schema.json")
    e6 = load_json(r3 / "config/r3_e6_xmla_replication_inference_protocol.json")
    seeds = load_json(r3 / "config/r3_e6_xmla_replication_seed_manifest.json")
    d10 = load_json(r3 / "config/r3_e14_d10_inference_authorization.json")
    schedule = parse_schedule(r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv")
    e7 = import_e7(r3 / "implementation/r3_e7_xmla_inference_engine.py")

    state_path = output / "D11_STATE.json"
    integrity_path = output / "D11_INTEGRITY_RECEIPT.json"
    result_path = output / "D11_RAW_INFERENCE_RESULTS.json"
    failure_path = output / "D11_ANALYSIS_FAILURE.json"

    state = {
        "contract_version": "mcad.nh_r3.e14.d11.analysis_state.v1",
        "analysis_id": analysis_id,
        "d9_archive_opened": False,
        "measured_receipt_ingestion_executed": False,
        "measurement_integrity_executed": False,
        "measurement_integrity_pass": False,
        "effect_computation_started": False,
        "effect_computation_completed": False,
        "result_interpretation_executed": False,
        "claim_reporting_executed": False,
    }
    atomic_json(state_path, state)

    try:
        state["d9_archive_opened"] = True
        atomic_json(state_path, state)
        receipts, archive_meta = load_arm_receipts_from_d9(d9)
        state["measured_receipt_ingestion_executed"] = True
        atomic_json(state_path, state)

        by_pair, strata, integrity = validate_integrity(receipts, schema, schedule)
        state["measurement_integrity_executed"] = True
        state["measurement_integrity_pass"] = True
        atomic_json(integrity_path, {**integrity, "archive": archive_meta})
        atomic_json(state_path, state)

        state["effect_computation_started"] = True
        atomic_json(state_path, state)

        primary_results: dict[str, Any] = {}
        raw_p: dict[str, float] = {}

        for metric in PRIMARY_METRICS:
            safe = [float(by_pair[(row["session_id"], "SAFE_PRUNING")][metric]) for row in schedule]
            permissive = [float(by_pair[(row["session_id"], "PERMISSIVE_GATED")][metric]) for row in schedule]
            metric_seeds = seeds["primary_family"][metric]
            res = e7.analyze_primary_pair(
                safe,
                permissive,
                strata,
                permutation_replicates=100000,
                bootstrap_replicates=20000,
                permutation_seed=int(metric_seeds["permutation"]["uint64_be_prefix"]),
                bootstrap_seed=int(metric_seeds["bootstrap"]["uint64_be_prefix"]),
            )
            raw_p[metric] = float(res["raw_one_sided_p"])
            primary_results[metric] = res

        holm = e7.holm_adjust(raw_p)
        for metric in PRIMARY_METRICS:
            primary_results[metric]["holm_rank"] = holm[metric]["holm_rank"]
            primary_results[metric]["holm_adjusted_one_sided_p"] = holm[metric]["holm_adjusted_one_sided_p"]

        secondary_break_even: dict[str, Any] = {}
        for metric in PRIMARY_METRICS:
            safe = [float(by_pair[(row["session_id"], "SAFE_PRUNING")][metric]) for row in schedule]
            ungated = [float(by_pair[(row["session_id"], "UNGATED_EXECUTE_ADMISSIBLE")][metric]) for row in schedule]
            seed = int(seeds["primary_family"][metric]["secondary_break_even_bootstrap"]["uint64_be_prefix"])
            secondary_break_even[metric] = e7.analyze_secondary_pair(
                safe,
                ungated,
                strata,
                bootstrap_replicates=20000,
                bootstrap_seed=seed,
                comparator_label="UNGATED_EXECUTE_ADMISSIBLE",
            )

        xmla_diagnostics: dict[str, Any] = {}
        for metric in XMLA_DIAGNOSTICS:
            safe = [float(by_pair[(row["session_id"], "SAFE_PRUNING")][metric]) for row in schedule]
            permissive = [float(by_pair[(row["session_id"], "PERMISSIVE_GATED")][metric]) for row in schedule]
            ungated = [float(by_pair[(row["session_id"], "UNGATED_EXECUTE_ADMISSIBLE")][metric]) for row in schedule]
            seed_info = seeds["xmla_secondary_diagnostics"][metric]
            xmla_diagnostics[metric] = {
                "safe_minus_permissive": e7.analyze_secondary_pair(
                    safe,
                    permissive,
                    strata,
                    bootstrap_replicates=20000,
                    bootstrap_seed=int(seed_info["descriptive_bootstrap"]["uint64_be_prefix"]),
                    comparator_label="PERMISSIVE_GATED",
                ),
                "safe_minus_ungated_break_even": e7.analyze_secondary_pair(
                    safe,
                    ungated,
                    strata,
                    bootstrap_replicates=20000,
                    bootstrap_seed=int(seed_info["secondary_break_even_bootstrap"]["uint64_be_prefix"]),
                    comparator_label="UNGATED_EXECUTE_ADMISSIBLE",
                ),
            }

        result = {
            "contract_version": "mcad.nh_r3.e14.d11.raw_preregistered_inference_result.v1",
            "classification": "RAW_PREREGISTERED_INFERENCE_COMPLETE_PENDING_D12_FREEZE_NO_RESULT_INTERPRETATION",
            "analysis_id": analysis_id,
            "source_run_id": EXPECTED_RUN_ID,
            "scientific_role": "SECONDARY_END_TO_END_CONFIRMATION",
            "measurement_integrity": {
                "classification": integrity["classification"],
                "pass": True,
                "receipt_count": 900,
                "session_count": 300,
                "strata": 20,
                "sessions_per_stratum": 15,
            },
            "primary_replication_family": {
                "comparison": "SAFE_PRUNING - PERMISSIVE_GATED",
                "metrics": PRIMARY_METRICS,
                "family_size": 8,
                "permutation_replicates": 100000,
                "bootstrap_replicates": 20000,
                "familywise_alpha": 0.05,
                "multiplicity": "Holm step-down across all 8 frozen primary metrics",
                "results": primary_results,
                "metric_specific_claim_assignment_performed": False,
                "global_system_benefit_claim_assignment_performed": False,
            },
            "secondary_break_even_family": {
                "comparison": "SAFE_PRUNING - UNGATED_EXECUTE_ADMISSIBLE",
                "confirmatory_p_values_computed": False,
                "results": secondary_break_even,
            },
            "xmla_specific_resource_diagnostics": {
                "metrics": XMLA_DIAGNOSTICS,
                "confirmatory_p_values_computed": False,
                "holm_family_membership": False,
                "results": xmla_diagnostics,
            },
            "claim_boundary": {
                "result_interpretation_executed": False,
                "metric_specific_claim_reporting_executed": False,
                "backend_equivalence_claim_executed": False,
                "effect_homogeneity_claim_executed": False,
                "cross_backend_effect_difference_test_executed": False,
                "cross_backend_synthesis_executed": False,
                "global_system_benefit_claim_executed": False,
                "D12_freeze_required_before_interpretation": True,
            },
            "execution_boundary": {
                "measurement_reexecution_executed": False,
                "backend_query_executed": False,
                "docker_command_executed": False,
                "http_request_executed": False,
                "xmla_query_executed": False,
                "automatic_retry_executed": False,
                "automatic_rerun_executed": False,
                "automatic_resume_executed": False,
                "effect_based_reseed_executed": False,
            },
        }
        atomic_json(result_path, result)

        state["effect_computation_completed"] = True
        atomic_json(state_path, state)

        print("D11_MEASUREMENT_INTEGRITY=PASS")
        print("D11_MEASURED_RECEIPT_COUNT=900")
        print("D11_SEMANTIC_SESSION_COUNT=300")
        print("D11_PRIMARY_METRIC_COUNT=8")
        print("D11_PRIMARY_PERMUTATION_REPLICATES=100000")
        print("D11_PRIMARY_BOOTSTRAP_REPLICATES=20000")
        print("D11_PRIMARY_HOLM_FAMILY_SIZE=8")
        print("D11_SECONDARY_BREAK_EVEN_METRIC_COUNT=8")
        print("D11_XMLA_DIAGNOSTIC_METRIC_COUNT=3")
        print("D11_RAW_INFERENCE_RESULTS_WRITTEN=true")
        print("D11_RESULT_VALUES_PRINTED_TO_CONSOLE=false")
        print("D11_RESULT_INTERPRETATION_EXECUTED=false")
        print("D11_CLAIM_REPORTING_EXECUTED=false")
        print("D11_ANALYSIS_PROGRAM_STATUS=PASS")
    except Exception as exc:
        failure = {
            "contract_version": "mcad.nh_r3.e14.d11.analysis_failure.v1",
            "analysis_id": analysis_id,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "state": state,
            "result_interpretation_executed": False,
            "claim_reporting_executed": False,
        }
        atomic_json(failure_path, failure)
        print("D11_ANALYSIS_PROGRAM_STATUS=FAIL")
        print(f"D11_FAILURE_TYPE={type(exc).__name__}")
        print("D11_RESULT_INTERPRETATION_EXECUTED=false")
        raise

def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("static-check")
    s.add_argument("--repo", required=True)

    r = sub.add_parser("run")
    r.add_argument("--repo", required=True)
    r.add_argument("--d9-evidence", required=True)
    r.add_argument("--output-dir", required=True)
    r.add_argument("--analysis-id", required=True)

    args = p.parse_args()
    if args.cmd == "static-check":
        result = validate_static(Path(args.repo))
        for key in [
            "static_check",
            "schedule_sessions",
            "schedule_strata",
            "sessions_per_stratum",
            "primary_metric_count",
            "permutation_replicates",
            "bootstrap_replicates",
            "familywise_alpha",
            "measured_archive_opened",
            "measured_receipt_ingested",
            "effect_computation_executed",
            "result_interpretation_executed",
        ]:
            print(f"D11_STATIC_{key.upper()}={result[key]}")
        return
    run_analysis(
        Path(args.repo),
        Path(args.d9_evidence),
        Path(args.output_dir),
        args.analysis_id,
    )

if __name__ == "__main__":
    main()
