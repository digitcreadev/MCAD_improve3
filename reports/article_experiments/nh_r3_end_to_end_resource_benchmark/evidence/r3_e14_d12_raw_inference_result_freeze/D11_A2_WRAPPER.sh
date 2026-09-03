#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/workspaces/MCAD_improve3"
BRANCH="paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_HEAD="cccd1bb2f7b4089f38c5d927311dea7c6e8a3850"

R3_REL="reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
RUNTIME_ROOT="/workspaces/MCAD_R3E_XMLA_ISOLATED_RUNTIME_b88cc576ec54"

D10_AUTH="$REPO/$R3_REL/config/r3_e14_d10_inference_authorization.json"
EXPECT_D10_AUTH_SHA="a311d75e58a0fb4e7ea34aab7fb5836ce7b69a1264600a8163d8212f33446929"
EXPECT_D10_AUTH_BLOB="d1a986c28af678b1160d466fee9c93b2ac9115d4"

D9_EVIDENCE="$REPO/$R3_REL/evidence/r3_e14_d9_raw_measured_evidence_freeze"
D9_MANIFEST="$D9_EVIDENCE/FREEZE_MANIFEST.json"
D9_SHA256SUMS="$D9_EVIDENCE/SHA256SUMS"
D9_RAW_SOURCE_SHA256SUMS="$D9_EVIDENCE/RAW_SOURCE_SHA256SUMS"
EXPECT_D9_MANIFEST_SHA="141d954c2f4e707653732aaa556847a34bc6bb5117128b5913093599f416a7df"
EXPECT_D9_SHA256SUMS_SHA="a4bd87bd5a6ec89f3e8bc85e987c3d9b3f803a456761a2152f1a4f69a640af49"
EXPECT_D9_RAW_SOURCE_SHA256SUMS_SHA="686b9681005e192e4e9a07e3bf791484c1dc1cd3630de921f56f65c766ad8cf8"

E5_SCHEMA="$REPO/$R3_REL/config/r3_e5_xmla_arm_receipt_schema.json"
E6_PROTOCOL="$REPO/$R3_REL/config/r3_e6_xmla_replication_inference_protocol.json"
E6_SEEDS="$REPO/$R3_REL/config/r3_e6_xmla_replication_seed_manifest.json"
E7_ENGINE="$REPO/$R3_REL/implementation/r3_e7_xmla_inference_engine.py"
SCHEDULE="$REPO/$R3_REL/config/r3_d0_confirmatory_primary_arm_order_schedule.csv"

EXPECT_E5_SCHEMA_BLOB="9dd353e1495e677c1d75cb0ccb8adfa2920c335e"
EXPECT_E6_PROTOCOL_BLOB="a49d00a38c2c62c6d7bff26a474d3e5662e8e301"
EXPECT_E6_SEEDS_BLOB="c0c412e83cffcddcda62d8354571fa9fea9c04ba"
EXPECT_E7_ENGINE_BLOB="8a77d336d66ea292dfb728ce55beb607f65128db"
EXPECT_SCHEDULE_BLOB="6b53ab6d271425b9e5113bdd405775f05c6d65df"

FAILED_ANALYSIS_ID="r3e_e14_d11_preregistered_inference_20260903T164348Z"
FAILED_OUTPUT="$RUNTIME_ROOT/$FAILED_ANALYSIS_ID"
FAILED_WRAPPER="$FAILED_OUTPUT/D11_WRAPPER.sh"
FAILED_ANALYSIS="$FAILED_OUTPUT/D11_ANALYSIS.py"
FAILED_RECEIPT="$FAILED_OUTPUT/D11_FAILURE_RECEIPT.json"

EXPECT_FAILED_WRAPPER_SHA="0aefb1819d2d41cf7c2b7d64c47c802e1f5454fc7862467290933d74095b7ba7"
EXPECT_FAILED_ANALYSIS_SHA="8d5cf0b9693a5896b08d46691c6cf83df200e87cd107b149681cf051a216d416"
EXPECT_FAILED_RECEIPT_SHA="c1b074f06b938c60202410a99efcd21afcc1349152672371bb1277d6d976449b"

A1_AUDIT="$RUNTIME_ROOT/r3_e14_d11_a1_static_audit_failure_20260903T164348Z.readonly_audit.json"
EXPECT_A1_AUDIT_SHA="a8582e00b9d2b1450f7c7933c750694f4bc464d6cc44a0567611436ffd032fea"

RECOVERY_AUTH_REL="$R3_REL/config/r3_e14_d11_a2_inference_recovery_authorization.json"
RECOVERY_AUTH="$REPO/$RECOVERY_AUTH_REL"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ANALYSIS_ID="r3e_e14_d11_a2_preregistered_inference_${STAMP}"
OUTPUT_DIR="$RUNTIME_ROOT/$ANALYSIS_ID"
CONSOLE_LOG="$OUTPUT_DIR/D11_CONSOLE.log"
ANALYSIS_PROGRAM="$OUTPUT_DIR/D11_ANALYSIS.py"
WRAPPER_COPY="$OUTPUT_DIR/D11_A2_WRAPPER.sh"
AUTH_COPY="$OUTPUT_DIR/D11_A2_RECOVERY_AUTHORIZATION.json"
STATE_FILE="$OUTPUT_DIR/D11_STATE.json"
INTEGRITY_RECEIPT="$OUTPUT_DIR/D11_INTEGRITY_RECEIPT.json"
RAW_RESULTS="$OUTPUT_DIR/D11_RAW_INFERENCE_RESULTS.json"
EXECUTION_RECEIPT="$OUTPUT_DIR/D11_EXECUTION_RECEIPT.json"
FAILURE_RECEIPT="$OUTPUT_DIR/D11_A2_FAILURE_RECEIPT.json"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ANALYSIS_TMP="$TMP/D11_ANALYSIS.py"

