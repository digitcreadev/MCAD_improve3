#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R3_HEAD = "41b2369a83a3073d986691bdf7293d322d8d7851"

R3_AUTH_BLOB = "904a345e1174afc2a482c459dbbba2909905329c"
R2_RECEIPT_BLOB = "09a2ed82c0ffc86c567e543aaa9010c409f3ee88"
D3_DRIVER_BLOB = "5563c6324f527a776ffb1ff29f4de0c07a8d744e"
D3_CONTRACT_BLOB = "c4e45aa2a04bdb084a2c9a9047f074c31a5cf665"
INTERRUPTION_FREEZE_BLOB = "67e256df516bd8079971c1dc645df408804cebe5"

EXTERNAL_CONFIRM = "EXECUTE_AUTHORIZED_NH_R3_D3_REPLACEMENT_PRIMARY_300"
INTERNAL_D3_CONFIRM = "EXECUTE_AUTHORIZED_NH_R3_D_CONFIRMATORY_PRIMARY_300"

PRESERVED = Path(
    "/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_INTERRUPTED_20260823T211928Z_"
    "PRESERVED_20260823T215439Z.tar.gz"
)
PRESERVED_SHA = "1c5bb0d802e1400a38c8bd57d629553f331821771d8bfbf83424caecd5d7fb37"
OLD_ATTEMPT = Path("/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_ATTEMPT_20260823T211928Z")

EXPECTED_RUNTIME_ROOT = Path(
    "/workspaces/MCAD_R3_ISOLATED_RUNTIME_d2f5e40171bd2daccec18e7d450644e0b510b5d8"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def import_d3(repo: Path):
    impl = repo / R3 / "implementation"
    sys.path.insert(0, str(impl))
    try:
        return importlib.import_module("r3_d3_primary_confirmatory_one_shot")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass


def validate_authorities(repo: Path):
    checks = (
        (repo / R3 / "config/r3_d3_r3_replacement_primary_300_execution_authorization.json",
         R3_AUTH_BLOB, "R3 replacement authorization"),
        (repo / R3 / "results/d3_r2_stable_host_runtime_rebind_receipt.json",
         R2_RECEIPT_BLOB, "R2 runtime receipt"),
        (repo / R3 / "implementation/r3_d3_primary_confirmatory_one_shot.py",
         D3_DRIVER_BLOB, "frozen D3 primary driver"),
        (repo / R3 / "config/r3_d3_primary_confirmatory_execution_contract.json",
         D3_CONTRACT_BLOB, "D3 execution contract"),
        (repo / R3 / "results/d3_interrupted_attempt_20260823T211928Z/interruption_freeze.json",
         INTERRUPTION_FREEZE_BLOB, "interruption freeze"),
    )
    for path, expected, label in checks:
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"{label} changed: {actual}")

    auth = json.loads(
        (repo / R3 / "config/r3_d3_r3_replacement_primary_300_execution_authorization.json")
        .read_text(encoding="utf-8")
    )
    execution = auth.get("replacement_execution") or {}
    if auth.get("contract_version") != "mcad.nh_r3.d3.r3.replacement_primary_300_execution_authorization.v1":
        raise RuntimeError("unexpected R3 authorization contract")
    if execution.get("replacement_primary_300_execution_authorized") is not True:
        raise RuntimeError("replacement PRIMARY 300 not authorized")
    if execution.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("replacement rerun scope changed")
    if execution.get("reuse_partial_receipts") is not False:
        raise RuntimeError("partial receipt reuse unexpectedly authorized")
    if execution.get("resume_from_arm_298") is not False:
        raise RuntimeError("partial resume unexpectedly authorized")
    if execution.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback unexpectedly activated")
    if execution.get("no_interim_effect_looks") is not True:
        raise RuntimeError("no-interim-look rule changed")
    if execution.get("confirm_token") != EXTERNAL_CONFIRM:
        raise RuntimeError("replacement confirm token changed")

    if not OLD_ATTEMPT.is_dir():
        raise RuntimeError("frozen interrupted attempt directory missing")
    receipts = list((OLD_ATTEMPT / "results/arm_runs").glob("*.json"))
    if len(receipts) != 297:
        raise RuntimeError(f"interrupted attempt receipt count changed: {len(receipts)}")
    if not PRESERVED.is_file():
        raise RuntimeError("preserved interrupted archive missing")
    if sha256(PRESERVED) != PRESERVED_SHA:
        raise RuntimeError("preserved interrupted archive SHA changed")

    d3 = import_d3(repo)
    dry = d3.dry_run(repo)
    expected = {
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fresh_mcad_sessions_planned": 600,
    }
    for key, value in expected.items():
        if int(dry[key]) != value:
            raise RuntimeError(f"frozen D3 dry-run mismatch: {key}")
    if dry.get("fallback_120_activated") is not False:
        raise RuntimeError("frozen D3 dry-run fallback changed")
    if dry.get("measurement_executed") is not False:
        raise RuntimeError("static validation executed measurement")
    if dry.get("backend_query_executed") is not False:
        raise RuntimeError("static validation executed backend query")
    return d3


def ensure_replacement_attempt_is_new(repo: Path, attempt_root: Path) -> None:
    repo = repo.resolve()
    attempt_root = attempt_root.resolve()
    try:
        attempt_root.relative_to(repo)
    except ValueError:
        pass
    else:
        raise RuntimeError("replacement attempt must be outside repository")

    if attempt_root.exists():
        raise RuntimeError(f"replacement attempt root already exists: {attempt_root}")

    existing = sorted(Path("/workspaces").glob("MCAD_R3_D3_REPLACEMENT_PRIMARY_ATTEMPT_*"))
    if existing:
        raise RuntimeError(
            "preexisting replacement attempt requires audit: " + ", ".join(str(p) for p in existing)
        )


