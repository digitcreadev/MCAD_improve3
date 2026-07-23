#!/usr/bin/env python3
"""MCAD V9.4.5a dual-path demo validation runner.

This script validates the demonstrator chain for:
- FoodMart via XMLA/eMondrian
- FoodMart via Direct BI
- MCAD BLOCK with no physical execution
- DW/scenario compatibility guard

It writes JSON, Markdown and CSV evidence under bi-stack/demo-evidence/runs/<timestamp>.
V9.4.5a adds readiness/retry isolation so the live check does not fail when Docker reports containers as started before mcad-api is accepting requests.
It depends only on the Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from typing import Any

OBJECTIVE_ID = "O_REAL_BEER_WA_MONTH"
SCENARIO_ID = "foodmart_q1_q6"
Q1_MDX = "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])"
Q3_BLOCK_MDX = "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[CA])"
RETRYABLE_HTTP_STATUSES = {0, 500, 502, 503, 504}
DEFAULT_RETRY_ATTEMPTS = int(os.environ.get("MCAD_DEMO_RETRY_ATTEMPTS", "24"))
DEFAULT_RETRY_SLEEP_S = float(os.environ.get("MCAD_DEMO_RETRY_SLEEP_S", "1.0"))


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class HttpResult(dict):
    @property
    def status(self) -> int:
        return int(self.get("_http_status", 0))


def http_json(method: str, url: str, payload: dict | None = None, timeout: int = 30) -> HttpResult:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(text) if text.strip() else {}
            except Exception:
                body = {"_raw_text": text}
            if isinstance(body, dict):
                body["_http_status"] = resp.status
                body["_url"] = url
                return HttpResult(body)
            return HttpResult({"items": body, "_http_status": resp.status, "_url": url})
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text) if text.strip() else {}
        except Exception:
            body = {"_raw_text": text}
        if isinstance(body, dict):
            body["_http_status"] = e.code
            body["_url"] = url
            body["_http_error"] = True
            return HttpResult(body)
        return HttpResult({"items": body, "_http_status": e.code, "_url": url, "_http_error": True})
    except Exception as e:
        return HttpResult({"ok": False, "_http_status": 0, "_url": url, "_exception": str(e)})


def get_path(d: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def is_retryable_response(result: dict) -> bool:
    status = int(result.get("_http_status", 0) or 0)
    if status in RETRYABLE_HTTP_STATUSES:
        return True
    detail = result.get("detail")
    if isinstance(detail, dict) and str(detail.get("code") or "") == "MCAD_API_UNAVAILABLE":
        return True
    if "Connection refused" in str(result.get("_exception") or result.get("_raw_text") or result):
        return True
    return False


def retry_call(label: str, fn, *, attempts: int = DEFAULT_RETRY_ATTEMPTS, sleep_s: float = DEFAULT_RETRY_SLEEP_S) -> HttpResult:
    last: HttpResult | None = None
    for attempt in range(1, max(1, attempts) + 1):
        res = fn()
        res["_attempt"] = attempt
        res["_label"] = label
        last = res
        if not is_retryable_response(res):
            return res
        if attempt < attempts:
            time.sleep(sleep_s)
    if last is None:
        return HttpResult({"ok": False, "_http_status": 0, "_exception": f"{label}: no response", "_attempt": 0})
    last["_retry_exhausted"] = True
    return last


def wait_for_endpoint(base_url: str, path: str, label: str, *, attempts: int = DEFAULT_RETRY_ATTEMPTS) -> HttpResult:
    return retry_call(label, lambda: http_json("GET", f"{base_url}{path}"), attempts=attempts)


def make_session(base_url: str, objective_id: str, dw_id: str) -> HttpResult:
    # Docker Compose can mark mcad-proxy as started before mcad-api is accepting TCP connections.
    # Retry session creation for transient 500/502/503/connection-refused failures, but do not retry
    # deterministic 400 guard responses such as DW_DISABLED.
    return retry_call(
        f"create_session:{dw_id}",
        lambda: http_json("POST", f"{base_url}/mcad/session/new", {"objective_id": objective_id, "dw_id": dw_id}),
    )


def execute_query(base_url: str, *, session_id: str, dw_id: str, mdx: str, query_id: str, source_scenario_id: str = SCENARIO_ID) -> HttpResult:
    payload = {
        "mdx": mdx,
        "query": mdx,
        "query_type": "mdx",
        "query_id": query_id,
        "objective_id": OBJECTIVE_ID,
        "session_id": session_id,
        "dw_id": dw_id,
        "execution_mode": "v9_4_5a_demo_validation",
        "source_scenario_id": source_scenario_id,
        "scenario_id": source_scenario_id,
        "scenario_query_id": query_id,
        "allow_fallback": False,
    }
    return retry_call(
        f"execute:{dw_id}:{query_id}",
        lambda: http_json("POST", f"{base_url}/bi/execute", payload, timeout=60),
    )


def extract_step(name: str, response: dict, expected_decision: str | None = None, expected_path_contains: str | None = None, require_physical: bool | None = None) -> dict:
    decision = str(get_path(response, "decision", "decision", default="")).upper()
    reason = get_path(response, "decision", "decision_reason_code", default="") or get_path(response, "decision", "details", "decision_reason_code", default="")
    ev = response.get("execution_evidence") if isinstance(response.get("execution_evidence"), dict) else {}
    exec_ev = ev.get("execution", {}) if isinstance(ev.get("execution"), dict) else {}
    mcad_gate = ev.get("mcad_gate", {}) if isinstance(ev.get("mcad_gate"), dict) else {}
    physical = exec_ev.get("physical_execution")
    path = exec_ev.get("execution_path") or response.get("execution_path") or ""
    adapter = exec_ev.get("adapter_id") or response.get("adapter_id") or ""
    ok = True
    checks: list[str] = []
    if response.status >= 400 or response.status == 0:
        ok = False
        checks.append(f"HTTP status not OK: {response.status}")
    if expected_decision and decision != expected_decision.upper():
        ok = False
        checks.append(f"expected decision {expected_decision}, got {decision or '∅'}")
    if expected_path_contains and expected_path_contains.lower() not in str(path).lower() and expected_path_contains.lower() not in str(adapter).lower():
        ok = False
        checks.append(f"expected path/adapter containing {expected_path_contains}, got path={path} adapter={adapter}")
    if require_physical is not None and bool(physical) != bool(require_physical):
        ok = False
        checks.append(f"expected physical_execution={require_physical}, got {physical}")
    return {
        "name": name,
        "pass": ok,
        "checks": checks,
        "http_status": response.status,
        "decision": decision,
        "reason": reason,
        "phi": get_path(response, "decision", "phi", default=None),
        "delta_phi": get_path(response, "decision", "delta_phi", default=None),
        "sat": get_path(response, "decision", "sat", default=None),
        "real": get_path(response, "decision", "real", default=None),
        "ceval": get_path(response, "decision", "ceval", default=None),
        "mcad_allowed": mcad_gate.get("allowed_by_mcad"),
        "physical_execution": physical,
        "execution_path": path,
        "adapter_id": adapter,
        "requested_dw_id": exec_ev.get("requested_dw_id") or response.get("dw_id"),
        "selected_dw_id": exec_ev.get("selected_dw_id") or response.get("dw_id"),
        "status_code": exec_ev.get("status_code"),
        "elapsed_ms": exec_ev.get("elapsed_ms"),
        "response_bytes": exec_ev.get("response_bytes"),
        "response_digest": exec_ev.get("response_digest") or exec_ev.get("result_digest"),
        "row_count": exec_ev.get("row_count") or get_path(response, "direct_result", "row_count", default=None),
        "xmla_response_type": exec_ev.get("xmla_response_type") or get_path(response, "direct_result", "xmla_response_type", default=None),
        "response_digest_full": stable_digest(response),
    }


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "name", "pass", "http_status", "decision", "reason", "phi", "delta_phi", "sat", "real", "ceval",
        "mcad_allowed", "physical_execution", "execution_path", "adapter_id", "requested_dw_id", "selected_dw_id",
        "status_code", "elapsed_ms", "response_bytes", "response_digest", "row_count", "xmla_response_type", "checks",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in fields}
            out["checks"] = "; ".join(row.get("checks") or [])
            writer.writerow(out)


def write_markdown(path: Path, summary: dict, steps: list[dict]) -> None:
    lines = [
        "# MCAD V9.4.5a Dual-Path Demo Validation Pack",
        "",
        f"Generated at: `{summary.get('generated_at')}`",
        f"Base URL: `{summary.get('base_url')}`",
        "",
        "## Summary",
        "",
        f"- Overall status: **{summary.get('overall_status')}**",
        f"- Passed steps: **{summary.get('passed_steps')} / {summary.get('total_steps')}**",
        f"- Output directory: `{summary.get('output_dir')}`",
        "",
        "## Validation Steps",
        "",
        "| Step | Pass | Decision | Reason | Path | Adapter | Physical | Rows | XMLA type | Digest |",
        "|---|---:|---|---|---|---|---:|---:|---|---|",
    ]
    for s in steps:
        lines.append(
            "| {name} | {pass_} | {decision} | {reason} | {path} | {adapter} | {physical} | {rows} | {xmla} | {digest} |".format(
                name=s.get("name"), pass_="✅" if s.get("pass") else "❌", decision=s.get("decision") or "—",
                reason=s.get("reason") or "—", path=s.get("execution_path") or "—", adapter=s.get("adapter_id") or "—",
                physical=s.get("physical_execution"), rows=s.get("row_count") if s.get("row_count") is not None else "—",
                xmla=s.get("xmla_response_type") or "—", digest=(str(s.get("response_digest") or "—")[:24] + "…") if s.get("response_digest") else "—",
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This pack is intended for the live BI demonstrator, not for replacing the article reproducibility campaign.",
        "It proves that the same MCAD objective can gate two selectable physical execution paths: XMLA/eMondrian and Direct BI.",
        "For BLOCK cases, `physical_execution=false` is expected and confirms that MCAD prevents physical execution.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run MCAD dual-path demo validation.")
    ap.add_argument("repo_root", nargs="?", default=".", help="Repository root")
    ap.add_argument("--base-url", default=os.environ.get("MCAD_PROXY_BASE", "http://127.0.0.1:9000"), help="mcad-proxy base URL")
    ap.add_argument("--output-dir", default="", help="Optional output directory")
    args = ap.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.output_dir).resolve() if args.output_dir else repo / "bi-stack" / "demo-evidence" / "runs" / timestamp
    out.mkdir(parents=True, exist_ok=True)

    raw_dir = out / "raw"
    raw_dir.mkdir(exist_ok=True)

    base_url = args.base_url.rstrip("/")
    steps: list[dict] = []
    raw: dict[str, Any] = {}

    health = wait_for_endpoint(base_url, "/health", "proxy_health")
    raw["health"] = health
    dw_list = wait_for_endpoint(base_url, "/mcad/datawarehouses", "datawarehouses")
    raw["datawarehouses"] = dw_list
    sc_list = wait_for_endpoint(base_url, "/bi/scenarios", "scenarios")
    raw["scenarios"] = sc_list

    # 1. XMLA/eMondrian path
    xmla_session = make_session(base_url, OBJECTIVE_ID, "foodmart")
    raw["xmla_session"] = xmla_session
    xmla_sid = get_path(xmla_session, "active", "session_id") or get_path(xmla_session, "session", "session_id") or ""
    xmla_resp = execute_query(base_url, session_id=str(xmla_sid), dw_id="foodmart", mdx=Q1_MDX, query_id="Q1_XMLA_ALLOW") if xmla_sid else HttpResult({"_http_status": 0, "_exception": "No XMLA session id"})
    raw["xmla_q1"] = xmla_resp
    steps.append(extract_step("FoodMart XMLA/eMondrian Q1 ALLOW", xmla_resp, expected_decision="ALLOW", expected_path_contains="xmla", require_physical=True))

    # 2. Direct BI path
    direct_session = make_session(base_url, OBJECTIVE_ID, "foodmart_sql_direct")
    raw["direct_session"] = direct_session
    direct_sid = get_path(direct_session, "active", "session_id") or get_path(direct_session, "session", "session_id") or ""
    direct_resp = execute_query(base_url, session_id=str(direct_sid), dw_id="foodmart_sql_direct", mdx=Q1_MDX, query_id="Q1_DIRECT_ALLOW") if direct_sid else HttpResult({"_http_status": 0, "_exception": "No Direct BI session id"})
    raw["direct_q1"] = direct_resp
    steps.append(extract_step("FoodMart Direct BI Q1 ALLOW", direct_resp, expected_decision="ALLOW", expected_path_contains="direct", require_physical=True))

    # 3. BLOCK with no physical execution
    block_session = make_session(base_url, OBJECTIVE_ID, "foodmart")
    raw["block_session"] = block_session
    block_sid = get_path(block_session, "active", "session_id") or get_path(block_session, "session", "session_id") or ""
    block_resp = execute_query(base_url, session_id=str(block_sid), dw_id="foodmart", mdx=Q3_BLOCK_MDX, query_id="Q3_BLOCK_OUT_OF_OBJECTIVE") if block_sid else HttpResult({"_http_status": 0, "_exception": "No block test session id"})
    raw["block_q3"] = block_resp
    steps.append(extract_step("MCAD BLOCK no physical execution", block_resp, expected_decision="BLOCK", require_physical=False))

    # 4. Compatibility/DW guard. Accept either HTTP rejection or a BLOCK decision, as both are valid guard behavior.
    aw_session = make_session(base_url, OBJECTIVE_ID, "adventureworks_xmla")
    raw["adventureworks_session_attempt"] = aw_session
    guard_pass = False
    guard_reason = ""
    if aw_session.status >= 400:
        guard_pass = True
        guard_reason = "HTTP_REJECTED_DISABLED_OR_INCOMPATIBLE_DW"
    else:
        aw_sid = get_path(aw_session, "active", "session_id") or get_path(aw_session, "session", "session_id") or ""
        aw_resp = execute_query(base_url, session_id=str(aw_sid), dw_id="adventureworks_xmla", mdx=Q1_MDX, query_id="Q1_FORCED_INCOMPATIBLE_DW") if aw_sid else HttpResult({"_http_status": 0, "_exception": "No forced AW session id"})
        raw["forced_adventureworks_execute"] = aw_resp
        dec = str(get_path(aw_resp, "decision", "decision", default="")).upper()
        guard_pass = dec == "BLOCK" or aw_resp.status >= 400
        guard_reason = get_path(aw_resp, "decision", "decision_reason_code", default="") or "BLOCK_OR_HTTP_REJECT"
    steps.append({
        "name": "Scenario/DW compatibility guard",
        "pass": guard_pass,
        "checks": [] if guard_pass else ["incompatible/disabled DW was not rejected"],
        "http_status": aw_session.status,
        "decision": "BLOCK" if guard_pass else "UNKNOWN",
        "reason": guard_reason,
        "phi": None,
        "delta_phi": None,
        "sat": None,
        "real": None,
        "ceval": None,
        "mcad_allowed": False,
        "physical_execution": False,
        "execution_path": "not_executed",
        "adapter_id": "—",
        "requested_dw_id": "adventureworks_xmla",
        "selected_dw_id": "—",
        "status_code": aw_session.status,
        "elapsed_ms": None,
        "response_bytes": None,
        "response_digest": stable_digest(aw_session),
        "row_count": None,
        "xmla_response_type": None,
        "response_digest_full": stable_digest(aw_session),
    })

    # Fetch report/evidence endpoints for the last active session, as additional artifacts.
    raw["evidence_archive_current"] = http_json("GET", f"{base_url}/mcad/evidence/current/archive")
    raw["session_report_json"] = http_json("GET", f"{base_url}/mcad/reports/current/session")
    raw["session_metrics_json"] = http_json("GET", f"{base_url}/mcad/metrics/current/session")

    for key, val in raw.items():
        write_json(raw_dir / f"{key}.json", val)

    passed = sum(1 for s in steps if s.get("pass"))
    summary = {
        "contract_version": "mcad.v9_4_5a.dual_path_demo_validation_pack.v2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base_url,
        "repo_root": str(repo),
        "output_dir": str(out),
        "objective_id": OBJECTIVE_ID,
        "scenario_id": SCENARIO_ID,
        "overall_status": "PASS" if passed == len(steps) else "FAIL",
        "passed_steps": passed,
        "total_steps": len(steps),
        "steps": steps,
        "raw_response_dir": str(raw_dir),
    }

    write_json(out / "dual_path_summary.json", summary)
    write_csv(out / "dual_path_steps.csv", steps)
    write_markdown(out / "dual_path_summary.md", summary, steps)
    (out / "xmla_q1_response_digest.txt").write_text(steps[0].get("response_digest_full", "") + "\n", encoding="utf-8")
    (out / "direct_q1_response_digest.txt").write_text(steps[1].get("response_digest_full", "") + "\n", encoding="utf-8")

    latest_file = repo / "bi-stack" / "demo-evidence" / "latest_path.txt"
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    latest_file.write_text(str(out) + "\n", encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("overall_status", "passed_steps", "total_steps", "output_dir")}, indent=2))
    print(f"Summary markdown: {out / 'dual_path_summary.md'}")
    print(f"Summary CSV:      {out / 'dual_path_steps.csv'}")
    print(f"Raw responses:    {raw_dir}")
    return 0 if summary["overall_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
