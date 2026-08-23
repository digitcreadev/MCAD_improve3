#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT = "d2f5e40171bd2daccec18e7d450644e0b510b5d8"

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
CONTRACT = R3 / "config/r3_b2k_isolated_executor_adapter_contract.json"
ADAPTER = R3 / "implementation/r3_isolated_executor_adapter.py"
EXECUTOR = R3 / "implementation/r3_dev_pilot_executor.py"
STATIC_RUNNER = R3 / "implementation/r3_resource_runner.py"
B2H_CONTRACT = R3 / "config/r3_b2h_isolated_runtime_contract.json"
B2H_COMPOSE = R3 / "runtime/r3_isolated_runtime.compose.yml"

EXPECTED = {
    "executor_sha256": "9a0b0f7f81a6e6cd59ac72a12e5674f0b55c1ac49893a0200a3b65eb43320e40",
    "static_runner_sha256": "fa4458a212dd88135d4806bcdfbc6e564ddd7daa9fe944653aa187079065761e",
    "b2h_contract_sha256": "9cb4b1a8156e949b74bb1608d25c5abdbc16c009d35435b0592b1941e59f1dc3",
    "b2h_compose_sha256": "48dd2c5b56aff6f786f1ef27b056b69663bcfef24883e37023ca0f4f6e3d476b",
    "b2j_archive_sha256": "66f3004b55da6cb2ee77daf495a2488b92bce929acc34d46d1be874881fb7616",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def function_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--b2j-archive")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()

    if git(repo, "branch", "--show-current") != BRANCH:
        raise SystemExit("wrong branch")

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT, "HEAD"],
        check=True,
    )

    def p(rel: Path) -> Path:
        return repo / rel

    assert sha256(p(EXECUTOR)) == EXPECTED["executor_sha256"]
    assert sha256(p(STATIC_RUNNER)) == EXPECTED["static_runner_sha256"]
    assert sha256(p(B2H_CONTRACT)) == EXPECTED["b2h_contract_sha256"]
    assert sha256(p(B2H_COMPOSE)) == EXPECTED["b2h_compose_sha256"]

    contract = json.loads(p(CONTRACT).read_text(encoding="utf-8"))
    assert contract["contract_version"] == "mcad.nh_r3.b2k.isolated_executor_adapter.v1"
    assert contract["parent_head"] == PARENT
    assert contract["b2j_clone_creation_evidence"]["archive_sha256"] == EXPECTED["b2j_archive_sha256"]
    assert contract["b2j_clone_creation_evidence"]["protected_historical_runtime_mutated"] is False
    assert contract["frozen_executor_authority"]["executor_modified"] is False
    assert contract["frozen_executor_authority"]["static_runner_modified"] is False
    assert contract["frozen_executor_authority"]["scientific_plan_logic_modified"] is False
    assert contract["frozen_executor_authority"]["timing_logic_modified"] is False
    assert contract["frozen_executor_authority"]["receipt_schema_modified"] is False
    assert contract["compatibility_problem"]["direct_use_of_frozen_executor_would_target_historical_compose"] is True
    assert contract["compatibility_problem"]["direct_use_forbidden_until_adapter_published"] is True
    assert contract["adapter_scope"]["frozen_executor_run_pilot_called_directly"] is True
    assert contract["adapter_scope"]["adapter_may_not_reimplement_scientific_loop"] is True
    assert contract["authorization"]["static_adapter_checkpoint_only"] is True
    assert contract["authorization"]["measured_execution_authorized_by_this_checkpoint"] is False
    assert contract["authorization"]["confirmatory_claim_authorized"] is False

    adapter_source = p(ADAPTER).read_text(encoding="utf-8")
    compile(adapter_source, str(p(ADAPTER)), "exec")
    tree = ast.parse(adapter_source)
    names = function_names(tree)

    required_functions = {
        "import_frozen_modules",
        "isolated_compose_cmd",
        "isolated_cgroup_snapshot",
        "patch_frozen_executor",
        "require_runtime_environment",
        "cmd_dry_run",
        "cmd_run",
    }
    missing = sorted(required_functions - names)
    if missing:
        raise SystemExit(f"adapter functions missing: {missing}")

    required_fragments = [
        'PROJECT = "mcad-r3-rerun1"',
        'MCAD_API_SERVICE = "r3-mcad-api"',
        'SQLSERVER_SERVICE = "r3-sqlserver"',
        'PROXY_SERVICE = "r3-mcad-proxy"',
        "executor.run_pilot(",
        "executor.dry_run(repo)",
        "module.read_sqlserver_cgroup_snapshot = read_isolated_sqlserver_cgroup_snapshot",
        "executor.compose_cmd = patched_compose_cmd",
        "executor.MCAD_API_SERVICE = MCAD_API_SERVICE",
    ]
    for fragment in required_fragments:
        if fragment not in adapter_source:
            raise SystemExit(f"required adapter fragment missing: {fragment}")

    forbidden_fragments = [
        'repo / "bi-stack/docker-compose.yml"',
        'repo / "bi-stack/docker-compose.r3-b2.override.yml"',
        'SQLSERVER_SERVICE = "adventureworks-sqlserver"',
        'MCAD_API_SERVICE = "mcad-api"',
        'PROJECT = "bi-stack"',
        "time.perf_counter_ns(",
        'receipt = {',
        'candidate_records.append(',
        'if bool(action["run_gate"])',
        'if bool(action["run_full_backend"])',
    ]
    for fragment in forbidden_fragments:
        if fragment in adapter_source:
            raise SystemExit(f"adapter reimplements or targets forbidden logic: {fragment}")

    executor_source = p(EXECUTOR).read_text(encoding="utf-8")
    assert 'SQLSERVICE = "adventureworks-sqlserver"' in executor_source
    assert 'MCAD_API_SERVICE = "mcad-api"' in executor_source
    assert 'str(repo / "bi-stack/docker-compose.yml")' in executor_source
    assert 'str(repo / "bi-stack/docker-compose.r3-b2.override.yml")' in executor_source

    static_source = p(STATIC_RUNNER).read_text(encoding="utf-8")
    assert 'SQLSERVER_SERVICE = "adventureworks-sqlserver"' in static_source
    assert 'str(repo / "bi-stack/docker-compose.yml")' in static_source

    if args.b2j_archive:
        archive = Path(args.b2j_archive).resolve()
        assert archive.is_file()
        assert sha256(archive) == EXPECTED["b2j_archive_sha256"]

    print("parent_ancestry=PASS")
    print("frozen_executor_sha256=PASS")
    print("frozen_static_runner_sha256=PASS")
    print("b2h_isolated_runtime_authority=PASS")
    print("b2j_clone_creation_evidence_authority=PASS")
    print("historical_targeting_in_frozen_executor_detected=true")
    print("adapter_operational_routing_only=PASS")
    print("adapter_scientific_loop_reimplementation=NONE")
    print("frozen_executor_modified=false")
    print("frozen_static_runner_modified=false")
    print("measured_execution_performed=false")
    print("docker_command_executed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_B2K_ISOLATED_EXECUTOR_ADAPTER_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
