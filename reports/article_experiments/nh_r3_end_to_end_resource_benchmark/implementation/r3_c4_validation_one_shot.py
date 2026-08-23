#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
C3_HEAD = "266bc62593652547b3184969e4003fe2178843f8"
CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_C_VALIDATION_40"
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


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def import_c2(repo: Path):
    impl = repo / R3_REL / "implementation"
    import sys
    sys.path.insert(0, str(impl))
    try:
        c2 = importlib.import_module("r3_c2_validation_executor")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass
    return c2


def validate_authorities(repo: Path) -> tuple[Any, Any, Any, dict[str, Any]]:
    c2 = import_c2(repo)
    c2.validate_future_authorization(repo)
    c1, b2k, b2e, plan = c2.validate_static_authorities(repo)

    if int(plan["semantic_sessions"]) != 40:
        raise RuntimeError("R3-C plan semantic_sessions changed")
    if len(plan["arm_runs"]) != 120:
        raise RuntimeError("R3-C plan arm_runs changed")
    if len(plan["candidate_actions"]) != 2880:
        raise RuntimeError("R3-C plan candidate_actions changed")
    if int(plan["gate_evaluations_planned"]) != 1920:
        raise RuntimeError("R3-C plan gate_evaluations changed")
    return c2, b2k, b2e, plan


def template_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    first: dict[str, dict[str, Any]] = {}
    for action in plan["candidate_actions"]:
        tid = str(action["template_id"])
        first.setdefault(tid, action)
    tids = tuple(sorted(first))
    if tids != EXPECTED_TEMPLATES:
        raise RuntimeError(f"warmup template set changed: {tids}")
    return [first[tid] for tid in tids]


