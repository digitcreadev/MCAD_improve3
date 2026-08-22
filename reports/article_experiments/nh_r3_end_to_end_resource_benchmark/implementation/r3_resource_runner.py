#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_HEAD = "51538eac15b8fe2717a36ff7cb701a66bb694025"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
SQLSERVER_SERVICE = "adventureworks-sqlserver"

B1_PREREG_SHA = "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f"
B1_SCHEDULE_SHA = "6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e"
BINDING_PLAN_SHA = "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
B2A1_RUNTIME_SHA = "fb0e12d1e8fe57272135078ce4171b68f8da8231f4a0d355e95b2fe9e572a59a"

ARMS = (
    "UNGATED_EXECUTE_ADMISSIBLE",
    "PERMISSIVE_GATED",
    "SAFE_PRUNING",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def parse_cpu_stat(text: str) -> int:
    values: dict[str, int] = {}
    for raw in text.splitlines():
        parts = raw.strip().split()
        if len(parts) != 2:
            continue
        key, value = parts
        try:
            values[key] = int(value)
        except ValueError:
            continue
    if "usage_usec" not in values:
        raise ValueError("cpu.stat missing usage_usec")
    return values["usage_usec"]


def parse_io_stat(text: str) -> tuple[int, int]:
    rbytes = 0
    wbytes = 0
    saw_device = False
    for raw in text.splitlines():
        parts = raw.strip().split()
        if not parts:
            continue
        saw_device = True
        for token in parts[1:]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            try:
                number = int(value)
            except ValueError:
                continue
            if key == "rbytes":
                rbytes += number
            elif key == "wbytes":
                wbytes += number
    if not saw_device:
        raise ValueError("io.stat has no device rows")
    return rbytes, wbytes


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


def cgroup_delta(before: CgroupSnapshot, after: CgroupSnapshot) -> CgroupDelta:
    delta = CgroupDelta(
        cpu_usage_usec=after.cpu_usage_usec - before.cpu_usage_usec,
        io_rbytes=after.io_rbytes - before.io_rbytes,
        io_wbytes=after.io_wbytes - before.io_wbytes,
    )
    if min(delta.cpu_usage_usec, delta.io_rbytes, delta.io_wbytes) < 0:
        raise ValueError("negative cgroup delta: invalidate arm run; never clamp")
    return delta


def compose_cmd(repo: Path, *args: str) -> list[str]:
    return [
        "docker", "compose",
        "-f", str(repo / "bi-stack/docker-compose.yml"),
        "-f", str(repo / "bi-stack/docker-compose.r3-b2.override.yml"),
        *args,
    ]


def read_sqlserver_cgroup_snapshot(repo: Path) -> CgroupSnapshot:
    # Read-only instrumentation. This never sends a SQL query.
    base = compose_cmd(repo, "exec", "-T", SQLSERVER_SERVICE)
    cpu = subprocess.check_output(
        [*base, "cat", "/sys/fs/cgroup/cpu.stat"],
        text=True,
    )
    io = subprocess.check_output(
        [*base, "cat", "/sys/fs/cgroup/io.stat"],
        text=True,
    )
    rbytes, wbytes = parse_io_stat(io)
    return CgroupSnapshot(
        cpu_usage_usec=parse_cpu_stat(cpu),
        io_rbytes=rbytes,
        io_wbytes=wbytes,
    )


def frozen_full_execute_rule(arm: str, row: dict[str, str]) -> bool:
    klass = str(row.get("class") or "")
    action = str(row.get("operational_action") or "")
    if arm in {"UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED"}:
        return klass != "INADMISSIBLE"
    if arm == "SAFE_PRUNING":
        return action in {"EXECUTE", "EXECUTE_FAIL_OPEN"}
    raise ValueError(f"unknown arm: {arm}")


def frozen_gate_rule(arm: str) -> bool:
    if arm == "UNGATED_EXECUTE_ADMISSIBLE":
        return False
    if arm in {"PERMISSIVE_GATED", "SAFE_PRUNING"}:
        return True
    raise ValueError(f"unknown arm: {arm}")


def completion_candidate_for_arm(arm: str, schedule_row: dict[str, str]) -> int:
    if arm == "SAFE_PRUNING":
        return int(schedule_row["completion_candidate_safe"])
    if arm in {"PERMISSIVE_GATED", "UNGATED_EXECUTE_ADMISSIBLE"}:
        return int(schedule_row["completion_candidate_permissive"])
    raise ValueError(f"unknown arm: {arm}")


def load_and_validate_inputs(repo: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    r3 = repo / R3_REL
    prereg = r3 / "config/r3_b1_measurement_preregistration.json"
    schedule = r3 / "config/r3_b1_arm_order_schedule.csv"
    binding = r3 / "results/full_sequence_binding.csv"
    binding_sha = r3 / "results/BINDING_PLAN_SHA256.txt"
    runtime = repo / "bi-stack/mcad-proxy/r3_measurement_app.py"

    if sha256(prereg) != B1_PREREG_SHA:
        raise RuntimeError("B1 preregistration changed")
    if sha256(schedule) != B1_SCHEDULE_SHA:
        raise RuntimeError("B1 arm schedule changed")
    if sha256(runtime) != B2A1_RUNTIME_SHA:
        raise RuntimeError("B2a.1 runtime changed")

    declared_binding = binding_sha.read_text(encoding="utf-8").split()[0]
    if declared_binding != BINDING_PLAN_SHA:
        raise RuntimeError("binding plan digest changed")

    contract = json.loads(prereg.read_text(encoding="utf-8"))
    if contract["authorization"]["measured_pilot_authorized"] is not False:
        raise RuntimeError("measured pilot unexpectedly authorized")
    if contract["scientific_authority"]["live_gate_may_relabel_frozen_action"] is not False:
        raise RuntimeError("live gate unexpectedly authoritative")

    schedule_rows = read_csv(schedule)
    binding_rows = read_csv(binding)

    if len(schedule_rows) != 20:
        raise RuntimeError(f"expected 20 pilot schedule rows, got {len(schedule_rows)}")
    if len(binding_rows) != 28800:
        raise RuntimeError(f"expected 28800 binding rows, got {len(binding_rows)}")

    return schedule_rows, binding_rows, contract


def build_plan(repo: Path) -> dict[str, Any]:
    schedule_rows, binding_rows, contract = load_and_validate_inputs(repo)
    pilot_sessions = {row["session_id"] for row in schedule_rows}
    by_session: dict[str, list[dict[str, str]]] = {sid: [] for sid in pilot_sessions}

    for row in binding_rows:
        sid = row.get("session_id", "")
        if sid in by_session:
            by_session[sid].append(row)

    for sid, rows in by_session.items():
        rows.sort(key=lambda r: int(r["candidate_index"]))
        indices = [int(r["candidate_index"]) for r in rows]
        if len(rows) != 24 or indices != list(range(1, 25)):
            raise RuntimeError(f"{sid}: expected candidates 1..24 exactly")

    arm_runs: list[dict[str, Any]] = []
    candidate_actions: list[dict[str, Any]] = []
    unique_templates: set[str] = set()

    for schedule_row in schedule_rows:
        sid = schedule_row["session_id"]
        arms = [schedule_row["arm_1"], schedule_row["arm_2"], schedule_row["arm_3"]]
        if set(arms) != set(ARMS):
            raise RuntimeError(f"{sid}: invalid arm permutation {arms}")

        for position, arm in enumerate(arms, start=1):
            completion_candidate = completion_candidate_for_arm(arm, schedule_row)
            rows = by_session[sid]
            full_count = 0
            gate_count = 0
            for row in rows:
                unique_templates.add(row["template_id"])
                run_gate = frozen_gate_rule(arm)
                run_full = frozen_full_execute_rule(arm, row)
                if run_gate:
                    gate_count += 1
                if run_full:
                    full_count += 1
                candidate_actions.append(
                    {
                        "session_id": sid,
                        "arm": arm,
                        "arm_position": position,
                        "candidate_index": int(row["candidate_index"]),
                        "query_id": row["query_id"],
                        "frozen_class": row["class"],
                        "frozen_operational_action": row["operational_action"],
                        "run_gate": run_gate,
                        "run_full_backend": run_full,
                        "is_completion_candidate": int(row["candidate_index"]) == completion_candidate,
                        "template_id": row["template_id"],
                        "query_template_path": row["query_template_path"],
                        "parameter_binding": row["parameter_binding"],
                    }
                )
            arm_runs.append(
                {
                    "block_index": int(schedule_row["block_index"]),
                    "session_id": sid,
                    "topology": schedule_row["topology"],
                    "pattern": schedule_row["pattern"],
                    "arm_position": position,
                    "arm": arm,
                    "completion_candidate": completion_candidate,
                    "planned_gate_evaluations": gate_count,
                    "planned_full_backend_executions": full_count,
                }
            )

    if len(arm_runs) != 60:
        raise RuntimeError(f"expected 60 arm runs, got {len(arm_runs)}")
    if len(candidate_actions) != 1440:
        raise RuntimeError(f"expected 1440 candidate actions, got {len(candidate_actions)}")

    return {
        "contract_version": "mcad.nh_r3.b2b.resource_runner.plan.v1",
        "parent_head": PARENT_HEAD,
        "measurement_authorized": False,
        "confirmatory_claim_authorized": False,
        "backend_started_by_plan": False,
        "measured_query_executed_by_plan": False,
        "objective_id": OBJECTIVE_ID,
        "pilot_sessions": len(pilot_sessions),
        "arm_runs": arm_runs,
        "candidate_actions": candidate_actions,
        "unique_templates_lexicographic": sorted(unique_templates),
        "timing_contract": contract["timing"],
        "cgroup_contract": contract["sqlserver_cgroup"],
        "cache_control": contract["cache_control"],
        "warmup": contract["warmup"],
    }


def write_plan(repo: Path, output: Path | None) -> dict[str, Any]:
    plan = build_plan(repo)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def preflight_readonly(repo: Path) -> dict[str, Any]:
    # Does not build/start containers and does not send BI/SQL requests.
    # If SQL Server is already running, only cgroup files are read.
    plan = build_plan(repo)
    out: dict[str, Any] = {
        "contract_version": "mcad.nh_r3.b2b.preflight_readonly.v1",
        "measurement_authorized": False,
        "plan_sessions": plan["pilot_sessions"],
        "plan_arm_runs": len(plan["arm_runs"]),
        "plan_candidate_actions": len(plan["candidate_actions"]),
        "backend_started_by_preflight": False,
        "measured_query_executed": False,
    }

    ps = subprocess.run(
        compose_cmd(repo, "ps", "-q", SQLSERVER_SERVICE),
        text=True,
        capture_output=True,
    )
    container_running = ps.returncode == 0 and bool(ps.stdout.strip())
    out["sqlserver_container_already_running"] = container_running

    if container_running:
        snap = read_sqlserver_cgroup_snapshot(repo)
        out["cgroup_readable"] = True
        out["cgroup_snapshot"] = {
            "cpu_usage_usec": snap.cpu_usage_usec,
            "io_rbytes": snap.io_rbytes,
            "io_wbytes": snap.io_wbytes,
        }
    else:
        out["cgroup_readable"] = None
        out["cgroup_snapshot"] = None

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="NH-R3-B resource runner scaffold")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="build deterministic 60-arm plan; no backend")
    p_plan.add_argument("--output")

    sub.add_parser(
        "preflight-readonly",
        help="validate plan and read cgroup only if SQL Server is already running; never starts backend",
    )

    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "plan":
        output = Path(args.output).resolve() if args.output else None
        plan = write_plan(repo, output)
        print(f"pilot_sessions={plan['pilot_sessions']}")
        print(f"planned_arm_runs={len(plan['arm_runs'])}")
        print(f"planned_candidate_actions={len(plan['candidate_actions'])}")
        print(f"unique_templates={len(plan['unique_templates_lexicographic'])}")
        print("backend_started=false")
        print("measured_query_executed=false")
        print("measurement_authorized=false")
        print("R3_B2B_PLAN=PASS")
        return

    if args.cmd == "preflight-readonly":
        out = preflight_readonly(repo)
        print(json.dumps(out, indent=2, sort_keys=True))
        print("backend_started=false")
        print("measured_query_executed=false")
        print("measurement_authorized=false")
        print("R3_B2B_PREFLIGHT_READONLY=PASS")
        return

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    main()
