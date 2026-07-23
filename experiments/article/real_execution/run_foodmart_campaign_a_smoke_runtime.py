#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = os.environ.get("MCAD_BASE_URL", "http://localhost:9000").rstrip("/")
DW_ID = os.environ.get("MCAD_SMOKE_DW_ID", "foodmart")

INSTALLED = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample/installed_smoke_sample.json"

RUN_ID = datetime.now(timezone.utc).strftime("foodmart_campaign_a_smoke_%Y%m%dT%H%M%SZ")
OUT_DIR = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_runtime" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Requêtes choisies pour couvrir ALLOW, BLOCK, bad grain, wrong slicer et redundancy.
SELECTED_ROLES = {
    "ALLOW_TARGET_PRIMARY",
    "ALLOW_TARGET_COMPLEMENTARY",
    "ALLOW_SUPERPOSED_MEASURES",
    "ALLOW_CATEGORY_AXIS_COVERAGE",
    "ALLOW_STATE_AXIS_COVERAGE",
    "BLOCK_WRONG_CATEGORY",
    "BLOCK_WRONG_STATE",
    "BLOCK_BAD_GRAIN_YEAR",
    "BLOCK_REDUNDANT_PRIMARY",
    "BLOCK_NON_TARGET_MEASURE",
}


def http_json(method: str, path: str, payload: Any | None = None, timeout: int = 240) -> dict:
    url = BASE_URL + path
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", errors="replace")
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(txt)
        except Exception:
            body = {"raw": txt[:2000]}
        return {
            "ok": False,
            "http_error": e.code,
            "url": url,
            "body": body,
        }


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def norm_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def extract_response_fields(resp: dict) -> dict[str, Any]:
    decision_obj = resp.get("decision") if isinstance(resp.get("decision"), dict) else {}
    ev = resp.get("execution_evidence") if isinstance(resp.get("execution_evidence"), dict) else {}
    exe = ev.get("execution") if isinstance(ev.get("execution"), dict) else {}
    gate = ev.get("mcad_gate") if isinstance(ev.get("mcad_gate"), dict) else {}

    decision = str(decision_obj.get("decision") or "").upper()
    reason = (
        decision_obj.get("decision_reason_code")
        or decision_obj.get("reason_code")
        or decision_obj.get("reason")
        or ""
    )

    physical = norm_bool(exe.get("physical_execution"))
    if physical is None:
        physical = norm_bool(resp.get("physical_execution"))

    blocked_before_execution = norm_bool(ev.get("blocked_before_execution"))
    if blocked_before_execution is None:
        blocked_before_execution = bool(decision == "BLOCK" and physical is False)

    return {
        "decision": decision,
        "reason": reason,
        "phi": decision_obj.get("phi"),
        "sat": decision_obj.get("sat"),
        "real": decision_obj.get("real"),
        "ceval": decision_obj.get("ceval"),
        "physical_execution": physical,
        "blocked_before_execution": blocked_before_execution,
        "execution_path": exe.get("execution_path") or resp.get("execution_path"),
        "adapter_id": exe.get("adapter_id") or resp.get("adapter_id"),
        "status_code": exe.get("status_code"),
        "elapsed_ms": exe.get("elapsed_ms"),
        "response_bytes": exe.get("response_bytes"),
        "response_digest": exe.get("response_digest") or exe.get("result_digest"),
        "mcad_allowed": gate.get("allowed_by_mcad"),
        "evidence_contract": ev.get("contract_version"),
    }


