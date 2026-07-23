#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", required=True, type=int)
    ap.add_argument("--batch-root", default="reports/article_experiments/foodmart_campaign_a_batches")
    args = ap.parse_args()

    root = Path(args.batch_root)
    candidates = []

    for d in root.glob("foodmart_campaign_a_batch_100_*"):
        p = d / "campaign_a_batch_summary.json"
        if not p.exists():
            continue

        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        if int(s.get("offset", -1)) != args.offset:
            continue

        failures = []

        if s.get("ok") is not True:
            failures.append("ok")
        if int(s.get("requested_session_limit", 0) or 0) != 100:
            failures.append("requested_session_limit")
        if int(s.get("executed_session_count", 0) or 0) != 100:
            failures.append("executed_session_count")
        if str(s.get("dw_id")) != "foodmart":
            failures.append("dw_id")
        if str(s.get("raw_policy")) != "none":
            failures.append("raw_policy")
        if int(s.get("mismatch_count", 0) or 0) != 0:
            failures.append("mismatch_count")
        if int(s.get("http_error_count", 0) or 0) != 0:
            failures.append("http_error_count")
        if int(s.get("canonical_gate_contract_violation_count", 0) or 0) != 0:
            failures.append("canonical_gate_contract_violation_count")
        if int(s.get("block_business_physical_execution_count", 0) or 0) != 0:
            failures.append("block_business_physical_execution_count")

        if failures:
            continue

        candidates.append((p.stat().st_mtime, d))

    if not candidates:
        raise SystemExit(f"[FAIL] No valid run found for offset={args.offset}")

    candidates.sort(reverse=True, key=lambda x: x[0])
    print(str(candidates[0][1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
