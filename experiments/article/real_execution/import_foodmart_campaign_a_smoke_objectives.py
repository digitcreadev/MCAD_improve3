#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "http://localhost:9000"

INSTALLED = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample/installed_smoke_sample.json"
OUT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample/imported_objectives_report.json"


def post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    installed = json.loads(INSTALLED.read_text(encoding="utf-8"))
    objectives = []

    for item in installed["installed"]:
        p = ROOT / item["installed_objective"]
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj.setdefault("name", obj.get("title") or obj.get("id") or obj.get("objective_id"))
        obj.setdefault("label", obj.get("name"))
        objectives.append(obj)

    report = post_json("/mcad/objectives/import", {"objectives": objectives})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
