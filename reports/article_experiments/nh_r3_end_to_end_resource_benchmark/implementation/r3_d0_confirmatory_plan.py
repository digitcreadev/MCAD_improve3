#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_HEAD = "9ddfbbdbb62bffc9cf9e7201a804814a09931a70"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R2_REL = Path("reports/article_experiments/nh_r2_objective_preserving_pruning")
ARMS = ("UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING")

EXPECTED_BINDING_DIGEST = "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
EXPECTED_A1_FREEZE_SHA256 = "e5d8e6857a22962623aa483eeb92f60cb66aac1e8e98ea3f6a7e060558a42f16"
EXPECTED_A2_FREEZE_SHA256 = "51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a"
EXPECTED_B1_PREREG_SHA256 = "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f"

PRIMARY_COHORT_BLOB = "8f937f2d8f20984dfa753a9d31271dc9779191d0"
FALLBACK_COHORT_BLOB = "72f2ec89dd0dcc6826745019b3c11b3361e36732"
SESSION_SUMMARY_BLOB = "00f5c92d4f06ce1092f49546088bc3461e3e752e"
FULL_BINDING_BLOB = "ce3930949b3991cc1af346b01f559f0a9a2798a5"
C5_ANALYSIS_BLOB = "906f1815f3514f87d19015becd8e6e1025576017"
C5_ANALYSIS_SHA256 = "810c685802ed482a0fe62498c9688c1b6c8fdfb09d93ae4f34505e289da56b4b"

PRIMARY_SEED_MATERIAL = "MCAD-NH-R3|R3-D0|primary-arm-order|a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff|51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a|8f937f2d8f20984dfa753a9d31271dc9779191d0"
FALLBACK_SEED_MATERIAL = "MCAD-NH-R3|R3-D0|fallback-arm-order|a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff|51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a|72f2ec89dd0dcc6826745019b3c11b3361e36732"
PRIMARY_SEED_SHA256 = hashlib.sha256(PRIMARY_SEED_MATERIAL.encode()).hexdigest()
FALLBACK_SEED_SHA256 = hashlib.sha256(FALLBACK_SEED_MATERIAL.encode()).hexdigest()

PRIMARY_SCHEDULE_REL = Path("config/r3_d0_confirmatory_primary_arm_order_schedule.csv")
FALLBACK_SCHEDULE_REL = Path("config/r3_d0_confirmatory_fallback_arm_order_schedule.csv")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def import_frozen_runner(repo: Path):
    implementation = repo / R3_REL / "implementation"
    sys.path.insert(0, str(implementation))
    try:
        import r3_resource_runner as frozen_runner  # type: ignore
    finally:
        try:
            sys.path.remove(str(implementation))
        except ValueError:
            pass
    return frozen_runner


