#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
TARGET_OBJECTIVE_FILE = Path("bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json")
DATA_REL = Path("bi-stack/mcad-api-data")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def file_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    return {
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for line in f if line.strip())


def build_clean_ckg_state(source: dict[str, Any]) -> dict[str, Any]:
    # Preserve the stable graph catalog only. Runtime evidence must start empty.
    out: dict[str, Any] = {
        "nodes": source.get("nodes", {}),
        "edges": source.get("edges", {}),
        "history": [],
        "objectives": source.get("objectives", {}),
        "session_coverage": {},
        "_ui_clean_runtime_note": {
            "created_utc": utc_stamp(),
            "policy": (
                "Preserve stable CKG nodes/edges/objectives; clear campaign history, "
                "session coverage and live evidence for a fresh UI session."
            ),
        },
    }
    # Keep schema-compatible optional fields, but clear their runtime content.
    for key in ("session_weighted_coverage", "session_resource_coverage"):
        if key in source:
            out[key] = {}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Back up the live MCAD UI runtime and prepare a clean, reproducible interactive profile."
    )
    ap.add_argument("--repo", default=".", help="MCAD_improve3 repository root")
    ap.add_argument(
        "--profile",
        choices=["adventureworks", "foodmart", "empty"],
        default="adventureworks",
        help="Imported-objective profile to preload after reset",
    )
    ap.add_argument("--apply", action="store_true", help="Actually modify bi-stack/mcad-api-data")
    ap.add_argument(
        "--backup-root",
        default="exports/ui_runtime_backups",
        help="Backup root relative to repo",
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    data_dir = repo / DATA_REL
    required = [
        repo / "bi-stack/mcad-proxy/session_ui.html",
        repo / "bi-stack/mcad-proxy/app.py",
        repo / "bi-stack/mcad-api/app.py",
        data_dir / "ckg_state.json",
        data_dir / "decision_details.json",
        data_dir / "imported_objectives.json",
        data_dir / "ckg_events.jsonl",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print(json.dumps({"ok": False, "missing": missing}, indent=2), file=sys.stderr)
        return 2

    objective: dict[str, Any] | None = None
    if args.profile == "adventureworks":
        objective_path = repo / TARGET_OBJECTIVE_FILE
        if not objective_path.exists():
            print(f"[FAIL] Missing target objective: {objective_path}", file=sys.stderr)
            return 2
        objective = read_json(objective_path)
        if str(objective.get("id")) != TARGET_OBJECTIVE_ID:
            print(f"[FAIL] Unexpected objective id in {objective_path}", file=sys.stderr)
            return 2

    before = {
        "ckg_state": file_summary(data_dir / "ckg_state.json"),
        "decision_details": file_summary(data_dir / "decision_details.json"),
        "imported_objectives": file_summary(data_dir / "imported_objectives.json"),
        "ckg_events": file_summary(data_dir / "ckg_events.jsonl"),
        "ckg_event_lines": count_jsonl(data_dir / "ckg_events.jsonl"),
    }

    source_state = read_json(data_dir / "ckg_state.json")
    clean_state = build_clean_ckg_state(source_state)
    imported = {"objectives": [objective] if objective is not None else []}

    plan = {
        "ok": True,
        "mode": "apply" if args.apply else "dry_run",
        "repo": str(repo),
        "profile": args.profile,
        "target_objective_id": TARGET_OBJECTIVE_ID if objective else None,
        "before": before,
        "planned_after": {
            "ckg_history_count": 0,
            "session_coverage_count": 0,
            "decision_detail_session_count": 0,
            "ckg_event_lines": 0,
            "imported_objective_count": len(imported["objectives"]),
        },
        "untouched": [
            "reports/article_experiments/ckg_runtimes/locked/**",
            "reports/article_experiments/**",
            "bi-stack/demo-evidence/**",
            "bi-stack/objectives/**",
            "bi-stack/direct-scenarios/**",
            "all source code",
        ],
    }

    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("\n[DRY-RUN] Re-run with --apply after reviewing the plan.")
        return 0

    stamp = utc_stamp()
    backup_dir = repo / args.backup_root / f"ui_runtime_before_reset_{stamp}"
    if backup_dir.exists():
        print(f"[FAIL] Backup already exists: {backup_dir}", file=sys.stderr)
        return 2
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(data_dir, backup_dir)

    backup_manifest = {
        "created_utc": stamp,
        "source": str(data_dir.relative_to(repo)),
        "profile_requested": args.profile,
        "files": {},
    }
    for p in sorted(x for x in backup_dir.rglob("*") if x.is_file()):
        backup_manifest["files"][p.relative_to(backup_dir).as_posix()] = file_summary(p)
    atomic_write_json(backup_dir / "BACKUP_MANIFEST.json", backup_manifest)

    atomic_write_json(data_dir / "ckg_state.json", clean_state)
    atomic_write_json(data_dir / "decision_details.json", {})
    atomic_write_json(data_dir / "imported_objectives.json", imported)
    atomic_write_text(data_dir / "ckg_events.jsonl", "")

    after = {
        "ckg_state": file_summary(data_dir / "ckg_state.json"),
        "decision_details": file_summary(data_dir / "decision_details.json"),
        "imported_objectives": file_summary(data_dir / "imported_objectives.json"),
        "ckg_events": file_summary(data_dir / "ckg_events.jsonl"),
        "ckg_event_lines": count_jsonl(data_dir / "ckg_events.jsonl"),
    }
    manifest = {
        **plan,
        "mode": "applied",
        "backup_dir": str(backup_dir.relative_to(repo)),
        "after": after,
        "next_steps": [
            "docker compose -f bi-stack/docker-compose.yml down",
            "docker compose -f bi-stack/docker-compose.yml up -d --build",
            "clear browser sessionStorage for the Codespaces origin or open a new incognito window",
            "open /mcad/session/ui and create an AdventureWorks SQL Direct session",
        ],
    }
    atomic_write_json(data_dir / "UI_CLEAN_RUNTIME_MANIFEST.json", manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("\n[OK] Clean UI runtime prepared. Locked A/B/C evidence was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
