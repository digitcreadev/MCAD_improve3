#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT = "fda8fef788741f44afca0ae1816849ab4abbc212"

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
PROTOCOL = R3 / "config/r3_b2g_instrumentation_recovery_protocol.json"
BOOTSTRAP = R3 / "implementation/r3_objective_bootstrap.py"
EXECUTOR = R3 / "implementation/r3_dev_pilot_executor.py"
B1 = R3 / "config/r3_b1_measurement_preregistration.json"
AUTH = R3 / "config/r3_b2c_dev_pilot_authorization.json"
B2E = R3 / "config/r3_b2e_dev_pilot_executor_contract.json"

APP = Path("bi-stack/mcad-api/app.py")
OBJECTIVE = Path("bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json")
PRIMARY = Path("backend/objectives.yaml")
FALLBACK = Path("backend/config/objectives.yaml")

OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"

EXPECTED = {
    "executor_sha256": "9a0b0f7f81a6e6cd59ac72a12e5674f0b55c1ac49893a0200a3b65eb43320e40",
    "b1_sha256": "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f",
    "auth_sha256": "78a7c9a92b9b9f1d7dd10821449205bc4bbd7b996c4808aec747df44027180a4",
    "b2e_sha256": "b2f1aa0c384bf86a24c6148a5f450fcbdce2521510800dbf3733a1a597ce65ba",
    "objective_blob": "82ad0cbe911a668e0638aee8ceb6453c784dbc37",
    "abort_archive_sha256": "4bba2a3c6095d1a7e703b5652ae6cd0da2886ea1163e40707c022bced5db41b4",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--abort-archive")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()

    if git(repo, "branch", "--show-current") != BRANCH:
        raise SystemExit("wrong branch")
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT, "HEAD"], check=True)

    def p(rel: Path) -> Path:
        return repo / rel

    assert sha256(p(EXECUTOR)) == EXPECTED["executor_sha256"]
    assert sha256(p(B1)) == EXPECTED["b1_sha256"]
    assert sha256(p(AUTH)) == EXPECTED["auth_sha256"]
    assert sha256(p(B2E)) == EXPECTED["b2e_sha256"]
    assert git(repo, "hash-object", str(OBJECTIVE)) == EXPECTED["objective_blob"]

    protocol = json.loads(p(PROTOCOL).read_text(encoding="utf-8"))
    assert protocol["contract_version"] == "mcad.nh_r3.b2g.instrumentation_recovery.v1"
    assert protocol["parent_head"] == PARENT
    assert protocol["incident"]["completed_arm_runs"] == 1
    assert protocol["incident"]["completed_gated_arm_runs"] == 0
    assert protocol["incident"]["pilot_summary_present"] is False
    assert protocol["incident"]["partial_receipt_sha256"] == "2c2662f0f797863062b713d5354aed99c72462f554cf9187289fc6e2ddbd5042"
    assert protocol["incident"]["abort_evidence_archive_sha256"] == EXPECTED["abort_archive_sha256"]
    assert protocol["repair"]["historical_files_modified"] is False
    assert protocol["repair"]["objective_semantics_modified"] is False
    assert protocol["repair"]["executor_modified"] is False
    assert protocol["scientific_disposition"]["aborted_attempt_excluded_from_all_effect_estimation"] is True
    assert protocol["scientific_disposition"]["effect_based_rerun"] is False
    assert protocol["scientific_disposition"]["confirmatory_claim_authorized"] is False
    assert protocol["fresh_attempt_policy"]["full_pilot_restart_from_ordinal_1"] is True
    assert protocol["fresh_attempt_policy"]["arm_runs"] == 60
    assert protocol["fresh_attempt_policy"]["candidate_actions"] == 1440
    assert protocol["fresh_attempt_policy"]["restart_sqlserver_before_attempt_local_warmup"] is True
    assert protocol["fresh_attempt_policy"]["warmup_repetitions_per_template"] == 1
    assert protocol["fresh_attempt_policy"]["verify_persistence_after_mcad_api_restart"] is True

    objective = json.loads(p(OBJECTIVE).read_text(encoding="utf-8"))
    assert objective["id"] == OBJECTIVE_ID
    assert OBJECTIVE_ID not in p(PRIMARY).read_text(encoding="utf-8")
    assert OBJECTIVE_ID not in p(FALLBACK).read_text(encoding="utf-8")

    app = p(APP).read_text(encoding="utf-8")
    required_fragments = [
        '_IMPORTED_OBJECTIVES_FILE = DATA_DIR / "imported_objectives.json"',
        '@app.post("/objectives/import")',
        "def _register_imported_objectives()",
        "def _objective_lookup(objective_id",
        '@app.post("/sessions/create")',
    ]
    for fragment in required_fragments:
        if fragment not in app:
            raise SystemExit(f"mcad-api import persistence fragment missing: {fragment}")

    bootstrap = p(BOOTSTRAP).read_text(encoding="utf-8")
    required_bootstrap = [
        'OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"',
        'f"{base}/objectives/import"',
        'f"{base}/objectives/{OBJECTIVE_ID}"',
        'f"{base}/sessions/create"',
        'backend_query_executed=false',
        'measurement_executed=false',
    ]
    for fragment in required_bootstrap:
        if fragment not in bootstrap:
            raise SystemExit(f"bootstrap fragment missing: {fragment}")

    compile(p(BOOTSTRAP).read_text(encoding="utf-8"), str(p(BOOTSTRAP)), "exec")
    compile(Path(__file__).read_text(encoding="utf-8"), str(Path(__file__).resolve()), "exec")

    if args.abort_archive:
        archive = Path(args.abort_archive).resolve()
        assert archive.is_file()
        assert sha256(archive) == EXPECTED["abort_archive_sha256"]

    print("parent_ancestry=PASS")
    print("frozen_authority_hashes=PASS")
    print("abort_incident_contract=PASS")
    print("objective_root_cause_contract=PASS")
    print("mcad_api_import_persistence_static_contract=PASS")
    print("objective_bootstrap_syntax=PASS")
    print("aborted_attempt_excluded_from_effect_estimation=true")
    print("effect_based_rerun=false")
    print("historical_objective_files_modified=false")
    print("executor_modified=false")
    print("confirmatory_claim_authorized=false")
    print("R3_B2G_RECOVERY_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
