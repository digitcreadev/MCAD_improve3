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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
E10_HEAD = "7e12c7d831a7dd0bf2893dcf73ea87f676ec6514"

OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
DW_ID = "adventureworks_xmla"
ADAPTER_ID = "xmla_mondrian"
PROJECT = "mcad-r3e-xmla1"

SQL_CONTAINER = "mcad-r3e-xmla1-r3e-adventureworks-sqlserver-1"
EMONDRIAN_CONTAINER = "mcad-r3e-xmla1-r3e-emondrian-adventureworks-1"
API_CONTAINER = "mcad-r3e-xmla1-r3e-mcad-api-1"
PROXY_CONTAINER = "mcad-r3e-xmla1-r3e-mcad-proxy-1"

SQL_IMAGE_ID = "sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89"
API_IMAGE_ID = "sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840"
PROXY_BASE_IMAGE_ID = "sha256:2494827f7dda2769fcd80e1659bbb2520b0aafe52fdefdc79e6fff07db0fe6b4"
EMONDRIAN_IMAGE_ID = "sha256:77d2d5395e902b28368bdc0357d9a1a6d928c415af160425248df5d2d0697a69"

E10_CHECKPOINT_REL = R3_REL / "results/r3_e10_runtime_integrity_freeze_checkpoint.json"
E10_CHECKPOINT_SHA256 = "31707c99daa88f2fc30cb982a0bb90d909e0a2eb46b99831d7ace22615efd453"
E5_CONTRACT_REL = R3_REL / "config/r3_e5_xmla_executor_receipt_static_contract.json"
E5_SCHEMA_REL = R3_REL / "config/r3_e5_xmla_arm_receipt_schema.json"
AUTH_REL = R3_REL / "config/r3_e13_xmla_measured_execution_authorization.json"

CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_E_XMLA_PRIMARY_300"
DEFAULT_MCAD_BASE = "http://127.0.0.1:18100"
DEFAULT_PROXY_BASE = "http://127.0.0.1:19100"

GATE_PATH = "/bi/r3/e11/measurement/gate-only"
FULL_PATH = "/bi/r3/e11/measurement/full-execute"
MEASUREMENT_CONTRACT = "mcad.nh_r3.e11.measurement_runtime.v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def validate_repo(repo: Path) -> None:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", E10_HEAD, "HEAD"],
        check=True,
    )


