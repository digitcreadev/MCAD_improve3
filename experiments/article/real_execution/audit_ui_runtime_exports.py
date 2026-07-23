#!/usr/bin/env python3
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPORT_DIR = ROOT / "reports/article_experiments/ui_demo_export"
OUT = ROOT / "reports/article_experiments/ui_runtime_export_audit.json"

REQUIRED_MARKERS = [
    "physical_execution",
    "response_digest",
    "adapter_id",
    "execution_path"
]

RECOMMENDED_MARKERS = [
    "blocked_before_execution",
    "selected_dw_id",
    "elapsed_ms",
    "row_count",
    "cell_count",
    "objective_id",
    "session_id",
    "decision",
    "ALLOW",
    "BLOCK"
]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_bundle(path: Path) -> str:
    if not path.exists():
        return ""
    txt = ""
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".json", ".csv", ".md", ".txt")):
                txt += "\n" + z.read(name).decode("utf-8", errors="replace")
    return txt


def main() -> int:
    files = [
        EXPORT_DIR / "demo_latest.json",
        EXPORT_DIR / "demo_latest.csv",
        EXPORT_DIR / "demo_latest.md",
    ]
    bundle = EXPORT_DIR / "demo_evidence_bundle.zip"

    all_text = ""
    file_results = []

    for p in files:
        txt = read_text(p)
        all_text += "\n" + txt
        file_results.append({
            "file": str(p.relative_to(ROOT)),
            "exists": p.exists(),
            "size": p.stat().st_size if p.exists() else 0,
            "missing_required": [m for m in REQUIRED_MARKERS if m not in txt],
            "missing_recommended": [m for m in RECOMMENDED_MARKERS if m not in txt]
        })

    bundle_txt = read_bundle(bundle)
    all_text += "\n" + bundle_txt
    file_results.append({
        "file": str(bundle.relative_to(ROOT)),
        "exists": bundle.exists(),
        "size": bundle.stat().st_size if bundle.exists() else 0,
        "missing_required": [m for m in REQUIRED_MARKERS if m not in bundle_txt],
        "missing_recommended": [m for m in RECOMMENDED_MARKERS if m not in bundle_txt]
    })

    status = {
        "ok": not [m for m in REQUIRED_MARKERS if m not in all_text],
        "export_dir": str(EXPORT_DIR.relative_to(ROOT)),
        "missing_global_required": [m for m in REQUIRED_MARKERS if m not in all_text],
        "missing_global_recommended": [m for m in RECOMMENDED_MARKERS if m not in all_text],
        "files": file_results,
        "conclusion": (
            "UI demo runtime exports are sufficient for article normalization."
            if not [m for m in REQUIRED_MARKERS if m not in all_text]
            else "UI demo runtime exports still need hardening."
        )
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
