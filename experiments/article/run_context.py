#!/usr/bin/env python3
"""Run context utilities for reproducible article experiments."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:
        return ""


def git_info() -> Dict[str, Any]:
    full_commit = _git(["rev-parse", "HEAD"])
    short_commit = _git(["rev-parse", "--short", "HEAD"])
    branch = _git(["branch", "--show-current"])
    status = _git(["status", "--short"])
    return {
        "branch": branch,
        "commit": full_commit,
        "short_commit": short_commit,
        "dirty": bool(status.strip()),
        "status_short": status.splitlines(),
    }


def make_run_id(seed: int, provided: str | None = None) -> str:
    if provided:
        return provided
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_commit = git_info().get("short_commit") or "nogit"
    return f"{stamp}_{short_commit}_seed{seed}"


def create_run_context(
    out_root: Path,
    seed: int,
    run_id: str | None = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    out_root = out_root.resolve()
    rid = make_run_id(seed=seed, provided=run_id)
    run_dir = out_root / rid

    if run_dir.exists() and not overwrite:
        raise SystemExit(f"[FAIL] run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "stats").mkdir(exist_ok=True)
    (run_dir / "tables").mkdir(exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()

    ctx = {
        "run_id": rid,
        "run_dir": str(run_dir),
        "created_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "created_at_local": now_local.replace(microsecond=0).isoformat(),
        "timezone_policy": "UTC is canonical; local time is informational.",
        "seed": seed,
        "git": git_info(),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "platform": platform.platform(),
        },
    }

    write_json(run_dir / "run_context.json", ctx)
    write_environment(run_dir)
    write_git_status(run_dir)
    return ctx


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_environment(run_dir: Path) -> None:
    lines = [
        f"python_executable={sys.executable}",
        f"python_version={sys.version}",
        f"platform={platform.platform()}",
        f"cwd={Path.cwd()}",
    ]
    run_dir.joinpath("environment.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_git_status(run_dir: Path) -> None:
    """Write the repository state at run creation time.

    The manifest already stores the exact commit. This file intentionally avoids
    embedding recent commit messages, so generated article artifacts do not
    expose internal development history.
    """
    status = _git(["status", "--short"])
    branch = _git(["branch", "--show-current"])
    commit = _git(["rev-parse", "HEAD"])
    text = "=== git identity ===\n"
    text += f"branch={branch}\n"
    text += f"commit={commit}\n\n"
    text += "=== git status --short ===\n"
    text += status + "\n"
    run_dir.joinpath("git_status.txt").write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksums(run_dir: Path) -> None:
    rows: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "checksums.sha256":
            continue
        rel = path.relative_to(run_dir).as_posix()
        rows.append(f"{sha256_file(path)}  {rel}")
    run_dir.joinpath("checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")
