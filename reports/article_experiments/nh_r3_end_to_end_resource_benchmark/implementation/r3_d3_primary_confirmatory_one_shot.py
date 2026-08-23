#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
D2_HEAD = "e399654ddcd0bb41febd07e8f12d384751407c5e"
CONFIRM_TOKEN = "EXECUTE_AUTHORIZED_NH_R3_D_CONFIRMATORY_PRIMARY_300"
EXPECTED_RUNTIME_ROOT = Path(
    "/workspaces/MCAD_R3_ISOLATED_RUNTIME_d2f5e40171bd2daccec18e7d450644e0b510b5d8"
)

EXPECTED = {
    "d2_auth_blob": "3dc900948f1022c6f991964f50570bbb1ad9bcff",
    "d2_auth_sha": "d3725ff2fea15c1501cfba26265922a19b2c41354b57c9bee81dce1e22415d2c",
    "d1_executor_blob": "ee0fb893a35086d01a69ee4eb8d70166ba2bb7b0",
    "d1_executor_sha": "b4e024ab12940a9824f39188e8b79e0974f166d7b98ac04ab7afe70082a012ae",
    "primary_schedule_blob": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
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


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def import_d1(repo: Path):
    impl = repo / R3_REL / "implementation"
    sys.path.insert(0, str(impl))
    try:
        return importlib.import_module("r3_d1_confirmatory_executor")
    finally:
        try:
            sys.path.remove(str(impl))
        except ValueError:
            pass


def validate_authorities(repo: Path):
    r3 = repo / R3_REL
    checks = (
        (
            r3 / "config/r3_d2_confirmatory_measurement_authorization.json",
            EXPECTED["d2_auth_blob"],
            EXPECTED["d2_auth_sha"],
            "D2 authorization",
        ),
        (
            r3 / "implementation/r3_d1_confirmatory_executor.py",
            EXPECTED["d1_executor_blob"],
            EXPECTED["d1_executor_sha"],
            "D1 executor",
        ),
        (
            r3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv",
            EXPECTED["primary_schedule_blob"],
            None,
            "D0 primary schedule",
        ),
    )
    for path, blob, sha, label in checks:
        actual_blob = git_blob_sha1(path)
        if actual_blob != blob:
            raise RuntimeError(f"{label} blob changed: {actual_blob}")
        if sha is not None and sha256(path) != sha:
            raise RuntimeError(f"{label} sha256 changed")

    d1 = import_d1(repo)
    auth = d1.validate_future_authorization(repo)
    if auth.get("d1_head") != "f567b869a7cea486a780b35bf4acc873245fda88":
        raise RuntimeError("D2 authorization D1 binding changed")
    _d0, _b2k, b2e, plan = d1.validate_static_authorities(repo)

    expected = {
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
    actual = {
        "semantic_sessions": int(plan["semantic_sessions"]),
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": int(plan["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(plan["full_backend_executions_planned"]),
        "gated_arm_runs": int(plan["gated_arm_runs"]),
        "ungated_arm_runs": int(plan["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(plan["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(plan["fresh_mcad_sessions_planned"]),
    }
    if actual != expected:
        raise RuntimeError(f"confirmatory plan changed: {actual}")
    return d1, b2e, plan


def ensure_output_outside_repo(repo: Path, output: Path) -> None:
    repo = repo.resolve()
    output = output.resolve()
    try:
        output.relative_to(repo)
    except ValueError:
        return
    raise RuntimeError("D3 output must be outside repository")


def template_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    first: dict[str, dict[str, Any]] = {}
    for action in plan["candidate_actions"]:
        tid = str(action["template_id"])
        first.setdefault(tid, action)
    tids = tuple(sorted(first))
    if tids != EXPECTED_TEMPLATES:
        raise RuntimeError(f"confirmatory warmup template set changed: {tids}")
    return [first[tid] for tid in tids]


def dry_run(repo: Path) -> dict[str, Any]:
    _d1, _b2e, plan = validate_authorities(repo)
    return {
        "contract_version": "mcad.nh_r3.d3.primary_confirmatory_dry_run.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "warmup_templates": [str(a["template_id"]) for a in template_actions(plan)],
        "warmup_measured": False,
        "sqlserver_restart_after_warmup": False,
        "semantic_sessions": int(plan["semantic_sessions"]),
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gate_evaluations_planned": int(plan["gate_evaluations_planned"]),
        "full_backend_executions_planned": int(plan["full_backend_executions_planned"]),
        "gated_arm_runs": int(plan["gated_arm_runs"]),
        "ungated_arm_runs": int(plan["ungated_arm_runs"]),
        "mcad_api_restarts_planned": int(plan["mcad_api_restarts_planned"]),
        "fresh_mcad_sessions_planned": int(plan["fresh_mcad_sessions_planned"]),
        "fallback_120_activated": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
    }


def run_warmup(repo: Path, attempt_root: Path, proxy_base: str) -> dict[str, Any]:
    _d1, b2e, plan = validate_authorities(repo)
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
        if row["physical_execution"] is not True or row["backend_request_count"] != 1:
            raise RuntimeError(f"warmup physical execution contract failed: {template_id}")
        rows.append(row)
        print(f"warmup_complete ordinal={ordinal} template_id={template_id}")

    receipt = {
        "contract_version": "mcad.nh_r3.d3.warmup_receipt.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "backend": "adventureworks_sql_direct",
        "measured": False,
        "repetitions": 1,
        "sqlserver_restart_after_warmup": False,
        "templates": rows,
    }
    atomic_json(attempt_root / "warmup_receipt.json", receipt)
    return receipt


def verify_output(repo: Path, attempt_root: Path) -> dict[str, Any]:
    _d1, _b2e, plan = validate_authorities(repo)
    warmup_path = attempt_root / "warmup_receipt.json"
    results_dir = attempt_root / "results"
    summary_path = results_dir / "confirmatory_primary_summary.json"
    arm_dir = results_dir / "arm_runs"

    if not warmup_path.is_file():
        raise RuntimeError("warmup receipt missing")
    if not summary_path.is_file():
        raise RuntimeError("confirmatory primary summary missing")
    if not arm_dir.is_dir():
        raise RuntimeError("confirmatory arm receipt directory missing")

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
    if summary.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("confirmatory analysis class changed")
    if summary.get("selection_role") != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("confirmatory selection role changed")
    if summary.get("primary_300_measured_execution_authorized") is not True:
        raise RuntimeError("primary 300 execution was not authorized in summary")
    if summary.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback activated in primary summary")
    if summary.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("D3 execution prematurely authorizes confirmatory claim")
    if summary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("D3 summary indicates effect-size tuning")
    if int(summary.get("semantic_sessions") or 0) != 300:
        raise RuntimeError("summary semantic_sessions != 300")
    if int(summary.get("arm_runs_completed") or 0) != 900:
        raise RuntimeError("summary arm_runs_completed != 900")
    if int(summary.get("candidate_actions_completed") or 0) != 21600:
        raise RuntimeError("summary candidate_actions_completed != 21600")

    receipts = sorted(arm_dir.glob("*.json"))
    if len(receipts) != 900:
        raise RuntimeError(f"expected 900 arm receipts, got {len(receipts)}")

    expected_by_key = {
        (str(r["session_id"]), str(r["arm"])): r for r in plan["arm_runs"]
    }
    plan_actions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for a in plan["candidate_actions"]:
        plan_actions[(str(a["session_id"]), str(a["arm"]))].append(a)

    seen: set[tuple[str, str]] = set()
    sessions: dict[str, set[str]] = defaultdict(set)
    ordinals: list[int] = []
    candidate_total = 0
    gate_total = 0
    full_total = 0
    fresh_gated = 0

    for path in receipts:
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = str(data["session_id"])
        arm = str(data["arm"])
        key = (sid, arm)
        if key in seen:
            raise RuntimeError(f"duplicate arm receipt: {key}")
        seen.add(key)
        sessions[sid].add(arm)
        ordinals.append(int(data["ordinal"]))

        expected = expected_by_key.get(key)
        if expected is None:
            raise RuntimeError(f"unexpected arm receipt: {key}")
        if int(data["block_index"]) != int(expected["block_index"]):
            raise RuntimeError(f"{key}: block index mismatch")
        if int(data["arm_position"]) != int(expected["arm_position"]):
            raise RuntimeError(f"{key}: arm position mismatch")
        if int(data["completion_candidate"]) != int(expected["completion_candidate"]):
            raise RuntimeError(f"{key}: completion boundary mismatch")

        records = data.get("candidate_records")
        if not isinstance(records, list) or len(records) != 24:
            raise RuntimeError(f"{key}: candidate_records count != 24")
        if [int(r["candidate_index"]) for r in records] != list(range(1, 25)):
            raise RuntimeError(f"{key}: candidate indices not 1..24")
        candidate_total += len(records)

        expected_actions = plan_actions[key]
        expected_gate = sum(bool(a["run_gate"]) for a in expected_actions)
        expected_full = sum(bool(a["run_full_backend"]) for a in expected_actions)
        if int(data["gate_evaluation_count"]) != expected_gate:
            raise RuntimeError(f"{key}: gate count mismatch")
        if int(data["full_backend_execution_count"]) != expected_full:
            raise RuntimeError(f"{key}: full backend execution count mismatch")
        gate_total += int(data["gate_evaluation_count"])
        full_total += int(data["full_backend_execution_count"])

        if arm != "UNGATED_EXECUTE_ADMISSIBLE":
            if not data.get("fresh_mcad_session_id"):
                raise RuntimeError(f"{key}: gated arm missing fresh session")
            fresh_gated += 1
        elif data.get("fresh_mcad_session_id") is not None:
            raise RuntimeError(f"{key}: ungated arm unexpectedly has MCAD session")

        if data.get("selection_role") != "CONFIRMATORY_PRIMARY":
            raise RuntimeError(f"{key}: selection role mismatch")
        if data.get("frozen_action_authority") != "NH_R2_R3_BINDING":
            raise RuntimeError(f"{key}: frozen action authority changed")
        if data.get("live_gate_action_authoritative") is not False:
            raise RuntimeError(f"{key}: live gate became authoritative")
        if data.get("confirmatory_claim_authorized") is not False:
            raise RuntimeError(f"{key}: confirmatory claim flag violated")
        if data.get("effect_size_tuning_performed") is not False:
            raise RuntimeError(f"{key}: effect-size tuning flag violated")

        if (
            int(data["sqlserver_cpu_usage_usec_delta"]) < 0
            or int(data["sqlserver_io_rbytes_delta"]) < 0
            or int(data["sqlserver_io_wbytes_delta"]) < 0
        ):
            raise RuntimeError(f"{key}: negative cgroup delta")

    if ordinals != list(range(1, 901)):
        raise RuntimeError("arm receipt ordinals are not exactly 1..900")
    if len(sessions) != 300:
        raise RuntimeError(f"expected 300 semantic sessions, got {len(sessions)}")
    required_arms = {
        "UNGATED_EXECUTE_ADMISSIBLE",
        "PERMISSIVE_GATED",
        "SAFE_PRUNING",
    }
    if any(arms != required_arms for arms in sessions.values()):
        raise RuntimeError("one or more sessions do not contain exactly all three arms")
    if candidate_total != 21600:
        raise RuntimeError(f"candidate receipt total != 21600: {candidate_total}")
    if gate_total != 14400:
        raise RuntimeError(f"gate total != 14400: {gate_total}")
    if full_total != 14580:
        raise RuntimeError(f"full backend execution total != 14580: {full_total}")
    if fresh_gated != 600:
        raise RuntimeError(f"fresh gated session total != 600: {fresh_gated}")

    out = {
        "contract_version": "mcad.nh_r3.d3.primary_confirmatory_integrity.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "warmup_templates_completed": 7,
        "semantic_sessions": 300,
        "arm_receipts": 900,
        "candidate_records": candidate_total,
        "gate_evaluations": gate_total,
        "full_backend_executions": full_total,
        "fresh_gated_sessions": fresh_gated,
        "negative_cgroup_delta_arm_runs": 0,
        "fallback_120_activated": False,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
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
) -> None:
    if confirm != CONFIRM_TOKEN:
        raise RuntimeError("explicit D3 PRIMARY 300 confirmation token required")
    if runtime_root.resolve() != EXPECTED_RUNTIME_ROOT.resolve():
        raise RuntimeError(f"unexpected isolated runtime root: {runtime_root}")
    ensure_output_outside_repo(repo, attempt_root)
    if attempt_root.exists():
        raise RuntimeError(f"attempt root already exists: {attempt_root}")

    validate_authorities(repo)
    attempt_root.mkdir(parents=True)

    manifest = {
        "contract_version": "mcad.nh_r3.d3.primary_confirmatory_attempt.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "parent_d2_head": D2_HEAD,
        "attempt_root": str(attempt_root),
        "runtime_root": str(runtime_root),
        "proxy_base": proxy_base,
        "mcad_base": mcad_base,
        "semantic_sessions": 300,
        "arm_runs": 900,
        "fallback_120_activated": False,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
        "status": "STARTED",
    }
    atomic_json(attempt_root / "attempt_manifest.json", manifest)

    run_warmup(repo, attempt_root, proxy_base)

    d1 = import_d1(repo)
    summary = d1.run_confirmatory_primary(
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
        "contract_version": "mcad.nh_r3.d3.handoff.v1",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "attempt_root": str(attempt_root),
        "integrity_status": "PASS",
        "fallback_120_activated": False,
        "effect_size_tuning_performed": False,
        "confirmatory_claim_authorized": False,
        "effect_analysis_performed": False,
        "next": "R3-D4_CONFIRMATORY_INFERENCE_AND_FREEZE",
    }
    atomic_json(attempt_root / "handoff.json", handoff)

    print(f"confirmatory_attempt_root={attempt_root}")
    print("warmup_templates_completed=7")
    print("semantic_sessions_completed=300")
    print("arm_runs_completed=900")
    print("candidate_actions_completed=21600")
    print("gate_evaluations_completed=14400")
    print("full_backend_executions_completed=14580")
    print("fresh_gated_sessions_completed=600")
    print("negative_cgroup_delta_arm_runs=0")
    print("fallback_120_activated=false")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("effect_analysis_performed=false")
    print("R3_D3_PRIMARY_CONFIRMATORY_ONE_SHOT=PASS")


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
        print("R3_D3_EXECUTION_KIT_DRY_RUN=PASS")
        return

    if args.cmd == "verify-output":
        result = verify_output(repo, Path(args.attempt_root).resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        print("R3_D3_OUTPUT_INTEGRITY_VERIFY=PASS")
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
