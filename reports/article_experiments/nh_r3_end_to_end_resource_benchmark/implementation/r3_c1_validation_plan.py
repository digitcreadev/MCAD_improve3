#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT_HEAD = "11d5c1128e13f30125299c1fa8719e5a0abc48bf"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R2_REL = Path("reports/article_experiments/nh_r2_objective_preserving_pruning")
ARMS = ("UNGATED_EXECUTE_ADMISSIBLE", "PERMISSIVE_GATED", "SAFE_PRUNING")
EXPECTED_BINDING_DIGEST = "a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
EXPECTED_A1_FREEZE_SHA256 = "e5d8e6857a22962623aa483eeb92f60cb66aac1e8e98ea3f6a7e060558a42f16"
EXPECTED_A2_FREEZE_SHA256 = "51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a"
EXPECTED_B1_PREREG_SHA256 = "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f"
EXPECTED_CALIBRATION_SHA256 = "94f4dc0ad7d07eaac8d2d2f7583117aaf79c5e03cabb2560f156418f04569da6"
EXPECTED_CALIBRATION_GIT_BLOB = "454a3110c9935aef3cb180098ac8d56ff7d9e7bd"
EXPECTED_SESSION_SUMMARY_GIT_BLOB = "00f5c92d4f06ce1092f49546088bc3461e3e752e"
EXPECTED_FULL_BINDING_GIT_BLOB = "ce3930949b3991cc1af346b01f559f0a9a2798a5"
EXPECTED_SCHEDULE_SHA256 = "4aede87cb911e5ce9baf0f372c011eb6435a6fd1f3411529577ccdbfe5ab6b70"
SEED_MATERIAL = 'MCAD-NH-R3|R3-C1|arm-order|a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff|51cf6cd77cc033c1bd99e3c897378e79c3a58f3a6c4d66549403feba306cd23a|94f4dc0ad7d07eaac8d2d2f7583117aaf79c5e03cabb2560f156418f04569da6'
SEED_SHA256 = "b66d344968cfa632afc25025b772c49eb8d03bc60ec631c26db703740e730462"


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


def deterministic_arm_assignments() -> list[tuple[str, str, str]]:
    perms = sorted(itertools.permutations(ARMS))
    seq: list[tuple[str, str, str]] = []
    for cycle in range(6):
        seq.extend(sorted(perms, key=lambda p: hashlib.sha256(
            f"{SEED_SHA256}|cycle={cycle}|{'|'.join(p)}".encode()
        ).hexdigest()))
    tails: list[tuple[str, tuple[tuple[str, str, str], ...]]] = []
    for tail in itertools.permutations(perms, 4):
        trial = seq + list(tail)
        counts = [Counter(p[i] for p in trial) for i in range(3)]
        if all(max(c.values()) - min(c.values()) <= 1 for c in counts):
            key = hashlib.sha256(
                (SEED_SHA256 + "|tail|" + ";".join(",".join(p) for p in tail)).encode()
            ).hexdigest()
            tails.append((key, tail))
    if not tails:
        raise RuntimeError("no balanced deterministic arm-order tail")
    seq.extend(list(min(tails, key=lambda x: x[0])[1]))
    if len(seq) != 40:
        raise RuntimeError("deterministic schedule length != 40")
    return seq