def dry_run(repo: Path) -> dict[str, Any]:
    validate_authorities(repo)
    return {
        "contract_version": "mcad.nh_r3.d3.r4.replacement_primary_dry_run.v1",
        "parent_r3_head": R3_HEAD,
        "replacement_primary_300_execution_authorized": True,
        "rerun_scope": "FULL_PRIMARY_300_FROM_BLOCK_1",
        "semantic_sessions": 300,
        "arm_runs": 900,
        "candidate_actions": 21600,
        "gate_evaluations_planned": 14400,
        "full_backend_executions_planned": 14580,
        "fresh_gated_sessions_planned": 600,
        "warmup_templates": 7,
        "reuse_partial_receipts": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "effect_analysis_performed": False,
        "confirmatory_claim_authorized": False,
    }


def run(
    repo: Path,
    runtime_root: Path,
    attempt_root: Path,
    proxy_base: str,
    mcad_base: str,
    confirm: str,
) -> None:
    if confirm != EXTERNAL_CONFIRM:
        raise RuntimeError("explicit replacement PRIMARY 300 confirmation token required")
    if runtime_root.resolve() != EXPECTED_RUNTIME_ROOT.resolve():
        raise RuntimeError(f"unexpected runtime root: {runtime_root}")

    d3 = validate_authorities(repo)
    ensure_replacement_attempt_is_new(repo, attempt_root)

    # This lineage receipt is written only after the frozen D3 driver succeeds.
    # The frozen driver itself remains byte-identical and uses its original
    # internal confirmation token.
    d3.run(
        repo=repo,
        runtime_root=runtime_root,
        attempt_root=attempt_root,
        proxy_base=proxy_base,
        mcad_base=mcad_base,
        confirm=INTERNAL_D3_CONFIRM,
    )

    integrity = d3.verify_output(repo, attempt_root)
    if integrity.get("integrity_status") != "PASS":
        raise RuntimeError("replacement output integrity did not pass")

    lineage = {
        "contract_version": "mcad.nh_r3.d3.r4.replacement_lineage.v1",
        "station": "MCAD-NH-R3",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "replacement_authorization_head": R3_HEAD,
        "replacement_attempt_root": str(attempt_root),
        "replaces_interrupted_attempt_run_id": "20260823T211928Z",
        "interrupted_attempt_archive_sha256": PRESERVED_SHA,
        "interrupted_attempt_receipts_reused": False,
        "resume_from_arm_298": False,
        "rerun_scope": "FULL_PRIMARY_300_FROM_BLOCK_1",
        "fallback_120_activated": False,
        "semantic_sessions_completed": 300,
        "arm_runs_completed": 900,
        "candidate_actions_completed": 21600,
        "gate_evaluations_completed": 14400,
        "full_backend_executions_completed": 14580,
        "fresh_gated_sessions_completed": 600,
        "effect_analysis_performed": False,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
        "integrity_status": "PASS",
        "next": "R3-D4_CONFIRMATORY_INFERENCE_AND_FREEZE",
    }
    atomic_json(attempt_root / "replacement_lineage.json", lineage)

    handoff = {
        "contract_version": "mcad.nh_r3.d3.r4.replacement_handoff.v1",
        "replacement_attempt_root": str(attempt_root),
        "integrity_status": "PASS",
        "partial_attempt_reused": False,
        "fallback_120_activated": False,
        "effect_analysis_performed": False,
        "confirmatory_claim_authorized": False,
        "next": "R3-D4_CONFIRMATORY_INFERENCE_AND_FREEZE",
    }
    atomic_json(attempt_root / "replacement_handoff.json", handoff)

    print(f"replacement_attempt_root={attempt_root}")
    print("warmup_templates_completed=7")
    print("replacement_semantic_sessions_completed=300")
    print("replacement_arm_runs_completed=900")
    print("replacement_candidate_actions_completed=21600")
    print("replacement_gate_evaluations_completed=14400")
    print("replacement_full_backend_executions_completed=14580")
    print("replacement_fresh_gated_sessions_completed=600")
    print("partial_attempt_reused=false")
    print("resume_from_arm_298=false")
    print("fallback_120_activated=false")
    print("effect_analysis_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_D3_R4_REPLACEMENT_PRIMARY_ONE_SHOT=PASS")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dry-run")

    p = sub.add_parser("run")
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--attempt-root", required=True)
    p.add_argument("--proxy-base", default="http://127.0.0.1:19000")
    p.add_argument("--mcad-base", default="http://127.0.0.1:18000")
    p.add_argument("--confirm", required=True, choices=[EXTERNAL_CONFIRM])

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "dry-run":
        print(json.dumps(dry_run(repo), indent=2, sort_keys=True))
        print("R3_D3_R4_REPLACEMENT_DRY_RUN=PASS_NO_MEASUREMENT")
        return

    if args.cmd == "run":
        run(
            repo=repo,
            runtime_root=Path(args.runtime_root).resolve(),
            attempt_root=Path(args.attempt_root).resolve(),
            proxy_base=args.proxy_base,
            mcad_base=args.mcad_base,
            confirm=args.confirm,
        )
        return


if __name__ == "__main__":
    main()
