#!/usr/bin/env python3
"""Validate an article experiment run directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


FORBIDDEN_TERMS = [
    "MCAD-Gate " + "V" + "2",
    "V" + "2 evaluation",
    "run_" + "1000" + "_sessions",
    "1000" + "-session",
    "historical " + "results",
    "legacy " + "results",
    "final " + "experimental",
    "sessions_index_" + "1000",
    "timelines_" + "1000",
]


def fail(msg: str) -> None:
    raise SystemExit(f"[FAIL] {msg}")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read JSON {path}: {exc}")


def text_files(root: Path) -> Iterable[Path]:
    suffixes = {".txt", ".md", ".json", ".csv", ".tex", ".log", ".sha256"}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in suffixes:
            yield p


def check_required_files(run_dir: Path) -> None:
    required = [
        "manifest.json",
        "run_context.json",
        "environment.txt",
        "git_status.txt",
        "checksums.sha256",
        "article_summary.json",
        "article_report.md",
        "article_metrics_by_session.csv",
        "article_metrics_by_query.csv",
        "article_summary_by_campaign_policy.csv",
        "stats/article_paired_stats.csv",
        "stats/article_paired_stats.json",
        "stats/article_statistical_report.md",
        "logs/run_article_experiments.log",
        "logs/run_article_paired_statistics.log",
    ]

    missing = [rel for rel in required if not (run_dir / rel).exists()]
    if missing:
        fail("missing required artifacts: " + ", ".join(missing))


def check_no_forbidden_terms(run_dir: Path) -> None:
    hits: list[str] = []
    for p in text_files(run_dir):
        rel = p.relative_to(run_dir).as_posix()
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for term in FORBIDDEN_TERMS:
            if term in txt or term in rel:
                hits.append(f"{rel}: {term}")
    if hits:
        fail("forbidden terms found:\n" + "\n".join(hits[:50]))


def check_no_1000_artifacts(run_dir: Path) -> None:
    hits = [p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*1000*")]
    if hits:
        fail("1000-suffixed artifacts found: " + ", ".join(hits))


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate an article experiment run directory.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--expect-full", action="store_true")
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        fail(f"run directory does not exist: {run_dir}")

    check_required_files(run_dir)

    manifest = read_json(run_dir / "manifest.json")
    summary = read_json(run_dir / "article_summary.json")

    total_sessions = int(summary.get("total_sessions", -1))
    total_queries = int(summary.get("total_queries", -1))

    if args.expect_full:
        if total_sessions != 4680:
            fail(f"expected 4680 sessions/validations, got {total_sessions}")
        if total_queries != 37440:
            fail(f"expected 37440 query decisions, got {total_queries}")

        actual = manifest.get("protocol", {}).get("actual_counts", {})
        if actual.get("total_sessions_or_validations") != 4680:
            fail(f"manifest actual session count mismatch: {actual}")
        if actual.get("total_query_decisions") != 37440:
            fail(f"manifest actual query count mismatch: {actual}")

    if args.require_clean and manifest.get("git", {}).get("dirty") is not False:
        fail("manifest reports dirty git state")

    check_no_1000_artifacts(run_dir)
    check_no_forbidden_terms(run_dir)

    print("[OK] article run is valid")
    print(f"run_dir={run_dir}")
    print(f"sessions_or_validations={total_sessions}")
    print(f"query_decisions={total_queries}")


if __name__ == "__main__":
    main()
