#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import tarfile
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

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

PAIRWISE = (
    ("SAFE_PRUNING", "PERMISSIVE_GATED"),
    ("SAFE_PRUNING", "UNGATED_EXECUTE_ADMISSIBLE"),
    ("PERMISSIVE_GATED", "UNGATED_EXECUTE_ADMISSIBLE"),
)

EXPECTED_ARCHIVE_SHA = "7e0e863dc72200312827dced4425eee8105e5384dfca938f53aba8bc1ad761c6"
EXPECTED_ARCHIVE_SIZE = 102767


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(tf: tarfile.TarFile, target: Path) -> None:
    base = target.resolve()
    members = tf.getmembers()
    for m in members:
        p = (target / m.name).resolve()
        if p != base and base not in p.parents:
            raise RuntimeError(f"unsafe archive member: {m.name}")
        if m.issym() or m.islnk():
            raise RuntimeError(f"links forbidden in results archive: {m.name}")
    tf.extractall(target)


def mean(xs: list[float]) -> float:
    return statistics.fmean(xs)


def median(xs: list[float]) -> float:
    return statistics.median(xs)


def stdev(xs: list[float]) -> float:
    return statistics.stdev(xs) if len(xs) >= 2 else 0.0


def fmt(v: Any) -> Any:
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 6)
    return v


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: fmt(row.get(k)) for k in fieldnames})