REPOSITORY_MUTATED=false
RECOVERY_AUTH_COMMIT_CREATED=false
RECOVERY_AUTH_PUSHED=false
OUTPUT_DIR_CREATED=false
D9_ARCHIVE_OPENED=false
MEASURED_RECEIPT_INGESTION_EXECUTED=false
MEASUREMENT_INTEGRITY_EXECUTED=false
EFFECT_COMPUTATION_STARTED=false
EFFECT_COMPUTATION_COMPLETED=false
RESULT_INTERPRETATION_EXECUTED=false

sha_file() {
  sha256sum "$1" | awk '{print $1}'
}

fail() {
  local reason="$1"
  echo
  echo "R3E_E14_D11_A2_PREREGISTERED_INFERENCE_EXECUTION=FAIL reason=$reason"
  echo "repository_mutated=$REPOSITORY_MUTATED"
  echo "recovery_authorization_commit_created=$RECOVERY_AUTH_COMMIT_CREATED"
  echo "recovery_authorization_pushed=$RECOVERY_AUTH_PUSHED"
  echo "output_dir_created=$OUTPUT_DIR_CREATED"
  echo "d9_archive_opened=$D9_ARCHIVE_OPENED"
  echo "measured_receipt_ingestion_executed=$MEASURED_RECEIPT_INGESTION_EXECUTED"
  echo "measurement_integrity_executed=$MEASUREMENT_INTEGRITY_EXECUTED"
  echo "effect_computation_started=$EFFECT_COMPUTATION_STARTED"
  echo "effect_computation_completed=$EFFECT_COMPUTATION_COMPLETED"
  echo "result_interpretation_executed=false"
  echo "measurement_reexecution_executed=false"
  echo "automatic_retry_executed=false"
  echo "automatic_rerun_executed=false"
  echo "automatic_resume_executed=false"
  echo "effect_based_reseed_executed=false"
  echo "docker_command_executed=false"
  echo "backend_http_request_executed=false"
  echo "xmla_query_executed=false"
  echo "RECOVERY=PRESERVE_FAILED_D11_V1_CURRENT_HEAD_AND_ANY_D11_A2_OUTPUT_RETURN_FULL_OUTPUT_DO_NOT_RERUN"
  echo "=== STOP ==="
  exit 1
}

echo "=== R3-E14 D11-A2 authorize fresh preregistered inference NO RESULT INTERPRETATION ==="
echo "PURPOSE=authorize_one_fresh_D11_recovery_after_pre_ingestion_static_audit_false_positive_then_execute_exact_E6_E7_plan"
echo "PARENT_HEAD=$PARENT_HEAD"
echo "FAILED_D11_V1_ANALYSIS_ID=$FAILED_ANALYSIS_ID"
echo "FAILED_D11_V1_RERUN_ALLOWED=false"
echo "FAILED_D11_V1_OUTPUT_REUSE_ALLOWED=false"
echo "FAILED_D11_V1_OUTPUT_DELETE_ALLOWED=false"
echo "ANALYSIS_ID=$ANALYSIS_ID"
echo "OUTPUT_DIR=$OUTPUT_DIR"
echo "D9_FROZEN_RAW_EVIDENCE_ONLY=true"
echo "MEASUREMENT_REEXECUTION_ALLOWED=false"
echo "RESULT_INTERPRETATION_ALLOWED=false"
echo "CLAIM_REPORTING_ALLOWED=false"
echo "CROSS_BACKEND_SYNTHESIS_ALLOWED=false"
echo "AUTOMATIC_RETRY_ALLOWED=false"
echo "AUTOMATIC_RERUN_ALLOWED=false"
echo "AUTOMATIC_RESUME_ALLOWED=false"
echo "EFFECT_BASED_RESEED_ALLOWED=false"
echo "DOCKER_COMMAND_ALLOWED=false"
echo "BACKEND_HTTP_REQUEST_ALLOWED=false"
echo "XMLA_QUERY_ALLOWED=false"
echo "HISTORICAL_ARTIFACT_MUTATION_ALLOWED=false"

echo
echo "=== 1. Exact Git authority / clean repository ==="
current_branch="$(git -C "$REPO" branch --show-current)"
local_head="$(git -C "$REPO" rev-parse HEAD)"
remote_head="$(git -C "$REPO" ls-remote origin "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"
status="$(git -C "$REPO" status --porcelain=v1 --untracked-files=all)"
index_status="$(git -C "$REPO" diff --cached --name-status)"

echo "current_branch=$current_branch"
echo "local_head=$local_head"
echo "remote_head=$remote_head"

[[ "$current_branch" == "$BRANCH" ]] || fail "wrong_branch"
[[ "$local_head" == "$PARENT_HEAD" ]] || fail "local_head_not_exact_D10_authorization"
[[ "$remote_head" == "$PARENT_HEAD" ]] || fail "remote_head_not_exact_D10_authorization"
[[ -z "$status" ]] || fail "repository_dirty_before_D11_A2"
[[ -z "$index_status" ]] || fail "index_not_clean_before_D11_A2"
[[ ! -e "$RECOVERY_AUTH" ]] || fail "D11_A2_recovery_authorization_already_exists"
[[ ! -e "$OUTPUT_DIR" ]] || fail "fresh_D11_A2_output_dir_already_exists"
echo "git_authority_gate=PASS"

echo
echo "=== 2. Authenticate exact D10 authorization / no interpretation boundary ==="
[[ -f "$D10_AUTH" ]] || fail "D10_authorization_missing"
[[ "$(sha_file "$D10_AUTH")" == "$EXPECT_D10_AUTH_SHA" ]] || fail "D10_authorization_sha_changed"
[[ "$(git -C "$REPO" hash-object "$D10_AUTH")" == "$EXPECT_D10_AUTH_BLOB" ]] || fail "D10_authorization_blob_changed"

python3 - "$D10_AUTH" <<'PYD10' || fail "D10_authorization_semantic_gate_failed"
import json, sys
from pathlib import Path