def deterministic_assignments(n: int, seed_sha256: str) -> list[tuple[str, str, str]]:
    if n % 6 != 0:
        raise RuntimeError("schedule length must be a multiple of six")
    perms = sorted(itertools.permutations(ARMS))
    out: list[tuple[str, str, str]] = []
    for cycle in range(n // 6):
        ordered = sorted(
            perms,
            key=lambda p: hashlib.sha256(
                f"{seed_sha256}|cycle={cycle}|{'|'.join(p)}".encode()
            ).hexdigest(),
        )
        out.extend(ordered)
    if len(out) != n:
        raise RuntimeError("deterministic schedule length mismatch")
    return out


def validate_authorities(repo: Path) -> dict[str, Any]:
    r3 = repo / R3_REL
    r2 = repo / R2_REL

    binding_sha_file = r3 / "results/BINDING_PLAN_SHA256.txt"
    a1 = r3 / "results/MCAD_NH_R3_A_PROTOCOL_FREEZE.json"
    a2 = r3 / "results/MCAD_NH_R3_A2_SEMANTIC_REFINEMENT_FREEZE.json"
    b1 = r3 / "config/r3_b1_measurement_preregistration.json"
    primary_path = r3 / "results/confirmatory_test_sessions.csv"
    fallback_path = r3 / "results/confirmatory_test_quota_fallback_120.csv"
    dev_path = r3 / "results/pilot_dev_sessions.csv"
    val_path = r3 / "results/calibration_val_sessions.csv"
    session_summary_path = r2 / "results/session_summary.csv"
    binding_path = r3 / "results/full_sequence_binding.csv"
    c5_path = r3 / "results/validation_v1/validation_analysis.json"

    declared = binding_sha_file.read_text(encoding="utf-8").split()[0]
    if declared != EXPECTED_BINDING_DIGEST:
        raise RuntimeError("binding digest changed")
    if sha256(a1) != EXPECTED_A1_FREEZE_SHA256:
        raise RuntimeError("R3-A1 freeze changed")
    if sha256(a2) != EXPECTED_A2_FREEZE_SHA256:
        raise RuntimeError("R3-A2 freeze changed")
    if sha256(b1) != EXPECTED_B1_PREREG_SHA256:
        raise RuntimeError("B1 preregistration changed")

    expected_blobs = (
        (primary_path, PRIMARY_COHORT_BLOB, "primary confirmatory cohort"),
        (fallback_path, FALLBACK_COHORT_BLOB, "fallback confirmatory cohort"),
        (session_summary_path, SESSION_SUMMARY_BLOB, "R2 session summary"),
        (binding_path, FULL_BINDING_BLOB, "full sequence binding"),
        (c5_path, C5_ANALYSIS_BLOB, "R3-C5 validation analysis"),
    )
    for path, expected, label in expected_blobs:
        actual = git_blob_sha1(path)
        if actual != expected:
            raise RuntimeError(f"{label} blob changed: {actual}")

    if sha256(c5_path) != C5_ANALYSIS_SHA256:
        raise RuntimeError("R3-C5 validation analysis SHA256 changed")
    c5 = json.loads(c5_path.read_text(encoding="utf-8"))
    readiness = c5.get("readiness") or {}
    if readiness.get("status") != "PASS_READY_FOR_R3D_STATIC_ACTIVATION":
        raise RuntimeError("R3-C5 readiness not PASS")
    if readiness.get("r3c_rerun_authorized") is not False:
        raise RuntimeError("R3-C rerun unexpectedly authorized")
    if readiness.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("R3-C unexpectedly promoted confirmatory claim")

    primary = read_csv(primary_path)
    fallback = read_csv(fallback_path)
    dev = read_csv(dev_path)
    val = read_csv(val_path)

    validate_cohort(
        primary,
        expected_n=300,
        expected_per_stratum=15,
        role="CONFIRMATORY_PRIMARY",
        reps=[f"R{i:03d}" for i in range(46, 61)],
        label="primary",
    )
    validate_cohort(
        fallback,
        expected_n=120,
        expected_per_stratum=6,
        role="RESOURCE_CONSTRAINED_FALLBACK",
        reps=[f"R{i:03d}" for i in range(46, 52)],
        label="fallback",
    )

    primary_ids = {r["session_id"] for r in primary}
    fallback_ids = {r["session_id"] for r in fallback}
    dev_ids = {r["session_id"] for r in dev}
    val_ids = {r["session_id"] for r in val}

    if not fallback_ids <= primary_ids:
        raise RuntimeError("fallback cohort is not a subset of primary test cohort")
    if primary_ids & dev_ids or primary_ids & val_ids:
        raise RuntimeError("confirmatory cohort overlaps DEV/VAL")

    primary_by_stratum: dict[tuple[str, str], list[str]] = {}
    fallback_by_stratum: dict[tuple[str, str], list[str]] = {}
    for rows, out in ((primary, primary_by_stratum), (fallback, fallback_by_stratum)):
        for row in rows:
            out.setdefault((row["topology"], row["pattern"]), []).append(row["session_id"])
    for key in sorted(primary_by_stratum):
        p = sorted(primary_by_stratum[key])
        f = sorted(fallback_by_stratum.get(key, []))
        if f != p[:6]:
            raise RuntimeError(f"fallback is not lexicographic first six in stratum {key}")

    return {
        "r3": r3,
        "r2": r2,
        "primary": primary,
        "fallback": fallback,
        "session_summary_path": session_summary_path,
        "binding_path": binding_path,
    }


def validate_cohort(
    rows: list[dict[str, str]],
    expected_n: int,
    expected_per_stratum: int,
    role: str,
    reps: list[str],
    label: str,
) -> None:
    if len(rows) != expected_n:
        raise RuntimeError(f"{label}: row count mismatch")
    if {r["split"] for r in rows} != {"test"}:
        raise RuntimeError(f"{label}: split changed")
    if {r["selection_role"] for r in rows} != {role}:
        raise RuntimeError(f"{label}: selection role changed")
    if len({r["session_id"] for r in rows}) != expected_n:
        raise RuntimeError(f"{label}: duplicate session ids")
    strata = Counter((r["topology"], r["pattern"]) for r in rows)
    if len(strata) != 20 or set(strata.values()) != {expected_per_stratum}:
        raise RuntimeError(f"{label}: stratum allocation changed")
    by_stratum: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        by_stratum.setdefault((r["topology"], r["pattern"]), []).append(
            r["session_id"].rsplit("-", 1)[-1]
        )
    for key, got in by_stratum.items():
        if sorted(got) != reps:
            raise RuntimeError(f"{label}: replicate set changed in {key}")


def schedule_rows(
    cohort: list[dict[str, str]],
    seed_sha256: str,
) -> list[dict[str, Any]]:
    assignments = deterministic_assignments(len(cohort), seed_sha256)
    rows: list[dict[str, Any]] = []
    for idx, (c, p) in enumerate(zip(cohort, assignments), start=1):
        rows.append({
            "block_index": idx,
            "session_id": c["session_id"],
            "topology": c["topology"],
            "pattern": c["pattern"],
            "selection_role": c["selection_role"],
            "arm_1": p[0],
            "arm_2": p[1],
            "arm_3": p[2],
        })
    return rows


def write_schedule(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"schedule already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "block_index", "session_id", "topology", "pattern",
        "selection_role", "arm_1", "arm_2", "arm_3",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def materialize_schedules(repo: Path) -> dict[str, str]:
    data = validate_authorities(repo)
    r3 = data["r3"]
    primary_path = r3 / PRIMARY_SCHEDULE_REL
    fallback_path = r3 / FALLBACK_SCHEDULE_REL

    write_schedule(primary_path, schedule_rows(data["primary"], PRIMARY_SEED_SHA256))
    write_schedule(fallback_path, schedule_rows(data["fallback"], FALLBACK_SEED_SHA256))

    return {
        "primary_schedule_sha256": sha256(primary_path),
        "fallback_schedule_sha256": sha256(fallback_path),
    }


def validate_schedule(
    path: Path,
    cohort: list[dict[str, str]],
    seed_sha256: str,
    expected_position_each: int,
    label: str,
) -> list[dict[str, str]]:
    rows = read_csv(path)
    expected = schedule_rows(cohort, seed_sha256)
    if len(rows) != len(expected):
        raise RuntimeError(f"{label}: schedule row count mismatch")
    fields = [
        "block_index", "session_id", "topology", "pattern",
        "selection_role", "arm_1", "arm_2", "arm_3",
    ]
    for i, (got, exp) in enumerate(zip(rows, expected), start=1):
        normalized = {k: str(exp[k]) for k in fields}
        if {k: got[k] for k in fields} != normalized:
            raise RuntimeError(f"{label}: deterministic schedule mismatch at row {i}")
    pos_counts = [Counter(r[f"arm_{i}"] for r in rows) for i in (1, 2, 3)]
    for pos, counts in enumerate(pos_counts, start=1):
        if set(counts) != set(ARMS):
            raise RuntimeError(f"{label}: position {pos} arm set changed")
        if set(counts.values()) != {expected_position_each}:
            raise RuntimeError(f"{label}: position {pos} balance changed: {dict(counts)}")
    return rows


def build_plan(repo: Path, mode: str) -> dict[str, Any]:
    data = validate_authorities(repo)
    r3 = data["r3"]
    if mode == "primary":
        cohort = data["primary"]
        schedule_path = r3 / PRIMARY_SCHEDULE_REL
        seed = PRIMARY_SEED_SHA256
        pos_each = 100
        stage_role = "CONFIRMATORY_PRIMARY"
    elif mode == "fallback":
        cohort = data["fallback"]
        schedule_path = r3 / FALLBACK_SCHEDULE_REL
        seed = FALLBACK_SEED_SHA256
        pos_each = 40
        stage_role = "RESOURCE_CONSTRAINED_FALLBACK"
    else:
        raise RuntimeError("mode must be primary or fallback")

    schedule = validate_schedule(schedule_path, cohort, seed, pos_each, mode)

    summaries = {r["session_id"]: r for r in read_csv(data["session_summary_path"])}
    ids = {r["session_id"] for r in cohort}
    by_session: dict[str, list[dict[str, str]]] = {sid: [] for sid in ids}
    for row in read_csv(data["binding_path"]):
        sid = row.get("session_id", "")
        if sid in by_session:
            by_session[sid].append(row)

    for sid, rows in by_session.items():
        rows.sort(key=lambda r: int(r["candidate_index"]))
        if len(rows) != 24 or [int(r["candidate_index"]) for r in rows] != list(range(1, 25)):
            raise RuntimeError(f"{sid}: frozen candidate sequence is not exactly 1..24")
        sm = summaries.get(sid)
        if sm is None or sm.get("objective_preserved") != "true":
            raise RuntimeError(f"{sid}: R2 objective preservation authority missing")
        for key in ("first_full_phi_candidate_safe", "first_full_phi_candidate_permissive"):
            v = int(sm[key])
            if not 1 <= v <= 24:
                raise RuntimeError(f"{sid}: invalid {key}")

    frozen = import_frozen_runner(repo)
    schedule_by_sid = {r["session_id"]: r for r in schedule}
    arm_runs: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    templates: set[str] = set()

    for block_index, c in enumerate(cohort, start=1):
        sid = c["session_id"]
        srow = schedule_by_sid[sid]
        sm = summaries[sid]
        rows = by_session[sid]
        for arm_position, arm in enumerate(
            (srow["arm_1"], srow["arm_2"], srow["arm_3"]),
            start=1,
        ):
            completion = int(
                sm["first_full_phi_candidate_safe"]
                if arm == "SAFE_PRUNING"
                else sm["first_full_phi_candidate_permissive"]
            )
            gate_count = 0
            full_count = 0
            for row in rows:
                run_gate = bool(frozen.frozen_gate_rule(arm))
                run_full = bool(frozen.frozen_full_execute_rule(arm, row))
                gate_count += int(run_gate)
                full_count += int(run_full)
                templates.add(row["template_id"])
                actions.append({
                    "block_index": block_index,
                    "session_id": sid,
                    "topology": c["topology"],
                    "pattern": c["pattern"],
                    "selection_role": stage_role,
                    "arm_position": arm_position,
                    "arm": arm,
                    "candidate_index": int(row["candidate_index"]),
                    "query_id": row["query_id"],
                    "frozen_class": row["class"],
                    "frozen_operational_action": row["operational_action"],
                    "template_id": row["template_id"],
                    "query_template_path": row["query_template_path"],
                    "parameter_binding": row["parameter_binding"],
                    "run_gate": run_gate,
                    "run_full_backend": run_full,
                    "is_completion_candidate": int(row["candidate_index"]) == completion,
                })
            arm_runs.append({
                "block_index": block_index,
                "session_id": sid,
                "topology": c["topology"],
                "pattern": c["pattern"],
                "selection_role": stage_role,
                "arm_position": arm_position,
                "arm": arm,
                "completion_candidate": completion,
                "gate_evaluations_planned": gate_count,
                "full_backend_executions_planned": full_count,
            })

    gated = sum(r["arm"] != "UNGATED_EXECUTE_ADMISSIBLE" for r in arm_runs)
    return {
        "contract_version": "mcad.nh_r3.d0.confirmatory_static_plan.v1",
        "stage": "R3-D_CONFIRMATORY_SQL_DIRECT",
        "mode": mode,
        "selection_role": stage_role,
        "semantic_sessions": len(cohort),
        "arm_runs": arm_runs,
        "candidate_actions": actions,
        "gated_arm_runs": gated,
        "ungated_arm_runs": len(arm_runs) - gated,
        "gate_evaluations_planned": sum(r["gate_evaluations_planned"] for r in arm_runs),
        "full_backend_executions_planned": sum(r["full_backend_executions_planned"] for r in arm_runs),
        "mcad_api_restarts_planned": len(arm_runs),
        "fresh_mcad_sessions_planned": gated,
        "unique_templates_lexicographic": sorted(templates),
        "schedule_sha256": sha256(schedule_path),
        "seed_sha256": seed,
        "measurement_authorized": False,
        "measurement_executed": False,
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
    }


def summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": plan["contract_version"],
        "stage": plan["stage"],
        "mode": plan["mode"],
        "selection_role": plan["selection_role"],
        "semantic_sessions": plan["semantic_sessions"],
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gated_arm_runs": plan["gated_arm_runs"],
        "ungated_arm_runs": plan["ungated_arm_runs"],
        "gate_evaluations_planned": plan["gate_evaluations_planned"],
        "full_backend_executions_planned": plan["full_backend_executions_planned"],
        "mcad_api_restarts_planned": plan["mcad_api_restarts_planned"],
        "fresh_mcad_sessions_planned": plan["fresh_mcad_sessions_planned"],
        "unique_templates_lexicographic": plan["unique_templates_lexicographic"],
        "schedule_sha256": plan["schedule_sha256"],
        "seed_sha256": plan["seed_sha256"],
        "measurement_authorized": False,
        "measurement_executed": False,
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("materialize-schedules")
    p = sub.add_parser("summary")
    p.add_argument("--mode", choices=["primary", "fallback"], required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "materialize-schedules":
        hashes = materialize_schedules(repo)
        print(json.dumps(hashes, indent=2, sort_keys=True))
        print("measurement_executed=false")
        print("backend_query_executed=false")
        print("R3_D0_CONFIRMATORY_SCHEDULE_MATERIALIZATION=PASS")
        return

    if args.cmd == "summary":
        s = summary(build_plan(repo, args.mode))
        print(json.dumps(s, indent=2, sort_keys=True))
        print("measurement_executed=false")
        print("backend_query_executed=false")
        print(f"R3_D0_CONFIRMATORY_{args.mode.upper()}_STATIC_PLAN=PASS")
        return


if __name__ == "__main__":
    main()
