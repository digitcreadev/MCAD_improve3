#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R4_HEAD = "eae990ad9125896cb733261177a0d7dbb8ae934f"
SOURCE_ARCHIVE_NAME = "MCAD_R3_D3_REPLACEMENT_PRIMARY_RESULTS_20260823T224457Z.tar.gz"
EXPECTED_ARCHIVE_SHA256 = "8ac00f467d7fb2235e6a4df2850278e1893103279077178ffe610db995a91ff5"

D0_PROTOCOL_BLOB = "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb"
D0_CONTRACT_BLOB = "6c608b951bca9b262cc69bb7964a48cec79c62b1"
R4_CONTRACT_BLOB = "9c836096dac1727fa859a0accc8800ac3c6de89d"
R4_DRIVER_BLOB = "8358bd8e5ca559f928e8da78e2de5dcc41bf687e"

SEED_NAMESPACE = "a550a533086d3eafe6fa4512caab03a85b3c8a06b7efb7c805c4da841f5ef8e0"
SIGN_FLIP_B = 100000
BOOTSTRAP_B = 20000
ALPHA = 0.05

ARMS = (
    "UNGATED_EXECUTE_ADMISSIBLE",
    "PERMISSIVE_GATED",
    "SAFE_PRUNING",
)

PRIMARY_METRICS = (
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
)