a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert a["contract_version"] == "mcad.nh_r3.e14.d10.inference_authorization.v1"
assert a["classification"] == "AUTHORIZED_PRE_SPECIFIED_XMLA_REPLICATION_INFERENCE_AFTER_RAW_FREEZE"
assert a["parent_d9_freeze_head"] == "332bee959911232505c99f2fa1a4fa2aa6e03cf5"

d11 = a["D11_execution_authorization"]
assert d11["measured_receipt_ingestion_authorized"] is True
assert d11["real_effect_analysis_authorized"] is True
assert d11["real_confidence_interval_computation_authorized"] is True
assert d11["real_p_value_computation_authorized"] is True
assert d11["holm_adjustment_authorized"] is True
assert d11["only_after_integrity_gate_pass"] is True
assert d11["new_measured_inference_wrapper_authorized"] is True
assert d11["wrapper_must_import_frozen_E7_functions_without_modifying_E7"] is True
assert d11["wrapper_must_be_static_audited_before_opening_D9_archives"] is True
assert d11["wrapper_must_use_exact_E6_seeds"] is True
assert d11["wrapper_must_use_all_8_primary_metrics"] is True
assert d11["wrapper_must_not_select_endpoints_based_on_results"] is True
assert d11["wrapper_must_not_change_alpha_tests_replicates_strata_or_estimands"] is True
assert d11["wrapper_must_not_rerun_measurement"] is True
assert d11["wrapper_must_not_execute_backend_or_docker_io"] is True
assert d11["analysis_output_must_be_outside_repository"] is True
assert d11["analysis_output_directory_must_not_preexist"] is True
assert d11["effect_based_retry_rerun_or_reseed_authorized"] is False
assert d11["automatic_retry_authorized"] is False
assert d11["automatic_rerun_authorized"] is False
assert d11["automatic_resume_authorized"] is False
assert d11["result_interpretation_or_claim_reporting_authorized_in_D11"] is False
assert d11["result_freeze_required_before_interpretation"] is True

ig = a["measurement_integrity_gate"]
assert ig["required_before_any_effect_computation"] is True
assert ig["frozen_e6_requirement_count"] == 11
assert ig["required_arm_receipts"] == 900
assert ig["required_semantic_sessions"] == 300
assert ig["required_arms_per_session"] == 3
assert ig["required_candidate_actions_per_receipt"] == 24
assert ig["require_all_frozen_session_ids"] is True
assert ig["require_arm_position_matches_frozen_schedule"] is True
assert ig["require_completion_candidate_reached"] is True
assert ig["require_completion_candidate_unique"] is True
assert ig["require_secret_value_recorded_false"] is True
assert ig["require_historical_runtime_targeted_false"] is True
assert ig["require_runtime_identity_match"] is True
assert ig["require_negative_cgroup_delta_detected_false"] is True
assert ig["require_no_missing_primary_metric_values"] is True
assert ig["imputation_authorized"] is False
assert ig["posthoc_outlier_exclusion_authorized"] is False

post = a["post_D11_boundary"]
assert post["D12_raw_inference_result_freeze_required"] is True
assert post["D12_must_freeze_exact_D11_code_and_outputs_before_result_interpretation"] is True
assert post["D13_result_interpretation_requires_separate_authorization"] is True
assert post["scientific_final_freeze_authorized_by_D10"] is False

assert a["claim_boundary"]["backend_equivalence_claim_authorized"] is False
assert a["claim_boundary"]["cross_backend_synthesis_authorized"] is False
assert a["claim_boundary"]["new_global_system_benefit_claim_authorized"] is False

print("D10_D11_authority_gate=PASS_PREREGISTERED_ANALYSIS_AUTHORIZED_NO_INTERPRETATION")
print("D11_result_interpretation_authorized=false")
print("D12_raw_result_freeze_required=true")
PYD10

echo
echo "=== 3. Authenticate D11-v1 failed output + exact A1 read-only audit ==="
[[ -f "$A1_AUDIT" ]] || fail "D11_A1_audit_missing"
[[ "$(sha_file "$A1_AUDIT")" == "$EXPECT_A1_AUDIT_SHA" ]] || fail "D11_A1_audit_sha_changed"
[[ -d "$FAILED_OUTPUT" ]] || fail "failed_D11_v1_output_missing"

FAILED_COUNT="$(find "$FAILED_OUTPUT" -maxdepth 1 -type f | wc -l | tr -d ' ')"
echo "failed_D11_v1_output_file_count=$FAILED_COUNT"
[[ "$FAILED_COUNT" == "3" ]] || fail "failed_D11_v1_output_topology_changed"
[[ "$(sha_file "$FAILED_WRAPPER")" == "$EXPECT_FAILED_WRAPPER_SHA" ]] || fail "failed_D11_v1_wrapper_sha_changed"
[[ "$(sha_file "$FAILED_ANALYSIS")" == "$EXPECT_FAILED_ANALYSIS_SHA" ]] || fail "failed_D11_v1_analysis_sha_changed"
[[ "$(sha_file "$FAILED_RECEIPT")" == "$EXPECT_FAILED_RECEIPT_SHA" ]] || fail "failed_D11_v1_receipt_sha_changed"

echo "D11_A1_audit_sha256=$(sha_file "$A1_AUDIT")"
echo "failed_D11_v1_wrapper_sha256=$(sha_file "$FAILED_WRAPPER")"
echo "failed_D11_v1_analysis_sha256=$(sha_file "$FAILED_ANALYSIS")"
echo "failed_D11_v1_receipt_sha256=$(sha_file "$FAILED_RECEIPT")"
echo "failed_D11_v1_preservation_gate=PASS_EXACT_3_FILES_UNCHANGED"
echo "failed_D11_v1_archive_opened=false"
echo "failed_D11_v1_measured_receipt_ingestion_executed=false"
echo "failed_D11_v1_effect_computation_started=false"
echo "failed_D11_v1_failure_classification=SELF_REFERENTIAL_STATIC_AUDIT_FALSE_POSITIVE"

