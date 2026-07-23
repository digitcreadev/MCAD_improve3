#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", required=True)
    args = ap.parse_args()

    evidence_root = Path(args.evidence_root)
    manifest = evidence_root / "runs_manifest.txt"

    if not manifest.exists():
        raise SystemExit(f"[FAIL] Missing manifest: {manifest}")

    runs = []
    seen = set()

    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        runs.append(Path(line))

    totals = {
        "ok": True,
        "campaign_kind": "foodmart_campaign_a_1000_ckg_first",
        "run_count": len(runs),
        "executed_session_count": 0,
        "executed_query_count": 0,
        "strict_match_count": 0,
        "session_context_match_count": 0,
        "allow_count": 0,
        "block_count": 0,
        "allow_business_physical_execution_count": 0,
        "block_business_physical_execution_count": 0,
        "blocked_before_business_execution_count": 0,
        "canonical_gate_contract_ok_count": 0,
        "canonical_gate_contract_violation_count": 0,
        "http_error_count": 0,
        "mismatch_count": 0,
        "source_runs": [str(r) for r in runs],
    }

    reason_counts = {}

    for r in runs:
        p = r / "campaign_a_batch_summary.json"
        if not p.exists():
            raise SystemExit(f"[FAIL] Missing summary: {p}")

        s = json.loads(p.read_text(encoding="utf-8"))

        for k in [
            "executed_session_count",
            "executed_query_count",
            "strict_match_count",
            "session_context_match_count",
            "allow_count",
            "block_count",
            "allow_business_physical_execution_count",
            "block_business_physical_execution_count",
            "blocked_before_business_execution_count",
            "canonical_gate_contract_ok_count",
            "canonical_gate_contract_violation_count",
            "http_error_count",
            "mismatch_count",
        ]:
            totals[k] += int(s.get(k, 0) or 0)

        for reason, count in (s.get("decision_reason_counts") or {}).items():
            reason_counts[reason] = reason_counts.get(reason, 0) + int(count)

    q = totals["executed_query_count"] or 1
    totals["strict_match_rate"] = totals["strict_match_count"] / q
    totals["session_context_match_rate"] = totals["session_context_match_count"] / q
    totals["decision_reason_counts"] = reason_counts

    required_zero = [
        "mismatch_count",
        "http_error_count",
        "canonical_gate_contract_violation_count",
        "block_business_physical_execution_count",
    ]

    if totals["run_count"] != 10:
        totals["ok"] = False
    if totals["executed_session_count"] != 1000:
        totals["ok"] = False
    for k in required_zero:
        if totals[k] != 0:
            totals["ok"] = False

    out = evidence_root / "campaign_a_1000_preliminary_summary.json"
    out.write_text(json.dumps(totals, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(totals, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