def load_and_validate(repo: Path) -> dict[str, Any]:
    r3 = repo / R3_REL
    r2 = repo / R2_REL
    binding_sha_file = r3 / "results/BINDING_PLAN_SHA256.txt"
    a1 = r3 / "results/MCAD_NH_R3_A_PROTOCOL_FREEZE.json"
    a2 = r3 / "results/MCAD_NH_R3_A2_SEMANTIC_REFINEMENT_FREEZE.json"
    b1 = r3 / "config/r3_b1_measurement_preregistration.json"
    calibration = r3 / "results/calibration_val_sessions.csv"
    schedule = r3 / "config/r3_c1_arm_order_schedule.csv"
    session_summary = r2 / "results/session_summary.csv"
    binding = r3 / "results/full_sequence_binding.csv"

    declared = binding_sha_file.read_text(encoding="utf-8").split()[0]
    if declared != EXPECTED_BINDING_DIGEST:
        raise RuntimeError("binding digest changed")
    if sha256(a1) != EXPECTED_A1_FREEZE_SHA256:
        raise RuntimeError("R3-A1 freeze changed")
    if sha256(a2) != EXPECTED_A2_FREEZE_SHA256:
        raise RuntimeError("R3-A2 freeze changed")
    if sha256(b1) != EXPECTED_B1_PREREG_SHA256:
        raise RuntimeError("B1 preregistration changed")
    if sha256(calibration) != EXPECTED_CALIBRATION_SHA256 or git_blob_sha1(calibration) != EXPECTED_CALIBRATION_GIT_BLOB:
        raise RuntimeError("frozen calibration cohort changed")
    if git_blob_sha1(session_summary) != EXPECTED_SESSION_SUMMARY_GIT_BLOB:
        raise RuntimeError("R2 session_summary changed")
    if git_blob_sha1(binding) != EXPECTED_FULL_BINDING_GIT_BLOB:
        raise RuntimeError("full_sequence_binding changed")
    if sha256(schedule) != EXPECTED_SCHEDULE_SHA256:
        raise RuntimeError("R3-C1 arm schedule changed")
    if hashlib.sha256(SEED_MATERIAL.encode()).hexdigest() != SEED_SHA256:
        raise RuntimeError("R3-C1 seed material changed")

    cohort = read_csv(calibration)
    sched = read_csv(schedule)
    if len(cohort) != 40 or len(sched) != 40:
        raise RuntimeError("R3-C cohort/schedule must contain 40 rows")
    if {r["split"] for r in cohort} != {"val"} or {r["selection_role"] for r in cohort} != {"CALIBRATION_NO_EFFECT_TUNING"}:
        raise RuntimeError("R3-C cohort role changed")
    if len({r["session_id"] for r in cohort}) != 40:
        raise RuntimeError("duplicate R3-C session")
    strata = Counter((r["topology"], r["pattern"]) for r in cohort)
    if len(strata) != 20 or set(strata.values()) != {2}:
        raise RuntimeError("R3-C stratum allocation changed")

    expected_assignments = deterministic_arm_assignments()
    for i, (c, s, p) in enumerate(zip(cohort, sched, expected_assignments), start=1):
        if int(s["block_index"]) != i:
            raise RuntimeError("R3-C block_index mismatch")
        for key in ("session_id", "topology", "pattern"):
            if s[key] != c[key]:
                raise RuntimeError(f"R3-C schedule/cohort mismatch at block {i}: {key}")
        if (s["arm_1"], s["arm_2"], s["arm_3"]) != p:
            raise RuntimeError(f"R3-C deterministic arm permutation mismatch at block {i}")
        if set(p) != set(ARMS):
            raise RuntimeError("invalid arm permutation")

    pos_counts = [Counter(s[f"arm_{i}"] for s in sched) for i in (1,2,3)]
    if any(max(c.values()) - min(c.values()) > 1 for c in pos_counts):
        raise RuntimeError("R3-C arm position balance > 1")

    summaries = {r["session_id"]: r for r in read_csv(session_summary)}
    cohort_ids = {r["session_id"] for r in cohort}
    by_session: dict[str, list[dict[str, str]]] = {sid: [] for sid in cohort_ids}
    for row in read_csv(binding):
        sid = row.get("session_id", "")
        if sid in by_session:
            by_session[sid].append(row)
    for sid, rows in by_session.items():
        rows.sort(key=lambda r: int(r["candidate_index"]))
        if len(rows) != 24 or [int(r["candidate_index"]) for r in rows] != list(range(1,25)):
            raise RuntimeError(f"{sid}: expected frozen candidates 1..24")
        if sid not in summaries:
            raise RuntimeError(f"{sid}: missing R2 session summary")
        sm = summaries[sid]
        if sm.get("objective_preserved") != "true":
            raise RuntimeError(f"{sid}: R2 objective preservation authority missing")
        for key in ("first_full_phi_candidate_safe", "first_full_phi_candidate_permissive"):
            value = int(sm[key])
            if not 1 <= value <= 24:
                raise RuntimeError(f"{sid}: invalid {key}")

    return {
        "cohort": cohort,
        "schedule": sched,
        "summaries": summaries,
        "by_session": by_session,
        "position_counts": [dict(c) for c in pos_counts],
    }