echo
echo "=== 4. Authenticate frozen E5/E6/E7 authorities and D9 byte freeze ==="
check_blob() {
  local path="$1" expected="$2" label="$3"
  [[ -f "$path" ]] || fail "missing_authority_$label"
  local got
  got="$(git -C "$REPO" hash-object "$path")"
  echo "${label}_git_blob=$got"
  [[ "$got" == "$expected" ]] || fail "authority_blob_changed_$label"
}

check_blob "$E5_SCHEMA" "$EXPECT_E5_SCHEMA_BLOB" "e5_receipt_schema"
check_blob "$E6_PROTOCOL" "$EXPECT_E6_PROTOCOL_BLOB" "e6_protocol"
check_blob "$E6_SEEDS" "$EXPECT_E6_SEEDS_BLOB" "e6_seed_manifest"
check_blob "$E7_ENGINE" "$EXPECT_E7_ENGINE_BLOB" "e7_engine"
check_blob "$SCHEDULE" "$EXPECT_SCHEDULE_BLOB" "d0_schedule"

[[ "$(sha_file "$D9_MANIFEST")" == "$EXPECT_D9_MANIFEST_SHA" ]] || fail "D9_manifest_sha_changed"
[[ "$(sha_file "$D9_SHA256SUMS")" == "$EXPECT_D9_SHA256SUMS_SHA" ]] || fail "D9_sha256s_sha_changed"
[[ "$(sha_file "$D9_RAW_SOURCE_SHA256SUMS")" == "$EXPECT_D9_RAW_SOURCE_SHA256SUMS_SHA" ]] || fail "D9_raw_source_sha256s_sha_changed"

python3 - "$E6_PROTOCOL" "$E6_SEEDS" "$D10_AUTH" <<'PYPLAN' || fail "frozen_plan_gate_failed"
import json, sys
from pathlib import Path

e6 = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
seeds = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
d10 = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

metrics = e6["shared_primary_replication_family"]["metrics"]
assert len(metrics) == 8
assert metrics == d10["primary_replication_family"]["metrics"]
assert e6["shared_primary_replication_family"]["permutation_test"]["replicates"] == 100000
assert e6["shared_primary_replication_family"]["confidence_interval"]["replicates"] == 20000
assert e6["shared_primary_replication_family"]["familywise_alpha"] == 0.05
assert e6["shared_primary_replication_family"]["multiplicity"] == "Holm step-down across all 8 frozen primary metrics"
assert e6["secondary_break_even_family"]["confirmatory_p_value"] is False
assert e6["xmla_specific_resource_diagnostics"]["confirmatory_p_values_authorized"] is False
assert e6["measurement_integrity"]["required_arm_receipts"] == 900
assert e6["measurement_integrity"]["required_semantic_sessions"] == 300
assert e6["measurement_integrity"]["required_arms_per_session"] == 3
assert len(e6["measurement_integrity"]["requirements"]) == 11
assert e6["measurement_integrity"]["no_effect_based_reruns"] is True
assert e6["measurement_integrity"]["no_interim_effect_looks"] is True
assert seeds["frozen_before_xmla_measurement"] is True
assert seeds["outcome_independent"] is True
assert set(seeds["primary_family"]) == set(metrics)

print("frozen_E6_E7_plan_gate=PASS_EXACT_PRE_SPECIFIED_PLAN")
print("primary_metric_count=8")
print("permutation_replicates=100000")
print("bootstrap_replicates=20000")
print("holm_family_size=8")
PYPLAN

echo
echo "=== 5. Generate exact D11-A2 analysis program OUTSIDE repository; STATIC AUDIT before D9 archive open ==="
cat > "$ANALYSIS_TMP" <<'PYANALYSIS'
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
PYANALYSIS

chmod 0755 "$ANALYSIS_TMP"
ANALYSIS_SHA="$(sha_file "$ANALYSIS_TMP")"
SELF_SHA="$(sha_file "$(readlink -f "$0")")"
echo "D11_A2_wrapper_sha256=$SELF_SHA"
echo "D11_A2_analysis_program_sha256=$ANALYSIS_SHA"

python3 - "$ANALYSIS_TMP" <<'PYSTATIC' || fail "D11_A2_analysis_static_audit_failed"
import ast, sys
from pathlib import Path

path = Path(sys.argv[1])
src = path.read_text(encoding="utf-8")
tree = ast.parse(src)

prohibited_import_roots = {
    "subprocess", "requests", "urllib", "socket", "http", "ftplib",
    "paramiko", "docker", "pymssql", "pyodbc", "sqlalchemy",
}
imports = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        imports.update(alias.name.split(".")[0] for alias in n.names)
    elif isinstance(n, ast.ImportFrom) and n.module:
        imports.add(n.module.split(".")[0])
bad_imports = sorted(imports & prohibited_import_roots)
assert not bad_imports, bad_imports

for n in ast.walk(tree):
    if isinstance(n, ast.Call):
        if isinstance(n.func, ast.Name) and n.func.id in {"eval", "exec", "compile"}:
            raise AssertionError(f"prohibited dynamic execution: {n.func.id}")

assert "candidate_traces" not in src
assert "run-primary" not in src
assert "docker compose" not in src
assert "http://" not in src
assert "https://" not in src
assert "PRIMARY_METRICS = [" in src
assert "100000" in src
assert "20000" in src
assert "holm_adjust" in src
assert "result_interpretation_executed" in src

print("D11_A2_analysis_AST_static_audit=PASS")
print("D11_A2_actual_run_primary_command_count=0")
print("D11_A2_actual_backend_or_docker_command_count=0")
print("D11_A2_candidate_trace_ingestion_planned=false")
print("D11_A2_result_interpretation_code_path_authorized=false")
PYSTATIC

