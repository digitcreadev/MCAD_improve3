#!/usr/bin/env python3
"""Smoke check for the article experimental evaluation pipeline."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]


def fail(msg: str) -> None:
    raise SystemExit(f"[FAIL] {msg}")


def main() -> None:
    run_id = "check_smoke"
    run_dir = REPO_ROOT / "reports" / "article_experiments" / run_id

    if run_dir.exists():
        shutil.rmtree(run_dir)

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "run_article_rebuild.py"),
        "--run-id",
        run_id,
        "--overwrite",
        "--a-repeats",
        "1",
        "--b-repeats",
        "1",
        "--c-repeats",
        "1",
        "--bootstrap",
        "50",
        "--seed",
        "20260625",
    ]

    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    summary_path = run_dir / "article_summary.json"
    manifest_path = run_dir / "manifest.json"
    stats_report = run_dir / "stats" / "article_statistical_report.md"

    if not summary_path.exists():
        fail("missing article_summary.json")
    if not manifest_path.exists():
        fail("missing manifest.json")
    if not stats_report.exists():
        fail("missing statistical report")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if summary.get("total_sessions") != 200:
        fail(f"unexpected smoke sessions: {summary.get('total_sessions')}")
    if summary.get("total_queries") != 1600:
        fail(f"unexpected smoke queries: {summary.get('total_queries')}")

    print("[OK] article experimental smoke check passed")
    print(f"run_dir={run_dir}")
    print("sessions=200")
    print("queries=1600")


if __name__ == "__main__":
    main()