def parse_manifest(root: Path) -> None:
    manifest = root / "RESULT_FILE_SHA256SUMS.txt"
    if not manifest.is_file():
        raise RuntimeError("RESULT_FILE_SHA256SUMS.txt missing")
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError(f"invalid manifest line: {raw!r}")
        expected, rel = parts
        rel = rel.lstrip("* ")
        p = root / rel
        if not p.is_file():
            raise RuntimeError(f"manifest target missing: {rel}")
        actual = sha256_file(p)
        if actual != expected:
            raise RuntimeError(f"manifest hash mismatch: {rel}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    archive = Path(args.archive).resolve()
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)

    if archive.stat().st_size != EXPECTED_ARCHIVE_SIZE:
        raise RuntimeError("archive size mismatch")
    archive_sha = sha256_file(archive)
    if archive_sha != EXPECTED_ARCHIVE_SHA:
        raise RuntimeError("archive SHA-256 mismatch")

    with tempfile.TemporaryDirectory(prefix="mcad_r3_b2m_") as td:
        extract = Path(td)
        with tarfile.open(archive, "r:gz") as tf:
            safe_extract(tf, extract)

        parse_manifest(extract)

        arm_dir = extract / "measured_output" / "arm_runs"
        summary_path = extract / "measured_output" / "pilot_summary.json"
        run_summary_path = extract / "run_summary.txt"
        warmup_dir = extract / "warmup"

        files = sorted(arm_dir.glob("*.json"))
        if len(files) != 60:
            raise RuntimeError(f"expected 60 arm receipts, got {len(files)}")
        if not summary_path.is_file():
            raise RuntimeError("pilot_summary.json missing")

        receipts = [json.loads(p.read_text(encoding="utf-8")) for p in files]
        pilot_summary = json.loads(summary_path.read_text(encoding="utf-8"))

        if [int(r["ordinal"]) for r in receipts] != list(range(1, 61)):
            raise RuntimeError("receipt ordinals are not 1..60")

        arm_counts = Counter(str(r["arm"]) for r in receipts)
        if arm_counts != Counter({a: 20 for a in ARMS}):
            raise RuntimeError(f"arm balance mismatch: {arm_counts}")

        if sum(len(r["candidate_records"]) for r in receipts) != 1440:
            raise RuntimeError("candidate record total != 1440")
        if sum(int(r["gate_evaluation_count"]) for r in receipts) != 960:
            raise RuntimeError("gate evaluation total != 960")
        if any(
            int(r[k]) < 0
            for r in receipts
            for k in (
                "sqlserver_cpu_usage_usec_delta",
                "sqlserver_io_rbytes_delta",
                "sqlserver_io_wbytes_delta",
            )
        ):
            raise RuntimeError("negative cgroup delta present")

        gated = [r for r in receipts if r["arm"] != "UNGATED_EXECUTE_ADMISSIBLE"]
        if len(gated) != 40 or not all(r.get("fresh_mcad_session_id") for r in gated):
            raise RuntimeError("fresh gated-session contract mismatch")

        session_ids = sorted({str(r["session_id"]) for r in receipts})
        if len(session_ids) != 20:
            raise RuntimeError("semantic session count != 20")

        by_session: dict[str, dict[str, dict[str, Any]]] = {}
        for r in receipts:
            sid = str(r["session_id"])
            arm = str(r["arm"])
            by_session.setdefault(sid, {})[arm] = r

        for sid, rows in by_session.items():
            if set(rows) != set(ARMS):
                raise RuntimeError(f"{sid}: missing arm")

        # Compact arm-run table.
        arm_fields = [
            "ordinal",
            "block_index",
            "session_id",
            "topology",
            "arm_position",
            "arm",
            "completion_candidate",
            "client_wall_ms",
            "time_to_analytical_objective_completion_ms",
            "gate_evaluation_count",
            "full_backend_execution_count",
            "nvac_physical_backend_request_count",
            "backend_request_count_including_gate_probes",
            "response_bytes",
            "sqlserver_cpu_usage_usec_delta",
            "sqlserver_io_rbytes_delta",
            "sqlserver_io_wbytes_delta",
        ]
        arm_rows = [{k: r.get(k) for k in arm_fields} for r in receipts]
        write_csv(out / "dev_pilot_arm_runs.csv", arm_fields, arm_rows)

        # Arm summaries.
        summary_rows: list[dict[str, Any]] = []
        for arm in ARMS:
            rows = [r for r in receipts if r["arm"] == arm]
            for metric in METRICS:
                vals = [float(r[metric]) for r in rows]
                summary_rows.append(
                    {
                        "arm": arm,
                        "metric": metric,
                        "n": len(vals),
                        "mean": mean(vals),
                        "median": median(vals),
                        "sd": stdev(vals),
                        "min": min(vals),
                        "max": max(vals),
                        "sum": sum(vals),
                    }
                )
        write_csv(
            out / "dev_pilot_arm_summary.csv",
            ["arm", "metric", "n", "mean", "median", "sd", "min", "max", "sum"],
            summary_rows,
        )

        # Paired session-level table.
        paired_fields = ["session_id"]
        for arm in ARMS:
            for metric in METRICS:
                paired_fields.append(f"{arm}__{metric}")

        paired_rows: list[dict[str, Any]] = []
        for sid in session_ids:
            row: dict[str, Any] = {"session_id": sid}
            for arm in ARMS:
                receipt = by_session[sid][arm]
                for metric in METRICS:
                    row[f"{arm}__{metric}"] = receipt[metric]
            paired_rows.append(row)
        write_csv(out / "dev_pilot_session_paired_metrics.csv", paired_fields, paired_rows)

        # Paired contrasts. Negative delta = A lower than B.
        contrast_rows: list[dict[str, Any]] = []
        for arm_a, arm_b in PAIRWISE:
            for metric in METRICS:
                a = [float(by_session[s][arm_a][metric]) for s in session_ids]
                b = [float(by_session[s][arm_b][metric]) for s in session_ids]
                d = [x - y for x, y in zip(a, b)]
                mean_a = mean(a)
                mean_b = mean(b)
                pct = None if mean_b == 0 else 100.0 * (mean_a / mean_b - 1.0)
                contrast_rows.append(
                    {
                        "arm_a": arm_a,
                        "arm_b": arm_b,
                        "metric": metric,
                        "n_pairs": len(d),
                        "mean_a": mean_a,
                        "mean_b": mean_b,
                        "mean_delta_a_minus_b": mean(d),
                        "median_delta_a_minus_b": median(d),
                        "percent_change_of_means_a_vs_b": pct,
                        "a_lower_count": sum(x < y for x, y in zip(a, b)),
                        "equal_count": sum(x == y for x, y in zip(a, b)),
                        "a_higher_count": sum(x > y for x, y in zip(a, b)),
                    }
                )
        write_csv(
            out / "dev_pilot_paired_contrasts.csv",
            [
                "arm_a", "arm_b", "metric", "n_pairs",
                "mean_a", "mean_b", "mean_delta_a_minus_b",
                "median_delta_a_minus_b", "percent_change_of_means_a_vs_b",
                "a_lower_count", "equal_count", "a_higher_count",
            ],
            contrast_rows,
        )

        def lookup(arm: str, metric: str) -> dict[str, Any]:
            return next(x for x in summary_rows if x["arm"] == arm and x["metric"] == metric)

        def contrast(a: str, b: str, metric: str) -> dict[str, Any]:
            return next(
                x for x in contrast_rows
                if x["arm_a"] == a and x["arm_b"] == b and x["metric"] == metric
            )

        safe_perm_req = contrast(
            "SAFE_PRUNING",
            "PERMISSIVE_GATED",
            "backend_request_count_including_gate_probes",
        )
        safe_perm_wall = contrast(
            "SAFE_PRUNING",
            "PERMISSIVE_GATED",
            "client_wall_ms",
        )
        safe_perm_completion = contrast(
            "SAFE_PRUNING",
            "PERMISSIVE_GATED",
            "time_to_analytical_objective_completion_ms",
        )

        warmup_ok = len(list(warmup_dir.glob("*.ok.json")))
        warmup_raw = len(list(warmup_dir.glob("*.raw.json")))
        warmup_agg = (warmup_dir / "WARMUP_AGGREGATE_SHA256.txt").read_text(encoding="utf-8").strip()

        analysis = {
            "contract_version": "mcad.nh_r3.b2m.dev_pilot_analysis.v1",
            "analysis_class": "DEV_DESCRIPTIVE_NONCONFIRMATORY",
            "source_archive": {
                "sha256": archive_sha,
                "size": archive.stat().st_size,
            },
            "integrity": {
                "result_manifest_verified": True,
                "arm_receipts": 60,
                "semantic_sessions": 20,
                "candidate_records": 1440,
                "gate_evaluations": 960,
                "gated_arms_with_nonempty_fresh_session": 40,
                "negative_cgroup_deltas": 0,
                "warmup_success_receipts": warmup_ok,
                "warmup_raw_receipts": warmup_raw,
                "warmup_aggregate_sha256": warmup_agg,
                "confirmatory_claim_authorized": False,
            },
            "pilot_summary": pilot_summary,
            "headline_descriptive_results": {
                "safe_vs_permissive_backend_requests": {
                    k: fmt(v) for k, v in safe_perm_req.items()
                },
                "safe_vs_permissive_client_wall_ms": {
                    k: fmt(v) for k, v in safe_perm_wall.items()
                },
                "safe_vs_permissive_completion_ms": {
                    k: fmt(v) for k, v in safe_perm_completion.items()
                },
            },
            "arm_means": {
                arm: {
                    metric: fmt(lookup(arm, metric)["mean"])
                    for metric in METRICS
                }
                for arm in ARMS
            },
            "interpretation_guardrails": {
                "dev_pilot_only": True,
                "descriptive_not_confirmatory": True,
                "no_p_values_computed": True,
                "no_effect_based_rerun": True,
                "lower_resource_or_time_values_are_descriptively_better": True,
            },
        }
        (out / "dev_pilot_analysis.json").write_text(
            json.dumps(analysis, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        readme = f"""# NH-R3 DEV pilot v3 - deterministic descriptive analysis

Source archive SHA-256: `{archive_sha}`  
Source archive size: `{archive.stat().st_size}` bytes.

## Integrity

- 20 semantic sessions.
- 60 arm runs: 20 per arm.
- 1,440 candidate records.
- 960 gate evaluations.
- 40 gated arm runs with a non-empty fresh MCAD session.
- 0 negative cgroup deltas.
- Warm-up: {warmup_ok} success receipts, {warmup_raw} ambiguous/raw receipts.
- Confirmatory claims remain unauthorized.

## Headline descriptive comparison: SAFE_PRUNING vs PERMISSIVE_GATED

- Mean backend requests: {safe_perm_req['mean_a']:.3f} vs {safe_perm_req['mean_b']:.3f}
  ({safe_perm_req['percent_change_of_means_a_vs_b']:.3f}% change; SAFE lower in
  {safe_perm_req['a_lower_count']}/20 paired sessions).
- Mean client wall time: {safe_perm_wall['mean_a']:.3f} ms vs
  {safe_perm_wall['mean_b']:.3f} ms
  ({safe_perm_wall['percent_change_of_means_a_vs_b']:.3f}% change; SAFE lower in
  {safe_perm_wall['a_lower_count']}/20 paired sessions).
- Mean time to analytical objective completion:
  {safe_perm_completion['mean_a']:.3f} ms vs
  {safe_perm_completion['mean_b']:.3f} ms
  ({safe_perm_completion['percent_change_of_means_a_vs_b']:.3f}% change; SAFE lower in
  {safe_perm_completion['a_lower_count']}/20 paired sessions).

These are DEV-pilot descriptive results, not confirmatory inference. No p-values
or post-hoc confirmatory claims are produced by this checkpoint.

## Files

- `dev_pilot_arm_runs.csv`: one row per measured arm run.
- `dev_pilot_arm_summary.csv`: descriptive summaries by arm and metric.
- `dev_pilot_session_paired_metrics.csv`: paired per-session metric matrix.
- `dev_pilot_paired_contrasts.csv`: paired descriptive contrasts.
- `dev_pilot_analysis.json`: machine-readable audit and headline results.
"""
        (out / "README.md").write_text(readme, encoding="utf-8")

        if run_summary_path.is_file():
            (out / "source_run_summary.txt").write_text(
                run_summary_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        manifest_paths = sorted(p for p in out.iterdir() if p.is_file())
        with (out / "SHA256SUMS.txt").open("w", encoding="utf-8") as fh:
            for p in manifest_paths:
                fh.write(f"{sha256_file(p)}  {p.name}\n")

        print("results_manifest_verified=PASS")
        print("semantic_sessions=20")
        print("arm_receipts=60")
        print("candidate_records=1440")
        print("gate_evaluations=960")
        print("gated_arms_with_nonempty_fresh_session=40")
        print("negative_cgroup_deltas=0")
        print(f"warmup_success_receipts={warmup_ok}")
        print(f"warmup_raw_receipts={warmup_raw}")
        print(
            "safe_vs_permissive_backend_requests_mean="
            f"{safe_perm_req['mean_a']:.3f}_vs_{safe_perm_req['mean_b']:.3f}"
        )
        print(
            "safe_vs_permissive_backend_requests_percent_change="
            f"{safe_perm_req['percent_change_of_means_a_vs_b']:.3f}"
        )
        print(
            "safe_vs_permissive_client_wall_ms_mean="
            f"{safe_perm_wall['mean_a']:.3f}_vs_{safe_perm_wall['mean_b']:.3f}"
        )
        print(
            "safe_vs_permissive_client_wall_percent_change="
            f"{safe_perm_wall['percent_change_of_means_a_vs_b']:.3f}"
        )
        print(
            "safe_vs_permissive_completion_ms_mean="
            f"{safe_perm_completion['mean_a']:.3f}_vs_{safe_perm_completion['mean_b']:.3f}"
        )
        print(
            "safe_vs_permissive_completion_percent_change="
            f"{safe_perm_completion['percent_change_of_means_a_vs_b']:.3f}"
        )
        print(
            "safe_vs_permissive_wall_lower_sessions="
            f"{safe_perm_wall['a_lower_count']}/20"
        )
        print(
            "safe_vs_permissive_backend_lower_sessions="
            f"{safe_perm_req['a_lower_count']}/20"
        )
        print("analysis_class=DEV_DESCRIPTIVE_NONCONFIRMATORY")
        print("R3_B2M_DETERMINISTIC_ANALYSIS=PASS")


if __name__ == "__main__":
    main()
