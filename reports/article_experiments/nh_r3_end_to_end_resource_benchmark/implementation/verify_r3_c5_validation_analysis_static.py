#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
RESULT_REL = R3_REL / "results/validation_v1"
C4_HEAD = "24335a3e9d98b53c7f63dff2b418d15a24dd2f2e"
EXPECTED_ARCHIVE_SHA = "116fc16926d7953cba90d89cee380ae494298b46327ebaf53a1152ec67711908"
DEV_BLOB = "6630fed75e43256c619927c911dcc03c6bfed0a6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", C4_HEAD, "HEAD"],
        check=True,
    )

    dev_path = repo / R3_REL / "results/dev_pilot_v3/dev_pilot_analysis.json"
    blob = subprocess.check_output(
        ["git", "-C", str(repo), "hash-object", str(dev_path)],
        text=True,
    ).strip()
    if blob != DEV_BLOB:
        raise RuntimeError(f"frozen DEV analysis blob changed: {blob}")

    result_dir = repo / RESULT_REL
    manifest_path = result_dir / "SHA256SUMS.txt"
    if not manifest_path.is_file():
        raise RuntimeError("validation result SHA256SUMS missing")

    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, name = raw.split("  ", 1)
        path = result_dir / name
        if sha256(path) != expected:
            raise RuntimeError(f"validation result hash mismatch: {name}")

    analysis = json.loads(
        (result_dir / "validation_analysis.json").read_text(encoding="utf-8")
    )
    if analysis.get("contract_version") != "mcad.nh_r3.c5.validation_analysis.v1":
        raise RuntimeError("unexpected validation analysis contract")
    if analysis.get("analysis_class") != "VALIDATION_CALIBRATION_NONCONFIRMATORY":
        raise RuntimeError("validation analysis class changed")
    src = analysis.get("source") or {}
    if src.get("archive_sha256") != EXPECTED_ARCHIVE_SHA:
        raise RuntimeError("source archive SHA changed")
    if src.get("c4_execution_kit_head") != C4_HEAD:
        raise RuntimeError("C4 source head changed")
    if src.get("frozen_dev_analysis_git_blob") != DEV_BLOB:
        raise RuntimeError("DEV source blob changed")
    integrity = analysis.get("integrity") or {}
    expected_ints = {
        "semantic_sessions": 40,
        "arm_receipts": 120,
        "candidate_records": 2880,
        "gate_evaluations": 1920,
        "full_backend_executions": 1945,
        "fresh_gated_sessions": 80,
        "negative_cgroup_delta_arm_runs": 0,
        "warmup_templates_completed": 7,
    }
    for key, val in expected_ints.items():
        if int(integrity.get(key, -1)) != val:
            raise RuntimeError(f"validation integrity mismatch: {key}")
    if integrity.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("effect-size tuning flag violated")
    if integrity.get("scientific_redesign_performed") is not False:
        raise RuntimeError("scientific redesign flag violated")
    if integrity.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("confirmatory boundary violated")

    readiness = analysis.get("readiness") or {}
    if readiness.get("status") != "PASS_READY_FOR_R3D_STATIC_ACTIVATION":
        raise RuntimeError("unexpected readiness status")
    if readiness.get("measurement_mechanics_change_required") is not False:
        raise RuntimeError("unexpected measurement-mechanics change")
    if readiness.get("effect_based_rerun_required") is not False:
        raise RuntimeError("unexpected effect-based rerun")
    if readiness.get("r3c_rerun_authorized") is not False:
        raise RuntimeError("R3-C rerun unexpectedly authorized")
    if readiness.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("R3-C analysis promoted a confirmatory claim")
    if readiness.get("next") != "R3-D0_CONFIRMATORY_SQL_DIRECT_STATIC_ACTIVATION_NO_MEASUREMENT":
        raise RuntimeError("unexpected next stage")

    print("source_archive_sha256=" + EXPECTED_ARCHIVE_SHA)
    print("frozen_dev_analysis_git_blob=" + DEV_BLOB)
    print("semantic_sessions=40")
    print("arm_receipts=120")
    print("candidate_records=2880")
    print("gate_evaluations=1920")
    print("full_backend_executions=1945")
    print("negative_cgroup_delta_arm_runs=0")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_C5_VALIDATION_ANALYSIS_STATIC_VERIFY=PASS_READY_FOR_R3D_STATIC_ACTIVATION")


if __name__ == "__main__":
    main()