def import_d0(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        return importlib.import_module("r3_d0_confirmatory_plan")
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass


def plan(repo: Path) -> dict[str, Any]:
    validate_repo(repo)
    if sha256(repo / E10_CHECKPOINT_REL) != E10_CHECKPOINT_SHA256:
        raise RuntimeError("E10 checkpoint changed")
    d0 = import_d0(repo)
    p = d0.build_plan(repo, "primary")
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
        "semantic_sessions": int(p["semantic_sessions"]),
        "arm_runs": len(p["arm_runs"]),
        "candidate_actions": len(p["candidate_actions"]),
        "gate_evaluations_planned": int(p["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(p["full_backend_executions_planned"]),
        "gated_arm_runs": int(p["gated_arm_runs"]),
        "ungated_arm_runs": int(p["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(p["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(p["fresh_mcad_sessions_planned"]),
    }
    if actual != expected:
        raise RuntimeError(f"frozen primary plan changed: {actual}")
    if p["selection_role"] != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("selection role changed")
    if len(p["unique_templates_lexicographic"]) != 7:
        raise RuntimeError("warmup template count changed")
    return p


def actions_by_arm(p: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for action in p["candidate_actions"]:
        key = (str(action["session_id"]), str(action["arm"]))
        out.setdefault(key, []).append(action)
    if len(out) != 900:
        raise RuntimeError("arm grouping cardinality changed")
    for key, rows in out.items():
        rows.sort(key=lambda x: int(x["candidate_index"]))
        if [int(x["candidate_index"]) for x in rows] != list(range(1, 25)):
            raise RuntimeError(f"{key}: candidates are not 1..24")
        hits = [x for x in rows if bool(x["is_completion_candidate"])]
        if len(hits) != 1:
            raise RuntimeError(f"{key}: completion candidate count != 1")
    return out


def validate_future_authorization(repo: Path) -> dict[str, Any]:
    auth_path = repo / AUTH_REL
    if not auth_path.is_file():
        raise RuntimeError(
            "R3-E13 measured-execution authorization file absent; "
            "R3-E measured execution remains forbidden"
        )
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.e13.xmla_measured_execution_authorization.v1":
        raise RuntimeError("unexpected R3-E13 authorization contract")
    a = data.get("authorization")
    if not isinstance(a, dict):
        raise RuntimeError("R3-E13 authorization payload missing")
    if a.get("primary_300_measured_execution_authorized") is not True:
        raise RuntimeError("R3-E primary measured execution not authorized")
    if a.get("effect_analysis_authorized") is not False:
        raise RuntimeError("measurement authorization cannot authorize effect analysis")
    if a.get("scientific_final_freeze_authorized") is not False:
        raise RuntimeError("measurement authorization cannot authorize final freeze")
    if a.get("historical_xmla_q1_q6_rerun_authorized") is not False:
        raise RuntimeError("historical XMLA rerun unexpectedly authorized")

    this_sha = sha256(Path(__file__).resolve())
    if data.get("executor_sha256") != this_sha:
        raise RuntimeError("R3-E13 authorization executor hash mismatch")
    if data.get("e10_head") != E10_HEAD:
        raise RuntimeError("R3-E13 authorization E10 binding mismatch")
    return data


def dry_run(repo: Path) -> dict[str, Any]:
    p = plan(repo)
    grouped = actions_by_arm(p)
    schema = json.loads((repo / E5_SCHEMA_REL).read_text(encoding="utf-8"))
    required = set(schema["required"])
    expected_required = {
        "receipt_version", "run_id", "session_id", "block_index", "topology", "pattern",
        "selection_role", "arm", "arm_position", "candidate_actions", "gate_evaluations",
        "full_backend_execution_count", "backend_request_count_including_gate_probes",
        "response_bytes", "client_wall_ms", "time_to_analytical_objective_completion_ms",
        "sqlserver_cpu_usage_usec_delta", "sqlserver_io_rbytes_delta", "sqlserver_io_wbytes_delta",
        "emondrian_cpu_usage_usec_delta", "emondrian_io_rbytes_delta", "emondrian_io_wbytes_delta",
        "completion_candidate_index", "completion_candidate_reached", "runtime_identity",
        "integrity_flags",
    }
    if required != expected_required:
        raise RuntimeError("E5 receipt required-field set changed")
    return {
        "contract_version": "mcad.nh_r3.e11.xmla_live_executor_dry_run.v1",
        "backend_id": DW_ID,
        "adapter": ADAPTER_ID,
        "semantic_sessions": int(p["semantic_sessions"]),
        "arm_runs": len(p["arm_runs"]),
        "candidate_actions": len(p["candidate_actions"]),
        "grouped_arm_runs": len(grouped),
        "gate_evaluations_planned": int(p["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(p["full_backend_executions_planned"]),
        "warmup_template_count": len(p["unique_templates_lexicographic"]),
        "expected_receipts": 900,
        "gate_path": GATE_PATH,
        "full_execute_path": FULL_PATH,
        "measurement_authorized": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "http_request_executed": False,
        "docker_command_executed": False,
        "effect_analysis_performed": False,
    }


@dataclass(frozen=True)
class CgroupSnapshot:
    cpu_usage_usec: int
    io_rbytes: int
    io_wbytes: int


@dataclass(frozen=True)
class CgroupDelta:
    cpu_usage_usec: int
    io_rbytes: int
    io_wbytes: int


def parse_cpu(text: str) -> int:
    vals = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) == 2:
            try:
                vals[p[0]] = int(p[1])
            except ValueError:
                pass
    if "usage_usec" not in vals:
        raise RuntimeError("cpu.stat missing usage_usec")
    return vals["usage_usec"]


def parse_io(text: str) -> tuple[int, int]:
    rbytes = 0
    wbytes = 0
    saw = False
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        saw = True
        for token in p[1:]:
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            try:
                n = int(v)
            except ValueError:
                continue
            if k == "rbytes":
                rbytes += n
            elif k == "wbytes":
                wbytes += n
    if not saw:
        raise RuntimeError("io.stat has no device rows")
    return rbytes, wbytes


def cgroup_snapshot(container: str) -> CgroupSnapshot:
    cpu = subprocess.check_output(
        ["docker", "exec", container, "cat", "/sys/fs/cgroup/cpu.stat"],
        text=True,
    )
    io = subprocess.check_output(
        ["docker", "exec", container, "cat", "/sys/fs/cgroup/io.stat"],
        text=True,
    )
    r, w = parse_io(io)
    return CgroupSnapshot(parse_cpu(cpu), r, w)


def cgroup_delta(before: CgroupSnapshot, after: CgroupSnapshot) -> CgroupDelta:
    d = CgroupDelta(
        after.cpu_usage_usec - before.cpu_usage_usec,
        after.io_rbytes - before.io_rbytes,
        after.io_wbytes - before.io_wbytes,
    )
    if min(d.cpu_usage_usec, d.io_rbytes, d.io_wbytes) < 0:
        raise RuntimeError("negative cgroup delta: invalidate arm run; never clamp")
    return d


def post_json(url: str, payload: dict[str, Any], timeout_s: float = 180.0) -> dict[str, Any]:
    r = requests.post(url, json=payload, timeout=timeout_s)
    if not r.ok:
        raise RuntimeError(f"POST {url} -> HTTP {r.status_code}: {r.text[:1200]}")
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("backend returned non-object JSON")
    return data


def wait_json(url: str, timeout_s: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                data = r.json()
                if isinstance(data, dict):
                    return data
            last = f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"readiness timeout {url}: {last}")


def compose_cmd(runtime_root: Path, *args: str) -> list[str]:
    base = runtime_root / "compose.yml"
    override = runtime_root / "r3_e12_measurement.override.yml"
    if not base.is_file() or not override.is_file():
        raise RuntimeError("authorized E12 runtime compose materialization missing")
    return [
        "docker", "compose",
        "-p", PROJECT,
        "-f", str(base),
        "-f", str(override),
        *args,
    ]


def restart_api(runtime_root: Path, mcad_base: str) -> None:
    subprocess.run(compose_cmd(runtime_root, "restart", "r3e-mcad-api"), check=True)
    wait_json(f"{mcad_base.rstrip('/')}/health", 90.0)


def create_session(mcad_base: str) -> str:
    data = post_json(
        f"{mcad_base.rstrip('/')}/sessions/create",
        {"objective_id": OBJECTIVE_ID, "dw_id": DW_ID},
        timeout_s=30.0,
    )
    s = data.get("session")
    if not isinstance(s, dict) or not s.get("session_id"):
        raise RuntimeError("invalid /sessions/create response")
    return str(s["session_id"])


def read_template(repo: Path, action: dict[str, Any]) -> str:
    p = repo / R3_REL / str(action["query_template_path"])
    if not p.is_file():
        raise RuntimeError(f"query template missing: {p}")
    return p.read_text(encoding="utf-8")


def validate_gate(data: dict[str, Any], query_id: str) -> tuple[int, int, dict[str, Any]]:
    if data.get("ok") is not True:
        raise RuntimeError(f"gate-only failed: {data}")
    if data.get("contract_version") != MEASUREMENT_CONTRACT or data.get("mode") != "gate_only":
        raise RuntimeError("unexpected E11 gate contract")
    if data.get("dw_id") != DW_ID or data.get("query_id") != query_id:
        raise RuntimeError("gate backend/query identity mismatch")
    if data.get("full_candidate_execution_performed") is not False:
        raise RuntimeError("gate-only executed full candidate")
    if data.get("full_result_ckg_update_performed") is not False:
        raise RuntimeError("gate-only updated full result CKG")
    if data.get("live_gate_action_authoritative") is not False:
        raise RuntimeError("live gate unexpectedly authoritative")
    nvac = data.get("nvac")
    if not isinstance(nvac, dict):
        raise RuntimeError("gate-only missing NVAC accounting")
    reqs = int(nvac.get("backend_request_count_including_gate_probes") or 0)
    b = int(nvac.get("physical_uncached_probe_response_bytes") or 0)
    return reqs, b, nvac


def validate_full(data: dict[str, Any], query_id: str) -> None:
    if data.get("ok") is not True:
        raise RuntimeError(f"full-execute failed: {data}")
    if data.get("contract_version") != MEASUREMENT_CONTRACT or data.get("mode") != "full_execute":
        raise RuntimeError("unexpected E11 full-execute contract")
    if data.get("dw_id") != DW_ID or data.get("adapter_id") != ADAPTER_ID:
        raise RuntimeError("unexpected XMLA backend identity")
    if data.get("query_id") != query_id:
        raise RuntimeError("full-execute query identity mismatch")
    if data.get("physical_execution") is not True:
        raise RuntimeError("full-execute was not physical")
    if int(data.get("backend_request_count") or 0) != 1:
        raise RuntimeError("full-execute backend_request_count != 1")
    if data.get("fallback_allowed") is not False or data.get("fallback_used") is not False:
        raise RuntimeError("fallback contract violated")
    if data.get("mcad_eval_performed") is not False or data.get("ckg_update_performed") is not False:
        raise RuntimeError("full-execute touched eval/CKG")
    if data.get("xmla_valid_response") is not True or data.get("xmla_has_fault") is True:
        raise RuntimeError("full-execute XMLA response invalid")
    if data.get("error") not in (None, ""):
        raise RuntimeError(f"full-execute returned error: {data.get('error')}")


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def ensure_output_outside_repo(repo: Path, output_dir: Path) -> None:
    try:
        output_dir.resolve().relative_to(repo.resolve())
    except ValueError:
        return
    raise RuntimeError("measured output must be outside repository")


def runtime_identity(auth: dict[str, Any]) -> dict[str, str]:
    expected_proxy = str(auth["runtime"]["derived_proxy_image_id"])
    checks = [
        (SQL_CONTAINER, SQL_IMAGE_ID),
        (EMONDRIAN_CONTAINER, EMONDRIAN_IMAGE_ID),
        (API_CONTAINER, API_IMAGE_ID),
        (PROXY_CONTAINER, expected_proxy),
    ]
    out = {"project_name": PROJECT}
    keys = [
        ("sqlserver", SQL_CONTAINER),
        ("emondrian", EMONDRIAN_CONTAINER),
        ("mcad_api", API_CONTAINER),
        ("mcad_proxy", PROXY_CONTAINER),
    ]
    for container, expected_image in checks:
        image = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.Image}}", container], text=True
        ).strip()
        running = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Running}}", container], text=True
        ).strip()
        if image != expected_image or running != "true":
            raise RuntimeError(f"runtime identity/state mismatch for {container}")
    for prefix, container in keys:
        out[f"{prefix}_container_id"] = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.Id}}", container], text=True
        ).strip()
        out[f"{prefix}_image_id"] = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.Image}}", container], text=True
        ).strip()
    return out


