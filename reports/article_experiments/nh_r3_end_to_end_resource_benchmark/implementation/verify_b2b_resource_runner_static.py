#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
BASE_PARENT = "51538eac15b8fe2717a36ff7cb701a66bb694025"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")

LEGACY_BLOBS = {
    "bi-stack/docker-compose.yml": "210d4fbb7d09ef2f4a8ad664f34278fb51185a4e",
    "bi-stack/mcad-proxy/Dockerfile": "e5d29c88134de88419a1bc4902c5efd7c11a96a4",
    "bi-stack/mcad-proxy/app.py": "032b5eb8d9fe9f5bc4943b87396d58de1e08f309",
    "bi-stack/mcad-proxy/execution/gateway.py": "d3a92ebe9fc417758c2865c43cba4af9d1ed9d03",
    "bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py": "e8e980e03904a4a418028a4edaabe1b82e56ba13",
}


def fail(reason: str) -> None:
    raise SystemExit(f"R3_B2B_STATIC_VERIFY=FAIL reason={reason}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def import_runner(path: Path):
    name = "_mcad_r3_b2b_runner_verify"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        fail("runner_import_spec_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    r3 = repo / R3_REL
    runner = r3 / "implementation/r3_resource_runner.py"
    contract_path = r3 / "config/r3_b2b_runner_contract.json"

    if git(repo, "branch", "--show-current") != BRANCH:
        fail("branch_changed")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_PARENT, "HEAD"],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0:
        fail("base_parent_not_ancestor")
    print("parent_ancestry=PASS")

    if not runner.is_file() or not contract_path.is_file():
        fail("b2b_files_missing")

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("parent_head") != BASE_PARENT:
        fail("contract_parent_mismatch")
    if contract.get("measurement_authorized") is not False:
        fail("measurement_became_authorized")
    if contract.get("confirmatory_claim_authorized") is not False:
        fail("confirmatory_claim_became_authorized")
    print("b2b_contract=PASS")

    prereg_path = r3 / "config/r3_b1_measurement_preregistration.json"
    schedule_path = r3 / "config/r3_b1_arm_order_schedule.csv"
    runtime_path = repo / "bi-stack/mcad-proxy/r3_measurement_app.py"
    if sha256(prereg_path) != "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f":
        fail("b1_prereg_changed")
    if sha256(schedule_path) != "6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e":
        fail("b1_schedule_changed")
    if sha256(runtime_path) != "fb0e12d1e8fe57272135078ce4171b68f8da8231f4a0d355e95b2fe9e572a59a":
        fail("b2a1_runtime_changed")
    print("frozen_parent_artifacts=PASS")

    binding = (r3 / "results/BINDING_PLAN_SHA256.txt").read_text(encoding="utf-8").split()[0]
    if binding != "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff":
        fail("binding_digest_changed")
    print("binding_digest=PASS")

    for rel, expected_blob in LEGACY_BLOBS.items():
        actual = git(repo, "hash-object", rel)
        head_blob = git(repo, "rev-parse", f"HEAD:{rel}")
        if actual != expected_blob or head_blob != expected_blob:
            fail(f"legacy_changed:{rel}")
    print("historical_reproducibility_anchors=PASS")

    source = runner.read_text(encoding="utf-8")
    try:
        compile(source, str(runner), "exec")
        ast.parse(source)
    except SyntaxError as exc:
        fail(f"runner_syntax:{exc}")
    print("runner_syntax=PASS")

    required_tokens = [
        "def parse_cpu_stat",
        "def parse_io_stat",
        "def cgroup_delta",
        "negative cgroup delta: invalidate arm run; never clamp",
        "def frozen_full_execute_rule",
        "def frozen_gate_rule",
        "def completion_candidate_for_arm",
        "def build_plan",
        "preflight-readonly",
        "backend_started_by_preflight",
        "measurement_authorized",
    ]
    for token in required_tokens:
        if token not in source:
            fail(f"runner_contract_token_missing:{token}")
    print("runner_contract_static=PASS")

    module = import_runner(runner)

    if module.parse_cpu_stat("usage_usec 123456\nuser_usec 100\nsystem_usec 200\n") != 123456:
        fail("cpu_stat_parser_wrong")
    rbytes, wbytes = module.parse_io_stat(
        "8:0 rbytes=100 wbytes=200 rios=1 wios=2\n"
        "8:16 rbytes=300 wbytes=400 rios=3 wios=4\n"
    )
    if (rbytes, wbytes) != (400, 600):
        fail("io_stat_parser_wrong")

    before = module.CgroupSnapshot(cpu_usage_usec=1000, io_rbytes=2000, io_wbytes=3000)
    after = module.CgroupSnapshot(cpu_usage_usec=1500, io_rbytes=2500, io_wbytes=3900)
    delta = module.cgroup_delta(before, after)
    if (delta.cpu_usage_usec, delta.io_rbytes, delta.io_wbytes) != (500, 500, 900):
        fail("cgroup_delta_wrong")
    try:
        module.cgroup_delta(after, before)
    except ValueError:
        pass
    else:
        fail("negative_cgroup_delta_not_rejected")
    print("cgroup_unit=PASS")

    with tempfile.TemporaryDirectory() as td:
        output = Path(td) / "plan.json"
        proc = subprocess.run(
            [
                sys.executable, str(runner),
                "--repo", str(repo),
                "plan",
                "--output", str(output),
            ],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr)
            fail("plan_mode_failed")
        plan = json.loads(output.read_text(encoding="utf-8"))

    if plan.get("pilot_sessions") != 20:
        fail("plan_pilot_session_count_wrong")
    if len(plan.get("arm_runs") or []) != 60:
        fail("plan_arm_run_count_wrong")
    if len(plan.get("candidate_actions") or []) != 1440:
        fail("plan_candidate_action_count_wrong")
    if plan.get("backend_started_by_plan") is not False:
        fail("plan_started_backend")
    if plan.get("measured_query_executed_by_plan") is not False:
        fail("plan_executed_query")
    if plan.get("measurement_authorized") is not False:
        fail("plan_authorized_measurement")

    arms = {r["arm"] for r in plan["arm_runs"]}
    if arms != {"UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING"}:
        fail("plan_arm_set_wrong")

    for run in plan["arm_runs"]:
        if not (1 <= int(run["completion_candidate"]) <= 24):
            fail("completion_candidate_out_of_range")

    safe_runs = [r for r in plan["arm_runs"] if r["arm"] == "SAFE_PRUNING"]
    permissive_runs = [r for r in plan["arm_runs"] if r["arm"] == "PERMISSIVE_GATED"]
    if len(safe_runs) != 20 or len(permissive_runs) != 20:
        fail("per_arm_run_count_wrong")

    print("deterministic_plan=PASS")
    print("pilot_sessions=20")
    print("planned_arm_runs=60")
    print("planned_candidate_actions=1440")

    print("backend_started_by_verifier=false")
    print("measured_query_executed=false")
    print("measurement_authorized=false")
    print("R3_B2B_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
