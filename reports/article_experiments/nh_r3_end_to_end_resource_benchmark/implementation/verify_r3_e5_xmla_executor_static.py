#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"

PARENT = "e34ba8e6e0c1267974305053557c6a28acfe2c11"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

CONTRACT = R3 / "config/r3_e5_xmla_executor_receipt_static_contract.json"
SCHEMA = R3 / "config/r3_e5_xmla_arm_receipt_schema.json"
EXECUTOR = R3 / "implementation/r3_e5_xmla_executor_static.py"
STATIC_RECEIPT = R3 / "results/e5_xmla_executor_static_receipt.json"

EXPECTED_BLOBS = {
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e1_xmla_isolated_runtime_plan.json":
        "7c158aa3d3cc2de552c1b078517af0eda107965c",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e3c_emondrian_pinned_build_inputs.json":
        "1e518596373205472b6df52633c5b130b43fc483",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e4_xmla_external_overlay_static_contract.json":
        "a07d35b69ff8c717c5d4c2610ba28685f0873827",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_d0_confirmatory_inference_protocol.json":
        "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_d0_confirmatory_primary_arm_order_schedule.csv":
        "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/r3_d0_confirmatory_plan.py":
        "54750b314717dc370ca65f84ca765c338b4abb2c",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/r3_dev_pilot_executor.py":
        "5eeaf00e00dfd6561959c81941acc902acf8b509",
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
ARMS = {"UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_git_authorities() -> None:
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git("rev-parse", f"{PARENT}^{{commit}}") != PARENT:
        raise RuntimeError("E4 parent missing")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", PARENT, "HEAD"], check=True)
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git("rev-parse", f"HEAD:{rel}")
        if actual != expected:
            raise RuntimeError(f"frozen authority changed: {rel} -> {actual}")


def verify_inherited_science() -> None:
    e1 = load_json(R3 / "config/r3_e1_xmla_isolated_runtime_plan.json")
    e4 = load_json(R3 / "config/r3_e4_xmla_external_overlay_static_contract.json")
    d0 = load_json(R3 / "config/r3_d0_confirmatory_inference_protocol.json")

    if e1["scientific_role"] != "SECONDARY_END_TO_END_CONFIRMATION":
        raise RuntimeError("E1 scientific role changed")
    if e1["frozen_reuse"]["confirmatory_test_sessions"] != 300:
        raise RuntimeError("E1 confirmatory cohort changed")
    if e1["frozen_reuse"]["arm_runs"] != 900:
        raise RuntimeError("E1 arm-run count changed")
    if e1["frozen_reuse"]["three_arms"] != [
        "UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING"
    ]:
        raise RuntimeError("E1 arm set/order changed")
    if e1["resource_attribution"]["shared_r3_metrics_preserved"] != SHARED:
        raise RuntimeError("shared R3 metric family changed")
    if e1["resource_attribution"]["xmla_specific_additional_metrics"] != XMLA_EXTRA:
        raise RuntimeError("XMLA-specific metric family changed")
    if e1["resource_attribution"]["new_global_claim_authorized"] is not False:
        raise RuntimeError("E1 unexpectedly authorizes global claim")

    if e4["parent_e3c_head"] != "43c0e5855909b045fbc1e0395d697a9794f02c10":
        raise RuntimeError("E4 parent binding changed")
    if e4["isolated_runtime"]["project_name"] != "mcad-r3e-xmla1":
        raise RuntimeError("E4 runtime project changed")
    if e4["execution_boundary"]["measurement_allowed"] is not False:
        raise RuntimeError("E4 unexpectedly authorizes measurement")

    family = d0["primary_endpoint_family"]
    if family["metrics"] != SHARED:
        raise RuntimeError("D0 primary endpoint family changed")
    if family["comparison"] != "SAFE_PRUNING - PERMISSIVE_GATED":
        raise RuntimeError("D0 primary comparison changed")
    if d0["secondary_break_even_family"]["comparison"] != "SAFE_PRUNING - UNGATED_EXECUTE_ADMISSIBLE":
        raise RuntimeError("D0 break-even comparison changed")
    if family["multiplicity"] != "Holm step-down across all 8 frozen primary metrics":
        raise RuntimeError("D0 multiplicity rule changed")


def verify_schedule() -> None:
    schedule = R3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv"
    with schedule.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 300:
        raise RuntimeError("primary schedule row count changed")
    if len({r["session_id"] for r in rows}) != 300:
        raise RuntimeError("primary schedule session ids changed")
    strata = Counter((r["topology"], r["pattern"]) for r in rows)
    if len(strata) != 20 or set(strata.values()) != {15}:
        raise RuntimeError("primary 20x15 stratification changed")
    for row in rows:
        if row["selection_role"] != "CONFIRMATORY_PRIMARY":
            raise RuntimeError("schedule selection role changed")
        ordered = [row["arm_1"], row["arm_2"], row["arm_3"]]
        if set(ordered) != ARMS or len(set(ordered)) != 3:
            raise RuntimeError("schedule arm permutation changed")


def verify_contract_and_schema() -> None:
    c = load_json(CONTRACT)
    s = load_json(SCHEMA)
    r = load_json(STATIC_RECEIPT)

    if c["contract_version"] != "mcad.nh_r3.e5.xmla_executor_receipt_static.v1":
        raise RuntimeError("unexpected E5 contract version")
    if c["parent_e4_head"] != PARENT:
        raise RuntimeError("E5 parent binding changed")
    if c["backend"] != {
        "adapter": "xmla_mondrian",
        "catalog": "AdventureWorksDW",
        "cube": "Adventure Works DW",
        "dataset": "AdventureWorksDW",
        "physical_query_language": "xmla_mdx",
        "warehouse_id": "adventureworks_xmla",
    }:
        raise RuntimeError("E5 backend identity changed")

    plan = c["frozen_plan"]
    expected_counts = {
        "semantic_sessions": 300,
        "strata": 20,
        "sessions_per_stratum": 15,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "candidates_per_arm_run": 24,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fixed_warmup_template_count": 7,
    }
    for key, value in expected_counts.items():
        if plan[key] != value:
            raise RuntimeError(f"E5 frozen plan changed: {key}")
    if plan["arms"] != ["UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING"]:
        raise RuntimeError("E5 arms changed")
    if plan["effect_size_tuning_performed"] is not False:
        raise RuntimeError("effect-size tuning flag changed")
    if plan["scientific_redesign_performed"] is not False:
        raise RuntimeError("scientific redesign flag changed")

    ra = c["resource_accounting"]
    if ra["shared_r3_primary_endpoint_family"] != SHARED:
        raise RuntimeError("E5 shared endpoint family changed")
    if ra["xmla_specific_additional_metrics"] != XMLA_EXTRA:
        raise RuntimeError("E5 XMLA metric family changed")
    if ra["xmla_specific_confirmatory_p_values_authorized"] is not False:
        raise RuntimeError("E5 prematurely authorizes XMLA p-values")
    if ra["negative_cgroup_delta_policy"] != "INVALIDATE_ARM_RUN_NEVER_CLAMP_TO_ZERO":
        raise RuntimeError("negative cgroup delta policy changed")

    boundary = c["runtime_boundary"]
    for key in [
        "bundle_read_required_in_e5", "docker_load_allowed", "docker_build_allowed",
        "container_create_start_restart_allowed", "database_restore_allowed",
        "http_request_allowed", "backend_query_allowed", "measurement_allowed",
        "measurement_authorization_file_present", "live_executor_implemented_in_e5",
    ]:
        if boundary[key] is not False:
            raise RuntimeError(f"E5 runtime boundary changed: {key}")

    required = set(s["required"])
    must = {
        "session_id", "arm", "candidate_actions",
        "full_backend_execution_count", "backend_request_count_including_gate_probes",
        "client_wall_ms", "time_to_analytical_objective_completion_ms",
        "sqlserver_cpu_usage_usec_delta", "sqlserver_io_rbytes_delta", "sqlserver_io_wbytes_delta",
        "emondrian_cpu_usage_usec_delta", "emondrian_io_rbytes_delta", "emondrian_io_wbytes_delta",
        "runtime_identity", "integrity_flags",
    }
    if not must.issubset(required):
        raise RuntimeError(f"E5 receipt schema missing required fields: {sorted(must - required)}")
    if s["properties"]["candidate_actions"].get("const") != 24:
        raise RuntimeError("receipt candidate count changed")
    if s["properties"]["integrity_flags"]["properties"]["secret_value_recorded"].get("const") is not False:
        raise RuntimeError("receipt schema permits secret recording")

    if r["parent_e4_head"] != PARENT:
        raise RuntimeError("static receipt parent changed")
    if r["measurement_performed"] is not False:
        raise RuntimeError("static receipt claims measurement")
    if r["backend_query_executed"] is not False:
        raise RuntimeError("static receipt claims backend execution")


def verify_executor_source_is_static_only() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    forbidden_imports = {"requests", "urllib", "http", "socket", "docker"}
    bad = imports & forbidden_imports
    if bad:
        raise RuntimeError(f"E5 static executor imports network/runtime modules: {sorted(bad)}")
    for token in ["http://", "https://", "/measurement/", "docker compose", "docker run", "docker exec"]:
        if token in source:
            raise RuntimeError(f"E5 static executor contains forbidden runtime token: {token}")


def load_executor():
    spec = importlib.util.spec_from_file_location("r3_e5_executor", EXECUTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import E5 executor")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_dry_run_and_refusal() -> None:
    mod = load_executor()
    dry = mod.dry_run(ROOT)
    expected = {
        "semantic_sessions": 300,
        "strata": 20,
        "sessions_per_stratum": 15,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "candidates_per_arm_run": 24,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fixed_warmup_template_count": 7,
        "expected_future_arm_receipts": 900,
    }
    for key, value in expected.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"E5 dry-run count changed: {key}")
    for key in [
        "measurement_authorized", "measurement_executed", "backend_query_executed",
        "http_request_executed", "docker_command_executed", "database_restore_performed",
        "effect_analysis_performed", "global_system_benefit_claim_authorized",
        "xmla_specific_confirmatory_p_values_authorized",
    ]:
        if dry[key] is not False:
            raise RuntimeError(f"E5 dry run unexpectedly enables {key}")

    try:
        mod.prove_measurement_refusal(ROOT)
    except RuntimeError as exc:
        expected_msg = (
            "R3-E5 is a static executor/receipt contract only; "
            "no R3-E materialization or measured-execution authorization exists"
        )
        if str(exc) != expected_msg:
            raise
    else:
        raise RuntimeError("E5 measured-execution refusal disappeared")


def main() -> None:
    verify_git_authorities()
    verify_inherited_science()
    verify_schedule()
    verify_contract_and_schema()
    verify_executor_source_is_static_only()
    verify_dry_run_and_refusal()

    print("e4_parent_and_lineage=PASS")
    print("frozen_d0_e1_e3c_e4_authorities=PASS")
    print("confirmatory_primary_schedule_300x3=PASS")
    print("shared_primary_endpoint_family_8=PASS")
    print("xmla_specific_resource_diagnostics_3=PASS")
    print("arm_receipt_schema=PASS")
    print("static_executor_no_network_or_docker_imports=PASS")
    print("measurement_authorization_present=false")
    print("backend_query_executed=false")
    print("measurement_executed=false")
    print("effect_analysis_performed=false")
    print("R3_E5_XMLA_EXECUTOR_RECEIPT_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
