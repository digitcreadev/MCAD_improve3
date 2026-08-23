#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
D0_HEAD = "f610dd5d1a61830385bb11f537eb1d740bb0ccc6"

D0_CONTRACT_BLOB = "6c608b951bca9b262cc69bb7964a48cec79c62b1"
D0_INFERENCE_BLOB = "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb"
D0_PLAN_BLOB = "54750b314717dc370ca65f84ca765c338b4abb2c"
PRIMARY_SCHEDULE_BLOB = "6b53ab6d271425b9e5113bdd405775f05c6d65df"
FALLBACK_SCHEDULE_BLOB = "bae0fd86e18236296c94b5b404203f06f4ad55b5"
B2E_EXECUTOR_BLOB = "5eeaf00e00dfd6561959c81941acc902acf8b509"
B2K_ADAPTER_BLOB = "41792ef397834dcea7369882c6273e693d2608e9"
ISOLATED_COMPOSE_BLOB = "f807f35039d89ac5dae153fb3fa36d99f4a33e53"

AUTH_REL = R3_REL / "config/r3_d2_confirmatory_measurement_authorization.json"
CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_D_CONFIRMATORY_PRIMARY_300"

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
        d0 = importlib.import_module("r3_d0_confirmatory_plan")
        b2k = importlib.import_module("r3_isolated_executor_adapter")
        b2e = importlib.import_module("r3_dev_pilot_executor")
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass
    return d0, b2k, b2e


