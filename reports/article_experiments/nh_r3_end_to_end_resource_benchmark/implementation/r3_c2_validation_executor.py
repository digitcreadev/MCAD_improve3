#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
C1_HEAD = "082457760ba1602c5eda5f74a9cb653eed3552e1"

C1_CONTRACT_SHA = "d3e3ac7b44e04a1720c780acff25fcb673f322a1"
C1_PLAN_SHA = "612edec91932d5abeb16da51b10eca6e58fb3c32"
B2E_EXECUTOR_SHA = "5eeaf00e00dfd6561959c81941acc902acf8b509"
B2K_ADAPTER_SHA = "41792ef397834dcea7369882c6273e693d2608e9"

AUTH_REL = R3_REL / "config/r3_c3_validation_measurement_authorization.json"
CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_C_VALIDATION_40"

DEFAULT_MCAD_BASE = "http://127.0.0.1:18000"
DEFAULT_PROXY_BASE = "http://127.0.0.1:19000"

ARMS = ("UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def import_modules(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        c1 = importlib.import_module("r3_c1_validation_plan")
        b2k = importlib.import_module("r3_isolated_executor_adapter")
        b2e = importlib.import_module("r3_dev_pilot_executor")
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass
    return c1, b2k, b2e


def validate_static_authorities(repo: Path) -> tuple[Any, Any, Any, dict[str, Any]]:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", C1_HEAD, "HEAD"], check=True)

    c1_path = repo / R3_REL / "config/r3_c1_validation_stage_contract.json"
    plan_path = repo / R3_REL / "implementation/r3_c1_validation_plan.py"
    b2e_path = repo / R3_REL / "implementation/r3_dev_pilot_executor.py"
    b2k_path = repo / R3_REL / "implementation/r3_isolated_executor_adapter.py"

    if git_blob_sha1(c1_path) != C1_CONTRACT_SHA:
        raise RuntimeError("R3-C1 contract changed")
    if git_blob_sha1(plan_path) != C1_PLAN_SHA:
        raise RuntimeError("R3-C1 plan changed")
    if git_blob_sha1(b2e_path) != B2E_EXECUTOR_SHA:
        raise RuntimeError("frozen B2e executor changed")
    if git_blob_sha1(b2k_path) != B2K_ADAPTER_SHA:
        raise RuntimeError("B2k isolated adapter changed")

    c1, b2k, b2e = import_modules(repo)
    plan = c1.build_plan(repo)

    if plan["semantic_sessions"] != 40:
        raise RuntimeError("validation plan semantic session count changed")
    if len(plan["arm_runs"]) != 120:
        raise RuntimeError("validation plan arm count changed")
    if len(plan["candidate_actions"]) != 2880:
        raise RuntimeError("validation plan candidate action count changed")
    if plan["gate_evaluations_planned"] != 1920:
        raise RuntimeError("validation plan gate count changed")
    if plan["gated_arm_runs"] != 80 or plan["ungated_arm_runs"] != 40:
        raise RuntimeError("validation plan arm partition changed")
    if plan["effect_size_tuning_performed"] is not False:
        raise RuntimeError("effect-size tuning flag changed")
    if plan["scientific_redesign_performed"] is not False:
        raise RuntimeError("scientific redesign flag changed")

    # Reuse the already-audited B2k routing patch. It mutates Python module
    # objects only; it does not execute Docker in this static path.
    patched_b2e, _ = b2k.patch_frozen_executor(repo)

    by_arm = patched_b2e.actions_by_arm(plan)
    if len(by_arm) != 120:
        raise RuntimeError("executor arm-group cardinality mismatch")
    if any(len(rows) != 24 for rows in by_arm.values()):
        raise RuntimeError("executor candidate grouping mismatch")

    completion_hits = {}
    for arm_run in plan["arm_runs"]:
        key = (str(arm_run["session_id"]), str(arm_run["arm"]))
        rows = by_arm[key]
        hits = [a for a in rows if bool(a["is_completion_candidate"])]
        if len(hits) != 1:
            raise RuntimeError(f"{key}: completion candidate count != 1")
        completion_hits[key] = int(hits[0]["candidate_index"])
        if completion_hits[key] != int(arm_run["completion_candidate"]):
            raise RuntimeError(f"{key}: completion boundary mismatch")

    return c1, b2k, patched_b2e, plan


def validate_future_authorization(repo: Path) -> dict[str, Any]:
    auth_path = repo / AUTH_REL
    if not auth_path.is_file():
        raise RuntimeError("R3-C3 measurement authorization file absent; R3-C measurement remains forbidden")
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.c3.validation_measurement_authorization.v1":
        raise RuntimeError("unexpected R3-C3 authorization contract")
    auth = data.get("authorization")
    if not isinstance(auth, dict):
        raise RuntimeError("R3-C3 authorization payload missing")
    if auth.get("validation_measured_execution_authorized") is not True:
        raise RuntimeError("R3-C measured validation not authorized")
    if auth.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("R3-C cannot authorize confirmatory claims")
    if auth.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("R3-C authorization indicates effect-size tuning")
    if data.get("c1_head") != C1_HEAD:
        raise RuntimeError("R3-C3 authorization not bound to frozen C1 head")
    return data


def dry_run(repo: Path) -> dict[str, Any]:
    _, b2k, patched_b2e, plan = validate_static_authorities(repo)
    routing_probe = patched_b2e.compose_cmd(
        repo,
        Path("/nonexistent/ignored.override.yml"),
        "restart",
        b2k.MCAD_API_SERVICE,
    )
    joined = " ".join(routing_probe)
    if "bi-stack/docker-compose.yml" in joined:
        raise RuntimeError("historical compose leaked into R3-C2 routing probe")
    if "-p mcad-r3-rerun1" not in joined:
        raise RuntimeError("isolated Docker project missing from routing probe")
    if "r3_isolated_runtime.compose.yml" not in joined:
        raise RuntimeError("isolated compose file missing from routing probe")

    return {
        "contract_version": "mcad.nh_r3.c2.validation_executor_dry_run.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "semantic_sessions": plan["semantic_sessions"],
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": plan["gate_evaluations_planned"],
        "gated_arm_runs": plan["gated_arm_runs"],
        "ungated_arm_runs": plan["ungated_arm_runs"],
        "mcad_api_restarts_planned": plan["mcad_api_restarts_planned"],
        "fresh_mcad_sessions_planned": plan["fresh_mcad_sessions_planned"],
        "historical_compose_targeted": False,
        "isolated_project": b2k.PROJECT,
        "isolated_mcad_api_service": b2k.MCAD_API_SERVICE,
        "isolated_sqlserver_service": b2k.SQLSERVER_SERVICE,
        "isolated_proxy_service": b2k.PROXY_SERVICE,
        "measurement_authorized": False,
        "measurement_executed": False,
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
    }


def ensure_output_outside_repo(repo: Path, output_dir: Path) -> None:
    repo = repo.resolve()
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(repo)
    except ValueError:
        return
    raise RuntimeError("measured validation output must be outside repository")


def run_validation(
    repo: Path,
    runtime_root: Path,
    output_dir: Path,
    proxy_base: str,
    mcad_base: str,
    confirm: str,
) -> dict[str, Any]:
    # This function is intentionally unreachable during R3-C2.
    if confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit R3-C validation confirmation token required")
    validate_future_authorization(repo)

    _, b2k, b2e, plan = validate_static_authorities(repo)
    b1_contract, _ = b2e.validate_frozen_authorities(repo)
    b2k.require_runtime_environment(repo, runtime_root)
    ensure_output_outside_repo(repo, output_dir)
    if output_dir.exists():
        raise RuntimeError(f"output directory already exists: {output_dir}")

    by_arm = b2e.actions_by_arm(plan)
    static_runner = b2e.import_static_runner(repo)

    output_dir.mkdir(parents=True)
    arm_dir = output_dir / "arm_runs"
    arm_dir.mkdir()

    summary_rows: list[dict[str, Any]] = []

    for ordinal, arm_run in enumerate(plan["arm_runs"], start=1):
        session_id = str(arm_run["session_id"])
        arm = str(arm_run["arm"])
        arm_position = int(arm_run["arm_position"])
        actions = by_arm[(session_id, arm)]

        # Same preregistered cache-control operation used by the frozen DEV executor.
        b2e.restart_mcad_api(repo, repo / b2k.COMPOSE_REL, mcad_base)
        gate_session_id = (
            b2e.create_fresh_session(mcad_base)
            if arm != "UNGATED_EXECUTE_ADMISSIBLE"
            else None
        )

        cgroup_before = static_runner.read_sqlserver_cgroup_snapshot(repo)
        gate_evaluations = 0
        full_backend_requests = 0
        nvac_backend_requests = 0
        response_bytes = 0
        candidate_records: list[dict[str, Any]] = []
        completion_ns: int | None = None
        wall_start_ns = time.perf_counter_ns()

        for action in actions:
            query_id = str(action["query_id"])
            mdx = b2e.read_template(repo, action)
            gate_data: dict[str, Any] | None = None
            full_data: dict[str, Any] | None = None
            nvac_data: dict[str, Any] | None = None
            live_gate_decision: str | None = None

            if bool(action["run_gate"]):
                gate_evaluations += 1
                payload = {
                    "mdx": mdx,
                    "query_type": "mdx",
                    "query_id": query_id,
                    "objective_id": b2e.OBJECTIVE_ID,
                    "session_id": gate_session_id,
                    "dw_id": b2e.DW_ID,
                }
                gate_data = b2e.post_json(
                    f"{proxy_base.rstrip('/')}/bi/r3/measurement/gate-only",
                    payload,
                    timeout_s=180.0,
                )
                b2e.validate_gate_response(gate_data, query_id)
                reqs, probe_bytes, nvac_data = b2e.gate_accounting(gate_data)
                nvac_backend_requests += reqs
                response_bytes += probe_bytes
                decision = gate_data.get("decision")
                if isinstance(decision, dict) and decision.get("decision") is not None:
                    live_gate_decision = str(decision.get("decision"))

            if bool(action["run_full_backend"]):
                payload = {
                    "mdx": mdx,
                    "query_type": "mdx",
                    "query_id": query_id,
                    "objective_id": b2e.OBJECTIVE_ID,
                    "session_id": gate_session_id,
                    "dw_id": b2e.DW_ID,
                    "allow_fallback": False,
                }
                full_data = b2e.post_json(
                    f"{proxy_base.rstrip('/')}/bi/r3/measurement/full-execute",
                    payload,
                    timeout_s=180.0,
                )
                b2e.validate_full_response(full_data, query_id)
                full_backend_requests += b2e.int0(full_data.get("backend_request_count"))
                response_bytes += b2e.int0(full_data.get("response_bytes"))

            candidate_done_ns = time.perf_counter_ns()
            if bool(action["is_completion_candidate"]):
                if completion_ns is not None:
                    raise RuntimeError(f"multiple completion candidates for {session_id}/{arm}")
                completion_ns = candidate_done_ns

            candidate_records.append({
                "candidate_index": int(action["candidate_index"]),
                "query_id": query_id,
                "template_id": str(action["template_id"]),
                "frozen_class": str(action["frozen_class"]),
                "frozen_operational_action": str(action["frozen_operational_action"]),
                "run_gate": bool(action["run_gate"]),
                "run_full_backend": bool(action["run_full_backend"]),
                "is_completion_candidate": bool(action["is_completion_candidate"]),
                "live_gate_decision": live_gate_decision,
                "gate_elapsed_ms": gate_data.get("gate_elapsed_ms") if gate_data else None,
                "nvac": nvac_data,
                "full_elapsed_ms": full_data.get("elapsed_ms") if full_data else None,
                "full_response_bytes": full_data.get("response_bytes") if full_data else None,
                "full_result_digest": full_data.get("result_digest") if full_data else None,
                "full_row_count": full_data.get("row_count") if full_data else None,
            })

        wall_stop_ns = time.perf_counter_ns()
        if completion_ns is None:
            raise RuntimeError(f"completion candidate not reached for {session_id}/{arm}")

        cgroup_after = static_runner.read_sqlserver_cgroup_snapshot(repo)
        delta = static_runner.cgroup_delta(cgroup_before, cgroup_after)

        receipt = {
            "contract_version": "mcad.nh_r3.c2.validation_arm_run.v1",
            "ordinal": ordinal,
            "block_index": int(arm_run["block_index"]),
            "session_id": session_id,
            "topology": str(arm_run["topology"]),
            "pattern": str(arm_run["pattern"]),
            "arm_position": arm_position,
            "arm": arm,
            "fresh_mcad_session_id": gate_session_id,
            "completion_candidate": int(arm_run["completion_candidate"]),
            "client_wall_ns": wall_stop_ns - wall_start_ns,
            "client_wall_ms": (wall_stop_ns - wall_start_ns) / 1_000_000.0,
            "time_to_analytical_objective_completion_ms": (completion_ns - wall_start_ns) / 1_000_000.0,
            "gate_evaluation_count": gate_evaluations,
            "full_backend_execution_count": full_backend_requests,
            "nvac_physical_backend_request_count": nvac_backend_requests,
            "backend_request_count_including_gate_probes": full_backend_requests + nvac_backend_requests,
            "response_bytes": response_bytes,
            "sqlserver_cpu_usage_usec_delta": int(delta.cpu_usage_usec),
            "sqlserver_io_rbytes_delta": int(delta.io_rbytes),
            "sqlserver_io_wbytes_delta": int(delta.io_wbytes),
            "negative_cgroup_delta_policy": b1_contract["sqlserver_cgroup"]["negative_delta_policy"],
            "live_gate_action_authoritative": False,
            "frozen_action_authority": "NH_R2_R3_BINDING",
            "selection_role": "CALIBRATION_NO_EFFECT_TUNING",
            "confirmatory_claim_authorized": False,
            "candidate_records": candidate_records,
        }
        receipt_path = arm_dir / f"{ordinal:03d}_{session_id}_{arm}.json"
        b2e.atomic_json(receipt_path, receipt)
        summary_rows.append({k: v for k, v in receipt.items() if k != "candidate_records"})
        print(
            f"validation_arm_complete ordinal={ordinal} session_id={session_id} arm={arm} "
            f"client_wall_ms={receipt['client_wall_ms']:.3f} "
            f"completion_ms={receipt['time_to_analytical_objective_completion_ms']:.3f} "
            f"backend_requests={receipt['backend_request_count_including_gate_probes']}"
        )

    if len(summary_rows) != 120:
        raise RuntimeError(f"expected 120 completed validation arm runs, got {len(summary_rows)}")

    summary = {
        "contract_version": "mcad.nh_r3.c2.validation_summary.v1",
        "validation_measured_execution_authorized": True,
        "analysis_class": "VALIDATION_CALIBRATION_NONCONFIRMATORY",
        "confirmatory_claim_authorized": False,
        "semantic_sessions": 40,
        "arm_runs_completed": 120,
        "candidate_actions_completed": 2880,
        "sqlserver_restart_after_warmup": False,
        "mcad_api_restart_before_each_arm": True,
        "fresh_session_for_each_gated_arm": True,
        "live_gate_may_relabel_frozen_action": False,
        "effect_size_tuning_performed": False,
        "arm_runs": summary_rows,
    }
    b2e.atomic_json(output_dir / "validation_summary.json", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="NH-R3-C2 validation executor specialized from frozen R3 plan/helpers")
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dry-run")

    p_refuse = sub.add_parser("authorization-refusal-probe")
    p_refuse.add_argument("--runtime-root", default="/tmp/forbidden")
    p_refuse.add_argument("--output-dir", default="/tmp/forbidden-output")

    p_run = sub.add_parser("run")
    p_run.add_argument("--runtime-root", required=True)
    p_run.add_argument("--output-dir", required=True)
    p_run.add_argument("--proxy-base", default=DEFAULT_PROXY_BASE)
    p_run.add_argument("--mcad-base", default=DEFAULT_MCAD_BASE)
    p_run.add_argument("--confirm", required=True, choices=[CONFIRM_TOKEN])

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "dry-run":
        print(json.dumps(dry_run(repo), indent=2, sort_keys=True))
        print("docker_command_executed=false")
        print("http_request_executed=false")
        print("measurement_executed=false")
        print("R3_C2_VALIDATION_EXECUTOR_DRY_RUN=PASS")
        return

    if args.cmd == "authorization-refusal-probe":
        try:
            validate_future_authorization(repo)
        except RuntimeError as exc:
            print(f"authorization_refusal_reason={exc}")
            print("docker_command_executed=false")
            print("http_request_executed=false")
            print("measurement_executed=false")
            print("R3_C2_AUTHORIZATION_REFUSAL_PROBE=PASS")
            return
        raise RuntimeError("authorization-refusal probe unexpectedly found an active C3 authorization")

    if args.cmd == "run":
        summary = run_validation(
            repo=repo,
            runtime_root=Path(args.runtime_root).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            proxy_base=args.proxy_base,
            mcad_base=args.mcad_base,
            confirm=args.confirm,
        )
        print(f"validation_arm_runs_completed={summary['arm_runs_completed']}")
        print(f"validation_candidate_actions_completed={summary['candidate_actions_completed']}")
        print("confirmatory_claim_authorized=false")
        print("R3_C2_VALIDATION_EXECUTION=PASS")
        return

    raise RuntimeError("unsupported command")


if __name__ == "__main__":
    main()
