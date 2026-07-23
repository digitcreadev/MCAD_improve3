#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LIVE_EVENTS = ROOT / "bi-stack/mcad-api-data/ckg_events.jsonl"
LIVE_STATE = ROOT / "bi-stack/mcad-api-data/ckg_state.json"

RUNTIME_ROOT = ROOT / "reports/article_experiments/ckg_runtimes"
WORK_ROOT = RUNTIME_ROOT / "work"
LOCKED_ROOT = RUNTIME_ROOT / "locked"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def make_writable(path: Path) -> None:
    if not path.exists():
        return
    for p in path.rglob("*"):
        try:
            mode = p.stat().st_mode
            p.chmod(mode | stat.S_IWUSR)
        except Exception:
            pass
    try:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    except Exception:
        pass


def make_readonly(path: Path) -> None:
    if not path.exists():
        return
    for p in path.rglob("*"):
        try:
            mode = p.stat().st_mode
            p.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        except Exception:
            pass
    try:
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    except Exception:
        pass


def runtime_dir(kind: str, runtime_id: str) -> Path:
    if kind == "work":
        return WORK_ROOT / runtime_id
    if kind == "locked":
        return LOCKED_ROOT / runtime_id
    raise SystemExit(f"[FAIL] Unknown runtime kind: {kind}")


def ensure_runtime_files(rd: Path) -> None:
    if not (rd / "ckg_events.jsonl").exists():
        raise SystemExit(f"[FAIL] Missing runtime events: {rd / 'ckg_events.jsonl'}")
    if not (rd / "ckg_state.json").exists():
        raise SystemExit(f"[FAIL] Missing runtime state: {rd / 'ckg_state.json'}")


def save_live_to_runtime(kind: str, runtime_id: str, note: str = "", readonly: bool = False) -> dict:
    rd = runtime_dir(kind, runtime_id)
    if rd.exists() and readonly:
        make_writable(rd)
    rd.mkdir(parents=True, exist_ok=True)

    if LIVE_EVENTS.exists():
        shutil.copy2(LIVE_EVENTS, rd / "ckg_events.jsonl")
    else:
        (rd / "ckg_events.jsonl").write_text("", encoding="utf-8")

    if LIVE_STATE.exists():
        shutil.copy2(LIVE_STATE, rd / "ckg_state.json")
    else:
        write_json(rd / "ckg_state.json", {})

    manifest = {
        "runtime_id": runtime_id,
        "kind": kind,
        "saved_from_live_utc": stamp(),
        "note": note,
        "events_line_count": count_lines(rd / "ckg_events.jsonl"),
        "state_file": "ckg_state.json",
        "events_file": "ckg_events.jsonl",
        "readonly": bool(readonly),
    }
    write_json(rd / "runtime_manifest.json", manifest)

    if readonly:
        make_readonly(rd)

    return manifest


def activate_runtime(kind: str, runtime_id: str, backup_live: bool = True) -> dict:
    rd = runtime_dir(kind, runtime_id)
    ensure_runtime_files(rd)

    if backup_live:
        backup_id = f"_live_backup_before_activate_{kind}_{runtime_id.replace('/', '__')}_{stamp()}"
        save_live_to_runtime("work", backup_id, note=f"Automatic live backup before activating {kind}/{runtime_id}")

    LIVE_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rd / "ckg_events.jsonl", LIVE_EVENTS)
    shutil.copy2(rd / "ckg_state.json", LIVE_STATE)

    return {
        "ok": True,
        "activated_kind": kind,
        "activated_runtime": runtime_id,
        "activated_utc": stamp(),
        "live_events_line_count": count_lines(LIVE_EVENTS),
        "note": "Activation copies runtime files into live mcad-api data paths. It does not modify the source runtime.",
    }


def init_clean_work_runtime(runtime_id: str, from_state: Path) -> dict:
    rd = runtime_dir("work", runtime_id)
    if rd.exists():
        make_writable(rd)
    rd.mkdir(parents=True, exist_ok=True)

    state = read_json(from_state)

    new_state = {
        "nodes": state.get("nodes", []),
        "edges": state.get("edges", []),
        "objectives": state.get("objectives", {}),
        "history": [],
        "session_coverage": {},
        "_campaign_reset_note": {
            "runtime_id": runtime_id,
            "kind": "work",
            "created_utc": stamp(),
            "policy": "Preserve CKG catalog nodes/edges/objectives; reset runtime evidence/history/session_coverage.",
        },
    }

    (rd / "ckg_events.jsonl").write_text("", encoding="utf-8")
    write_json(rd / "ckg_state.json", new_state)

    manifest = {
        "runtime_id": runtime_id,
        "kind": "work",
        "created_utc": stamp(),
        "source_state": str(from_state),
        "events_line_count": 0,
        "preserved_nodes_count": len(new_state.get("nodes", []) or []),
        "preserved_edges_count": len(new_state.get("edges", []) or []),
        "preserved_objectives_count": len(new_state.get("objectives", {}) or {}),
        "readonly": False,
    }
    write_json(rd / "runtime_manifest.json", manifest)
    return manifest