python3 "$ANALYSIS_TMP" static-check --repo "$REPO" || fail "D11_A2_static_check_failed"
echo "D11_A2_static_audit_gate=PASS_BEFORE_D9_ARCHIVE_OPEN"
echo "D9_archive_opened=false"
echo "measured_receipt_ingestion_executed=false"
echo "effect_computation_started=false"

echo
echo "=== 6. Materialize/publish separate D11-A2 recovery authorization BEFORE measured ingestion ==="
python3 - \
  "$RECOVERY_AUTH" "$PARENT_HEAD" "$ANALYSIS_ID" "$OUTPUT_DIR" "$SELF_SHA" "$ANALYSIS_SHA" \
  "$EXPECT_A1_AUDIT_SHA" <<'PYAUTH' || fail "D11_A2_recovery_authorization_creation_failed"
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path

out_s, parent, analysis_id, output_dir, wrapper_sha, analysis_sha, a1_sha = sys.argv[1:]
data = {
    "contract_version": "mcad.nh_r3.e14.d11_a2.inference_recovery_authorization.v1",
    "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "classification": "AUTHORIZED_SINGLE_FRESH_D11_PREREGISTERED_INFERENCE_RECOVERY_AFTER_PRE_INGESTION_STATIC_AUDIT_FALSE_POSITIVE",
    "parent_D10_authorization_head": parent,
    "authority": {
        "D10_authorization_sha256": "a311d75e58a0fb4e7ea34aab7fb5836ce7b69a1264600a8163d8212f33446929",
        "D10_authorization_git_blob": "d1a986c28af678b1160d466fee9c93b2ac9115d4",
        "D9_freeze_manifest_sha256": "141d954c2f4e707653732aaa556847a34bc6bb5117128b5913093599f416a7df",
        "D11_A1_readonly_audit_sha256": a1_sha,
        "E5_receipt_schema_git_blob": "9dd353e1495e677c1d75cb0ccb8adfa2920c335e",
        "E6_protocol_git_blob": "a49d00a38c2c62c6d7bff26a474d3e5662e8e301",
        "E6_seed_manifest_git_blob": "c0c412e83cffcddcda62d8354571fa9fea9c04ba",
        "E7_engine_git_blob": "8a77d336d66ea292dfb728ce55beb607f65128db",
        "D0_schedule_git_blob": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    },
    "failed_D11_v1": {
        "analysis_id": "r3e_e14_d11_preregistered_inference_20260903T164348Z",
        "classification": "SELF_REFERENTIAL_STATIC_AUDIT_FALSE_POSITIVE_PRE_INGESTION",
        "wrapper_sha256": "0aefb1819d2d41cf7c2b7d64c47c802e1f5454fc7862467290933d74095b7ba7",
        "analysis_program_sha256": "8d5cf0b9693a5896b08d46691c6cf83df200e87cd107b149681cf051a216d416",
        "failure_receipt_sha256": "c1b074f06b938c60202410a99efcd21afcc1349152672371bb1277d6d976449b",
        "output_preservation_required": True,
        "output_reuse_authorized": False,
        "output_delete_authorized": False,
        "rerun_authorized": False,
        "D9_archive_opened": False,
        "measured_receipt_ingestion_executed": False,
        "measurement_integrity_executed": False,
        "effect_computation_started": False,
        "result_interpretation_executed": False,
    },
    "fresh_recovery": {
        "attempt_cardinality_authorized": 1,
        "analysis_id": analysis_id,
        "output_dir": output_dir,
        "output_dir_must_not_preexist": True,
        "wrapper_sha256": wrapper_sha,
        "analysis_program_sha256": analysis_sha,
        "static_audit_completed_before_D9_archive_open": True,
        "scientific_plan_changed": False,
        "failed_D11_v1_output_reuse_authorized": False,
        "candidate_trace_ingestion_authorized": False,
        "D9_ARM_RUNS_receipt_ingestion_authorized": True,
    },
    "measurement_integrity": {
        "must_pass_before_any_effect_computation": True,
        "frozen_requirement_count": 11,
        "required_arm_receipts": 900,
        "required_semantic_sessions": 300,
        "required_arms_per_session": 3,
        "required_candidate_actions_per_receipt": 24,
        "negative_cgroup_delta_policy": "FAIL_INTEGRITY_STOP_NO_EFFECT_COMPUTATION",
        "missing_primary_metric_policy": "FAIL_INTEGRITY_STOP_NO_EFFECT_COMPUTATION",
        "imputation_authorized": False,
        "posthoc_outlier_exclusion_authorized": False,
    },
    "inferential_scope": {
        "primary_metrics": [
            "full_backend_execution_count",
            "backend_request_count_including_gate_probes",
            "client_wall_ms",
            "sqlserver_cpu_usage_usec_delta",
            "sqlserver_io_rbytes_delta",
            "sqlserver_io_wbytes_delta",
            "response_bytes",
            "time_to_analytical_objective_completion_ms",
        ],
        "primary_comparison": "SAFE_PRUNING - PERMISSIVE_GATED",
        "permutation_replicates": 100000,
        "bootstrap_replicates": 20000,
        "familywise_alpha": 0.05,
        "multiplicity": "Holm step-down across all 8 frozen primary metrics",
        "secondary_break_even_comparison": "SAFE_PRUNING - UNGATED_EXECUTE_ADMISSIBLE",
        "secondary_confirmatory_p_values_authorized": False,
        "xmla_specific_confirmatory_p_values_authorized": False,
        "exact_E6_outcome_independent_seeds_required": True,
    },
    "execution_boundary": {
        "measurement_reexecution_authorized": False,
        "backend_query_authorized": False,
        "docker_command_authorized": False,
        "http_request_authorized": False,
        "xmla_query_authorized": False,
        "automatic_retry_authorized": False,
        "automatic_rerun_authorized": False,
        "automatic_resume_authorized": False,
        "effect_based_reseed_authorized": False,
        "result_interpretation_authorized": False,
        "claim_reporting_authorized": False,
        "cross_backend_synthesis_authorized": False,
    },
    "post_success_boundary": {
        "D12_raw_inference_result_freeze_required": True,
        "D12_must_freeze_exact_wrapper_analysis_code_integrity_receipt_raw_results_and_execution_receipt": True,
        "D13_result_interpretation_requires_separate_authorization": True,
    },
    "next": "R3-E14-D12_RAW_INFERENCE_RESULT_FREEZE_NO_INTERPRETATION",
}
Path(out_s).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("D11_A2_recovery_authorization_materialized=true")
PYAUTH

