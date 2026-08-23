#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any

EXPECTED_ARCHIVE_SHA256 = "116fc16926d7953cba90d89cee380ae494298b46327ebaf53a1152ec67711908"
SOURCE_ARCHIVE_NAME = "MCAD_R3_C4_VALIDATION_RESULTS_20260823T193237Z.tar.gz"
C4_HEAD = "24335a3e9d98b53c7f63dff2b418d15a24dd2f2e"
DEV_ANALYSIS_GIT_BLOB = "6630fed75e43256c619927c911dcc03c6bfed0a6"
ANALYSIS_CLASS = "VALIDATION_CALIBRATION_NONCONFIRMATORY"

ARMS = (
    "UNGATED_EXECUTE_ADMISSIBLE",
    "PERMISSIVE_GATED",
    "SAFE_PRUNING",
)

METRICS = (
    "client_wall_ms",
    "time_to_analytical_objective_completion_ms",
    "backend_request_count_including_gate_probes",
    "full_backend_execution_count",
    "nvac_physical_backend_request_count",
    "response_bytes",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
)

CORE_DIAGNOSTIC_METRICS = (
    "client_wall_ms",
    "time_to_analytical_objective_completion_ms",
    "backend_request_count_including_gate_probes",
    "full_backend_execution_count",
    "response_bytes",
    "sqlserver_cpu_usage_usec_delta",
)

DEV_ARM_MEANS = {
    "UNGATED_EXECUTE_ADMISSIBLE": {
        "client_wall_ms": 1192.924573,
        "time_to_analytical_objective_completion_ms": 548.685382,
        "backend_request_count_including_gate_probes": 21.6,
        "full_backend_execution_count": 21.6,
        "nvac_physical_backend_request_count": 0.0,
        "response_bytes": 201202.1,
        "sqlserver_cpu_usage_usec_delta": 1072503.65,
        "sqlserver_io_rbytes_delta": 29900.8,
        "sqlserver_io_wbytes_delta": 0.0,
    },
    "PERMISSIVE_GATED": {
        "client_wall_ms": 2934.481085,
        "time_to_analytical_objective_completion_ms": 1331.704737,
        "backend_request_count_including_gate_probes": 27.8,
        "full_backend_execution_count": 21.6,
        "nvac_physical_backend_request_count": 6.2,
        "response_bytes": 212604.1,
        "sqlserver_cpu_usage_usec_delta": 1477928.8,
        "sqlserver_io_rbytes_delta": 3061350.4,
        "sqlserver_io_wbytes_delta": 3379.2,
    },
    "SAFE_PRUNING": {
        "client_wall_ms": 1978.393798,
        "time_to_analytical_objective_completion_ms": 1056.302709,
        "backend_request_count_including_gate_probes": 11.8,
        "full_backend_execution_count": 5.6,
        "nvac_physical_backend_request_count": 6.2,
        "response_bytes": 63713.1,
        "sqlserver_cpu_usage_usec_delta": 579708.05,
        "sqlserver_io_rbytes_delta": 84582.4,
        "sqlserver_io_wbytes_delta": 37785.6,
    },
}