ALL_METRICS = PRIMARY_METRICS


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def seed_int(material: str) -> int:
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest(), "big")


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def pct_change(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return (a / b - 1.0) * 100.0


def percentile_linear(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise RuntimeError("percentile on empty values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    w = pos - lo
    return sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w


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
        raise RuntimeError(f"expected exactly one archive root, got {roots}")
    return roots[0]


def verify_internal_manifest(tf: tarfile.TarFile, root: str) -> tuple[int, list[str]]:
    manifest_name = f"{root}/SHA256SUMS.txt"
    raw = read_member(tf, manifest_name).decode("utf-8")
    bad: list[str] = []
    count = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        expected, rel = line.split("  ", 1)
        rel_clean = rel[2:] if rel.startswith("./") else rel
        actual = sha256_bytes(read_member(tf, f"{root}/{rel_clean}"))
        count += 1
        if actual != expected:
            bad.append(rel)
    return count, bad


def validate_repo_authorities(repo: Path) -> None:
    checks = (
        (
            repo / R3 / "config/r3_d0_confirmatory_inference_protocol.json",
            D0_PROTOCOL_BLOB,
            "D0 inference protocol",
        ),
        (
            repo / R3 / "config/r3_d0_confirmatory_static_activation_contract.json",
            D0_CONTRACT_BLOB,
            "D0 static activation contract",
        ),
        (
            repo / R3 / "config/r3_d3_r4_replacement_execution_contract.json",
            R4_CONTRACT_BLOB,
            "R4 execution contract",
        ),
        (
            repo / R3 / "implementation/r3_d3_r4_replacement_primary_one_shot.py",
            R4_DRIVER_BLOB,
            "R4 replacement driver",
        ),
    )
    for path, expected, label in checks:
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"{label} blob changed: {actual}")

    protocol = json.loads(
        (repo / R3 / "config/r3_d0_confirmatory_inference_protocol.json").read_text(
            encoding="utf-8"
        )
    )
    family = protocol.get("primary_endpoint_family") or {}
    if family.get("comparison") != "SAFE_PRUNING - PERMISSIVE_GATED":
        raise RuntimeError("primary comparison changed")
    if tuple(family.get("metrics") or []) != PRIMARY_METRICS:
        raise RuntimeError("primary metric family changed")
    if int((family.get("permutation_test") or {}).get("replicates", -1)) != SIGN_FLIP_B:
        raise RuntimeError("sign-flip replicate count changed")
    if int((family.get("confidence_interval") or {}).get("replicates", -1)) != BOOTSTRAP_B:
        raise RuntimeError("bootstrap replicate count changed")
    if float(family.get("familywise_alpha", -1)) != ALPHA:
        raise RuntimeError("familywise alpha changed")
    if (family.get("permutation_test") or {}).get("seed_namespace_sha256") != SEED_NAMESPACE:
        raise RuntimeError("seed namespace changed")


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

        def load_json(rel: str) -> dict[str, Any]:
            return json.loads(read_member(tf, f"{root}/{rel}").decode("utf-8"))

        integrity = load_json("integrity_summary.json")
        attempt = load_json("attempt_manifest.json")
        handoff = load_json("handoff.json")
        replacement_lineage = load_json("replacement_lineage.json")
        replacement_handoff = load_json("replacement_handoff.json")
        warmup = load_json("warmup_receipt.json")
        summary = load_json("results/confirmatory_primary_summary.json")

        prefix = f"{root}/results/arm_runs/"
        arm_names = sorted(
            n for n in names if n.startswith(prefix) and n.endswith(".json")
        )
        rows: list[dict[str, Any]] = []
        for name in arm_names:
            row = json.loads(read_member(tf, name).decode("utf-8"))
            records = row.pop("candidate_records")
            row["_candidate_record_count"] = len(records)
            rows.append(row)

    return {
        "archive_sha256": actual_sha,
        "archive_root": root,
        "archive_members": len(names),
        "internal_manifest_entries": manifest_count,
        "integrity": integrity,
        "attempt": attempt,
        "handoff": handoff,
        "replacement_lineage": replacement_lineage,
        "replacement_handoff": replacement_handoff,
        "warmup": warmup,
        "summary": summary,
        "arm_rows": sorted(rows, key=lambda r: int(r["ordinal"])),
    }


def validate_source(source: dict[str, Any]) -> None:
    integrity = source["integrity"]
    attempt = source["attempt"]
    handoff = source["handoff"]
    lineage = source["replacement_lineage"]
    replacement_handoff = source["replacement_handoff"]
    warmup = source["warmup"]
    summary = source["summary"]
    rows = source["arm_rows"]

    if integrity.get("integrity_status") != "PASS":
        raise RuntimeError("replacement integrity is not PASS")
    expected_integrity = {
        "semantic_sessions": 300,
        "arm_receipts": 900,
        "candidate_records": 21600,
        "gate_evaluations": 14400,
        "full_backend_executions": 14580,
        "fresh_gated_sessions": 600,
        "negative_cgroup_delta_arm_runs": 0,
        "warmup_templates_completed": 7,
    }
    for key, value in expected_integrity.items():
        if int(integrity.get(key, -1)) != value:
            raise RuntimeError(f"integrity mismatch: {key}")

    if integrity.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("integrity analysis class changed")
    if integrity.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback activated")
    if integrity.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("effect-size tuning flag violated")
    if integrity.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("measurement prematurely authorized confirmatory claim")

    if attempt.get("status") != "COMPLETE_INTEGRITY_PASS":
        raise RuntimeError("attempt did not close COMPLETE_INTEGRITY_PASS")
    if handoff.get("next") != "R3-D4_CONFIRMATORY_INFERENCE_AND_FREEZE":
        raise RuntimeError("D3 handoff next stage changed")

    if lineage.get("integrity_status") != "PASS":
        raise RuntimeError("replacement lineage integrity not PASS")
    if lineage.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("replacement lineage scope changed")
    if lineage.get("interrupted_attempt_receipts_reused") is not False:
        raise RuntimeError("interrupted receipts were reused")
    if lineage.get("resume_from_arm_298") is not False:
        raise RuntimeError("replacement resumed interrupted attempt")
    if lineage.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback activated in lineage")
    if lineage.get("effect_analysis_performed") is not False:
        raise RuntimeError("effect analysis occurred during measurement")
    if lineage.get("replacement_authorization_head") != "41b2369a83a3073d986691bdf7293d322d8d7851":
        raise RuntimeError("replacement lineage authorization head changed")

    if replacement_handoff.get("integrity_status") != "PASS":
        raise RuntimeError("replacement handoff integrity not PASS")
    if replacement_handoff.get("partial_attempt_reused") is not False:
        raise RuntimeError("replacement handoff indicates partial reuse")
    if replacement_handoff.get("fallback_120_activated") is not False:
        raise RuntimeError("replacement handoff indicates fallback")
    if replacement_handoff.get("next") != "R3-D4_CONFIRMATORY_INFERENCE_AND_FREEZE":
        raise RuntimeError("replacement handoff next stage changed")

    warm_rows = warmup.get("templates")
    if not isinstance(warm_rows, list) or len(warm_rows) != 7:
        raise RuntimeError("warmup count != 7")
    if warmup.get("measured") is not False:
        raise RuntimeError("warmup unexpectedly measured")

    if summary.get("analysis_class") != "CONFIRMATORY_PRIMARY_SQL_DIRECT":
        raise RuntimeError("summary analysis class changed")
    if summary.get("selection_role") != "CONFIRMATORY_PRIMARY":
        raise RuntimeError("summary selection role changed")
    if summary.get("fallback_120_activated") is not False:
        raise RuntimeError("summary fallback activated")
    if summary.get("confirmatory_claim_authorized") is not False:
        raise RuntimeError("summary confirmatory claim prematurely authorized")
    if summary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("summary effect-size tuning flag violated")

    if len(rows) != 900:
        raise RuntimeError(f"expected 900 arm receipts, got {len(rows)}")

    sessions: dict[str, set[str]] = defaultdict(set)
    strata: dict[tuple[str, str], set[str]] = defaultdict(set)
    ordinals: list[int] = []
    candidate_total = 0
    gate_total = 0
    full_total = 0
    fresh_gated = 0

    for r in rows:
        sid = str(r["session_id"])
        arm = str(r["arm"])
        ordinals.append(int(r["ordinal"]))
        sessions[sid].add(arm)
        strata[(str(r["topology"]), str(r["pattern"]))].add(sid)
        candidate_total += int(r["_candidate_record_count"])
        gate_total += int(r["gate_evaluation_count"])
        full_total += int(r["full_backend_execution_count"])
        if arm != "UNGATED_EXECUTE_ADMISSIBLE" and r.get("fresh_mcad_session_id"):
            fresh_gated += 1

        if r.get("selection_role") != "CONFIRMATORY_PRIMARY":
            raise RuntimeError("arm receipt selection role changed")
        if r.get("frozen_action_authority") != "NH_R2_R3_BINDING":
            raise RuntimeError("frozen action authority changed")
        if r.get("live_gate_action_authoritative") is not False:
            raise RuntimeError("live gate became authoritative")
        if r.get("confirmatory_claim_authorized") is not False:
            raise RuntimeError("arm receipt prematurely authorizes claim")
        if r.get("effect_size_tuning_performed") is not False:
            raise RuntimeError("arm receipt effect-size tuning flag violated")
        if int(r["_candidate_record_count"]) != 24:
            raise RuntimeError("candidate record count per arm != 24")
        if (
            int(r["sqlserver_cpu_usage_usec_delta"]) < 0
            or int(r["sqlserver_io_rbytes_delta"]) < 0
            or int(r["sqlserver_io_wbytes_delta"]) < 0
        ):
            raise RuntimeError("negative cgroup delta encountered")

    if ordinals != list(range(1, 901)):
        raise RuntimeError("arm ordinals are not exactly 1..900")
    if len(sessions) != 300:
        raise RuntimeError("semantic session cardinality != 300")
    if any(arms != set(ARMS) for arms in sessions.values()):
        raise RuntimeError("a semantic session does not contain exactly three frozen arms")
    if len(strata) != 20 or set(len(v) for v in strata.values()) != {15}:
        raise RuntimeError("stratum allocation is not 20 x 15")
    if candidate_total != 21600:
        raise RuntimeError("candidate total != 21600")
    if gate_total != 14400:
        raise RuntimeError("gate total != 14400")
    if full_total != 14580:
        raise RuntimeError("full backend execution total != 14580")
    if fresh_gated != 600:
        raise RuntimeError("fresh gated session total != 600")


def session_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        out[str(row["session_id"])][str(row["arm"])] = row
    return out


def arm_means(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        out[arm] = {
            metric: mean([float(r[metric]) for r in sub])
            for metric in ALL_METRICS
        }
    return out


def sign_flip_test(deltas: list[float], metric: str) -> dict[str, Any]:
    obs = mean(deltas)
    rng = random.Random(seed_int(f"{SEED_NAMESPACE}|{metric}"))
    count = 0
    n = len(deltas)
    for _ in range(SIGN_FLIP_B):
        total = 0.0
        for d in deltas:
            total += d if rng.getrandbits(1) else -d
        t = total / n
        if t <= obs:
            count += 1
    p = (1.0 + count) / (SIGN_FLIP_B + 1.0)
    return {
        "observed_mean_difference": obs,
        "permutations": SIGN_FLIP_B,
        "extreme_count_t_perm_le_t_obs": count,
        "raw_one_sided_p": p,
        "seed_sha256": hashlib.sha256(
            f"{SEED_NAMESPACE}|{metric}".encode("utf-8")
        ).hexdigest(),
    }


def bootstrap_both(
    session_ids_by_stratum: dict[tuple[str, str], list[str]],
    sessions: dict[str, dict[str, dict[str, Any]]],
    metric: str,
) -> tuple[list[float], list[float], str]:
    seed_material = f"{SEED_NAMESPACE}|bootstrap|{metric}"
    rng = random.Random(seed_int(seed_material))
    sp: list[float] = []
    su: list[float] = []
    strata = [session_ids_by_stratum[k] for k in sorted(session_ids_by_stratum)]
    for ids in strata:
        if len(ids) != 15:
            raise RuntimeError("bootstrap stratum does not have 15 sessions")

    for _ in range(BOOTSTRAP_B):
        total_sp = 0.0
        total_su = 0.0
        n = 0
        for ids in strata:
            for _j in range(15):
                sid = ids[rng.randrange(15)]
                safe = float(sessions[sid]["SAFE_PRUNING"][metric])
                perm = float(sessions[sid]["PERMISSIVE_GATED"][metric])
                ung = float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
                total_sp += safe - perm
                total_su += safe - ung
                n += 1
        sp.append(total_sp / n)
        su.append(total_su / n)
    return sp, su, hashlib.sha256(seed_material.encode("utf-8")).hexdigest()


def holm_adjust(raw_p: dict[str, float]) -> dict[str, dict[str, Any]]:
    m = len(raw_p)
    ordered = sorted(raw_p.items(), key=lambda kv: (kv[1], kv[0]))
    adjusted_running = 0.0
    out: dict[str, dict[str, Any]] = {}
    for rank, (metric, p) in enumerate(ordered, start=1):
        candidate = min(1.0, (m - rank + 1) * p)
        adjusted_running = max(adjusted_running, candidate)
        out[metric] = {
            "holm_rank": rank,
            "raw_one_sided_p": p,
            "holm_adjusted_one_sided_p": min(1.0, adjusted_running),
        }
    return out


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            clean = {}
            for k in fields:
                v = row.get(k)
                if isinstance(v, float):
                    clean[k] = f"{v:.12g}"
                elif v is None:
                    clean[k] = ""
                elif isinstance(v, bool):
                    clean[k] = "true" if v else "false"
                else:
                    clean[k] = v
            w.writerow(clean)


def generate(repo: Path, archive: Path, out_dir: Path) -> None:
    if out_dir.exists():
        raise RuntimeError(f"D4 output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    validate_repo_authorities(repo)
    source = load_source(archive)
    validate_source(source)

    rows = source["arm_rows"]
    sessions = session_map(rows)
    means = arm_means(rows)

    by_stratum: dict[tuple[str, str], list[str]] = defaultdict(list)
    for sid in sorted(sessions):
        any_arm = sessions[sid]["SAFE_PRUNING"]
        by_stratum[(str(any_arm["topology"]), str(any_arm["pattern"]))].append(sid)
    for key in by_stratum:
        by_stratum[key] = sorted(by_stratum[key])

    primary_work: dict[str, dict[str, Any]] = {}
    secondary_work: dict[str, dict[str, Any]] = {}
    raw_p: dict[str, float] = {}
    session_rows: list[dict[str, Any]] = []

    for sid in sorted(sessions):
        safe = sessions[sid]["SAFE_PRUNING"]
        rec: dict[str, Any] = {
            "session_id": sid,
            "topology": safe["topology"],
            "pattern": safe["pattern"],
            "rep": sid.rsplit("-", 1)[-1],
        }
        for metric in ALL_METRICS:
            u = float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
            p = float(sessions[sid]["PERMISSIVE_GATED"][metric])
            s = float(sessions[sid]["SAFE_PRUNING"][metric])
            rec[f"{metric}__ungated"] = u
            rec[f"{metric}__permissive"] = p
            rec[f"{metric}__safe"] = s
            rec[f"{metric}__safe_minus_permissive"] = s - p
            rec[f"{metric}__safe_minus_ungated"] = s - u
        session_rows.append(rec)

    for metric in PRIMARY_METRICS:
        sp_deltas = [
            float(sessions[sid]["SAFE_PRUNING"][metric])
            - float(sessions[sid]["PERMISSIVE_GATED"][metric])
            for sid in sorted(sessions)
        ]
        su_deltas = [
            float(sessions[sid]["SAFE_PRUNING"][metric])
            - float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
            for sid in sorted(sessions)
        ]

        perm = sign_flip_test(sp_deltas, metric)
        raw_p[metric] = float(perm["raw_one_sided_p"])

        boot_sp, boot_su, boot_seed = bootstrap_both(by_stratum, sessions, metric)
        boot_sp.sort()
        boot_su.sort()

        primary_work[metric] = {
            "metric": metric,
            "n_pairs": 300,
            "mean_safe": means["SAFE_PRUNING"][metric],
            "mean_permissive": means["PERMISSIVE_GATED"][metric],
            "mean_difference_safe_minus_permissive": mean(sp_deltas),
            "median_difference_safe_minus_permissive": statistics.median(sp_deltas),
            "safe_lower_count": sum(d < 0 for d in sp_deltas),
            "equal_count": sum(d == 0 for d in sp_deltas),
            "safe_higher_count": sum(d > 0 for d in sp_deltas),
            "percent_change_of_means_safe_vs_permissive": pct_change(
                means["SAFE_PRUNING"][metric], means["PERMISSIVE_GATED"][metric]
            ),
            "ci95_lower_mean_difference": percentile_linear(boot_sp, 0.025),
            "ci95_upper_mean_difference": percentile_linear(boot_sp, 0.975),
            "bootstrap_replicates": BOOTSTRAP_B,
            "bootstrap_seed_sha256": boot_seed,
            **perm,
        }

        secondary_work[metric] = {
            "metric": metric,
            "n_pairs": 300,
            "mean_safe": means["SAFE_PRUNING"][metric],
            "mean_ungated": means["UNGATED_EXECUTE_ADMISSIBLE"][metric],
            "mean_difference_safe_minus_ungated": mean(su_deltas),
            "median_difference_safe_minus_ungated": statistics.median(su_deltas),
            "safe_lower_count": sum(d < 0 for d in su_deltas),
            "equal_count": sum(d == 0 for d in su_deltas),
            "safe_higher_count": sum(d > 0 for d in su_deltas),
            "percent_change_of_means_safe_vs_ungated": pct_change(
                means["SAFE_PRUNING"][metric],
                means["UNGATED_EXECUTE_ADMISSIBLE"][metric],
            ),
            "ci95_lower_mean_difference": percentile_linear(boot_su, 0.025),
            "ci95_upper_mean_difference": percentile_linear(boot_su, 0.975),
            "bootstrap_replicates": BOOTSTRAP_B,
            "bootstrap_seed_sha256": boot_seed,
            "confirmatory_p_value_computed": False,
        }

    holm = holm_adjust(raw_p)

    primary_rows: list[dict[str, Any]] = []
    confirmed_metrics: list[str] = []
    for metric in PRIMARY_METRICS:
        rec = dict(primary_work[metric])
        rec.update(holm[metric])
        confirmed = (
            rec["mean_difference_safe_minus_permissive"] < 0
            and rec["holm_adjusted_one_sided_p"] <= ALPHA
        )
        rec["confirmatory_reduction_confirmed"] = confirmed
        if confirmed:
            confirmed_metrics.append(metric)
        primary_rows.append(rec)

    secondary_rows = [secondary_work[m] for m in PRIMARY_METRICS]

    arm_rows = []
    for arm in ARMS:
        for metric in ALL_METRICS:
            arm_rows.append(
                {
                    "arm": arm,
                    "metric": metric,
                    "n": 300,
                    "mean": means[arm][metric],
                }
            )

    stratum_rows: list[dict[str, Any]] = []
    for (topology, pattern), ids in sorted(by_stratum.items()):
        rec: dict[str, Any] = {
            "topology": topology,
            "pattern": pattern,
            "n_sessions": len(ids),
        }
        for metric in PRIMARY_METRICS:
            sp = [
                float(sessions[sid]["SAFE_PRUNING"][metric])
                - float(sessions[sid]["PERMISSIVE_GATED"][metric])
                for sid in ids
            ]
            su = [
                float(sessions[sid]["SAFE_PRUNING"][metric])
                - float(sessions[sid]["UNGATED_EXECUTE_ADMISSIBLE"][metric])
                for sid in ids
            ]
            rec[f"{metric}__safe_minus_permissive_mean"] = mean(sp)
            rec[f"{metric}__safe_minus_ungated_mean"] = mean(su)
        stratum_rows.append(rec)

    session_fields = ["session_id", "topology", "pattern", "rep"]
    for metric in ALL_METRICS:
        session_fields.extend(
            [
                f"{metric}__ungated",
                f"{metric}__permissive",
                f"{metric}__safe",
                f"{metric}__safe_minus_permissive",
                f"{metric}__safe_minus_ungated",
            ]
        )
    write_csv(out_dir / "confirmatory_session_paired_metrics.csv", session_fields, session_rows)

    write_csv(
        out_dir / "confirmatory_arm_means.csv",
        ["arm", "metric", "n", "mean"],
        arm_rows,
    )

    primary_fields = [
        "metric", "n_pairs", "mean_safe", "mean_permissive",
        "mean_difference_safe_minus_permissive",
        "median_difference_safe_minus_permissive",
        "safe_lower_count", "equal_count", "safe_higher_count",
        "percent_change_of_means_safe_vs_permissive",
        "ci95_lower_mean_difference", "ci95_upper_mean_difference",
        "bootstrap_replicates", "bootstrap_seed_sha256",
        "observed_mean_difference", "permutations",
        "extreme_count_t_perm_le_t_obs", "raw_one_sided_p",
        "seed_sha256", "holm_rank", "holm_adjusted_one_sided_p",
        "confirmatory_reduction_confirmed",
    ]
    write_csv(
        out_dir / "confirmatory_primary_endpoint_family.csv",
        primary_fields,
        primary_rows,
    )

    secondary_fields = [
        "metric", "n_pairs", "mean_safe", "mean_ungated",
        "mean_difference_safe_minus_ungated",
        "median_difference_safe_minus_ungated",
        "safe_lower_count", "equal_count", "safe_higher_count",
        "percent_change_of_means_safe_vs_ungated",
        "ci95_lower_mean_difference", "ci95_upper_mean_difference",
        "bootstrap_replicates", "bootstrap_seed_sha256",
        "confirmatory_p_value_computed",
    ]
    write_csv(
        out_dir / "confirmatory_secondary_break_even.csv",
        secondary_fields,
        secondary_rows,
    )

    stratum_fields = ["topology", "pattern", "n_sessions"]
    for metric in PRIMARY_METRICS:
        stratum_fields.extend(
            [
                f"{metric}__safe_minus_permissive_mean",
                f"{metric}__safe_minus_ungated_mean",
            ]
        )
    write_csv(
        out_dir / "confirmatory_stratum_diagnostics.csv",
        stratum_fields,
        stratum_rows,
    )

    analysis = {
        "contract_version": "mcad.nh_r3.d4.confirmatory_inference_analysis.v1",
        "station": "MCAD-NH-R3",
        "stage": "R3-D_CONFIRMATORY_SQL_DIRECT",
        "analysis_class": "CONFIRMATORY_PRIMARY_SQL_DIRECT",
        "source": {
            "archive_name": SOURCE_ARCHIVE_NAME,
            "archive_sha256": source["archive_sha256"],
            "archive_root": source["archive_root"],
            "archive_members": source["archive_members"],
            "internal_manifest_entries": source["internal_manifest_entries"],
            "internal_manifest_verified": True,
            "r4_execution_kit_head": R4_HEAD,
            "interrupted_partial_receipts_reused": False,
            "resume_from_arm_298": False,
            "fallback_120_activated": False,
        },
        "measurement_integrity": {
            "status": "PASS",
            "semantic_sessions": 300,
            "arm_receipts": 900,
            "candidate_records": 21600,
            "gate_evaluations": 14400,
            "full_backend_executions": 14580,
            "fresh_gated_sessions": 600,
            "negative_cgroup_delta_arm_runs": 0,
            "warmup_templates_completed": 7,
        },
        "frozen_inference_protocol": {
            "git_blob": D0_PROTOCOL_BLOB,
            "primary_comparison": "SAFE_PRUNING - PERMISSIVE_GATED",
            "primary_metrics": list(PRIMARY_METRICS),
            "sign_flip_replicates": SIGN_FLIP_B,
            "bootstrap_replicates": BOOTSTRAP_B,
            "holm_familywise_alpha": ALPHA,
            "seed_namespace_sha256": SEED_NAMESPACE,
            "lower_is_better": True,
            "global_claim_rule": (
                "No global system-benefit claim merely because one or more endpoints confirm."
            ),
        },
        "implementation": {
            "rng_engine": "Python random.Random (MT19937)",
            "seed_integer": "big-endian integer of SHA256(seed-rule material)",
            "percentile_ci": "linear interpolation at q*(B-1)",
            "same_bootstrap_resamples_primary_secondary": True,
            "effect_size_tuning_performed": False,
            "scientific_redesign_performed": False,
        },
        "arm_means": means,
        "primary_endpoint_family": {
            "results": {r["metric"]: r for r in primary_rows},
            "confirmed_metric_count": len(confirmed_metrics),
            "confirmed_metrics": confirmed_metrics,
            "all_8_confirmed": len(confirmed_metrics) == 8,
            "global_system_benefit_claim_authorized": False,
        },
        "secondary_break_even_family": {
            "confirmatory_p_values_computed": False,
            "results": {r["metric"]: r for r in secondary_rows},
        },
        "claim_boundary": {
            "endpoint_specific_confirmatory_reductions_authorized": confirmed_metrics,
            "global_system_benefit_claim_authorized": False,
            "effect_size_tuning_performed": False,
            "posthoc_endpoint_selection_performed": False,
            "fallback_120_activated": False,
        },
        "next": "R3-E0_XMLA_EMONDRIAN_END_TO_END_REPLICATION_STATIC_ACTIVATION_NO_MEASUREMENT",
    }
    (out_dir / "confirmatory_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    files = sorted(
        p for p in out_dir.iterdir()
        if p.is_file() and p.name != "SHA256SUMS.txt"
    )
    manifest_lines = [
        f"{sha256_bytes(p.read_bytes())}  {p.name}\n"
        for p in files
    ]
    (out_dir / "SHA256SUMS.txt").write_text("".join(manifest_lines), encoding="utf-8")

    print("source_archive_sha256=" + source["archive_sha256"])
    print("measurement_integrity=PASS")
    print("primary_endpoint_family_metrics=8")
    print("confirmed_metric_count=" + str(len(confirmed_metrics)))
    for rec in primary_rows:
        print(
            "primary_metric="
            + rec["metric"]
            + "|mean_diff="
            + format(float(rec["mean_difference_safe_minus_permissive"]), ".12g")
            + "|raw_p="
            + format(float(rec["raw_one_sided_p"]), ".12g")
            + "|holm_p="
            + format(float(rec["holm_adjusted_one_sided_p"]), ".12g")
            + "|ci95=["
            + format(float(rec["ci95_lower_mean_difference"]), ".12g")
            + ","
            + format(float(rec["ci95_upper_mean_difference"]), ".12g")
            + "]|confirmed="
            + ("true" if rec["confirmatory_reduction_confirmed"] else "false")
        )
    print("secondary_break_even_confirmatory_p_values_computed=false")
    print("global_system_benefit_claim_authorized=false")
    print("effect_size_tuning_performed=false")
    print("scientific_redesign_performed=false")
    print("R3_D4_CONFIRMATORY_INFERENCE_GENERATE=PASS")


def verify_output(out_dir: Path) -> None:
    analysis_path = out_dir / "confirmatory_analysis.json"
    if not analysis_path.is_file():
        raise RuntimeError("confirmatory_analysis.json missing")
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != "mcad.nh_r3.d4.confirmatory_inference_analysis.v1":
        raise RuntimeError("unexpected D4 analysis contract")
    if (data.get("measurement_integrity") or {}).get("status") != "PASS":
        raise RuntimeError("D4 measurement integrity not PASS")
    family = data.get("primary_endpoint_family") or {}
    results = family.get("results") or {}
    if tuple(results.keys()) != PRIMARY_METRICS:
        raise RuntimeError("D4 primary result metric order/family changed")
    for metric in PRIMARY_METRICS:
        rec = results[metric]
        expected = (
            float(rec["mean_difference_safe_minus_permissive"]) < 0
            and float(rec["holm_adjusted_one_sided_p"]) <= ALPHA
        )
        if bool(rec["confirmatory_reduction_confirmed"]) != expected:
            raise RuntimeError(f"D4 claim rule mismatch for {metric}")
        p = float(rec["raw_one_sided_p"])
        hp = float(rec["holm_adjusted_one_sided_p"])
        if not (0 < p <= 1 and 0 < hp <= 1):
            raise RuntimeError(f"invalid p-value for {metric}")
        if hp + 1e-15 < p:
            raise RuntimeError(f"Holm p below raw p for {metric}")
    if family.get("global_system_benefit_claim_authorized") is not False:
        raise RuntimeError("global claim boundary violated")
    secondary = data.get("secondary_break_even_family") or {}
    if secondary.get("confirmatory_p_values_computed") is not False:
        raise RuntimeError("secondary confirmatory p-values unexpectedly computed")
    boundary = data.get("claim_boundary") or {}
    if boundary.get("effect_size_tuning_performed") is not False:
        raise RuntimeError("effect-size tuning flag violated")
    if boundary.get("posthoc_endpoint_selection_performed") is not False:
        raise RuntimeError("posthoc endpoint selection flag violated")
    if boundary.get("fallback_120_activated") is not False:
        raise RuntimeError("fallback flag violated")
    if data.get("next") != "R3-E0_XMLA_EMONDRIAN_END_TO_END_REPLICATION_STATIC_ACTIVATION_NO_MEASUREMENT":
        raise RuntimeError("unexpected D4 next stage")

    manifest = out_dir / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise RuntimeError("D4 SHA256SUMS missing")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split("  ", 1)
        path = out_dir / name
        if sha256_bytes(path.read_bytes()) != expected:
            raise RuntimeError(f"D4 output SHA mismatch: {name}")

    print("measurement_integrity=PASS")
    print("confirmed_metric_count=" + str(int(family.get("confirmed_metric_count", -1))))
    print("global_system_benefit_claim_authorized=false")
    print("secondary_confirmatory_p_values_computed=false")
    print("R3_D4_CONFIRMATORY_INFERENCE_VERIFY=PASS")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("generate")
    p.add_argument("--archive", required=True)
    p.add_argument("--out-dir", required=True)

    p = sub.add_parser("verify-output")
    p.add_argument("--out-dir", required=True)

    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "generate":
        generate(repo, Path(args.archive).resolve(), Path(args.out_dir).resolve())
        return
    if args.cmd == "verify-output":
        verify_output(Path(args.out_dir).resolve())
        return


if __name__ == "__main__":
    main()