RECOVERY_AUTH_SHA="$(sha_file "$RECOVERY_AUTH")"
echo "D11_A2_recovery_authorization_sha256=$RECOVERY_AUTH_SHA"

git -C "$REPO" add -f -- "$RECOVERY_AUTH_REL" || fail "git_add_D11_A2_recovery_authorization_failed"
python3 - "$REPO" "$RECOVERY_AUTH_REL" <<'PYSTAGEAUTH' || fail "D11_A2_recovery_authorization_stage_scope_failed"
import subprocess, sys
repo, path = sys.argv[1:]
rows = subprocess.check_output(
    ["git", "-C", repo, "diff", "--cached", "--name-status"], text=True
).splitlines()
assert rows == ["A\t" + path], rows
print("D11_A2_recovery_authorization_stage_scope_gate=PASS_EXACT_ONE_NEW_CONFIG_FILE")
PYSTAGEAUTH

git -C "$REPO" diff --cached --check || fail "D11_A2_recovery_authorization_diff_check_failed"
git -C "$REPO" commit \
  -m "chore(experiments): authorize R3-E14 D11 fresh inference recovery" \
  || fail "D11_A2_recovery_authorization_commit_failed"
RECOVERY_AUTH_COMMIT_CREATED=true
REPOSITORY_MUTATED=true

RECOVERY_AUTH_COMMIT="$(git -C "$REPO" rev-parse HEAD)"
RECOVERY_AUTH_PARENT="$(git -C "$REPO" rev-parse HEAD^)"
echo "D11_A2_recovery_authorization_commit=$RECOVERY_AUTH_COMMIT"
echo "D11_A2_recovery_authorization_commit_parent=$RECOVERY_AUTH_PARENT"
[[ "$RECOVERY_AUTH_PARENT" == "$PARENT_HEAD" ]] || fail "D11_A2_recovery_authorization_parent_mismatch"

REMOTE_PRE_PUSH="$(git -C "$REPO" ls-remote origin "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"
[[ "$REMOTE_PRE_PUSH" == "$PARENT_HEAD" ]] || fail "remote_moved_before_D11_A2_authorization_push"
git -C "$REPO" push origin "HEAD:$BRANCH" || fail "D11_A2_recovery_authorization_push_failed"
RECOVERY_AUTH_PUSHED=true
REMOTE_AFTER_PUSH="$(git -C "$REPO" ls-remote origin "refs/heads/$BRANCH" | awk 'NR==1{print $1}')"
[[ "$REMOTE_AFTER_PUSH" == "$RECOVERY_AUTH_COMMIT" ]] || fail "remote_not_exact_D11_A2_authorization_commit"
echo "D11_A2_recovery_authorization_push_gate=PASS"

echo
echo "=== 7. Create fresh authorized output and copy exact code/provenance; failed D11-v1 untouched ==="
mkdir "$OUTPUT_DIR" || fail "fresh_D11_A2_output_dir_creation_failed"
OUTPUT_DIR_CREATED=true
cp -- "$ANALYSIS_TMP" "$ANALYSIS_PROGRAM" || fail "copy_D11_A2_analysis_program_failed"
cp -- "$(readlink -f "$0")" "$WRAPPER_COPY" || fail "copy_D11_A2_wrapper_failed"
cp -- "$RECOVERY_AUTH" "$AUTH_COPY" || fail "copy_D11_A2_authorization_failed"
chmod 0755 "$ANALYSIS_PROGRAM" "$WRAPPER_COPY"

[[ "$(sha_file "$ANALYSIS_PROGRAM")" == "$ANALYSIS_SHA" ]] || fail "copied_analysis_program_sha_changed"
[[ "$(sha_file "$WRAPPER_COPY")" == "$SELF_SHA" ]] || fail "copied_wrapper_sha_changed"
[[ "$(sha_file "$AUTH_COPY")" == "$RECOVERY_AUTH_SHA" ]] || fail "copied_authorization_sha_changed"

FAILED_COUNT_AFTER="$(find "$FAILED_OUTPUT" -maxdepth 1 -type f | wc -l | tr -d ' ')"
[[ "$FAILED_COUNT_AFTER" == "3" ]] || fail "failed_D11_v1_output_changed_after_authorization"
[[ "$(sha_file "$FAILED_WRAPPER")" == "$EXPECT_FAILED_WRAPPER_SHA" ]] || fail "failed_D11_v1_wrapper_changed_after_authorization"
[[ "$(sha_file "$FAILED_ANALYSIS")" == "$EXPECT_FAILED_ANALYSIS_SHA" ]] || fail "failed_D11_v1_analysis_changed_after_authorization"
[[ "$(sha_file "$FAILED_RECEIPT")" == "$EXPECT_FAILED_RECEIPT_SHA" ]] || fail "failed_D11_v1_receipt_changed_after_authorization"
echo "failed_D11_v1_post_authorization_preservation_gate=PASS"