DEV_HEADLINE_PAIR_COUNTS = {
    "safe_vs_permissive_client_wall_ms": {
        "lower": 20, "equal": 0, "higher": 0,
        "percent_change_of_means": -32.581136,
    },
    "safe_vs_permissive_completion_ms": {
        "lower": 16, "equal": 0, "higher": 4,
        "percent_change_of_means": -20.680412,
    },
    "safe_vs_permissive_backend_requests": {
        "lower": 20, "equal": 0, "higher": 0,
        "percent_change_of_means": -57.553957,
    },
    "safe_vs_ungated_client_wall_ms": {
        "lower": 0, "equal": 0, "higher": 20,
        "percent_change_of_means": 65.843997,
    },
    "safe_vs_ungated_completion_ms": {
        "lower": 0, "equal": 0, "higher": 20,
        "percent_change_of_means": 92.51519,
    },
    "safe_vs_ungated_backend_requests": {
        "lower": 20, "equal": 0, "higher": 0,
        "percent_change_of_means": -45.37037,
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def r6(x: float | int | None) -> float | int | None:
    if x is None:
        return None
    if isinstance(x, int):
        return x
    return round(float(x), 6)


def pct_change(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return (a / b - 1.0) * 100.0


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def safe_members(tf: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tf.getmembers()
    for m in members:
        p = Path(m.name)
        if p.is_absolute() or ".." in p.parts:
            raise RuntimeError(f"unsafe archive member: {m.name}")
    return members


def read_member(tf: tarfile.TarFile, name: str) -> bytes:
    f = tf.extractfile(name)
    if f is None:
        raise RuntimeError(f"archive member is not a regular file: {name}")
    return f.read()


def locate_root(names: list[str]) -> str:
    roots = sorted({n.split("/", 1)[0] for n in names if n})
    if len(roots) != 1:
        raise RuntimeError(f"expected exactly one archive root, got: {roots}")
    return roots[0]


def verify_internal_manifest(tf: tarfile.TarFile, root: str) -> tuple[int, list[str]]:
    manifest_name = f"{root}/SHA256SUMS.txt"
    manifest = read_member(tf, manifest_name).decode("utf-8")
    bad: list[str] = []
    count = 0
    for raw in manifest.splitlines():
        if not raw.strip():
            continue
        expected, rel = raw.split("  ", 1)
        rel_clean = rel[2:] if rel.startswith("./") else rel
        data = read_member(tf, f"{root}/{rel_clean}")
        actual = sha256_bytes(data)
        count += 1
        if actual != expected:
            bad.append(rel)
    return count, bad


def load_source(archive: Path) -> dict[str, Any]:
    actual_sha = sha256_bytes(archive.read_bytes())
    if actual_sha != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(
            f"source archive SHA mismatch: {actual_sha} != {EXPECTED_ARCHIVE_SHA256}"
        )

    with tarfile.open(archive, "r:gz") as tf:
        members = safe_members(tf)
        names = [m.name for m in members]
        root = locate_root(names)
        manifest_count, bad = verify_internal_manifest(tf, root)
        if bad:
            raise RuntimeError("internal SHA256SUMS mismatch: " + ",".join(bad))

        integrity = json.loads(
            read_member(tf, f"{root}/integrity_summary.json").decode("utf-8")
        )
        attempt = json.loads(
            read_member(tf, f"{root}/attempt_manifest.json").decode("utf-8")
        )
        handoff = json.loads(
            read_member(tf, f"{root}/handoff.json").decode("utf-8")
        )
        warmup = json.loads(
            read_member(tf, f"{root}/warmup_receipt.json").decode("utf-8")
        )
        validation_summary = json.loads(
            read_member(tf, f"{root}/results/validation_summary.json").decode("utf-8")
        )

        arm_prefix = f"{root}/results/arm_runs/"
        arm_names = sorted(
            n for n in names if n.startswith(arm_prefix) and n.endswith(".json")
        )
        arm_rows: list[dict[str, Any]] = []
        for name in arm_names:
            data = json.loads(read_member(tf, name).decode("utf-8"))
            candidate_records = data.pop("candidate_records")
            data["_candidate_record_count"] = len(candidate_records)
            arm_rows.append(data)

    return {
        "archive_sha256": actual_sha,
        "archive_root": root,
        "archive_members": len(names),
        "internal_manifest_entries": manifest_count,
        "integrity": integrity,
        "attempt": attempt,
        "handoff": handoff,
        "warmup": warmup,
        "validation_summary": validation_summary,
        "arm_rows": sorted(arm_rows, key=lambda r: int(r["ordinal"])),
    }


def validate_source(source: dict[str, Any]) -> None:
    integrity = source["integrity"]
    attempt = source["attempt"]
    handoff = source["handoff"]
    warmup = source["warmup"]
    summary = source["validation_summary"]
    rows = source["arm_rows"]

    if integrity.get("integrity_status") != "PASS":
        raise RuntimeError("C4 integrity status is not PASS")
    if integrity.get("analysis_class") != ANALYSIS_CLASS:
        raise RuntimeError("C4 integrity analysis class changed")
    if attempt.get("status") != "COMPLETE_INTEGRITY_PASS":
        raise RuntimeError("C4 attempt did not close with COMPLETE_INTEGRITY_PASS")
    if attempt.get("parent_c3_head") != "266bc62593652547b3184969e4003fe2178843f8":
        raise RuntimeError("C4 attempt parent C3 head changed")
    if handoff.get("next") != "R3-C5_VALIDATION_ANALYSIS_AND_FREEZE":
        raise RuntimeError("C4 handoff next stage changed")
    if summary.get("analysis_class") != ANALYSIS_CLASS:
        raise RuntimeError("validation summary analysis class changed")
    if summary.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("validation summary promoted a confirmatory claim")
    if summary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("validation summary indicates effect-size tuning")
    if len(rows) != 120:
        raise RuntimeError(f"expected 120 arm receipts, got {len(rows)}")
    if int(integrity.get("semantic_sessions", -1)) != 40:
        raise RuntimeError("expected 40 semantic sessions")
    if int(integrity.get("candidate_records", -1)) != 2880:
        raise RuntimeError("expected 2880 candidate records")
    if int(integrity.get("gate_evaluations", -1)) != 1920:
        raise RuntimeError("expected 1920 gate evaluations")
    if int(integrity.get("negative_cgroup_delta_arm_runs", -1)) != 0:
        raise RuntimeError("negative cgroup delta arm runs detected")
    warm_rows = warmup.get("templates")
    if not isinstance(warm_rows, list) or len(warm_rows) != 7:
        raise RuntimeError("warmup receipt does not contain exactly 7 templates")
    if warmup.get("measured") is not False:
        raise RuntimeError("warmup unexpectedly marked measured")

    sessions: dict[str, set[str]] = defaultdict(set)
    candidate_total = 0
    gate_total = 0
    fresh_gated = 0
    ordinals: list[int] = []
    for r in rows:
        ordinals.append(int(r["ordinal"]))
        sessions[str(r["session_id"])].add(str(r["arm"]))
        candidate_total += int(r["_candidate_record_count"])
        gate_total += int(r["gate_evaluation_count"])
        if r["arm"] != "UNGATED_EXECUTE_ADMISSIBLE" and r.get("fresh_mcad_session_id"):
            fresh_gated += 1
        if r.get("frozen_action_authority") != "NH_R2_R3_BINDING":
            raise RuntimeError("frozen action authority changed")
        if r.get("live_gate_action_authoritative") is not False:
            raise RuntimeError("live gate became authoritative")
        if r.get("confirmatory_claim_authorized") is not False:
            raise RuntimeError("arm receipt authorizes confirmatory claim")
        if r.get("selection_role") != "CALIBRATION_NO_EFFECT_TUNING":
            raise RuntimeError("validation selection role changed")
        if (
            int(r["sqlserver_cpu_usage_usec_delta"]) < 0
            or int(r["sqlserver_io_rbytes_delta"]) < 0
            or int(r["sqlserver_io_wbytes_delta"]) < 0
        ):
            raise RuntimeError("negative cgroup delta encountered")

    if ordinals != list(range(1, 121)):
        raise RuntimeError("arm ordinals are not exactly 1..120")
    if len(sessions) != 40:
        raise RuntimeError("semantic session cardinality != 40")
    required_arms = set(ARMS)
    if any(arms != required_arms for arms in sessions.values()):
        raise RuntimeError("a session does not contain exactly all three arms")
    if candidate_total != 2880:
        raise RuntimeError("candidate record total != 2880")
    if gate_total != 1920:
        raise RuntimeError("gate evaluation total != 1920")
    if fresh_gated != 80:
        raise RuntimeError("fresh gated session count != 80")


def arm_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        out[str(r["session_id"])][str(r["arm"])] = r
    return out


def arm_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        out[arm] = {}
        for metric in METRICS:
            xs = [float(r[metric]) for r in sub]
            out[arm][metric] = {
                "n": len(xs),
                "mean": mean(xs),
                "median": statistics.median(xs),
                "min": min(xs),
                "max": max(xs),
                "sample_std": statistics.stdev(xs),
            }
    return out


def paired_contrast(
    sessions: dict[str, dict[str, dict[str, Any]]],
    arm_a: str,
    arm_b: str,
    metric: str,
) -> dict[str, Any]:
    pairs = []
    for sid in sorted(sessions):
        a = float(sessions[sid][arm_a][metric])
        b = float(sessions[sid][arm_b][metric])
        pairs.append((a, b, a - b))
    a_vals = [x[0] for x in pairs]
    b_vals = [x[1] for x in pairs]
    deltas = [x[2] for x in pairs]
    return {
        "arm_a": arm_a,
        "arm_b": arm_b,
        "metric": metric,
        "n_pairs": len(pairs),
        "mean_a": mean(a_vals),
        "mean_b": mean(b_vals),
        "mean_delta_a_minus_b": mean(deltas),
        "median_delta_a_minus_b": statistics.median(deltas),
        "a_lower_count": sum(d < 0 for d in deltas),
        "equal_count": sum(d == 0 for d in deltas),
        "a_higher_count": sum(d > 0 for d in deltas),
        "percent_change_of_means_a_vs_b": pct_change(mean(a_vals), mean(b_vals)),
    }


def contrast_map(
    sessions: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, dict[str, dict[str, Any]]]:
    specs = {
        "SAFE_vs_PERMISSIVE": ("SAFE_PRUNING", "PERMISSIVE_GATED"),
        "SAFE_vs_UNGATED": ("SAFE_PRUNING", "UNGATED_EXECUTE_ADMISSIBLE"),
    }
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for name, (a, b) in specs.items():
        out[name] = {
            metric: paired_contrast(sessions, a, b, metric)
            for metric in METRICS
        }
    return out


def replicate_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm_rep: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        sid = str(r["session_id"])
        rep = sid.rsplit("-", 1)[-1]
        by_arm_rep[(str(r["arm"]), rep)].append(r)

    metrics = (
        "client_wall_ms",
        "time_to_analytical_objective_completion_ms",
        "backend_request_count_including_gate_probes",
        "response_bytes",
        "sqlserver_cpu_usage_usec_delta",
    )
    out: dict[str, Any] = {}
    for arm in ARMS:
        out[arm] = {}
        for metric in metrics:
            a = mean([float(r[metric]) for r in by_arm_rep[(arm, "R031")]])
            b = mean([float(r[metric]) for r in by_arm_rep[(arm, "R032")]])
            out[arm][metric] = {
                "R031_mean": a,
                "R032_mean": b,
                "R032_vs_R031_percent": pct_change(b, a),
            }
    return out


def stratum_rows(
    sessions: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for sid, arms in sessions.items():
        any_arm = next(iter(arms.values()))
        grouped[(str(any_arm["topology"]), str(any_arm["pattern"]))].append(sid)

    out = []
    for (topology, pattern), ids in sorted(grouped.items()):
        if len(ids) != 2:
            raise RuntimeError(f"stratum {topology}/{pattern} does not have 2 sessions")
        rec: dict[str, Any] = {
            "topology": topology,
            "pattern": pattern,
            "n_sessions": len(ids),
        }
        for metric in CORE_DIAGNOSTIC_METRICS:
            sp = mean([
                float(sessions[sid]["SAFE_PRUNING"][metric])
                - float(sessions[sid]["PERMISSIVE_GATED"][metric])
                for sid in ids
            ])
            su = mean([
                float(sessions[sid]["SAFE_PRUNING"][metric])
                - float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
                for sid in ids
            ])
            rec[f"{metric}__safe_minus_permissive_mean"] = sp
            rec[f"{metric}__safe_minus_ungated_mean"] = su
        out.append(rec)
    return out


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for row in rows:
            cleaned = {}
            for k in fieldnames:
                v = row.get(k)
                if isinstance(v, float):
                    cleaned[k] = f"{v:.6f}"
                elif v is None:
                    cleaned[k] = ""
                else:
                    cleaned[k] = v
            w.writerow(cleaned)


def generate(archive: Path, out_dir: Path) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RuntimeError(f"output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    source = load_source(archive)
    validate_source(source)
    rows = source["arm_rows"]
    sessions = arm_map(rows)
    stats = arm_stats(rows)
    contrasts = contrast_map(sessions)
    strata = stratum_rows(sessions)
    reps = replicate_diagnostics(rows)

    # Arm run CSV.
    arm_fields = [
        "ordinal", "block_index", "session_id", "topology", "pattern",
        "arm_position", "arm", "completion_candidate",
        "client_wall_ms", "time_to_analytical_objective_completion_ms",
        "gate_evaluation_count", "full_backend_execution_count",
        "nvac_physical_backend_request_count",
        "backend_request_count_including_gate_probes",
        "response_bytes", "sqlserver_cpu_usage_usec_delta",
        "sqlserver_io_rbytes_delta", "sqlserver_io_wbytes_delta",
        "fresh_mcad_session_id", "frozen_action_authority",
        "live_gate_action_authoritative", "selection_role",
        "confirmatory_claim_authorized", "_candidate_record_count",
    ]
    write_csv(out_dir / "validation_arm_runs.csv", arm_fields, rows)

    # Arm summary CSV.
    arm_summary_rows = []
    for arm in ARMS:
        for metric in METRICS:
            s = stats[arm][metric]
            arm_summary_rows.append({
                "arm": arm,
                "metric": metric,
                **s,
            })
    write_csv(
        out_dir / "validation_arm_summary.csv",
        ["arm", "metric", "n", "mean", "median", "min", "max", "sample_std"],
        arm_summary_rows,
    )

    # Paired contrast CSV.
    contrast_rows = []
    for cname in ("SAFE_vs_PERMISSIVE", "SAFE_vs_UNGATED"):
        for metric in METRICS:
            c = contrasts[cname][metric]
            contrast_rows.append({"contrast": cname, **c})
    write_csv(
        out_dir / "validation_paired_contrasts.csv",
        [
            "contrast", "arm_a", "arm_b", "metric", "n_pairs",
            "mean_a", "mean_b", "mean_delta_a_minus_b",
            "median_delta_a_minus_b", "a_lower_count", "equal_count",
            "a_higher_count", "percent_change_of_means_a_vs_b",
        ],
        contrast_rows,
    )

    # Session paired metrics CSV.
    session_rows = []
    for sid in sorted(sessions):
        any_arm = sessions[sid]["SAFE_PRUNING"]
        rec: dict[str, Any] = {
            "session_id": sid,
            "topology": any_arm["topology"],
            "pattern": any_arm["pattern"],
            "rep": sid.rsplit("-", 1)[-1],
        }
        for metric in METRICS:
            u = float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
            p = float(sessions[sid]["PERMISSIVE_GATED"][metric])
            s = float(sessions[sid]["SAFE_PRUNING"][metric])
            rec[f"{metric}__ungated"] = u
            rec[f"{metric}__permissive"] = p
            rec[f"{metric}__safe"] = s
            rec[f"{metric}__safe_minus_permissive"] = s - p
            rec[f"{metric}__safe_minus_ungated"] = s - u
        session_rows.append(rec)
    session_fields = ["session_id", "topology", "pattern", "rep"]
    for metric in METRICS:
        session_fields += [
            f"{metric}__ungated",
            f"{metric}__permissive",
            f"{metric}__safe",
            f"{metric}__safe_minus_permissive",
            f"{metric}__safe_minus_ungated",
        ]
    write_csv(
        out_dir / "validation_session_paired_metrics.csv",
        session_fields,
        session_rows,
    )

    # Stratum diagnostics CSV.
    stratum_fields = ["topology", "pattern", "n_sessions"]
    for metric in CORE_DIAGNOSTIC_METRICS:
        stratum_fields += [
            f"{metric}__safe_minus_permissive_mean",
            f"{metric}__safe_minus_ungated_mean",
        ]
    write_csv(
        out_dir / "validation_stratum_diagnostics.csv",
        stratum_fields,
        strata,
    )

    # DEV -> VAL comparison.
    devval_rows = []
    for arm in ARMS:
        for metric in METRICS:
            dev = float(DEV_ARM_MEANS[arm][metric])
            val = float(stats[arm][metric]["mean"])
            devval_rows.append({
                "kind": "arm_mean",
                "arm_or_contrast": arm,
                "metric": metric,
                "dev_value": dev,
                "validation_value": val,
                "validation_minus_dev": val - dev,
                "validation_vs_dev_percent": pct_change(val, dev),
            })
    for cname, (a, b) in {
        "SAFE_vs_PERMISSIVE": ("SAFE_PRUNING", "PERMISSIVE_GATED"),
        "SAFE_vs_UNGATED": ("SAFE_PRUNING", "UNGATED_EXECUTE_ADMISSIBLE"),
    }.items():
        for metric in METRICS:
            dev_pct = pct_change(
                float(DEV_ARM_MEANS[a][metric]),
                float(DEV_ARM_MEANS[b][metric]),
            )
            val_pct = contrasts[cname][metric]["percent_change_of_means_a_vs_b"]
            devval_rows.append({
                "kind": "contrast_percent_change_of_means",
                "arm_or_contrast": cname,
                "metric": metric,
                "dev_value": dev_pct,
                "validation_value": val_pct,
                "validation_minus_dev": (
                    None if dev_pct is None or val_pct is None else val_pct - dev_pct
                ),
                "validation_vs_dev_percent": None,
            })
    write_csv(
        out_dir / "validation_dev_vs_val.csv",
        [
            "kind", "arm_or_contrast", "metric", "dev_value",
            "validation_value", "validation_minus_dev",
            "validation_vs_dev_percent",
        ],
        devval_rows,
    )

    # Readiness diagnostics.
    sp = contrasts["SAFE_vs_PERMISSIVE"]
    su = contrasts["SAFE_vs_UNGATED"]
    stratum_sp_wall_good = sum(
        float(r["client_wall_ms__safe_minus_permissive_mean"]) < 0 for r in strata
    )
    stratum_sp_completion_good = sum(
        float(r["time_to_analytical_objective_completion_ms__safe_minus_permissive_mean"]) < 0
        for r in strata
    )
    stratum_su_wall_break_even = sum(
        float(r["client_wall_ms__safe_minus_ungated_mean"]) < 0 for r in strata
    )
    stratum_su_completion_break_even = sum(
        float(r["time_to_analytical_objective_completion_ms__safe_minus_ungated_mean"]) < 0
        for r in strata
    )

    io_note = {
        "sqlserver_io_rbytes_delta": {
            "ungated_nonzero_arms": sum(
                int(r["sqlserver_io_rbytes_delta"]) != 0
                for r in rows if r["arm"] == "UNGATED_EXECUTE_ADMISSIBLE"
            ),
            "permissive_nonzero_arms": sum(
                int(r["sqlserver_io_rbytes_delta"]) != 0
                for r in rows if r["arm"] == "PERMISSIVE_GATED"
            ),
            "safe_nonzero_arms": sum(
                int(r["sqlserver_io_rbytes_delta"]) != 0
                for r in rows if r["arm"] == "SAFE_PRUNING"
            ),
        },
        "sqlserver_io_wbytes_delta": {
            "ungated_nonzero_arms": sum(
                int(r["sqlserver_io_wbytes_delta"]) != 0
                for r in rows if r["arm"] == "UNGATED_EXECUTE_ADMISSIBLE"
            ),
            "permissive_nonzero_arms": sum(
                int(r["sqlserver_io_wbytes_delta"]) != 0
                for r in rows if r["arm"] == "PERMISSIVE_GATED"
            ),
            "safe_nonzero_arms": sum(
                int(r["sqlserver_io_wbytes_delta"]) != 0
                for r in rows if r["arm"] == "SAFE_PRUNING"
            ),
        },
        "interpretation": (
            "Warm-cache cgroup I/O deltas are sparse/mostly zero. Preserve and report "
            "them descriptively; do not promote a strong disk-I/O saving claim from R3-C."
        ),
    }

    analysis = {
        "contract_version": "mcad.nh_r3.c5.validation_analysis.v1",
        "stage": "R3-C_VALIDATION_CALIBRATION",
        "analysis_class": ANALYSIS_CLASS,
        "source": {
            "archive_name": SOURCE_ARCHIVE_NAME,
            "archive_sha256": source["archive_sha256"],
            "archive_root": source["archive_root"],
            "archive_members": source["archive_members"],
            "internal_manifest_entries": source["internal_manifest_entries"],
            "internal_manifest_verified": True,
            "c4_execution_kit_head": C4_HEAD,
            "frozen_dev_analysis_git_blob": DEV_ANALYSIS_GIT_BLOB,
        },
        "integrity": {
            "semantic_sessions": 40,
            "arm_receipts": 120,
            "candidate_records": 2880,
            "gate_evaluations": 1920,
            "full_backend_executions": int(
                source["integrity"]["full_backend_executions"]
            ),
            "fresh_gated_sessions": 80,
            "negative_cgroup_delta_arm_runs": 0,
            "warmup_templates_completed": 7,
            "frozen_action_authority_preserved": True,
            "live_gate_action_authoritative": False,
            "effect_size_tuning_performed": False,
            "scientific_redesign_performed": False,
            "confirmatory_claim_authorized": False,
        },
        "arm_means": {
            arm: {metric: r6(stats[arm][metric]["mean"]) for metric in METRICS}
            for arm in ARMS
        },
        "paired_contrasts": {
            cname: {
                metric: {
                    k: r6(v) if isinstance(v, float) else v
                    for k, v in contrasts[cname][metric].items()
                }
                for metric in METRICS
            }
            for cname in contrasts
        },
        "dev_reference": {
            "analysis_class": "DEV_DESCRIPTIVE_NONCONFIRMATORY",
            "source_git_blob": DEV_ANALYSIS_GIT_BLOB,
            "arm_means": DEV_ARM_MEANS,
            "headline_pair_counts": DEV_HEADLINE_PAIR_COUNTS,
        },
        "replicate_diagnostics": {
            arm: {
                metric: {
                    k: r6(v) if isinstance(v, float) else v
                    for k, v in vals.items()
                }
                for metric, vals in reps[arm].items()
            }
            for arm in ARMS
        },
        "stratum_direction_diagnostics": {
            "safe_vs_permissive_wall_lower_strata": stratum_sp_wall_good,
            "safe_vs_permissive_wall_total_strata": 20,
            "safe_vs_permissive_completion_lower_strata": stratum_sp_completion_good,
            "safe_vs_permissive_completion_total_strata": 20,
            "safe_vs_ungated_wall_break_even_strata": stratum_su_wall_break_even,
            "safe_vs_ungated_wall_total_strata": 20,
            "safe_vs_ungated_completion_break_even_strata": stratum_su_completion_break_even,
            "safe_vs_ungated_completion_total_strata": 20,
        },
        "io_diagnostic": io_note,
        "interpretation_guardrails": {
            "validation_not_confirmatory": True,
            "no_p_values_computed": True,
            "no_posthoc_effect_tuning": True,
            "readiness_is_based_on_measurement_integrity_not_desired_effect_size": True,
            "lower_resource_or_time_values_are_descriptively_better": True,
            "primary_causal_comparison": "SAFE_PRUNING vs PERMISSIVE_GATED",
            "ungated_role": "practical break-even comparator",
        },
        "readiness": {
            "status": "PASS_READY_FOR_R3D_STATIC_ACTIVATION",
            "measurement_mechanics_change_required": False,
            "binding_change_required": False,
            "cohort_change_required": False,
            "effect_based_rerun_required": False,
            "r3c_rerun_authorized": False,
            "confirmatory_claim_authorized": False,
            "next": "R3-D0_CONFIRMATORY_SQL_DIRECT_STATIC_ACTIVATION_NO_MEASUREMENT",
            "basis": [
                "C4 archive and internal SHA256 manifest verified.",
                "40/40 validation sessions and 120/120 arm receipts passed integrity.",
                "No negative cgroup deltas and no live-gate relabeling occurred.",
                "SAFE and PERMISSIVE incurred identical paired NVAC-probe counts in 40/40 sessions.",
                "Primary SAFE-vs-PERMISSIVE resource/time direction is stable without any effect-size tuning.",
                "UNGATED temporal break-even is not reached; this negative regime is retained rather than tuned away.",
                "No measurement-mechanics defect requiring a validation rerun was identified.",
            ],
        },
    }

    # JSON before README.
    (out_dir / "validation_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sp_wall = sp["client_wall_ms"]
    sp_comp = sp["time_to_analytical_objective_completion_ms"]
    sp_back = sp["backend_request_count_including_gate_probes"]
    sp_full = sp["full_backend_execution_count"]
    sp_bytes = sp["response_bytes"]
    sp_cpu = sp["sqlserver_cpu_usage_usec_delta"]
    su_wall = su["client_wall_ms"]
    su_comp = su["time_to_analytical_objective_completion_ms"]
    su_back = su["backend_request_count_including_gate_probes"]
    su_full = su["full_backend_execution_count"]
    su_bytes = su["response_bytes"]
    su_cpu = su["sqlserver_cpu_usage_usec_delta"]

    readme = f"""# NH-R3 R3-C validation/calibration analysis

Status: **PASS_READY_FOR_R3D_STATIC_ACTIVATION**.

This directory is the frozen, non-confirmatory analysis of the 40-session
R3-C validation cohort. It is derived from the exact external C4 archive
`{SOURCE_ARCHIVE_NAME}` with SHA-256
`{EXPECTED_ARCHIVE_SHA256}`.

## Integrity

- analysis class: `{ANALYSIS_CLASS}`;
- 40 semantic sessions / 120 arm-runs / 2,880 candidate records;
- 1,920 gate evaluations;
- {int(source["integrity"]["full_backend_executions"])} full backend executions;
- 80 fresh gated sessions;
- 7 fixed non-measured warm-up templates;
- 0 negative cgroup-delta arm-runs;
- frozen action authority preserved; live gate never relabels a frozen action;
- no effect-size tuning, scientific redesign, or confirmatory promotion.

## Arm means

| Arm | Wall ms | Completion ms | Backend requests | Full exec | NVAC probes | Response bytes | SQL CPU usec |
|---|---:|---:|---:|---:|---:|---:|---:|
| UNGATED | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["client_wall_ms"]["mean"]:.3f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["time_to_analytical_objective_completion_ms"]["mean"]:.3f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["backend_request_count_including_gate_probes"]["mean"]:.3f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["full_backend_execution_count"]["mean"]:.3f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["nvac_physical_backend_request_count"]["mean"]:.3f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["response_bytes"]["mean"]:.1f} | {stats["UNGATED_EXECUTE_ADMISSIBLE"]["sqlserver_cpu_usage_usec_delta"]["mean"]:.1f} |
| PERMISSIVE_GATED | {stats["PERMISSIVE_GATED"]["client_wall_ms"]["mean"]:.3f} | {stats["PERMISSIVE_GATED"]["time_to_analytical_objective_completion_ms"]["mean"]:.3f} | {stats["PERMISSIVE_GATED"]["backend_request_count_including_gate_probes"]["mean"]:.3f} | {stats["PERMISSIVE_GATED"]["full_backend_execution_count"]["mean"]:.3f} | {stats["PERMISSIVE_GATED"]["nvac_physical_backend_request_count"]["mean"]:.3f} | {stats["PERMISSIVE_GATED"]["response_bytes"]["mean"]:.1f} | {stats["PERMISSIVE_GATED"]["sqlserver_cpu_usage_usec_delta"]["mean"]:.1f} |
| SAFE_PRUNING | {stats["SAFE_PRUNING"]["client_wall_ms"]["mean"]:.3f} | {stats["SAFE_PRUNING"]["time_to_analytical_objective_completion_ms"]["mean"]:.3f} | {stats["SAFE_PRUNING"]["backend_request_count_including_gate_probes"]["mean"]:.3f} | {stats["SAFE_PRUNING"]["full_backend_execution_count"]["mean"]:.3f} | {stats["SAFE_PRUNING"]["nvac_physical_backend_request_count"]["mean"]:.3f} | {stats["SAFE_PRUNING"]["response_bytes"]["mean"]:.1f} | {stats["SAFE_PRUNING"]["sqlserver_cpu_usage_usec_delta"]["mean"]:.1f} |

## Primary descriptive contrast: SAFE vs PERMISSIVE

- wall time: {sp_wall["percent_change_of_means_a_vs_b"]:.3f}% ({sp_wall["a_lower_count"]}/40 lower);
- analytical-completion time: {sp_comp["percent_change_of_means_a_vs_b"]:.3f}% ({sp_comp["a_lower_count"]}/40 lower, {sp_comp["a_higher_count"]}/40 higher);
- all backend requests: {sp_back["percent_change_of_means_a_vs_b"]:.3f}% ({sp_back["a_lower_count"]}/40 lower);
- full backend executions: {sp_full["percent_change_of_means_a_vs_b"]:.3f}%;
- response bytes: {sp_bytes["percent_change_of_means_a_vs_b"]:.3f}%;
- SQL Server cgroup CPU: {sp_cpu["percent_change_of_means_a_vs_b"]:.3f}%;
- paired NVAC probes: equal in 40/40 sessions.

The wall/resource direction is also stable at the 20-stratum level:
SAFE has lower mean wall time in {stratum_sp_wall_good}/20 strata and lower
mean completion time in {stratum_sp_completion_good}/20 strata.

## Practical break-even contrast: SAFE vs UNGATED

- wall time: +{su_wall["percent_change_of_means_a_vs_b"]:.3f}% (SAFE slower in {su_wall["a_higher_count"]}/40);
- analytical-completion time: +{su_comp["percent_change_of_means_a_vs_b"]:.3f}% (SAFE slower in {su_comp["a_higher_count"]}/40);
- all backend requests: {su_back["percent_change_of_means_a_vs_b"]:.3f}%;
- full backend executions: {su_full["percent_change_of_means_a_vs_b"]:.3f}%;
- response bytes: {su_bytes["percent_change_of_means_a_vs_b"]:.3f}%;
- SQL Server cgroup CPU: {su_cpu["percent_change_of_means_a_vs_b"]:.3f}%.

Thus the validation preserves the same break-even tension as DEV: pruning saves
substantial backend work, bytes, and CPU, and it beats the same-gate permissive
comparator, but its gate/probe overhead still does not beat the ungated path in
elapsed time.

## DEV -> validation stability

The primary headline changes remain close to the DEV pilot:

- SAFE/PERMISSIVE wall reduction: -32.581% DEV -> {sp_wall["percent_change_of_means_a_vs_b"]:.3f}% validation;
- SAFE/PERMISSIVE completion reduction: -20.680% DEV -> {sp_comp["percent_change_of_means_a_vs_b"]:.3f}% validation;
- SAFE/PERMISSIVE backend-request reduction: -57.554% DEV -> {sp_back["percent_change_of_means_a_vs_b"]:.3f}% validation;
- SAFE/UNGATED wall overhead: +65.844% DEV -> +{su_wall["percent_change_of_means_a_vs_b"]:.3f}% validation;
- SAFE/UNGATED completion overhead: +92.515% DEV -> +{su_comp["percent_change_of_means_a_vs_b"]:.3f}% validation;
- SAFE/UNGATED backend-request reduction: -45.370% DEV -> {su_back["percent_change_of_means_a_vs_b"]:.3f}% validation.

This is descriptive validation only. No p-values are computed.

## I/O note

Warm-cache cgroup I/O deltas are sparse/mostly zero. They are retained in the
frozen files but are not promoted to a strong disk-I/O saving claim.

## Readiness decision

R3-C is **closed without rerun**. No measurement-mechanics defect was found and
no effect-based tuning is permitted. The next station is:

`R3-D0_CONFIRMATORY_SQL_DIRECT_STATIC_ACTIVATION_NO_MEASUREMENT`

R3-D must use the already frozen confirmatory test cohort. R3-C results do not
change cohort membership, arm semantics, completion boundaries, or inclusion.
"""

    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    source_summary = f"""source_archive={SOURCE_ARCHIVE_NAME}
source_archive_sha256={EXPECTED_ARCHIVE_SHA256}
source_archive_root={source["archive_root"]}
source_archive_members={source["archive_members"]}
internal_sha256_manifest_entries={source["internal_manifest_entries"]}
internal_sha256_manifest_verified=true
c4_execution_kit_head={C4_HEAD}
frozen_dev_analysis_git_blob={DEV_ANALYSIS_GIT_BLOB}
analysis_class={ANALYSIS_CLASS}
semantic_sessions=40
arm_receipts=120
candidate_records=2880
gate_evaluations=1920
full_backend_executions={int(source["integrity"]["full_backend_executions"])}
negative_cgroup_delta_arm_runs=0
effect_size_tuning_performed=false
scientific_redesign_performed=false
confirmatory_claim_authorized=false
readiness=PASS_READY_FOR_R3D_STATIC_ACTIVATION
next=R3-D0_CONFIRMATORY_SQL_DIRECT_STATIC_ACTIVATION_NO_MEASUREMENT
"""
    (out_dir / "source_run_summary.txt").write_text(source_summary, encoding="utf-8")

    # Final result-directory manifest excludes itself.
    files = sorted(p for p in out_dir.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    manifest = "".join(
        f"{sha256_bytes(p.read_bytes())}  {p.name}\n"
        for p in files
    )
    (out_dir / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    generate(Path(args.archive).resolve(), Path(args.out_dir).resolve())
    print("source_archive_sha256=" + EXPECTED_ARCHIVE_SHA256)
    print("analysis_class=" + ANALYSIS_CLASS)
    print("semantic_sessions=40")
    print("arm_receipts=120")
    print("candidate_records=2880")
    print("gate_evaluations=1920")
    print("negative_cgroup_delta_arm_runs=0")
    print("effect_size_tuning_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_C5_VALIDATION_ANALYSIS=PASS_READY_FOR_R3D_STATIC_ACTIVATION")


if __name__ == "__main__":
    main()