def main() -> int:
    installed = json.loads(INSTALLED.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    raw_index: list[dict[str, Any]] = []

    # Vérification visibilité scénarios.
    scen_catalog = http_json("GET", "/bi/scenarios?include_incompatible=true", timeout=60)
    scen_txt = json.dumps(scen_catalog, ensure_ascii=False)
    missing_scenarios = [
        x["scenario_id"]
        for x in installed["installed"]
        if x["scenario_id"] not in scen_txt
    ]

    if missing_scenarios:
        summary = {
            "ok": False,
            "error": "Some installed scenarios are not visible through /bi/scenarios.",
            "missing_scenarios": missing_scenarios,
        }
        write_json(OUT_DIR / "foodmart_campaign_a_smoke_summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 1

    for sample in installed["installed"]:
        scenario_id = sample["scenario_id"]
        objective_id = sample["objective_id"]
        scenario_path = ROOT / sample["installed_scenario"]

        scenario_queries = json.loads(scenario_path.read_text(encoding="utf-8"))
        selected_queries = [
            q for q in scenario_queries
            if q.get("query_role") in SELECTED_ROLES
        ]

        session_resp = http_json(
            "POST",
            "/mcad/session/new",
            {"objective_id": objective_id, "dw_id": DW_ID},
            timeout=90,
        )

        session_id = (
            session_resp.get("active", {}).get("session_id")
            or session_resp.get("session", {}).get("session_id")
            or ""
        )

        for index, q in enumerate(selected_queries, start=1):
            query_id = q.get("logical_query_id") or q.get("id") or f"{scenario_id}_Q{index:02d}"
            expected = str(q.get("expected_decision") or "").upper()

            payload = {
                "mdx": q.get("mdx"),
                "query_type": "mdx",
                "query_id": query_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "dw_id": DW_ID,
                "source_scenario_id": scenario_id,
                "scenario_id": scenario_id,
                "scenario_query_index": q.get("id"),
                "scenario_query_id": query_id,
                "scenario_name": scenario_id,
                "scenario_source": "campaign_a_smoke_runtime",
                "execution_mode": "campaign_a_smoke_runtime",
                "allow_fallback": False,
            }

            t0 = time.time()
            resp = http_json("POST", "/bi/execute", payload, timeout=300)
            client_elapsed_ms = int((time.time() - t0) * 1000)

            fields = extract_response_fields(resp) if resp.get("ok", True) is not False else {}

            row = {
                "run_id": RUN_ID,
                "campaign_id": "A_foodmart_deep",
                "sample_type": "runtime_smoke",
                "scenario_id": scenario_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "dw_id": DW_ID,
                "query_id": query_id,
                "query_role": q.get("query_role"),
                "expected_decision": expected,
                "decision": fields.get("decision", ""),
                "decision_match": expected == fields.get("decision", ""),
                "reason": fields.get("reason", ""),
                "physical_execution": fields.get("physical_execution"),
                "blocked_before_execution": fields.get("blocked_before_execution"),
                "execution_path": fields.get("execution_path"),
                "adapter_id": fields.get("adapter_id"),
                "status_code": fields.get("status_code"),
                "elapsed_ms": fields.get("elapsed_ms"),
                "client_elapsed_ms": client_elapsed_ms,
                "response_digest": fields.get("response_digest"),
                "phi": fields.get("phi"),
                "sat": fields.get("sat"),
                "real": fields.get("real"),
                "ceval": fields.get("ceval"),
                "http_error": resp.get("http_error"),
                "ok_response": resp.get("ok"),
            }

            rows.append(row)

            raw_file = OUT_DIR / "raw" / f"{scenario_id}_{q.get('id','Q')}.json"
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            write_json(raw_file, resp)
            raw_index.append({
                "query_id": query_id,
                "raw_file": str(raw_file.relative_to(ROOT)),
            })

            print(
                f"{scenario_id} {q.get('id')} expected={expected} "
                f"decision={row['decision']} match={row['decision_match']} "
                f"physical={row['physical_execution']} blocked_before={row['blocked_before_execution']}"
            )

    total = len(rows)
    matches = sum(1 for r in rows if r["decision_match"] is True)
    allow_rows = [r for r in rows if r["decision"] == "ALLOW"]
    block_rows = [r for r in rows if r["decision"] == "BLOCK"]

    summary = {
        "ok": total > 0 and matches == total,
        "run_id": RUN_ID,
        "campaign_id": "A_foodmart_deep",
        "sample_scenario_count": len(installed["installed"]),
        "executed_query_count": total,
        "decision_match_count": matches,
        "decision_match_rate": matches / total if total else 0.0,
        "allow_count": len(allow_rows),
        "block_count": len(block_rows),
        "physical_execution_count": sum(1 for r in rows if r["physical_execution"] is True),
        "blocked_before_execution_count": sum(1 for r in rows if r["blocked_before_execution"] is True),
        "http_error_count": sum(1 for r in rows if r.get("http_error")),
        "dw_id": DW_ID,
        "output_dir": str(OUT_DIR.relative_to(ROOT)),
        "raw_index": raw_index,
    }

    write_csv(OUT_DIR / "foodmart_campaign_a_smoke_by_query.csv", rows)
    write_json(OUT_DIR / "foodmart_campaign_a_smoke_summary.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