echo
echo "=== 8. D9 byte authentication; NO archive decompression yet ==="
(
  cd "$D9_EVIDENCE"
  sha256sum -c SHA256SUMS >/dev/null
) || fail "D9_frozen_evidence_sha256_verification_failed"
ARM_ARCHIVE_PART_COUNT="$(find "$D9_EVIDENCE" -maxdepth 1 -type f -name 'ARM_RUNS.tar.gz.part-*' | wc -l | tr -d ' ')"
TRACE_ARCHIVE_PART_COUNT="$(find "$D9_EVIDENCE" -maxdepth 1 -type f -name 'CANDIDATE_TRACES.tar.gz.part-*' | wc -l | tr -d ' ')"
echo "D9_arm_archive_part_count=$ARM_ARCHIVE_PART_COUNT"
echo "D9_candidate_trace_archive_part_count=$TRACE_ARCHIVE_PART_COUNT"
[[ "$ARM_ARCHIVE_PART_COUNT" -ge 1 ]] || fail "D9_arm_archive_parts_missing"
[[ "$TRACE_ARCHIVE_PART_COUNT" -ge 1 ]] || fail "D9_candidate_trace_archive_parts_missing"
echo "D9_byte_authentication_gate=PASS"
echo "D9_archive_decompressed=false"
echo "candidate_trace_archive_opened=false"

echo
echo "=== 9. FINAL single fresh preregistered D11-A2 execution ==="
echo "D11_MEASURED_INGESTION_STARTING=true"
echo "NO_RETRY_NO_RERUN_NO_RESUME_NO_RESEED_IF_ANY_FAILURE=true"
D9_ARCHIVE_OPENED=true

set +e
python3 "$ANALYSIS_PROGRAM" run \
  --repo "$REPO" \
  --d9-evidence "$D9_EVIDENCE" \
  --output-dir "$OUTPUT_DIR" \
  --analysis-id "$ANALYSIS_ID" \
  2>&1 | tee "$CONSOLE_LOG"
ANALYSIS_STATUS=${PIPESTATUS[0]}
set -e

echo "D11_A2_analysis_exit_status=$ANALYSIS_STATUS"

if [[ -f "$STATE_FILE" ]]; then
  python3 - "$STATE_FILE" <<'PYSTATEPRINT'
import json, sys
from pathlib import Path
s = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in [
    "d9_archive_opened",
    "measured_receipt_ingestion_executed",
    "measurement_integrity_executed",
    "measurement_integrity_pass",
    "effect_computation_started",
    "effect_computation_completed",
    "result_interpretation_executed",
    "claim_reporting_executed",
]:
    print(f"D11_STATE_{key}={str(s.get(key)).lower()}")
PYSTATEPRINT
fi

if [[ "$ANALYSIS_STATUS" -ne 0 ]]; then
  python3 - \
    "$FAILURE_RECEIPT" "$ANALYSIS_ID" "$ANALYSIS_STATUS" "$RECOVERY_AUTH_COMMIT" \
    "$SELF_SHA" "$ANALYSIS_SHA" "$CONSOLE_LOG" "$STATE_FILE" <<'PYFAIL'
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

