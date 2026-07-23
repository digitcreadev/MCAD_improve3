#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


REQUIRED_ENDPOINT_MARKERS = [
    '@app.get("/mcad/reports/current/session")',
    '@app.get("/mcad/reports/current/session/markdown")',
    '@app.get("/mcad/reports/current/session/csv")',
    '@app.get("/mcad/metrics/current/session")',
    '@app.get("/mcad/metrics/current/session/markdown")',
    '@app.get("/mcad/metrics/current/session/csv")',
    '@app.get("/mcad/evidence/current")',
    '@app.get("/mcad/evidence/current/archive")',
    '@app.get("/mcad/demo-evidence/latest")',
    '@app.get("/mcad/demo-evidence/latest/json")',
    '@app.get("/mcad/demo-evidence/latest/csv")',
    '@app.get("/mcad/demo-evidence/latest/markdown")',
    '@app.get("/mcad/demo-evidence/latest/bundle.zip")',
    '@app.post("/mcad/demo-evidence/run")',
    '@app.get("/mcad/demo-evidence/run/status")'
]

REQUIRED_TEXT_MARKERS = [
    "physical_execution",
    "blocked_before_execution",
    "adapter_id",
    "selected_dw_id",
    "execution_path",
    "elapsed_ms",
    "response_bytes",
    "response_digest",
    "xmla_response_type",
    "row_count",
    "contract_version",
    "mcad.execution_evidence.v1",
    "mcad.session_report.v1",
    "mcad.experimental_metrics.v1"
]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy-app", default="bi-stack/mcad-proxy/app.py")
    ap.add_argument("--proxy-ui", default="bi-stack/mcad-proxy/session_ui.html")
    ap.add_argument("--out", default="reports/article_experiments/ui_report_contract_audit.json")
    args = ap.parse_args()

    proxy_app = ROOT / args.proxy_app
    proxy_ui = ROOT / args.proxy_ui

    app_text = read_text(proxy_app)
    ui_text = read_text(proxy_ui)
    combined = app_text + "\n" + ui_text

    missing_endpoints = [m for m in REQUIRED_ENDPOINT_MARKERS if m not in app_text]
    missing_markers = [m for m in REQUIRED_TEXT_MARKERS if m not in combined]

    status = {
        "ok": not missing_endpoints and not missing_markers,
        "proxy_app": str(proxy_app.relative_to(ROOT)),
        "proxy_ui": str(proxy_ui.relative_to(ROOT)),
        "endpoint_markers_checked": len(REQUIRED_ENDPOINT_MARKERS),
        "text_markers_checked": len(REQUIRED_TEXT_MARKERS),
        "missing_endpoints": missing_endpoints,
        "missing_text_markers": missing_markers,
        "conclusion": (
            "UI reports appear sufficient for Campaigns B and C normalization."
            if not missing_endpoints and not missing_markers
            else "UI reports need small hardening before being used as article evidence."
        ),
        "required_article_normalization_fields": [
            "article_run_id",
            "campaign_id",
            "dataset_id",
            "objective_id",
            "session_template_id",
            "session_instance_id",
            "query_index",
            "query_id",
            "expected_decision",
            "decision",
            "backend_id",
            "dw_id",
            "execution_path",
            "adapter_id",
            "physical_execution",
            "blocked_before_execution",
            "row_count_or_cell_count",
            "elapsed_ms",
            "response_digest",
            "block_reason"
        ]
    }

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
