#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
BATCH_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_batches"
CKG_EVENTS = ROOT / "bi-stack/mcad-api-data/ckg_events.jsonl"
CKG_STATE = ROOT / "bi-stack/mcad-api-data/ckg_state.json"
ARCHIVE = ROOT / "reports/article_experiments/_archived_before_campaign_1000/recovery_after_crash"

OFFSETS = [0,100,200,300,400,500,600,700,800,900]

def load_summary(d: Path):
    p = d / "campaign_a_batch_summary.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def is_valid_summary(s, offset: int) -> bool:
    if not s:
        return False
    return (
        s.get("ok") is True
        and int(s.get("offset", -1)) == offset
        and int(s.get("requested_session_limit", 0) or 0) == 100
        and int(s.get("executed_session_count", 0) or 0) == 100
        and str(s.get("dw_id")) == "foodmart"
        and str(s.get("raw_policy")) == "none"
        and int(s.get("mismatch_count", 0) or 0) == 0
        and int(s.get("http_error_count", 0) or 0) == 0
        and int(s.get("canonical_gate_contract_violation_count", 0) or 0) == 0
        and int(s.get("block_business_physical_execution_count", 0) or 0) == 0
    )

def latest_valid_run_for_offset(offset: int):
    candidates = []
    for d in BATCH_ROOT.glob("foodmart_campaign_a_batch_100_*"):
        s = load_summary(d)
        if is_valid_summary(s, offset):
            p = d / "campaign_a_batch_summary.json"
            candidates.append((p.stat().st_mtime, d, s))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0]

def event_constraints(e):
    out = []
    for k in ("covered_constraints", "calculable_constraints"):
        v = e.get(k)
        if isinstance(v, list):
            out.extend(v)
    urs = e.get("useful_result_summary") or {}
    if isinstance(urs, dict):
        for k in ("covered_constraints", "calculable_constraints", "linked_constraints"):
            v = urs.get(k)
            if isinstance(v, list):
                out.extend(v)
    return sorted(set(str(x) for x in out if x))

def main():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    valid = []
    expected_ckg_events = 0

    for offset in OFFSETS:
        found = latest_valid_run_for_offset(offset)
        if not found:
            continue
        _, d, s = found
        valid.append((offset, d, s))
        expected_ckg_events += int(s.get("allow_business_physical_execution_count", 0) or 0)

    current_lines = 0
    lines = []
    if CKG_EVENTS.exists():
        lines = CKG_EVENTS.read_text(encoding="utf-8").splitlines()
        current_lines = len(lines)

    print("=== Valid completed offsets ===")
    for offset, d, s in valid:
        print(f"offset={offset} allow_physical={s.get('allow_business_physical_execution_count')} run={d}")

    print()
    print("expected_ckg_events_from_valid_offsets:", expected_ckg_events)
    print("current_ckg_events_lines:", current_lines)

    if current_lines < expected_ckg_events:
        raise SystemExit(
            "[FAIL] ckg_events.jsonl has fewer events than expected from valid completed offsets. "
            "Do not resume before manual inspection."
        )

    if current_lines > expected_ckg_events:
        print("[REPAIR] Truncating orphan CKG events from interrupted offset.")
        shutil.copy2(CKG_EVENTS, ARCHIVE / f"ckg_events_before_truncate_{ts}.jsonl")
        kept = lines[:expected_ckg_events]
        CKG_EVENTS.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        lines = kept
    else:
        print("[OK] No orphan CKG events detected.")

    if CKG_STATE.exists():
        shutil.copy2(CKG_STATE, ARCHIVE / f"ckg_state_before_runtime_rebuild_{ts}.json")

        state = json.loads(CKG_STATE.read_text(encoding="utf-8"))
        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass

        session_coverage = {}
        for e in events:
            sid = e.get("session_id")
            if not sid:
                continue
            constraints = event_constraints(e)
            if not constraints:
                continue
            session_coverage.setdefault(sid, set()).update(constraints)

        state["history"] = events
        state["session_coverage"] = {
            sid: sorted(vals) for sid, vals in session_coverage.items()
        }
        state["_campaign_recovery_note"] = {
            "kind": "rebuild_runtime_state_after_codespace_crash",
            "recovered_at_utc": ts,
            "valid_offsets": [offset for offset, _, _ in valid],
            "ckg_event_count": len(events),
        }

        CKG_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[OK] Rebuilt ckg_state runtime fields from retained ckg_events.jsonl.")

    print()
    print("=== Recovery result ===")
    print("valid_offset_count:", len(valid))
    print("valid_offsets:", [offset for offset, _, _ in valid])
    print("ckg_events_lines_after:", len(CKG_EVENTS.read_text(encoding='utf-8').splitlines()) if CKG_EVENTS.exists() else 0)

if __name__ == "__main__":
    main()
