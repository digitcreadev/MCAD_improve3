#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
D2_HEAD = "e399654ddcd0bb41febd07e8f12d384751407c5e"

EXPECTED = {
    "d2_auth_blob": "3dc900948f1022c6f991964f50570bbb1ad9bcff",
    "d2_auth_sha": "d3725ff2fea15c1501cfba26265922a19b2c41354b57c9bee81dce1e22415d2c",
    "d1_executor_blob": "ee0fb893a35086d01a69ee4eb8d70166ba2bb7b0",
    "d1_executor_sha": "b4e024ab12940a9824f39188e8b79e0974f166d7b98ac04ab7afe70082a012ae",
    "primary_schedule_blob": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    "measurement_protocol_blob": "2d3a49794f196c6b6a43b3a0041dfd46dff357ab",
}

EXPECTED_TEMPLATES = (
    "AW_ATOM_COST",
    "AW_ATOM_MARGIN",
    "AW_ATOM_SALES",
    "AW_BAD_GRAIN_YEAR",
    "AW_DISTRACTOR_ACCESSORIES_SALES",
    "AW_MIX_ACCESSORIES_SALES_COST",
    "AW_PAIR_SALES_COST",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def check(path: Path, blob: str, sha: str | None, label: str) -> None:
    actual_blob = git_blob_sha1(path)
    if actual_blob != blob:
        raise RuntimeError(f"{label} blob changed: {actual_blob}")
    if sha is not None and sha256(path) != sha:
        raise RuntimeError(f"{label} sha256 changed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    r3 = repo / R3_REL

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", D2_HEAD, "HEAD"],
        check=True,
    )

    check(
        r3 / "config/r3_d2_confirmatory_measurement_authorization.json",
        EXPECTED["d2_auth_blob"], EXPECTED["d2_auth_sha"], "D2 authorization"
    )
    check(
        r3 / "implementation/r3_d1_confirmatory_executor.py",
        EXPECTED["d1_executor_blob"], EXPECTED["d1_executor_sha"], "D1 executor"
    )
    check(
        r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv",
        EXPECTED["primary_schedule_blob"], None, "D0 primary schedule"
    )
    check(
        r3 / "docs/MEASUREMENT_PROTOCOL.md",
        EXPECTED["measurement_protocol_blob"], None, "measurement protocol"
    )

    contract = json.loads(
        (r3 / "config/r3_d3_primary_confirmatory_execution_contract.json")
        .read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.d3.primary_confirmatory_execution_kit.v1":
        raise RuntimeError("unexpected D3 execution contract")
    if contract.get("parent_d2_head") != D2_HEAD:
        raise RuntimeError("D3 contract not bound to D2")
    if contract.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("D3 analysis class changed")

    warmup = contract.get("warmup") or {}
    if warmup.get("required") is not True or warmup.get("measured") is not False:
        raise RuntimeError("D3 warmup contract changed")
    if int(warmup.get("unique_templates", -1)) != 7:
        raise RuntimeError("D3 warmup template count changed")
    if warmup.get("sqlserver_restart_after_warmup") is not False:
        raise RuntimeError("D3 SQL Server restart after warmup is forbidden")

    primary = contract.get("primary_execution") or {}
    expected_contract = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "gated_arm_runs": 600,
        "ungated_arm_runs": 300,
        "mcad_api_restarts_planned": 900,
        "fresh_gated_sessions_planned": 600,
    }
    for key, value in expected_contract.items():
        if int(primary.get(key, -1)) != value:
            raise RuntimeError(f"D3 contract mismatch: {key}")
    if primary.get("fallback_120_activated") is not False:
        raise RuntimeError("D3 fallback unexpectedly activated")
    if primary.get("no_interim_effect_looks") is not True:
        raise RuntimeError("D3 no-interim-look rule changed")
    if primary.get("effect_size_tuning_allowed") is not False:
        raise RuntimeError("D3 effect-size tuning unexpectedly allowed")
    if primary.get("confirmatory_claim_authorized_during_execution") is not False:
        raise RuntimeError("D3 execution prematurely authorizes claim")

    impl = r3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        d3 = importlib.import_module("r3_d3_primary_confirmatory_one_shot")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass

    dry = d3.dry_run(repo)
    # The frozen D0/D1 plan vocabulary uses fresh_mcad_sessions_planned,
    # while the D3 execution contract names the same cardinality
    # fresh_gated_sessions_planned.  Verify both envelopes explicitly.
    expected_dry = {
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
    for key, value in expected_dry.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"D3 dry-run mismatch: {key}")
    if tuple(dry["warmup_templates"]) != EXPECTED_TEMPLATES:
        raise RuntimeError("D3 dry-run warmup template set/order changed")
    if dry.get("warmup_measured") is not False:
        raise RuntimeError("D3 dry-run warmup unexpectedly measured")
    if dry.get("fallback_120_activated") is not False:
        raise RuntimeError("D3 dry-run fallback activated")
    if dry.get("measurement_executed") is not False:
        raise RuntimeError("D3 static verify executed measurement")
    if dry.get("backend_query_executed") is not False:
        raise RuntimeError("D3 static verify executed backend query")
    if dry.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("D3 static verify prematurely authorized claim")

    print("d2_parent_head=" + D2_HEAD)
    print("warmup_templates=7")
    print("warmup_measured=false")
    print("primary_semantic_sessions=300")
    print("primary_arm_runs=900")
    print("primary_candidate_actions=21600")
    print("primary_gate_evaluations_planned=14400")
    print("primary_full_backend_executions_planned=14580")
    print("primary_fresh_gated_sessions_planned=600")
    print("fallback_120_activated=false")
    print("no_interim_effect_looks=true")
    print("measurement_executed=false")
    print("backend_query_executed=false")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D3_EXECUTION_KIT_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