def clone_runtime(src_kind: str, src_id: str, dst_kind: str, dst_id: str, readonly: bool = False) -> dict:
    src = runtime_dir(src_kind, src_id)
    dst = runtime_dir(dst_kind, dst_id)
    ensure_runtime_files(src)

    if dst.exists():
        make_writable(dst)
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    make_writable(dst)

    manifest = read_json(dst / "runtime_manifest.json")
    manifest.update({
        "runtime_id": dst_id,
        "kind": dst_kind,
        "cloned_from": f"{src_kind}/{src_id}",
        "cloned_utc": stamp(),
        "events_line_count": count_lines(dst / "ckg_events.jsonl"),
        "readonly": bool(readonly),
    })
    write_json(dst / "runtime_manifest.json", manifest)

    if readonly:
        make_readonly(dst)

    return manifest


def lock_work_runtime(src_id: str, locked_id: str) -> dict:
    return clone_runtime("work", src_id, "locked", locked_id, readonly=True)


def status() -> dict:
    items = []
    for kind, root in [("work", WORK_ROOT), ("locked", LOCKED_ROOT)]:
        if root.exists():
            for rd in sorted(p for p in root.rglob("*") if p.is_dir()):
                if (rd / "ckg_events.jsonl").exists() or (rd / "runtime_manifest.json").exists():
                    runtime_id = str(rd.relative_to(root))
                    items.append({
                        "kind": kind,
                        "runtime_id": runtime_id,
                        "events_line_count": count_lines(rd / "ckg_events.jsonl"),
                        "has_state": (rd / "ckg_state.json").exists(),
                        "manifest": (rd / "runtime_manifest.json").exists(),
                    })

    return {
        "live": {
            "events_line_count": count_lines(LIVE_EVENTS),
            "ckg_events": str(LIVE_EVENTS.relative_to(ROOT)),
            "ckg_state": str(LIVE_STATE.relative_to(ROOT)),
        },
        "runtime_root": str(RUNTIME_ROOT.relative_to(ROOT)),
        "runtimes": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("save-live")
    p.add_argument("--kind", choices=["work", "locked"], default="work")
    p.add_argument("--runtime-id", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--readonly", action="store_true")

    p = sub.add_parser("activate")
    p.add_argument("--kind", choices=["work", "locked"], default="work")
    p.add_argument("--runtime-id", required=True)
    p.add_argument("--no-backup-live", action="store_true")

    p = sub.add_parser("init-clean-work")
    p.add_argument("--runtime-id", required=True)
    p.add_argument("--from-state", default="bi-stack/mcad-api-data/ckg_state.json")

    p = sub.add_parser("clone")
    p.add_argument("--src-kind", choices=["work", "locked"], required=True)
    p.add_argument("--src-id", required=True)
    p.add_argument("--dst-kind", choices=["work", "locked"], required=True)
    p.add_argument("--dst-id", required=True)
    p.add_argument("--readonly", action="store_true")

    p = sub.add_parser("lock-work")
    p.add_argument("--src-id", required=True)
    p.add_argument("--locked-id", required=True)

    sub.add_parser("status")

    args = ap.parse_args()

    if args.cmd == "save-live":
        out = save_live_to_runtime(args.kind, args.runtime_id, args.note, readonly=args.readonly)
    elif args.cmd == "activate":
        out = activate_runtime(args.kind, args.runtime_id, backup_live=not args.no_backup_live)
    elif args.cmd == "init-clean-work":
        src = Path(args.from_state)
        if not src.is_absolute():
            src = ROOT / src
        out = init_clean_work_runtime(args.runtime_id, src)
    elif args.cmd == "clone":
        out = clone_runtime(args.src_kind, args.src_id, args.dst_kind, args.dst_id, readonly=args.readonly)
    elif args.cmd == "lock-work":
        out = lock_work_runtime(args.src_id, args.locked_id)
    elif args.cmd == "status":
        out = status()
    else:
        raise SystemExit("[FAIL] Unknown command")

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