out_s, analysis_id, status_s, auth_commit, wrapper_sha, analysis_sha, console_s, state_s = sys.argv[1:]
def sha(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
state_path = Path(state_s)
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
data = {
    "contract_version": "mcad.nh_r3.e14.d11_a2.failure_receipt.v1",
    "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "analysis_id": analysis_id,
    "analysis_exit_status": int(status_s),
    "recovery_authorization_commit": auth_commit,
    "wrapper_sha256": wrapper_sha,
    "analysis_program_sha256": analysis_sha,
    "console_sha256": sha(Path(console_s)),
    "state": state,
    "automatic_retry_executed": False,
    "automatic_rerun_executed": False,
    "automatic_resume_executed": False,
    "effect_based_reseed_executed": False,
    "result_interpretation_executed": False,
    "claim_reporting_executed": False,
    "next": "SEPARATE_D11_A3_FAILURE_AUDIT_REQUIRED",
}
Path(out_s).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("D11_A2_failure_receipt_created=true")
PYFAIL
  echo "D11_A2_failure_receipt_sha256=$(sha_file "$FAILURE_RECEIPT")"
  echo "R3E_E14_D11_A2_PREREGISTERED_INFERENCE_EXECUTION=FAILED_OR_PARTIAL"
  echo "SEPARATE_FAILURE_AUDIT_REQUIRED=true"
  echo "RESULT_INTERPRETATION_ALLOWED=false"
  echo "DO_NOT_RERUN=true"
  echo "=== STOP ==="
  exit 1
fi

echo
echo "=== 10. Mechanical completion check ONLY; DO NOT print/interpret result values ==="
[[ -f "$STATE_FILE" ]] || fail "D11_state_missing_after_success"
[[ -f "$INTEGRITY_RECEIPT" ]] || fail "D11_integrity_receipt_missing_after_success"
[[ -f "$RAW_RESULTS" ]] || fail "D11_raw_results_missing_after_success"
[[ -f "$CONSOLE_LOG" ]] || fail "D11_console_missing_after_success"

python3 - "$STATE_FILE" "$INTEGRITY_RECEIPT" <<'PYCOMPLETE' || fail "D11_mechanical_completion_gate_failed"
import json, sys
from pathlib import Path
state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
integrity = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert state["d9_archive_opened"] is True
assert state["measured_receipt_ingestion_executed"] is True
assert state["measurement_integrity_executed"] is True
assert state["measurement_integrity_pass"] is True
assert state["effect_computation_started"] is True
assert state["effect_computation_completed"] is True
assert state["result_interpretation_executed"] is False
assert state["claim_reporting_executed"] is False
assert integrity["classification"] == "PASS_ALL_11_FROZEN_E6_INTEGRITY_REQUIREMENTS"
assert integrity["arm_receipts"] == 900
assert integrity["semantic_sessions"] == 300
assert integrity["frozen_requirement_count"] == 11
assert integrity["archive"]["archive_member_count"] == 900
assert integrity["archive"]["archive_member_hashes_verified"] == 900
print("D11_mechanical_completion_gate=PASS_INTEGRITY_AND_EFFECT_COMPUTATION_COMPLETE")
print("D11_result_file_content_read_by_wrapper=false")
print("D11_result_interpretation_executed=false")
PYCOMPLETE

MEASURED_RECEIPT_INGESTION_EXECUTED=true
MEASUREMENT_INTEGRITY_EXECUTED=true
EFFECT_COMPUTATION_STARTED=true
EFFECT_COMPUTATION_COMPLETED=true

RAW_RESULTS_SHA="$(sha_file "$RAW_RESULTS")"
INTEGRITY_SHA="$(sha_file "$INTEGRITY_RECEIPT")"
STATE_SHA="$(sha_file "$STATE_FILE")"
CONSOLE_SHA="$(sha_file "$CONSOLE_LOG")"

python3 - \
  "$EXECUTION_RECEIPT" "$ANALYSIS_ID" "$RECOVERY_AUTH_COMMIT" "$RECOVERY_AUTH_SHA" \
  "$SELF_SHA" "$ANALYSIS_SHA" "$RAW_RESULTS_SHA" "$INTEGRITY_SHA" "$STATE_SHA" "$CONSOLE_SHA" <<'PYEXEC' 
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path

(out_s, analysis_id, auth_commit, auth_sha, wrapper_sha, analysis_sha,
 raw_sha, integrity_sha, state_sha, console_sha) = sys.argv[1:]

data = {
    "contract_version": "mcad.nh_r3.e14.d11_a2.raw_inference_execution_receipt.v1",
    "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "classification": "RAW_PREREGISTERED_INFERENCE_COMPLETE_PENDING_D12_FREEZE_NO_RESULT_INTERPRETATION",
    "analysis_id": analysis_id,
    "source_run_id": "r3e_e14_d8_a3_replacement_primary300_20260903T105543Z",
    "recovery_authorization_commit": auth_commit,
    "recovery_authorization_sha256": auth_sha,
    "wrapper_sha256": wrapper_sha,
    "analysis_program_sha256": analysis_sha,
    "raw_inference_results_sha256": raw_sha,
    "measurement_integrity_receipt_sha256": integrity_sha,
    "state_sha256": state_sha,
    "console_sha256": console_sha,
    "mechanical_completion": {
        "measured_arm_receipts_ingested": 900,
        "semantic_sessions": 300,
        "primary_metric_count": 8,
        "primary_permutation_replicates_each": 100000,
        "primary_bootstrap_replicates_each": 20000,
        "holm_family_size": 8,
        "secondary_break_even_metric_count": 8,
        "xmla_diagnostic_metric_count": 3,
        "measurement_integrity_pass": True,
        "effect_computation_completed": True,
    },
    "scientific_boundary": {
        "result_values_printed_to_console": False,
        "result_interpretation_executed": False,
        "claim_reporting_executed": False,
        "cross_backend_synthesis_executed": False,
        "measurement_reexecution_executed": False,
        "D12_raw_result_freeze_required": True,
        "D13_result_interpretation_requires_separate_authorization": True,
    },
    "failure_policy": {
        "automatic_retry_executed": False,
        "automatic_rerun_executed": False,
        "automatic_resume_executed": False,
        "effect_based_reseed_executed": False,
    },
    "next": "R3-E14-D12_RAW_INFERENCE_RESULT_FREEZE_NO_INTERPRETATION",
}
Path(out_s).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("D11_A2_execution_receipt_created=true")
PYEXEC
PYEXEC_STATUS=$?
[[ "$PYEXEC_STATUS" -eq 0 ]] || fail "D11_execution_receipt_creation_failed"

EXECUTION_RECEIPT_SHA="$(sha_file "$EXECUTION_RECEIPT")"

echo
echo "=== 11. Final D11-A2 boundary: raw inference exists, interpretation remains forbidden ==="
echo "analysis_id=$ANALYSIS_ID"
echo "output_dir=$OUTPUT_DIR"
echo "D11_A2_recovery_authorization_commit=$RECOVERY_AUTH_COMMIT"
echo "D11_A2_recovery_authorization_sha256=$RECOVERY_AUTH_SHA"
echo "D11_A2_wrapper_sha256=$SELF_SHA"
echo "D11_A2_analysis_program_sha256=$ANALYSIS_SHA"
echo "D11_measurement_integrity_receipt_sha256=$INTEGRITY_SHA"
echo "D11_raw_inference_results_sha256=$RAW_RESULTS_SHA"
echo "D11_state_sha256=$STATE_SHA"
echo "D11_console_sha256=$CONSOLE_SHA"
echo "D11_execution_receipt_sha256=$EXECUTION_RECEIPT_SHA"
echo "D11_MEASURED_RECEIPT_INGESTION_EXECUTED=true"
echo "D11_MEASUREMENT_INTEGRITY=PASS"
echo "D11_EFFECT_COMPUTATION_COMPLETED=true"
echo "D11_RESULT_VALUES_PRINTED_TO_CONSOLE=false"
echo "D11_RESULT_INTERPRETATION_EXECUTED=false"
echo "D11_CLAIM_REPORTING_EXECUTED=false"
echo "D11_CROSS_BACKEND_SYNTHESIS_EXECUTED=false"
echo "D11_CANDIDATE_TRACE_INGESTION_EXECUTED=false"
echo "measurement_reexecution_executed=false"
echo "automatic_retry_executed=false"
echo "automatic_rerun_executed=false"
echo "automatic_resume_executed=false"
echo "effect_based_reseed_executed=false"
echo "docker_command_executed=false"
echo "backend_http_request_executed=false"
echo "xmla_query_executed=false"
echo "D12_RAW_INFERENCE_RESULT_FREEZE_REQUIRED=true"
echo "D13_RESULT_INTERPRETATION_REQUIRES_SEPARATE_AUTHORIZATION=true"
echo "R3E_E14_D11_A2_PREREGISTERED_INFERENCE_EXECUTION=PASS_RAW_INFERENCE_COMPLETE_PENDING_D12_FREEZE_NO_RESULT_INTERPRETATION"
echo "NEXT=RETURN_FULL_OUTPUT_FOR_D12_RAW_INFERENCE_RESULT_FREEZE_NO_INTERPRETATION"
echo "=== STOP ==="