def build_plan(repo: Path) -> dict[str, Any]:
    data = load_and_validate(repo)
    frozen = import_frozen_runner(repo)
    actions: list[dict[str, Any]] = []
    arm_runs: list[dict[str, Any]] = []
    templates: set[str] = set()

    schedule_by_sid = {r["session_id"]: r for r in data["schedule"]}
    cohort_order = [r["session_id"] for r in data["cohort"]]
    for block_index, sid in enumerate(cohort_order, start=1):
        srow = schedule_by_sid[sid]
        sm = data["summaries"][sid]
        rows = data["by_session"][sid]
        arms = [srow["arm_1"], srow["arm_2"], srow["arm_3"]]
        for arm_position, arm in enumerate(arms, start=1):
            completion = int(sm["first_full_phi_candidate_safe"] if arm == "SAFE_PRUNING" else sm["first_full_phi_candidate_permissive"])
            full_count = 0
            gate_count = 0
            for row in rows:
                run_gate = bool(frozen.frozen_gate_rule(arm))
                run_full = bool(frozen.frozen_full_execute_rule(arm, row))
                gate_count += int(run_gate)
                full_count += int(run_full)
                templates.add(row["template_id"])
                actions.append({
                    "block_index": block_index,
                    "session_id": sid,
                    "topology": srow["topology"],
                    "pattern": srow["pattern"],
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
                "topology": srow["topology"],
                "pattern": srow["pattern"],
                "arm_position": arm_position,
                "arm": arm,
                "completion_candidate": completion,
                "gate_evaluations_planned": gate_count,
                "full_backend_executions_planned": full_count,
            })

    gated = sum(1 for r in arm_runs if r["arm"] != "UNGATED_EXECUTE_ADMISSIBLE")
    equal_completion = sum(
        1 for sid in cohort_order
        if data["summaries"][sid]["first_full_phi_candidate_safe"] == data["summaries"][sid]["first_full_phi_candidate_permissive"]
    )
    return {
        "contract_version": "mcad.nh_r3.c1.validation_static_plan.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "selection_role": "CALIBRATION_NO_EFFECT_TUNING",
        "semantic_sessions": 40,
        "arm_runs": arm_runs,
        "candidate_actions": actions,
        "gated_arm_runs": gated,
        "ungated_arm_runs": len(arm_runs) - gated,
        "gate_evaluations_planned": sum(r["gate_evaluations_planned"] for r in arm_runs),
        "mcad_api_restarts_planned": len(arm_runs),
        "fresh_mcad_sessions_planned": gated,
        "unique_templates_lexicographic": sorted(templates),
        "safe_permissive_equal_completion_candidate_sessions": equal_completion,
        "arm_position_counts": data["position_counts"],
        "binding_plan_sha256": EXPECTED_BINDING_DIGEST,
        "arm_schedule_sha256": EXPECTED_SCHEDULE_SHA256,
        "seed_sha256": SEED_SHA256,
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
        "selection_role": plan["selection_role"],
        "semantic_sessions": plan["semantic_sessions"],
        "arm_runs": len(plan["arm_runs"]),
        "candidate_actions": len(plan["candidate_actions"]),
        "gated_arm_runs": plan["gated_arm_runs"],
        "ungated_arm_runs": plan["ungated_arm_runs"],
        "gate_evaluations_planned": plan["gate_evaluations_planned"],
        "mcad_api_restarts_planned": plan["mcad_api_restarts_planned"],
        "fresh_mcad_sessions_planned": plan["fresh_mcad_sessions_planned"],
        "unique_templates_lexicographic": plan["unique_templates_lexicographic"],
        "safe_permissive_equal_completion_candidate_sessions": plan["safe_permissive_equal_completion_candidate_sessions"],
        "arm_position_counts": plan["arm_position_counts"],
        "binding_plan_sha256": plan["binding_plan_sha256"],
        "arm_schedule_sha256": plan["arm_schedule_sha256"],
        "seed_sha256": plan["seed_sha256"],
        "measurement_authorized": False,
        "measurement_executed": False,
        "confirmatory_claim_authorized": False,
        "effect_size_tuning_performed": False,
        "scientific_redesign_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen NH-R3-C validation plan without measurement")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--full-json", action="store_true")
    args = parser.parse_args()
    plan = build_plan(Path(args.repo).resolve())
    print(json.dumps(plan if args.full_json else summary(plan), indent=2, sort_keys=True))
    print("R3_C1_VALIDATION_STATIC_PLAN=PASS")

if __name__ == "__main__":
    main()
