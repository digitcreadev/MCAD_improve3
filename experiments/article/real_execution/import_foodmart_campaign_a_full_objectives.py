#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "http://localhost:9000"

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
OBJ_DIR = LIB / "objectives"

OUT = ROOT / "reports/article_experiments/foodmart_campaign_a_full_install/imported_full_objectives_report.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    objectives = []

    for p in sorted(OBJ_DIR.glob("objective_fm_a_*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj.setdefault("name", obj.get("title") or obj.get("id") or obj.get("objective_id"))
        obj.setdefault("label", obj.get("name"))
        objectives.append(obj)

    report = post_json("/mcad/objectives/import", {"objectives": objectives})
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "ok": report.get("ok"),
        "submitted_objective_count": len(objectives),
        "report_file": str(OUT.relative_to(ROOT)),
        "raw_report": report,
    }, indent=2, ensure_ascii=False))

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
