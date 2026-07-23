#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prepare a clean CKG runtime for an article campaign while preserving the CKG catalog."
    )
    ap.add_argument("--campaign-id", required=True, help="Example: B_multidataset or C_backend_portability")
    ap.add_argument("--ckg-events", default="bi-stack/mcad-api-data/ckg_events.jsonl")
    ap.add_argument("--ckg-state", default="bi-stack/mcad-api-data/ckg_state.json")
    ap.add_argument("--checkpoint-dir", default="reports/article_experiments/_safe_checkpoints")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ckg_events = ROOT / args.ckg_events
    ckg_state = ROOT / args.ckg_state
    checkpoint_root = ROOT / args.checkpoint_dir

    stamp = utc_stamp()
    checkpoint_dir = checkpoint_root / f"before_{args.campaign_id}_{stamp}"

    current_events_lines = 0
    if ckg_events.exists():
        current_events_lines = sum(1 for _ in ckg_events.open(encoding="utf-8"))

    state = read_json(ckg_state)

    preserved = {
        "nodes": state.get("nodes", []),
        "edges": state.get("edges", []),
        "objectives": state.get("objectives", {}),
    }

    new_state = {
        **preserved,
        "history": [],
        "session_coverage": {},
        "_campaign_reset_note": {
            "campaign_id": args.campaign_id,
            "reset_ts_utc": stamp,
            "policy": "Preserve CKG catalog nodes/edges/objectives; reset runtime events/history/session_coverage.",
            "previous_events_line_count": current_events_lines,
        },
    }

    report = {
        "ok": True,
        "dry_run": args.dry_run,
        "campaign_id": args.campaign_id,
        "checkpoint_dir": str(checkpoint_dir.relative_to(ROOT)),
        "ckg_events": str(ckg_events.relative_to(ROOT)),
        "ckg_state": str(ckg_state.relative_to(ROOT)),
        "current_events_line_count": current_events_lines,
        "preserved_nodes_count": len(preserved.get("nodes") or []),
        "preserved_edges_count": len(preserved.get("edges") or []),
        "preserved_objectives_count": len(preserved.get("objectives") or {}),
        "runtime_after_reset": {
            "ckg_events_lines": 0,
            "history_count": 0,
            "session_coverage_count": 0,
        },
    }

    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if ckg_events.exists():
        shutil.copy2(ckg_events, checkpoint_dir / "ckg_events_before_reset.jsonl")
    if ckg_state.exists():
        shutil.copy2(ckg_state, checkpoint_dir / "ckg_state_before_reset.json")

    ckg_events.parent.mkdir(parents=True, exist_ok=True)
    ckg_events.write_text("", encoding="utf-8")
    write_json(ckg_state, new_state)

    write_json(checkpoint_dir / "prepare_ckg_runtime_report.json", report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