def dry_run(repo: Path) -> dict[str, Any]:
    c2, b2k, _b2e, plan = validate_authorities(repo)
    auth = c2.validate_future_authorization(repo)
    warm = template_actions(plan)

    return {
        "contract_version": "mcad.nh_r3.c4.validation_one_shot_dry_run.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "analysis_class": "VALIDATION_CALIBRATION_NONCONFIRMATORY",
        "warmup_templates": [str(a["template_id"]) for a in warm],
        "warmup_measured": False,
        "sqlserver_restart_after_warmup": False,
        "semantic_sessions": int(plan["semantic_sessions"]),
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": int(plan["gate_evaluations_planned"]),
        "gated_arm_runs": int(plan["gated_arm_runs"]),
        "ungated_arm_runs": int(plan["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(plan["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(plan["fresh_mcad_sessions_planned"]),
        "isolated_project": b2k.PROJECT,
        "validation_measured_execution_authorized": bool(
            auth["authorization"]["validation_measured_execution_authorized"]
        ),
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "measurement_executed": False,
        "backend_query_executed": False,
    }


def run_warmup(
    repo: Path,
    attempt_root: Path,
    proxy_base: str,
) -> dict[str, Any]:
    c2, _b2k, b2e, plan = validate_authorities(repo)
    rows: list[dict[str, Any]] = []

    for ordinal, action in enumerate(template_actions(plan), start=1):
        query_id = str(action["query_id"])
        template_id = str(action["template_id"])
        mdx = b2e.read_template(repo, action)
        payload = {
            "mdx": mdx,
            "query_type": "mdx",
            "query_id": query_id,
            "objective_id": b2e.OBJECTIVE_ID,
            "session_id": None,
            "dw_id": b2e.DW_ID,
            "allow_fallback": False,
        }
        data = b2e.post_json(
            f"{proxy_base.rstrip('/')}/bi/r3/measurement/full-execute",
            payload,
            timeout_s=180.0,
        )
        b2e.validate_full_response(data, query_id)
        row = {
            "ordinal": ordinal,
            "template_id": template_id,
            "query_id": query_id,
            "physical_execution": bool(data.get("physical_execution")),
            "backend_request_count": int(data.get("backend_request_count") or 0),
            "elapsed_ms": data.get("elapsed_ms"),
            "response_bytes": int(data.get("response_bytes") or 0),
            "result_digest": data.get("result_digest"),
            "row_count": data.get("row_count"),
            "measured": False,
        }
        if row["backend_request_count"] != 1 or row["physical_execution"] is not True:
            raise RuntimeError(f"warmup physical execution contract failed: {template_id}")
        rows.append(row)
        print(f"warmup_complete ordinal={ordinal} template_id={template_id}")

    receipt = {
        "contract_version": "mcad.nh_r3.c4.warmup_receipt.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "backend": "adventureworks_sql_direct",
        "measured": False,
        "repetitions": 1,
        "sqlserver_restart_after_warmup": False,
        "templates": rows,
    }
    atomic_json(attempt_root / "warmup_receipt.json", receipt)
    return receipt


def verify_output(repo: Path, attempt_root: Path) -> dict[str, Any]:
    _c2, _b2k, _b2e, plan = validate_authorities(repo)
    warmup_path = attempt_root / "warmup_receipt.json"
    results_dir = attempt_root / "results"
    summary_path = results_dir / "validation_summary.json"
    arm_dir = results_dir / "arm_runs"

    if not warmup_path.is_file():
        raise RuntimeError("warmup receipt missing")
    if not summary_path.is_file():
        raise RuntimeError("validation summary missing")
    if not arm_dir.is_dir():
        raise RuntimeError("arm receipt directory missing")

    warm = json.loads(warmup_path.read_text(encoding="utf-8"))
    warm_rows = warm.get("templates")
    if not isinstance(warm_rows, list) or len(warm_rows) != 7:
        raise RuntimeError("warmup receipt count != 7")
    if tuple(str(r["template_id"]) for r in warm_rows) != EXPECTED_TEMPLATES:
        raise RuntimeError("warmup order/set mismatch")
    if any(r.get("physical_execution") is not True for r in warm_rows):
        raise RuntimeError("non-physical warmup row")
    if any(int(r.get("backend_request_count") or 0) != 1 for r in warm_rows):
        raise RuntimeError("warmup backend request count mismatch")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("analysis_class") != "VALIDATION_CALIBRATION_NONCONFIRMATORY":
        raise RuntimeError("validation analysis class changed")
    if summary.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("validation incorrectly authorizes confirmatory claims")
    if summary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("validation indicates effect-size tuning")
    if int(summary.get("semantic_sessions") or 0) != 40:
        raise RuntimeError("validation summary semantic session count != 40")
    if int(summary.get("arm_runs_completed") or 0) != 120:
        raise RuntimeError("validation summary arm count != 120")
    if int(summary.get("candidate_actions_completed") or 0) != 2880:
        raise RuntimeError("validation summary candidate count != 2880")

    receipts = sorted(arm_dir.glob("*.json"))
    if len(receipts) != 120:
        raise RuntimeError(f"expected 120 arm receipts, got {len(receipts)}")

    expected_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for arm in plan["arm_runs"]:
        expected_by_key[(str(arm["session_id"]), str(arm["arm"]))] = arm

    seen_keys: set[tuple[str, str]] = set()
    sessions: dict[str, set[str]] = defaultdict(set)
    candidate_total = 0
    gate_total = 0
    full_total = 0
    negative_rows: list[str] = []
    ordinals: list[int] = []

    for path in receipts:
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = str(data["session_id"])
        arm = str(data["arm"])
        key = (sid, arm)
        if key in seen_keys:
            raise RuntimeError(f"duplicate arm receipt: {key}")
        seen_keys.add(key)
        sessions[sid].add(arm)
        ordinals.append(int(data["ordinal"]))

        expected = expected_by_key.get(key)
        if expected is None:
            raise RuntimeError(f"unexpected arm receipt: {key}")

        records = data.get("candidate_records")
        if not isinstance(records, list) or len(records) != 24:
            raise RuntimeError(f"{key}: candidate_records count != 24")
        if [int(r["candidate_index"]) for r in records] != list(range(1, 25)):
            raise RuntimeError(f"{key}: candidate indices not 1..24")
        candidate_total += len(records)

        expected_gate = sum(1 for a in plan["candidate_actions"]
                            if str(a["session_id"]) == sid and str(a["arm"]) == arm and bool(a["run_gate"]))
        expected_full = sum(1 for a in plan["candidate_actions"]
                            if str(a["session_id"]) == sid and str(a["arm"]) == arm and bool(a["run_full_backend"]))

        if int(data["gate_evaluation_count"]) != expected_gate:
            raise RuntimeError(f"{key}: gate count mismatch")
        if int(data["full_backend_execution_count"]) != expected_full:
            raise RuntimeError(f"{key}: full backend execution count mismatch")
        gate_total += int(data["gate_evaluation_count"])
        full_total += int(data["full_backend_execution_count"])

        if int(data["completion_candidate"]) != int(expected["completion_candidate"]):
            raise RuntimeError(f"{key}: completion boundary mismatch")
        if data.get("live_gate_action_authoritative") is not False:
            raise RuntimeError(f"{key}: live gate became authoritative")
        if data.get("confirmatory_claim_authorized") is not False:
            raise RuntimeError(f"{key}: confirmatory claim flag violated")

        cpu = int(data["sqlserver_cpu_usage_usec_delta"])
        rb = int(data["sqlserver_io_rbytes_delta"])
        wb = int(data["sqlserver_io_wbytes_delta"])
        if cpu < 0 or rb < 0 or wb < 0:
            negative_rows.append(path.name)

    if ordinals != list(range(1, 121)):
        raise RuntimeError("arm receipt ordinals are not exactly 1..120")
    if len(sessions) != 40:
        raise RuntimeError(f"expected 40 semantic sessions, got {len(sessions)}")
    required_arms = {"UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING"}
    if any(arms != required_arms for arms in sessions.values()):
        raise RuntimeError("one or more semantic sessions do not contain exactly all three arms")
    if candidate_total != 2880:
        raise RuntimeError(f"candidate receipt total != 2880: {candidate_total}")
    if gate_total != 1920:
        raise RuntimeError(f"gate total != 1920: {gate_total}")
    if negative_rows:
        raise RuntimeError(
            "negative cgroup delta invalidates arm run(s); never clamp: " + ",".join(negative_rows)
        )

    out = {
        "contract_version": "mcad.nh_r3.c4.validation_integrity.v1",
        "analysis_class": "VALIDATION_CALIBRATION_NONCONFIRMATORY",
        "warmup_templates_completed": 7,
        "semantic_sessions": 40,
        "arm_receipts": 120,
        "candidate_records": candidate_total,
        "gate_evaluations": gate_total,
        "full_backend_executions": full_total,
        "negative_cgroup_delta_arm_runs": 0,
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
        "integrity_status": "PASS",
    }
    atomic_json(attempt_root / "integrity_summary.json", out)
    return out


def run(
    repo: Path,
    runtime_root: Path,
    attempt_root: Path,
    proxy_base: str,
    mcad_base: str,
    confirm: str,
) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit R3-C validation confirmation token required")

    expected_runtime_root = Path(
        "/workspaces/MCAD_R3_ISOLATED_RUNTIME_d2f5e40171bd2daccec18e7d450644e0b510b5d8"
    ).resolve()
    if runtime_root.resolve() != expected_runtime_root:
        raise RuntimeError(f"unexpected isolated runtime root: {runtime_root}")

    # Prevent any backend warm-up if the output location would violate the
    # frozen external-output boundary.
    c2 = import_c2(repo)
    c2.ensure_output_outside_repo(repo, attempt_root)

    if attempt_root.exists():
        raise RuntimeError(f"attempt root already exists: {attempt_root}")
    attempt_root.mkdir(parents=True)

    manifest = {
        "contract_version": "mcad.nh_r3.c4.attempt_manifest.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "parent_c3_head": C3_HEAD,
        "analysis_class": "VALIDATION_CALIBRATION_NONCONFIRMATORY",
        "attempt_root": str(attempt_root),
        "runtime_root": str(runtime_root),
        "proxy_base": proxy_base,
        "mcad_base": mcad_base,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
        "status": "STARTED",
    }
    atomic_json(attempt_root / "attempt_manifest.json", manifest)

    run_warmup(repo, attempt_root, proxy_base)

    c2 = import_c2(repo)
    summary = c2.run_validation(
        repo=repo,
        runtime_root=runtime_root,
        output_dir=attempt_root / "results",
        proxy_base=proxy_base,
        mcad_base=mcad_base,
        confirm=confirm,
    )

    integrity = verify_output(repo, attempt_root)
    manifest["status"] = "COMPLETE_INTEGRITY_PASS"
    manifest["arm_runs_completed"] = int(summary["arm_runs_completed"])
    manifest["candidate_actions_completed"] = int(summary["candidate_actions_completed"])
    manifest["integrity_status"] = integrity["integrity_status"]
    atomic_json(attempt_root / "attempt_manifest.json", manifest)

    handoff = {
        "contract_version": "mcad.nh_r3.c4.handoff.v1",
        "attempt_root": str(attempt_root),
        "analysis_class": "VALIDATION_CALIBRATION_NONCONFIRMATORY",
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "integrity_status": "PASS",
        "archive_created_by_driver": False,
        "next": "R3-C5_VALIDATION_ANALYSIS_AND_FREEZE",
    }
    atomic_json(attempt_root / "handoff.json", handoff)

    print(f"validation_attempt_root={attempt_root}")
    print("warmup_templates_completed=7")
    print("r3c_semantic_sessions=40")
    print("r3c_arm_runs_completed=120")
    print("r3c_candidate_actions_completed=2880")
    print("r3c_gate_evaluations=1920")
    print("negative_cgroup_delta_arm_runs=0")
    print("analysis_class=VALIDATION_CALIBRATION_NONCONFIRMATORY")
    print("confirmatory_claim_authorized=false")
    print("effect_size_tuning_performed=false")
    print("R3_C4_VALIDATION_ONE_SHOT=PASS")
    return handoff


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dry-run")

    p_verify = sub.add_parser("verify-output")
    p_verify.add_argument("--attempt-root", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--runtime-root", required=True)
    p_run.add_argument("--attempt-root", required=True)
    p_run.add_argument("--proxy-base", default="http://127.0.0.1:19000")
    p_run.add_argument("--mcad-base", default="http://127.0.0.1:18000")
    p_run.add_argument("--confirm", required=True, choices=[CONFIRM_TOKEN])

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "dry-run":
        print(json.dumps(dry_run(repo), indent=2, sort_keys=True))
        print("measurement_executed=false")
        print("backend_query_executed=false")
        print("R3_C4_EXECUTION_KIT_DRY_RUN=PASS")
        return

    if args.cmd == "verify-output":
        result = verify_output(repo, Path(args.attempt_root).resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        print("R3_C4_OUTPUT_INTEGRITY_VERIFY=PASS")
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