def validate_static_authorities(repo: Path) -> tuple[Any, Any, Any, dict[str, Any]]:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", D0_HEAD, "HEAD"],
        check=True,
    )

    r3 = repo / R3_REL
    checks = (
        (r3 / "config/r3_d0_confirmatory_static_activation_contract.json", D0_CONTRACT_BLOB, "D0 activation contract"),
        (r3 / "config/r3_d0_confirmatory_inference_protocol.json", D0_INFERENCE_BLOB, "D0 inference protocol"),
        (r3 / "implementation/r3_d0_confirmatory_plan.py", D0_PLAN_BLOB, "D0 confirmatory plan"),
        (r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv", PRIMARY_SCHEDULE_BLOB, "D0 primary schedule"),
        (r3 / "config/r3_d0_confirmatory_fallback_arm_order_schedule.csv", FALLBACK_SCHEDULE_BLOB, "D0 fallback schedule"),
        (r3 / "implementation/r3_dev_pilot_executor.py", B2E_EXECUTOR_BLOB, "frozen B2e executor"),
        (r3 / "implementation/r3_isolated_executor_adapter.py", B2K_ADAPTER_BLOB, "B2k isolated adapter"),
        (r3 / "runtime/r3_isolated_runtime.compose.yml", ISOLATED_COMPOSE_BLOB, "isolated compose"),
    )
    for path, expected, label in checks:
        actual = git_blob_sha1(path)
        if actual != expected:
            raise RuntimeError(f"{label} changed: {actual}")

    d0, b2k, b2e = import_modules(repo)
    plan = d0.build_plan(repo, "primary")

    expected = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "gated_arm_runs": 600,
        "ungated_arm_runs": 300,
        "mcad_api_restarts_planned": 900,
        "fresh_mcad_sessions_planned": 600,
    }
    actual = {
        "semantic_sessions": int(plan["semantic_sessions"]),
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": int(plan["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(plan["full_backend_executions_planned"]),
        "gated_arm_runs": int(plan["gated_arm_runs"]),
        "ungated_arm_runs": int(plan["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(plan["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(plan["fresh_mcad_sessions_planned"]),
    }
    if actual != expected:
        raise RuntimeError(f"primary confirmatory plan changed: {actual}")
    if plan["selection_role"] != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("primary selection role changed")
    if len(plan["unique_templates_lexicographic"]) != 7:
        raise RuntimeError("primary template set changed")
    if plan["effect_size_tuning_performed"] is not False:
        raise RuntimeError("effect-size tuning flag changed")
    if plan["scientific_redesign_performed"] is not False:
        raise RuntimeError("scientific redesign flag changed")
    if plan["measurement_authorized"] is not False:
        raise RuntimeError("D0 unexpectedly authorizes measurement")
    if plan["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("D0 prematurely authorizes a confirmatory claim")

    # Reuse the audited B2e scientific execution loop and B2k operational
    # routing patch. This mutates Python module objects only in static paths.
    patched_b2e, _ = b2k.patch_frozen_executor(repo)
    by_arm = patched_b2e.actions_by_arm(plan)
    if len(by_arm) != 900:
        raise RuntimeError("confirmatory executor arm-group cardinality mismatch")
    if any(len(rows) != 24 for rows in by_arm.values()):
        raise RuntimeError("confirmatory executor candidate grouping mismatch")

    for arm_run in plan["arm_runs"]:
        key = (str(arm_run["session_id"]), str(arm_run["arm"]))
        rows = by_arm[key]
        hits = [a for a in rows if bool(a["is_completion_candidate"])]
        if len(hits) != 1:
            raise RuntimeError(f"{key}: completion candidate count != 1")
        if int(hits[0]["candidate_index"]) != int(arm_run["completion_candidate"]):
            raise RuntimeError(f"{key}: completion boundary mismatch")

    return d0, b2k, patched_b2e, plan


def validate_future_authorization(repo: Path) -> dict[str, Any]:
    auth_path = repo / AUTH_REL
    if not auth_path.is_file():
        raise RuntimeError(
            "R3-D2 confirmatory measurement authorization file absent; "
            "R3-D measured execution remains forbidden"
        )
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.d2.confirmatory_measurement_authorization.v1":
        raise RuntimeError("unexpected R3-D2 authorization contract")
    auth = data.get("authorization")
    if not isinstance(auth, dict):
        raise RuntimeError("R3-D2 authorization payload missing")
    if auth.get("primary_300_measured_execution_authorized") is not True:
        raise RuntimeError("R3-D primary measured execution not authorized")
    if auth.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback activated in primary executor authorization")
    if auth.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("R3-D2 authorization indicates effect-size tuning")
    if auth.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("measurement authorization cannot itself authorize a claim")
    if data.get("d0_head") != D0_HEAD:
        raise RuntimeError("R3-D2 authorization not bound to frozen D0 head")
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
        raise RuntimeError("historical compose leaked into R3-D1 routing probe")
    if "-p mcad-r3-rerun1" not in joined:
        raise RuntimeError("isolated Docker project missing from routing probe")
    if "r3_isolated_runtime.compose.yml" not in joined:
        raise RuntimeError("isolated compose file missing from routing probe")

    return {
        "contract_version": "mcad.nh_r3.d1.confirmatory_executor_dry_run.v1",
        "stage": "R3-D_CONFIRMATORY_SQL_DIRECT",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "selection_role": "CONFIRMATORY_PRIMARY",
        "semantic_sessions": int(plan["semantic_sessions"]),
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": int(plan["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(plan["full_backend_executions_planned"]),
        "gated_arm_runs": int(plan["gated_arm_runs"]),
        "ungated_arm_runs": int(plan["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(plan["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(plan["fresh_mcad_sessions_planned"]),
        "historical_compose_targeted": False,
        "isolated_project": b2k.PROJECT,
        "isolated_mcad_api_service": b2k.MCAD_API_SERVICE,
        "isolated_sqlserver_service": b2k.SQLSERVER_SERVICE,
        "isolated_proxy_service": b2k.PROXY_SERVICE,
        "fallback_activation_authorized_now": False,
        "measurement_authorized": False,
        "measurement_executed": False,
        "backend_query_executed": False,
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
    raise RuntimeError("measured confirmatory output must be outside repository")


def run_confirmatory_primary(
    repo: Path,
    runtime_root: Path,
    output_dir: Path,
    proxy_base: str,
    mcad_base: str,
    confirm: str,
) -> dict[str, Any]:
    # Intentionally unreachable during R3-D1.
    if confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit R3-D primary confirmation token required")
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

        if (
            int(delta.cpu_usage_usec) < 0
            or int(delta.io_rbytes) < 0
            or int(delta.io_wbytes) < 0
        ):
            raise RuntimeError(
                f"negative cgroup delta invalidates arm run {ordinal}; never clamp to zero"
            )

        receipt = {
            "contract_version": "mcad.nh_r3.d1.confirmatory_primary_arm_run.v1",
            "ordinal": ordinal,
            "block_index": int(arm_run["block_index"]),
            "session_id": session_id,
            "topology": str(arm_run["topology"]),
            "pattern": str(arm_run["pattern"]),
            "selection_role": "CONFIRMATORY_PRIMARY",
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
            "confirmatory_claim_authorized": False,
            "effect_size_tuning_performed": False,
            "candidate_records": candidate_records,
        }
        receipt_path = arm_dir / f"{ordinal:04d}_{session_id}_{arm}.json"
        b2e.atomic_json(receipt_path, receipt)
        summary_rows.append({k: v for k, v in receipt.items() if k != "candidate_records"})
        print(
            f"confirmatory_arm_complete ordinal={ordinal} session_id={session_id} arm={arm} "
            f"client_wall_ms={receipt['client_wall_ms']:.3f} "
            f"completion_ms={receipt['time_to_analytical_objective_completion_ms']:.3f} "
            f"backend_requests={receipt['backend_request_count_including_gate_probes']}"
        )

    if len(summary_rows) != 900:
        raise RuntimeError(f"expected 900 completed confirmatory arm runs, got {len(summary_rows)}")

    summary = {
        "contract_version": "mcad.nh_r3.d1.confirmatory_primary_summary.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "selection_role": "CONFIRMATORY_PRIMARY",
        "primary_300_measured_execution_authorized": True,
        "fallback_120_activated": False,
        "confirmatory_claim_authorized": False,
        "semantic_sessions": 300,
        "arm_runs_completed": 900,
        "candidate_actions_completed": 21600,
        "sqlserver_restart_after_warmup": False,
        "mcad_api_restart_before_each_arm": True,
        "fresh_session_for_each_gated_arm": True,
        "live_gate_may_relabel_frozen_action": False,
        "effect_size_tuning_performed": False,
        "arm_runs": summary_rows,
    }
    b2e.atomic_json(output_dir / "confirmatory_primary_summary.json", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dry-run")
    sub.add_parser("authorization-refusal-probe")

    p_run = sub.add_parser("run-primary")
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
        print("R3_D1_CONFIRMATORY_EXECUTOR_DRY_RUN=PASS")
        return

    if args.cmd == "authorization-refusal-probe":
        if (repo / AUTH_REL).exists():
            raise RuntimeError("R3-D2 authorization unexpectedly exists during D1")
        try:
            validate_future_authorization(repo)
        except RuntimeError as exc:
            msg = str(exc)
            if "authorization file absent" not in msg:
                raise
            print("authorization_refusal_reason=" + msg)
            print("docker_command_executed=false")
            print("http_request_executed=false")
            print("measurement_executed=false")
            print("R3_D1_AUTHORIZATION_REFUSAL_PROBE=PASS")
            return
        raise RuntimeError("authorization refusal probe unexpectedly passed authorization")

    if args.cmd == "run-primary":
        run_confirmatory_primary(
            repo=repo,
            runtime_root=Path(args.runtime_root).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            proxy_base=args.proxy_base,
            mcad_base=args.mcad_base,
            confirm=args.confirm,
        )
        return


if __name__ == "__main__":
    main()