def warmup(repo: Path, p: dict[str, Any], proxy_base: str) -> None:
    first_by_template: dict[str, dict[str, Any]] = {}
    for a in p["candidate_actions"]:
        first_by_template.setdefault(str(a["template_id"]), a)
    if len(first_by_template) != 7:
        raise RuntimeError("warmup template cardinality != 7")
    for template_id in sorted(first_by_template):
        a = first_by_template[template_id]
        query_id = f"WARMUP::{template_id}"
        payload = {
            "mdx": read_template(repo, a),
            "query_type": "mdx",
            "query_id": query_id,
            "objective_id": OBJECTIVE_ID,
            "dw_id": DW_ID,
            "allow_fallback": False,
        }
        data = post_json(
            f"{proxy_base.rstrip('/')}{FULL_PATH}",
            payload,
            timeout_s=180.0,
        )
        validate_full(data, query_id)


def run_primary(
    repo: Path,
    runtime_root: Path,
    output_dir: Path,
    run_id: str,
    proxy_base: str,
    mcad_base: str,
    confirm: str,
) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit R3-E confirm token required")
    auth = validate_future_authorization(repo)
    p = plan(repo)
    grouped = actions_by_arm(p)
    ensure_output_outside_repo(repo, output_dir)
    if output_dir.exists():
        raise RuntimeError(f"output directory already exists: {output_dir}")

    rid = runtime_identity(auth)
    output_dir.mkdir(parents=True)
    arm_dir = output_dir / "arm_runs"
    trace_dir = output_dir / "candidate_traces"
    arm_dir.mkdir()
    trace_dir.mkdir()

    # Frozen seven-template warmup outside all measured arm timers.
    warmup(repo, p, proxy_base)

    summaries = []
    for ordinal, arm_run in enumerate(p["arm_runs"], start=1):
        session_id = str(arm_run["session_id"])
        arm = str(arm_run["arm"])
        arm_position = int(arm_run["arm_position"])
        actions = grouped[(session_id, arm)]

        # Frozen cache-control: restart MCAD API before every arm, outside timers.
        restart_api(runtime_root, mcad_base)
        gate_session = create_session(mcad_base) if arm != "UNGATED_EXECUTE_ADMISSIBLE" else None

        sql_before = cgroup_snapshot(SQL_CONTAINER)
        emo_before = cgroup_snapshot(EMONDRIAN_CONTAINER)

        gate_evaluations = 0
        full_backend = 0
        gate_backend = 0
        response_bytes = 0
        completion_ns = None
        traces = []
        wall_start = time.perf_counter_ns()

        for action in actions:
            qid = str(action["query_id"])
            mdx = read_template(repo, action)
            gate_data = None
            full_data = None
            nvac = None
            live_decision = None

            if bool(action["run_gate"]):
                gate_evaluations += 1
                gate_data = post_json(
                    f"{proxy_base.rstrip('/')}{GATE_PATH}",
                    {
                        "mdx": mdx,
                        "query_type": "mdx",
                        "query_id": qid,
                        "objective_id": OBJECTIVE_ID,
                        "session_id": gate_session,
                        "dw_id": DW_ID,
                    },
                    timeout_s=180.0,
                )
                reqs, b, nvac = validate_gate(gate_data, qid)
                gate_backend += reqs
                response_bytes += b
                d = gate_data.get("decision")
                if isinstance(d, dict) and d.get("decision") is not None:
                    live_decision = str(d.get("decision"))

            if bool(action["run_full_backend"]):
                full_data = post_json(
                    f"{proxy_base.rstrip('/')}{FULL_PATH}",
                    {
                        "mdx": mdx,
                        "query_type": "mdx",
                        "query_id": qid,
                        "objective_id": OBJECTIVE_ID,
                        "session_id": gate_session,
                        "dw_id": DW_ID,
                        "allow_fallback": False,
                    },
                    timeout_s=180.0,
                )
                validate_full(full_data, qid)
                full_backend += int(full_data.get("backend_request_count") or 0)
                response_bytes += int(full_data.get("response_bytes") or 0)

            now = time.perf_counter_ns()
            if bool(action["is_completion_candidate"]):
                if completion_ns is not None:
                    raise RuntimeError(f"multiple completion candidates {session_id}/{arm}")
                completion_ns = now

            traces.append(
                {
                    "candidate_index": int(action["candidate_index"]),
                    "query_id": qid,
                    "template_id": str(action["template_id"]),
                    "frozen_class": str(action["frozen_class"]),
                    "frozen_operational_action": str(action["frozen_operational_action"]),
                    "run_gate": bool(action["run_gate"]),
                    "run_full_backend": bool(action["run_full_backend"]),
                    "is_completion_candidate": bool(action["is_completion_candidate"]),
                    "live_gate_decision": live_decision,
                    "gate_elapsed_ms": gate_data.get("gate_elapsed_ms") if gate_data else None,
                    "nvac": nvac,
                    "full_elapsed_ms": full_data.get("elapsed_ms") if full_data else None,
                    "full_response_bytes": full_data.get("response_bytes") if full_data else None,
                    "full_result_digest": full_data.get("result_digest") if full_data else None,
                    "full_row_count": full_data.get("row_count") if full_data else None,
                }
            )

        wall_stop = time.perf_counter_ns()
        if completion_ns is None:
            raise RuntimeError(f"completion candidate not reached {session_id}/{arm}")

        sql_after = cgroup_snapshot(SQL_CONTAINER)
        emo_after = cgroup_snapshot(EMONDRIAN_CONTAINER)
        sql_delta = cgroup_delta(sql_before, sql_after)
        emo_delta = cgroup_delta(emo_before, emo_after)

        receipt = {
            "receipt_version": "mcad.nh_r3.e5.xmla_arm_receipt.v1",
            "run_id": run_id,
            "session_id": session_id,
            "block_index": int(arm_run["block_index"]),
            "topology": str(arm_run["topology"]),
            "pattern": str(arm_run["pattern"]),
            "selection_role": "CONFIRMATORY_PRIMARY",
            "arm": arm,
            "arm_position": arm_position,
            "candidate_actions": 24,
            "gate_evaluations": gate_evaluations,
            "full_backend_execution_count": full_backend,
            "backend_request_count_including_gate_probes": full_backend + gate_backend,
            "response_bytes": response_bytes,
            "client_wall_ms": (wall_stop - wall_start) / 1_000_000.0,
            "time_to_analytical_objective_completion_ms": (completion_ns - wall_start) / 1_000_000.0,
            "sqlserver_cpu_usage_usec_delta": int(sql_delta.cpu_usage_usec),
            "sqlserver_io_rbytes_delta": int(sql_delta.io_rbytes),
            "sqlserver_io_wbytes_delta": int(sql_delta.io_wbytes),
            "emondrian_cpu_usage_usec_delta": int(emo_delta.cpu_usage_usec),
            "emondrian_io_rbytes_delta": int(emo_delta.io_rbytes),
            "emondrian_io_wbytes_delta": int(emo_delta.io_wbytes),
            # E5 schema is 0-based; frozen D0 candidate indices are 1..24.
            "completion_candidate_index": int(arm_run["completion_candidate"]) - 1,
            "completion_candidate_reached": True,
            "runtime_identity": rid,
            "integrity_flags": {
                "negative_cgroup_delta_detected": False,
                "secret_value_recorded": False,
                "historical_runtime_targeted": False,
                "completion_candidate_unique": True,
            },
        }

        atomic_json(arm_dir / f"{ordinal:04d}_{session_id}_{arm}.json", receipt)
        atomic_json(trace_dir / f"{ordinal:04d}_{session_id}_{arm}.json", {"candidates": traces})
        summaries.append(receipt)
        print(
            f"r3e_arm_complete ordinal={ordinal} session_id={session_id} arm={arm} "
            f"wall_ms={receipt['client_wall_ms']:.3f} "
            f"completion_ms={receipt['time_to_analytical_objective_completion_ms']:.3f}"
        )

    if len(summaries) != 900:
        raise RuntimeError(f"expected 900 receipts, got {len(summaries)}")

    summary = {
        "contract_version": "mcad.nh_r3.e11.xmla_primary_measured_summary.v1",
        "run_id": run_id,
        "scientific_role": "SECONDARY_END_TO_END_CONFIRMATION",
        "selection_role": "CONFIRMATORY_PRIMARY",
        "semantic_sessions": 300,
        "arm_runs_completed": 900,
        "candidate_actions_completed": 21600,
        "warmup_template_count": 7,
        "mcad_api_restart_before_each_arm": True,
        "fresh_session_for_each_gated_arm": True,
        "live_gate_may_relabel_frozen_action": False,
        "effect_analysis_authorized": False,
        "scientific_final_freeze_authorized": False,
        "receipts": summaries,
    }
    atomic_json(output_dir / "r3e_primary_summary.json", summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/workspaces/MCAD_improve3")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dry-run")
    sub.add_parser("authorization-refusal-probe")

    p = sub.add_parser("run-primary")
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--proxy-base", default=DEFAULT_PROXY_BASE)
    p.add_argument("--mcad-base", default=DEFAULT_MCAD_BASE)
    p.add_argument("--confirm", required=True, choices=[CONFIRM_TOKEN])

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "dry-run":
        print(json.dumps(dry_run(repo), indent=2, sort_keys=True))
        print("docker_command_executed=false")
        print("http_request_executed=false")
        print("backend_query_executed=false")
        print("measurement_executed=false")
        print("R3_E11_XMLA_LIVE_EXECUTOR_DRY_RUN=PASS_NO_BACKEND_IO")
        return

    if args.cmd == "authorization-refusal-probe":
        if (repo / AUTH_REL).exists():
            raise RuntimeError("R3-E13 authorization unexpectedly exists during E11")
        try:
            validate_future_authorization(repo)
        except RuntimeError as exc:
            if "authorization file absent" not in str(exc):
                raise
            print(f"authorization_refusal_reason={exc}")
            print("docker_command_executed=false")
            print("http_request_executed=false")
            print("backend_query_executed=false")
            print("measurement_executed=false")
            print("R3_E11_MEASUREMENT_AUTHORIZATION_REFUSAL=PASS")
            return
        raise RuntimeError("authorization refusal unexpectedly failed to refuse")

    run_primary(
        repo=repo,
        runtime_root=Path(args.runtime_root).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        run_id=args.run_id,
        proxy_base=args.proxy_base,
        mcad_base=args.mcad_base,
        confirm=args.confirm,
    )


if __name__ == "__main__":
    main()
