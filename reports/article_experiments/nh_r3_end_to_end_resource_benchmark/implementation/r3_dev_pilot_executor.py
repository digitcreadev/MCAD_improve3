#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
MIN_PARENT_HEAD = "4736455d48483021e07fcc5d44a12f55bfeb652b"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
DW_ID = "adventureworks_sql_direct"
ADAPTER_ID = "adventureworks_direct"
SQLSERVICE = "adventureworks-sqlserver"
MCAD_API_SERVICE = "mcad-api"
PROXY_SERVICE = "mcad-proxy"

B1_SHA = "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f"
B2C_AUTH_SHA = "78a7c9a92b9b9f1d7dd10821449205bc4bbd7b996c4808aec747df44027180a4"
SCHEDULE_SHA = "6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e"
BINDING_DIGEST = "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
B2A1_RUNTIME_SHA = "fb0e12d1e8fe57272135078ce4171b68f8da8231f4a0d355e95b2fe9e572a59a"

ARMS = (
    "UNGATED_EXECUTE_ADMISSIBLE",
    "PERMISSIVE_GATED",
    "SAFE_PRUNING",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def compose_cmd(repo: Path, pilot_override: Path, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(repo / "bi-stack/docker-compose.yml"),
        "-f",
        str(repo / "bi-stack/docker-compose.r3-b2.override.yml"),
        "-f",
        str(pilot_override),
        *args,
    ]


def import_static_runner(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        import r3_resource_runner as static_runner  # type: ignore
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass
    return static_runner


def validate_frozen_authorities(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    r3 = repo / R3_REL
    b1 = r3 / "config/r3_b1_measurement_preregistration.json"
    auth = r3 / "config/r3_b2c_dev_pilot_authorization.json"
    schedule = r3 / "config/r3_b1_arm_order_schedule.csv"
    binding_sha = r3 / "results/BINDING_PLAN_SHA256.txt"
    runtime = repo / "bi-stack/mcad-proxy/r3_measurement_app.py"

    if sha256(b1) != B1_SHA:
        raise RuntimeError("B1 preregistration changed")
    if sha256(auth) != B2C_AUTH_SHA:
        raise RuntimeError("B2c authorization changed")
    if sha256(schedule) != SCHEDULE_SHA:
        raise RuntimeError("B1 schedule changed")
    if sha256(runtime) != B2A1_RUNTIME_SHA:
        raise RuntimeError("B2a.1 runtime changed")

    declared_binding = binding_sha.read_text(encoding="utf-8").split()[0]
    if declared_binding != BINDING_DIGEST:
        raise RuntimeError("binding plan digest changed")

    b1_data = json.loads(b1.read_text(encoding="utf-8"))
    auth_data = json.loads(auth.read_text(encoding="utf-8"))

    if b1_data["authorization"]["measured_pilot_authorized"] is not False:
        raise RuntimeError("historical B1 authorization was rewritten")
    if b1_data["scientific_authority"]["live_gate_may_relabel_frozen_action"] is not False:
        raise RuntimeError("live gate unexpectedly authoritative")
    if auth_data["authorization"]["dev_measured_pilot_authorized"] is not True:
        raise RuntimeError("B2c DEV pilot authorization missing")
    if auth_data["authorization"]["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("confirmatory claims unexpectedly authorized")
    if auth_data["historical_artifacts_must_remain_unchanged"] is not True:
        raise RuntimeError("historical immutability contract missing")

    return b1_data, auth_data


def validate_repo_state(repo: Path) -> None:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", MIN_PARENT_HEAD, "HEAD"],
        check=True,
    )
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("working tree not clean")


def load_plan(repo: Path) -> dict[str, Any]:
    validate_frozen_authorities(repo)
    static_runner = import_static_runner(repo)
    plan = static_runner.build_plan(repo)
    if plan["pilot_sessions"] != 20:
        raise RuntimeError("plan does not contain 20 pilot sessions")
    if len(plan["arm_runs"]) != 60:
        raise RuntimeError("plan does not contain 60 arm runs")
    if len(plan["candidate_actions"]) != 1440:
        raise RuntimeError("plan does not contain 1440 candidate actions")
    return plan


def actions_by_arm(plan: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for action in plan["candidate_actions"]:
        key = (str(action["session_id"]), str(action["arm"]))
        out.setdefault(key, []).append(action)
    for key, rows in out.items():
        rows.sort(key=lambda x: int(x["candidate_index"]))
        if [int(x["candidate_index"]) for x in rows] != list(range(1, 25)):
            raise RuntimeError(f"{key}: candidate order is not 1..24")
    return out


def ensure_output_outside_repo(repo: Path, output_dir: Path) -> None:
    repo = repo.resolve()
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(repo)
    except ValueError:
        return
    raise RuntimeError("measured output directory must be outside repository")


def wait_http_json(url: str, timeout_s: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=3)
            if response.ok:
                data = response.json()
                return data if isinstance(data, dict) else {"value": data}
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"readiness timeout for {url}: {last_error}")


def post_json(url: str, payload: dict[str, Any], timeout_s: float = 180.0) -> dict[str, Any]:
    response = requests.post(url, json=payload, timeout=timeout_s)
    text = response.text
    if not response.ok:
        raise RuntimeError(f"POST {url} -> HTTP {response.status_code}: {text[:1500]}")
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"POST {url} returned invalid JSON: {text[:1500]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"POST {url} returned non-object JSON")
    return data


def restart_mcad_api(repo: Path, pilot_override: Path, mcad_base: str) -> None:
    subprocess.run(
        compose_cmd(repo, pilot_override, "restart", MCAD_API_SERVICE),
        check=True,
        stdout=subprocess.DEVNULL,
    )
    health = wait_http_json(f"{mcad_base.rstrip('/')}/health", timeout_s=90.0)
    if not health:
        raise RuntimeError("mcad-api health response is empty")


def create_fresh_session(mcad_base: str) -> str:
    data = post_json(
        f"{mcad_base.rstrip('/')}/sessions/create",
        {"objective_id": OBJECTIVE_ID, "dw_id": DW_ID},
        timeout_s=30.0,
    )
    session = data.get("session")
    if not isinstance(session, dict) or not session.get("session_id"):
        raise RuntimeError(f"invalid /sessions/create response: {data}")
    return str(session["session_id"])


def read_template(repo: Path, action: dict[str, Any]) -> str:
    path = repo / R3_REL / str(action["query_template_path"])
    if not path.is_file():
        raise RuntimeError(f"template missing: {path}")
    return path.read_text(encoding="utf-8")


def validate_gate_response(data: dict[str, Any], query_id: str) -> None:
    if data.get("ok") is not True:
        raise RuntimeError(f"gate-only failed: {data}")
    if data.get("contract_version") != "mcad.nh_r3.b2.measurement_runtime.v1.1":
        raise RuntimeError("unexpected gate-only contract version")
    if data.get("mode") != "gate_only":
        raise RuntimeError("unexpected gate-only mode")
    if data.get("query_id") != query_id:
        raise RuntimeError("gate-only query_id mismatch")
    if data.get("full_candidate_execution_performed") is not False:
        raise RuntimeError("gate-only performed full candidate execution")
    if data.get("full_result_ckg_update_performed") is not False:
        raise RuntimeError("gate-only performed full result CKG update")
    if data.get("live_gate_action_authoritative") is not False:
        raise RuntimeError("live gate unexpectedly authoritative")


def validate_full_response(data: dict[str, Any], query_id: str) -> None:
    if data.get("ok") is not True:
        raise RuntimeError(f"full-execute failed: {data}")
    if data.get("contract_version") != "mcad.nh_r3.b2.measurement_runtime.v1.1":
        raise RuntimeError("unexpected full-execute contract version")
    if data.get("mode") != "full_execute":
        raise RuntimeError("unexpected full-execute mode")
    if data.get("dw_id") != DW_ID or data.get("adapter_id") != ADAPTER_ID:
        raise RuntimeError("unexpected full-execute backend")
    if data.get("query_id") != query_id:
        raise RuntimeError("full-execute query_id mismatch")
    if data.get("physical_execution") is not True:
        raise RuntimeError("full-execute was not physical")
    if int(data.get("backend_request_count") or 0) != 1:
        raise RuntimeError("full-execute backend_request_count != 1")
    if data.get("fallback_allowed") is not False or data.get("fallback_used") is not False:
        raise RuntimeError("full-execute fallback contract violated")
    if data.get("mcad_eval_performed") is not False or data.get("ckg_update_performed") is not False:
        raise RuntimeError("full-execute touched MCAD eval/CKG")
    if data.get("error") not in (None, ""):
        raise RuntimeError(f"full-execute returned error: {data.get('error')}")


def int0(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def gate_accounting(data: dict[str, Any]) -> tuple[int, int, dict[str, Any]]:
    nvac = data.get("nvac")
    if not isinstance(nvac, dict):
        raise RuntimeError("gate-only response missing nvac accounting")
    requests_count = int0(nvac.get("backend_request_count_including_gate_probes"))
    bytes_count = int0(nvac.get("physical_uncached_probe_response_bytes"))
    return requests_count, bytes_count, nvac


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run_pilot(
    repo: Path,
    pilot_override: Path,
    output_dir: Path,
    proxy_base: str,
    mcad_base: str,
) -> dict[str, Any]:
    validate_repo_state(repo)
    b1, auth = validate_frozen_authorities(repo)
    plan = load_plan(repo)
    by_arm = actions_by_arm(plan)
    static_runner = import_static_runner(repo)

    ensure_output_outside_repo(repo, output_dir)
    if output_dir.exists():
        raise RuntimeError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    arm_dir = output_dir / "arm_runs"
    arm_dir.mkdir()

    if auth["authorization"]["dev_measured_pilot_authorized"] is not True:
        raise RuntimeError("DEV measured pilot is not authorized")
    if auth["authorization"]["confirmatory_claim_authorized"] is not False:
        raise RuntimeError("confirmatory claim gate violated")

    summary_rows: list[dict[str, Any]] = []

    for ordinal, arm_run in enumerate(plan["arm_runs"], start=1):
        session_id = str(arm_run["session_id"])
        arm = str(arm_run["arm"])
        arm_position = int(arm_run["arm_position"])
        actions = by_arm[(session_id, arm)]

        # Preregistered cache control: restart mcad-api before EVERY arm, outside timers.
        restart_mcad_api(repo, pilot_override, mcad_base)
        gate_session_id = create_fresh_session(mcad_base) if arm != "UNGATED_EXECUTE_ADMISSIBLE" else None

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
            mdx = read_template(repo, action)
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
                    "objective_id": OBJECTIVE_ID,
                    "session_id": gate_session_id,
                    "dw_id": DW_ID,
                }
                gate_data = post_json(
                    f"{proxy_base.rstrip('/')}/bi/r3/measurement/gate-only",
                    payload,
                    timeout_s=180.0,
                )
                validate_gate_response(gate_data, query_id)
                reqs, probe_bytes, nvac_data = gate_accounting(gate_data)
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
                    "objective_id": OBJECTIVE_ID,
                    "session_id": gate_session_id,
                    "dw_id": DW_ID,
                    "allow_fallback": False,
                }
                full_data = post_json(
                    f"{proxy_base.rstrip('/')}/bi/r3/measurement/full-execute",
                    payload,
                    timeout_s=180.0,
                )
                validate_full_response(full_data, query_id)
                full_backend_requests += int0(full_data.get("backend_request_count"))
                response_bytes += int0(full_data.get("response_bytes"))

            candidate_done_ns = time.perf_counter_ns()
            if bool(action["is_completion_candidate"]):
                if completion_ns is not None:
                    raise RuntimeError(f"multiple completion candidates for {session_id}/{arm}")
                completion_ns = candidate_done_ns

            candidate_records.append(
                {
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
                }
            )

        wall_stop_ns = time.perf_counter_ns()

        if completion_ns is None:
            raise RuntimeError(f"completion candidate not reached for {session_id}/{arm}")

        cgroup_after = static_runner.read_sqlserver_cgroup_snapshot(repo)
        delta = static_runner.cgroup_delta(cgroup_before, cgroup_after)

        receipt = {
            "contract_version": "mcad.nh_r3.b2e.dev_pilot_arm_run.v1",
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
            "negative_cgroup_delta_policy": b1["sqlserver_cgroup"]["negative_delta_policy"],
            "live_gate_action_authoritative": False,
            "frozen_action_authority": "NH_R2_R3_BINDING",
            "confirmatory_claim_authorized": False,
            "candidate_records": candidate_records,
        }

        receipt_path = arm_dir / f"{ordinal:03d}_{session_id}_{arm}.json"
        atomic_json(receipt_path, receipt)
        summary_rows.append({k: v for k, v in receipt.items() if k != "candidate_records"})
        print(
            f"arm_run_complete ordinal={ordinal} session_id={session_id} arm={arm} "
            f"client_wall_ms={receipt['client_wall_ms']:.3f} "
            f"completion_ms={receipt['time_to_analytical_objective_completion_ms']:.3f} "
            f"backend_requests={receipt['backend_request_count_including_gate_probes']}"
        )

    if len(summary_rows) != 60:
        raise RuntimeError(f"expected 60 completed arm runs, got {len(summary_rows)}")

    summary = {
        "contract_version": "mcad.nh_r3.b2e.dev_pilot_summary.v1",
        "dev_measured_pilot_authorized": True,
        "confirmatory_claim_authorized": False,
        "semantic_sessions": 20,
        "arm_runs_completed": 60,
        "candidate_actions_completed": 1440,
        "sqlserver_restart_after_warmup": False,
        "mcad_api_restart_before_each_arm": True,
        "fresh_session_for_each_gated_arm": True,
        "live_gate_may_relabel_frozen_action": False,
        "arm_runs": summary_rows,
    }
    atomic_json(output_dir / "pilot_summary.json", summary)
    return summary


def dry_run(repo: Path) -> dict[str, Any]:
    validate_repo_state(repo)
    b1, auth = validate_frozen_authorities(repo)
    plan = load_plan(repo)
    gated_arm_runs = sum(1 for x in plan["arm_runs"] if x["arm"] != "UNGATED_EXECUTE_ADMISSIBLE")
    out = {
        "contract_version": "mcad.nh_r3.b2e.dev_pilot_executor_dry_run.v1",
        "dev_measured_pilot_authorized": auth["authorization"]["dev_measured_pilot_authorized"],
        "confirmatory_claim_authorized": auth["authorization"]["confirmatory_claim_authorized"],
        "pilot_sessions": plan["pilot_sessions"],
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gated_arm_runs": gated_arm_runs,
        "ungated_arm_runs": len(plan["arm_runs"]) - gated_arm_runs,
        "mcad_api_restarts_planned": len(plan["arm_runs"]),
        "fresh_mcad_sessions_planned": gated_arm_runs,
        "measurement_executed": False,
        "timing_contract": b1["timing"],
        "cgroup_contract": b1["sqlserver_cgroup"],
        "cache_control": b1["cache_control"],
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="NH-R3-B2e DEV pilot executor")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dry-run", help="validate exact 60-arm plan; no HTTP/Docker mutation")

    p_run = sub.add_parser("run", help="execute the authorized measured DEV pilot")
    p_run.add_argument("--pilot-override", required=True)
    p_run.add_argument("--output-dir", required=True)
    p_run.add_argument("--proxy-base", default="http://127.0.0.1:9000")
    p_run.add_argument("--mcad-base", default="http://127.0.0.1:8000")
    p_run.add_argument(
        "--confirm",
        required=True,
        choices=["EXECUTE_AUTHORIZED_NH_R3_DEV_PILOT"],
    )

    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "dry-run":
        out = dry_run(repo)
        print(json.dumps(out, indent=2, sort_keys=True))
        print("measured_execution_performed=false")
        print("R3_B2E_EXECUTOR_DRY_RUN=PASS")
        return

    if args.cmd == "run":
        if args.confirm != "EXECUTE_AUTHORIZED_NH_R3_DEV_PILOT":
            raise SystemExit("explicit DEV pilot confirmation missing")
        summary = run_pilot(
            repo=repo,
            pilot_override=Path(args.pilot_override).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            proxy_base=args.proxy_base,
            mcad_base=args.mcad_base,
        )
        print(f"arm_runs_completed={summary['arm_runs_completed']}")
        print(f"candidate_actions_completed={summary['candidate_actions_completed']}")
        print("confirmatory_claim_authorized=false")
        print("R3_B2E_DEV_PILOT_EXECUTION=PASS")
        return

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    main()
