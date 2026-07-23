#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


BASELINES = ["naive", "measure_overlap", "random_matched"]
MCAD = "mcad_gate"


def safe_float(x: Any) -> float:
    if x is None or x == "":
        return 0.0
    return float(x)


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def percentile(xs: List[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def bootstrap_ci_mean(xs: List[float], *, n_boot: int, seed: int) -> Tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(xs)
    vals = []
    for _ in range(n_boot):
        vals.append(mean([xs[rng.randrange(n)] for _ in range(n)]))
    return percentile(vals, 0.025), percentile(vals, 0.975)


def normal_approx_paired_sign_pvalue(diffs: List[float]) -> float:
    non_zero = [d for d in diffs if abs(d) > 1e-12]
    n = len(non_zero)
    if n == 0:
        return 1.0
    positives = sum(1 for d in non_zero if d > 0)
    # Normal approximation to two-sided sign test.
    mu = n / 2.0
    sigma = math.sqrt(n / 4.0)
    z = (abs(positives - mu) - 0.5) / sigma if sigma else 0.0
    # Two-sided p-value from normal CDF via erf.
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    return max(0.0, min(1.0, p))


def paired_cohens_dz(diffs: List[float]) -> float:
    sd = stdev(diffs)
    return mean(diffs) / sd if sd else 0.0


def load_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def trace_key(r: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    return (
        r["campaign"],
        r["dataset"],
        r["objective_id"],
        r["backend_mode"],
        r["session_length"],
        r["trace_id"],
    )


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fmt(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def make_markdown_table(rows: List[Dict[str, Any]], cols: List[str]) -> str:
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> None:
    cols = [
        "campaign",
        "baseline",
        "paired_traces",
        "coverage_preservation_ratio_mean",
        "coverage_preservation_ratio_ci95_low",
        "coverage_preservation_ratio_ci95_high",
        "coverage_gain_mean",
        "execution_reduction_ratio_mean",
        "non_contrib_execution_reduction_ratio_mean",
        "false_allow_reduction_ratio_mean",
        "false_block_diff_mean",
        "cohens_dz_phi_diff",
        "sign_test_pvalue_phi_diff",
    ]

    md = [
        "# MCAD-Gate paired statistical analysis",
        "",
        f"Generated at: `{meta['generated_at']}`",
        f"Input run: `{meta['input_run_dir']}`",
        f"Bootstrap resamples: `{meta['bootstrap_resamples']}`",
        "",
        "## Paired comparison summary",
        "",
        make_markdown_table(rows, cols),
        "",
        "## Interpretation",
        "",
        "The analysis compares MCAD-Gate against each baseline on the same analytical traces using `trace_id`. The most important indicators are coverage preservation, execution reduction, non-contributive execution reduction, false-allow reduction, and false-block difference.",
        "",
        "A coverage preservation ratio equal to 1 means that MCAD-Gate preserves at least the useful final contribution reached by the baseline. The coverage gain reports whether MCAD-Gate exceeds or falls below the baseline. A high non-contributive execution reduction ratio means that MCAD-Gate avoids useless analytical executions. A false-block difference close to 0 indicates that MCAD-Gate does not sacrifice useful queries.",
        "",
    ]

    (out_dir / "article_statistical_report.md").write_text("\n".join(md), encoding="utf-8")


def write_latex(out_dir: Path, rows: List[Dict[str, Any]]) -> None:
    table_dir = out_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    cols = [
        "campaign",
        "baseline",
        "paired_traces",
        "coverage_preservation_ratio_mean",
        "coverage_gain_mean",
        "execution_reduction_ratio_mean",
        "non_contrib_execution_reduction_ratio_mean",
        "false_allow_reduction_ratio_mean",
        "false_block_diff_mean",
    ]

    lines = [
        "\\begin{tabular}{llrrrrrr}",
        "\\hline",
        "Campaign & Baseline & Traces & Coverage preservation & Exec. reduction & Non-contrib. reduction & False-allow reduction & False-block diff. \\\\",
        "\\hline",
    ]
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v).replace("_", "\\_"))
        lines.append(" & ".join(vals) + " \\\\")
    lines += ["\\hline", "\\end{tabular}", ""]
    (table_dir / "table_article_paired_stats.tex").write_text("\n".join(lines), encoding="utf-8")


def analyze_campaign(rows: List[Dict[str, Any]], campaign: str, baseline: str, n_boot: int, seed: int) -> Dict[str, Any]:
    by_trace_policy: Dict[Tuple[str, str, str, str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        if r["campaign"] != campaign:
            continue
        if r["policy"] in {MCAD, baseline}:
            by_trace_policy[trace_key(r)][r["policy"]] = r

    pairs = []
    for key, d in by_trace_policy.items():
        if MCAD in d and baseline in d:
            pairs.append((key, d[MCAD], d[baseline]))

    phi_diffs = []
    coverage_ratios = []
    exec_reductions = []
    non_contrib_reductions = []
    false_allow_reductions = []
    false_block_diffs = []
    latency_p95_diffs = []

    for _, m, b in pairs:
        m_phi = safe_float(m["phi_final"])
        b_phi = safe_float(b["phi_final"])
        m_exec = safe_float(m["executed"])
        b_exec = safe_float(b["executed"])
        m_non = safe_float(m["non_contributive_execution"])
        b_non = safe_float(b["non_contributive_execution"])
        m_fa = safe_float(m["false_allow"])
        b_fa = safe_float(b["false_allow"])
        m_fb = safe_float(m["false_block"])
        b_fb = safe_float(b["false_block"])

        phi_gain = m_phi - b_phi
        phi_diffs.append(phi_gain)

        if b_phi <= 0:
            coverage_preservation = 1.0 if m_phi >= b_phi else 0.0
        else:
            coverage_preservation = min(safe_div(m_phi, b_phi), 1.0)

        coverage_ratios.append(coverage_preservation)
        exec_reductions.append(1.0 - safe_div(m_exec, b_exec))
        non_contrib_reductions.append(1.0 - safe_div(m_non, b_non))
        false_allow_reductions.append(1.0 - safe_div(m_fa, b_fa))
        false_block_diffs.append(m_fb - b_fb)
        latency_p95_diffs.append(safe_float(m["decision_latency_p95_ms"]) - safe_float(b["decision_latency_p95_ms"]))

    cov_low, cov_high = bootstrap_ci_mean(coverage_ratios, n_boot=n_boot, seed=seed + 11)
    phi_low, phi_high = bootstrap_ci_mean(phi_diffs, n_boot=n_boot, seed=seed + 13)
    exec_low, exec_high = bootstrap_ci_mean(exec_reductions, n_boot=n_boot, seed=seed + 17)
    non_low, non_high = bootstrap_ci_mean(non_contrib_reductions, n_boot=n_boot, seed=seed + 19)
    fa_low, fa_high = bootstrap_ci_mean(false_allow_reductions, n_boot=n_boot, seed=seed + 23)

    return {
        "campaign": campaign,
        "baseline": baseline,
        "paired_traces": len(pairs),

        "coverage_preservation_ratio_mean": mean(coverage_ratios),
        "coverage_preservation_ratio_ci95_low": cov_low,
        "coverage_preservation_ratio_ci95_high": cov_high,

        "coverage_gain_mean": mean(phi_diffs),
        "coverage_gain_ci95_low": phi_low,
        "coverage_gain_ci95_high": phi_high,
        "phi_diff_mean": mean(phi_diffs),
        "phi_diff_ci95_low": phi_low,
        "phi_diff_ci95_high": phi_high,

        "execution_reduction_ratio_mean": mean(exec_reductions),
        "execution_reduction_ratio_ci95_low": exec_low,
        "execution_reduction_ratio_ci95_high": exec_high,

        "non_contrib_execution_reduction_ratio_mean": mean(non_contrib_reductions),
        "non_contrib_execution_reduction_ratio_ci95_low": non_low,
        "non_contrib_execution_reduction_ratio_ci95_high": non_high,

        "false_allow_reduction_ratio_mean": mean(false_allow_reductions),
        "false_allow_reduction_ratio_ci95_low": fa_low,
        "false_allow_reduction_ratio_ci95_high": fa_high,

        "false_block_diff_mean": mean(false_block_diffs),
        "latency_p95_diff_ms_mean": mean(latency_p95_diffs),

        "cohens_dz_phi_diff": paired_cohens_dz(phi_diffs),
        "sign_test_pvalue_phi_diff": normal_approx_paired_sign_pvalue(phi_diffs),
    }


def run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    in_csv = run_dir / "article_metrics_by_session.csv"
    if not in_csv.exists():
        raise SystemExit(f"missing input CSV: {in_csv}")

    out_dir = Path(args.out_dir) if args.out_dir else run_dir / "stats"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(in_csv)

    campaigns = [
        "A_core_foodmart_mcad_gate",
        "B_multidataset_generalization",
    ]

    out_rows = []
    for campaign in campaigns:
        for baseline in BASELINES:
            out_rows.append(
                analyze_campaign(
                    rows,
                    campaign=campaign,
                    baseline=baseline,
                    n_boot=args.bootstrap,
                    seed=args.seed + len(out_rows) * 101,
                )
            )

    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "input_run_dir": str(run_dir),
        "output_dir": str(out_dir),
        "bootstrap_resamples": args.bootstrap,
        "seed": args.seed,
        "note": "Paired comparisons are computed on trace_id. Campaign C is excluded because it only contains MCAD-Gate policy rows.",
    }

    write_csv(out_dir / "article_paired_stats.csv", out_rows)
    write_json(out_dir / "article_paired_stats.json", {"meta": meta, "rows": out_rows})
    write_report(out_dir, out_rows, meta)
    write_latex(out_dir, out_rows)

    print("=== MCAD-Gate paired statistical analysis OK ===")
    print(f"input={run_dir}")
    print(f"output={out_dir}")
    print(f"rows={len(out_rows)}")
    print(f"report={out_dir / 'article_statistical_report.md'}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Paired statistical analysis for MCAD-Gate campaigns.")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out-dir", default="")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260625)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
