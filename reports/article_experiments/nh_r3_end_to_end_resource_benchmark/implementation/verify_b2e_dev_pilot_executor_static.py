#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_HEAD = "4736455d48483021e07fcc5d44a12f55bfeb652b"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")

EXP_EXECUTOR_SHA = "9a0b0f7f81a6e6cd59ac72a12e5674f0b55c1ac49893a0200a3b65eb43320e40"
EXP_CONTRACT_SHA = "b2f1aa0c384bf86a24c6148a5f450fcbdce2521510800dbf3733a1a597ce65ba"
EXP_B1_SHA = "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f"
EXP_AUTH_SHA = "78a7c9a92b9b9f1d7dd10821449205bc4bbd7b996c4808aec747df44027180a4"
EXP_SCHEDULE_SHA = "6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e"
EXP_RUNTIME_SHA = "fb0e12d1e8fe57272135078ce4171b68f8da8231f4a0d355e95b2fe9e572a59a"
EXP_BINDING_DIGEST = "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    r3 = repo / R3_REL

    executor = r3 / "implementation/r3_dev_pilot_executor.py"
    contract = r3 / "config/r3_b2e_dev_pilot_executor_contract.json"
    static_runner = r3 / "implementation/r3_resource_runner.py"
    b1 = r3 / "config/r3_b1_measurement_preregistration.json"
    auth = r3 / "config/r3_b2c_dev_pilot_authorization.json"
    schedule = r3 / "config/r3_b1_arm_order_schedule.csv"
    binding_sha = r3 / "results/BINDING_PLAN_SHA256.txt"
    runtime = repo / "bi-stack/mcad-proxy/r3_measurement_app.py"

    if subprocess.check_output(["git", "-C", str(repo), "branch", "--show-current"], text=True).strip() != BRANCH:
        fail("wrong branch")

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT_HEAD, "HEAD"],
        check=True,
    )
    print("parent_ancestry=PASS")

    for path in (executor, contract, static_runner, b1, auth, schedule, binding_sha, runtime):
        if not path.is_file():
            fail(f"missing required file: {path}")

    if sha256(executor) != EXP_EXECUTOR_SHA:
        fail("executor hash mismatch")
    if sha256(contract) != EXP_CONTRACT_SHA:
        fail("contract hash mismatch")
    if sha256(b1) != EXP_B1_SHA:
        fail("B1 hash mismatch")
    if sha256(auth) != EXP_AUTH_SHA:
        fail("B2c authorization hash mismatch")
    if sha256(schedule) != EXP_SCHEDULE_SHA:
        fail("schedule hash mismatch")
    if sha256(runtime) != EXP_RUNTIME_SHA:
        fail("runtime hash mismatch")
    if binding_sha.read_text(encoding="utf-8").split()[0] != EXP_BINDING_DIGEST:
        fail("binding digest mismatch")
    print("frozen_authority_hashes=PASS")

    contract_data = json.loads(contract.read_text(encoding="utf-8"))
    assert contract_data["authorization"]["dev_measured_pilot_authorized"] is True
    assert contract_data["authorization"]["confirmatory_claim_authorized"] is False
    assert contract_data["execution"] == {
        "candidate_actions": 1440,
        "gated_arm_runs": 40,
        "pilot_arm_runs": 60,
        "pilot_sessions": 20,
        "ungated_arm_runs": 20,
    }
    assert contract_data["measurement"]["live_gate_may_relabel_frozen_action"] is False
    assert contract_data["measurement"]["negative_cgroup_delta_invalidates_arm"] is True
    assert contract_data["measurement"]["output_must_be_outside_repository_during_pilot"] is True
    assert contract_data["operational_gate"]["measurement_executed_by_static_verification"] is False
    assert contract_data["operational_gate"]["next_required_gate"] == "commit_and_publish_executor_before_measured_DEV_pilot"
    print("executor_contract=PASS")

    source = executor.read_text(encoding="utf-8")
    ast.parse(source)
    print("executor_syntax=PASS")

    required_fragments = [
        "/bi/r3/measurement/gate-only",
        "/bi/r3/measurement/full-execute",
        "/sessions/create",
        "restart_mcad_api",
        "read_sqlserver_cgroup_snapshot",
        "cgroup_delta",
        "time.perf_counter_ns()",
        "backend_request_count_including_gate_probes",
        "live_gate_action_authoritative",
        "EXECUTE_AUTHORIZED_NH_R3_DEV_PILOT",
        "output directory must be outside repository",
    ]
    for fragment in required_fragments:
        if fragment not in source:
            fail(f"executor missing required fragment: {fragment}")

    forbidden_fragments = [
        "compose_cmd(repo, pilot_override, \"up\"",
        "compose_cmd(repo, pilot_override, \"start\"",
        "/ckg/update\"",
    ]
    for fragment in forbidden_fragments:
        if fragment in source:
            fail(f"executor contains forbidden lifecycle/CKG fragment: {fragment}")

    print("executor_static_contract=PASS")

    proc = subprocess.run(
        [
            sys.executable,
            str(executor),
            "--repo",
            str(repo),
            "dry-run",
        ],
        text=True,
        capture_output=True,
    )
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        fail(f"executor dry-run failed: {proc.returncode}")

    if "R3_B2E_EXECUTOR_DRY_RUN=PASS" not in proc.stdout:
        fail("dry-run PASS marker missing")

    json_text = proc.stdout.split("measured_execution_performed=false", 1)[0].strip()
    data = json.loads(json_text)
    assert data["pilot_sessions"] == 20
    assert data["arm_runs"] == 60
    assert data["candidate_actions"] == 1440
    assert data["gated_arm_runs"] == 40
    assert data["ungated_arm_runs"] == 20
    assert data["mcad_api_restarts_planned"] == 60
    assert data["fresh_mcad_sessions_planned"] == 40
    assert data["measurement_executed"] is False
    assert data["dev_measured_pilot_authorized"] is True
    assert data["confirmatory_claim_authorized"] is False
    print("deterministic_executor_dry_run=PASS")

    print("backend_started_by_static_verifier=false")
    print("measured_query_executed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_B2E_EXECUTOR_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
