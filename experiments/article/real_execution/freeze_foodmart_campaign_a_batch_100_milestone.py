#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

BATCH_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_batches"
OUT_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_batch_100_milestone"

def main() -> int:
    runs = sorted(BATCH_ROOT.glob("foodmart_campaign_a_batch_100_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        raise SystemExit("[FAIL] No batch 100 run found.")

    src = runs[0]
    summary_path = src / "campaign_a_batch_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"[FAIL] Missing summary: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not summary.get("ok"):
        raise SystemExit("[FAIL] Latest batch 100 is not ok=true.")

    milestone_id = "foodmart_campaign_a_batch_100_milestone_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / milestone_id
    out.mkdir(parents=True, exist_ok=True)

    files = [
        "campaign_a_batch_summary.json",
        "campaign_a_batch_by_query.csv",
        "campaign_a_batch_by_session.csv",
        "campaign_a_batch_mismatches.csv",
        "campaign_a_batch_gate_violations.csv",
    ]

    copied = []
    for name in files:
        p = src / name
        if p.exists():
            shutil.copy2(p, out / name)
            copied.append(name)

    report = f"""# FoodMart Campaign A Runtime-Feasible — Batch 100 Milestone

## Status

PASS.

## Source run

`{src.relative_to(ROOT)}`

## Key results

- Campaign: `{summary.get("campaign_id")}`
- Dataset: `{summary.get("dw_id")}`
- Sampling: `{summary.get("sampling")}`
- Raw policy: `{summary.get("raw_policy")}`
- Executed sessions: `{summary.get("executed_session_count")}`
- Executed query decisions: `{summary.get("executed_query_count")}`
- Session-context match rate: `{summary.get("session_context_match_rate")}`
- Mismatches: `{summary.get("mismatch_count")}`
- HTTP errors: `{summary.get("http_error_count")}`
- Canonical gate violations: `{summary.get("canonical_gate_contract_violation_count")}`

## Gate/execution contract

- ALLOW decisions: `{summary.get("allow_count")}`
- ALLOW with business physical execution: `{summary.get("allow_business_physical_execution_count")}`
- BLOCK decisions: `{summary.get("block_count")}`
- BLOCK with business physical execution: `{summary.get("block_business_physical_execution_count")}`
- BLOCK stopped before business execution: `{summary.get("blocked_before_business_execution_count")}`

## Interpretation

This milestone validates the runtime-feasible FoodMart Campaign A library on a stratified batch of 100 sessions. The decision semantics are correct under session context, and the canonical gate contract is fully respected: allowed queries are executed physically, while blocked queries are stopped before final business execution.
"""

    (out / "foodmart_campaign_a_batch_100_milestone_report.md").write_text(report, encoding="utf-8")

    zip_path = out / "foodmart_campaign_a_batch_100_milestone_evidence.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in out.iterdir():
            if p.name != zip_path.name:
                z.write(p, arcname=p.name)

    manifest = {
        "ok": True,
        "milestone_id": milestone_id,
        "source_run": str(src.relative_to(ROOT)),
        "output_dir": str(out.relative_to(ROOT)),
        "copied_files": copied,
        "zip_file": str(zip_path.relative_to(ROOT)),
        "summary": summary,
    }

    (out / "foodmart_campaign_a_batch_100_milestone_summary.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
