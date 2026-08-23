#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
EXECUTOR_MODULE = "r3_dev_pilot_executor"
STATIC_RUNNER_MODULE = "r3_resource_runner"

PROJECT = "mcad-r3-rerun1"
COMPOSE_REL = R3_REL / "runtime/r3_isolated_runtime.compose.yml"
MCAD_API_SERVICE = "r3-mcad-api"
SQLSERVER_SERVICE = "r3-sqlserver"
PROXY_SERVICE = "r3-mcad-proxy"

DEFAULT_MCAD_BASE = "http://127.0.0.1:18000"
DEFAULT_PROXY_BASE = "http://127.0.0.1:19000"
CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_DEV_PILOT"


def import_frozen_modules(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        import r3_dev_pilot_executor as executor  # type: ignore
        import r3_resource_runner as static_runner  # type: ignore
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass
    return executor, static_runner


def isolated_compose_cmd(repo: Path, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "-f",
        str(repo / COMPOSE_REL),
        *args,
    ]


def isolated_cgroup_snapshot(repo: Path, static_runner: Any):
    base = isolated_compose_cmd(repo, "exec", "-T", SQLSERVER_SERVICE)
    cpu = subprocess.check_output(
        [*base, "cat", "/sys/fs/cgroup/cpu.stat"],
        text=True,
    )
    io = subprocess.check_output(
        [*base, "cat", "/sys/fs/cgroup/io.stat"],
        text=True,
    )
    rbytes, wbytes = static_runner.parse_io_stat(io)
    return static_runner.CgroupSnapshot(
        cpu_usage_usec=static_runner.parse_cpu_stat(cpu),
        io_rbytes=rbytes,
        io_wbytes=wbytes,
    )


def patch_frozen_executor(repo: Path):
    executor, static_runner = import_frozen_modules(repo)

    original_import_static_runner = executor.import_static_runner

    def patched_compose_cmd(repo_arg: Path, _pilot_override: Path, *args: str) -> list[str]:
        return isolated_compose_cmd(repo_arg, *args)

    def patched_import_static_runner(repo_arg: Path):
        module = original_import_static_runner(repo_arg)

        def read_isolated_sqlserver_cgroup_snapshot(repo_inner: Path):
            return isolated_cgroup_snapshot(repo_inner, module)

        module.read_sqlserver_cgroup_snapshot = read_isolated_sqlserver_cgroup_snapshot
        return module

    executor.compose_cmd = patched_compose_cmd
    executor.MCAD_API_SERVICE = MCAD_API_SERVICE
    executor.SQLSERVICE = SQLSERVER_SERVICE
    executor.PROXY_SERVICE = PROXY_SERVICE
    executor.import_static_runner = patched_import_static_runner

    return executor, static_runner


def require_runtime_environment(repo: Path, runtime_root: Path) -> None:
    repo = repo.resolve()
    runtime_root = runtime_root.resolve()

    if repo == runtime_root or repo in runtime_root.parents:
        raise RuntimeError("isolated runtime root must be outside repository")

    if os.environ.get("R3_AW_SA_PASSWORD", "") == "":
        raise RuntimeError("R3_AW_SA_PASSWORD is required for isolated compose operations")

    os.environ["R3_REPO_ROOT"] = str(repo)
    os.environ["R3_RUNTIME_ROOT"] = str(runtime_root)


def cmd_dry_run(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    executor, _ = patch_frozen_executor(repo)

    probe = executor.compose_cmd(repo, Path("/nonexistent/ignored.override.yml"), "restart", MCAD_API_SERVICE)
    expected_prefix = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "-f",
        str(repo / COMPOSE_REL),
    ]
    if probe[: len(expected_prefix)] != expected_prefix:
        raise RuntimeError(f"isolated compose routing mismatch: {probe}")
    if "bi-stack/docker-compose.yml" in " ".join(probe):
        raise RuntimeError("historical compose leaked into isolated routing")
    if "mcad-api" in probe and MCAD_API_SERVICE not in probe:
        raise RuntimeError("historical mcad-api service leaked into isolated routing")

    dry = executor.dry_run(repo)

    if dry["pilot_sessions"] != 20:
        raise RuntimeError("frozen dry-run pilot session count changed")
    if dry["arm_runs"] != 60:
        raise RuntimeError("frozen dry-run arm count changed")
    if dry["candidate_actions"] != 1440:
        raise RuntimeError("frozen dry-run candidate action count changed")
    if dry["measurement_executed"] is not False:
        raise RuntimeError("dry-run unexpectedly executed measurement")

    print("adapter_contract_version=mcad.nh_r3.b2k.isolated_executor_adapter.v1")
    print("routing_project=mcad-r3-rerun1")
    print("routing_mcad_api_service=r3-mcad-api")
    print("routing_sqlserver_service=r3-sqlserver")
    print("routing_proxy_service=r3-mcad-proxy")
    print("historical_compose_targeted=false")
    print("frozen_executor_dry_run=PASS")
    print("pilot_sessions=20")
    print("arm_runs=60")
    print("candidate_actions=1440")
    print("measurement_executed=false")
    print("docker_command_executed=false")
    print("R3_B2K_ISOLATED_EXECUTOR_ADAPTER_DRY_RUN=PASS")


def cmd_run(args: argparse.Namespace) -> None:
    if args.confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit measured DEV pilot confirmation token required")

    repo = Path(args.repo).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    output_dir = Path(args.output_dir).resolve()

    require_runtime_environment(repo, runtime_root)

    executor, _ = patch_frozen_executor(repo)

    # The frozen executor retains all scientific loop, timing, receipt, action,
    # session, cache-control, and validation logic. The adapter changes only
    # the operational Docker/HTTP target to the isolated runtime.
    summary = executor.run_pilot(
        repo=repo,
        pilot_override=repo / COMPOSE_REL,
        output_dir=output_dir,
        proxy_base=args.proxy_base,
        mcad_base=args.mcad_base,
    )

    print(f"isolated_adapter_completed_arm_runs={summary['arm_runs_completed']}")
    print(f"isolated_adapter_candidate_actions={summary['candidate_actions_completed']}")
    print("isolated_adapter_confirmatory_claim_authorized=false")
    print("R3_B2K_ISOLATED_EXECUTOR_ADAPTER_RUN=PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="NH-R3 isolated routing adapter for frozen B2e executor")
    parser.add_argument("--repo", default=".")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry-run")
    p_dry.set_defaults(func=cmd_dry_run)

    p_run = sub.add_parser("run")
    p_run.add_argument("--runtime-root", required=True)
    p_run.add_argument("--output-dir", required=True)
    p_run.add_argument("--proxy-base", default=DEFAULT_PROXY_BASE)
    p_run.add_argument("--mcad-base", default=DEFAULT_MCAD_BASE)
    p_run.add_argument("--confirm", required=True, choices=[CONFIRM_TOKEN])
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
