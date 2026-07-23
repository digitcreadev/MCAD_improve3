#!/usr/bin/env python3
"""Run the experimental evaluation reported in the article."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from protocol_config import (  # noqa: E402
    BOOTSTRAP_DEFAULT,
    EXPECTED_COUNTS,
    SEED_DEFAULT,
)
from run_context import create_run_context, write_checksums, write_json  # noqa: E402


def run_logged(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + shlex.join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc.returncode != 0:
        raise SystemExit(f"[FAIL] command failed; see {log_path}")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the article experimental evaluation.")
    p.add_argument("--out-root", default="reports/article_experiments")
    p.add_argument("--run-id", default="")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--seed", type=int, default=SEED_DEFAULT)
    p.add_argument("--bootstrap", type=int, default=BOOTSTRAP_DEFAULT)
    p.add_argument("--a-repeats", type=int, default=75)
    p.add_argument("--b-repeats", type=int, default=10)
    p.add_argument("--c-repeats", type=int, default=12)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    ctx = create_run_context(
        out_root=Path(args.out_root),
        seed=args.seed,
        run_id=args.run_id or None,
        overwrite=args.overwrite,
    )
    run_dir = Path(ctx["run_dir"])
    logs_dir = run_dir / "logs"

    experiments_script = SCRIPT_DIR / "run_article_experiments.py"
    stats_script = SCRIPT_DIR / "run_article_paired_statistics.py"

    run_logged(
        [
            sys.executable,
            str(experiments_script),
            "--out-dir",
            str(run_dir),
            "--a-repeats",
            str(args.a_repeats),
            "--b-repeats",
            str(args.b_repeats),
            "--c-repeats",
            str(args.c_repeats),
            "--seed",
            str(args.seed),
        ],
        logs_dir / "run_article_experiments.log",
    )

    run_logged(
        [
            sys.executable,
            str(stats_script),
            "--run-dir",
            str(run_dir),
            "--bootstrap",
            str(args.bootstrap),
            "--seed",
            str(args.seed),
        ],
        logs_dir / "run_article_paired_statistics.log",
    )

    summary_path = run_dir / "article_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"[FAIL] missing summary: {summary_path}")

    summary = read_json(summary_path)

    actual_counts = {
        "total_sessions_or_validations": summary.get("total_sessions"),
        "total_query_decisions": summary.get("total_queries"),
    }

    manifest = {
        "run_id": ctx["run_id"],
        "created_at_utc": ctx["created_at_utc"],
        "created_at_local": ctx["created_at_local"],
        "timezone_policy": ctx["timezone_policy"],
        "git": ctx["git"],
        "seed": args.seed,
        "bootstrap_resamples": args.bootstrap,
        "protocol": {
            "campaign_a_repeats": args.a_repeats,
            "campaign_b_repeats": args.b_repeats,
            "campaign_c_repeats": args.c_repeats,
            "expected_counts": EXPECTED_COUNTS,
            "actual_counts": actual_counts,
        },
        "artifacts": {
            "summary_json": "article_summary.json",
            "report_md": "article_report.md",
            "sessions_csv": "article_metrics_by_session.csv",
            "query_decisions_csv": "article_metrics_by_query.csv",
            "campaign_policy_summary_csv": "article_summary_by_campaign_policy.csv",
            "statistics_dir": "stats",
            "logs_dir": "logs",
            "checksums": "checksums.sha256",
        },
    }

    write_json(run_dir / "manifest.json", manifest)
    write_checksums(run_dir)

    print("[OK] Article experimental rebuild completed")
    print(f"run_id={ctx['run_id']}")
    print(f"run_dir={run_dir}")
    print(f"sessions_or_validations={actual_counts['total_sessions_or_validations']}")
    print(f"query_decisions={actual_counts['total_query_decisions']}")
    print(f"manifest={run_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
