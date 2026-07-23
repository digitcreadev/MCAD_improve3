#!/usr/bin/env python3
"""MCAD V9.5.2 AdventureWorksDW evidence validation runner.

This live validation pack executes an AdventureWorksDW scenario against the
SQL Server Direct adapter. It validates the MCAD gate, physical-execution
contract, row/evidence production, and BLOCK no-execution behavior.

The scenario may contain any number of queries. Expected decisions are read
from each query entry (`expected_decision`), so the pack is not tied to Q1-Q6.
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
from typing import Any, Callable

DEFAULT_OBJECTIVE_FILE = "bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
DEFAULT_SCENARIO_FILE = "bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"
DEFAULT_DW_ID = "adventureworks_sql_direct"
DEFAULT_RETRY_ATTEMPTS = int(os.environ.get("MCAD_AW_DEMO_RETRY_ATTEMPTS", "24"))
DEFAULT_RETRY_SLEEP_S = float(os.environ.get("MCAD_AW_DEMO_RETRY_SLEEP_S", "1.0"))
RETRYABLE_HTTP_STATUSES = {0, 500, 502, 503, 504}


def stable_digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class HttpResult(dict):
    @property
    def status(self) -> int:
        return int(self.get("_http_status", 0) or 0)


def http_json(method: str, url: str, payload: dict | None = None, timeout: int = 60) -> HttpResult:
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
            if not isinstance(body, dict):
                body = {"items": body}
            body["_http_status"] = resp.status
            body["_url"] = url
            return HttpResult(body)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text) if text.strip() else {}
        except Exception:
            body = {"_raw_text": text}
        if not isinstance(body, dict):
            body = {"items": body}
        body["_http_status"] = exc.code
        body["_url"] = url
        body["_http_error"] = True
        return HttpResult(body)
    except Exception as exc:
        return HttpResult({"ok": False, "_http_status": 0, "_url": url, "_exception": str(exc)})


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
    if isinstance(detail, dict) and str(detail.get("code") or "") in {"MCAD_API_UNAVAILABLE", "GATEWAY_UNAVAILABLE"}:
        return True
    text = str(result.get("_exception") or result.get("_raw_text") or result)
    if "Connection refused" in text or "timed out" in text or "Temporary failure" in text:
        return True
    return False


def retry_call(label: str, fn: Callable[[], HttpResult], *, attempts: int = DEFAULT_RETRY_ATTEMPTS, sleep_s: float = DEFAULT_RETRY_SLEEP_S) -> HttpResult:
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


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def import_objective_and_scenario(base_url: str, objective: dict, scenario: dict) -> dict[str, HttpResult]:
    raw: dict[str, HttpResult] = {}
    raw["objective_import"] = retry_call(
        "objective_import",
        lambda: http_json("POST", f"{base_url}/mcad/objectives/import", objective, timeout=60),
    )
    raw["scenario_validate"] = retry_call(
        "scenario_validate",
        lambda: http_json("POST", f"{base_url}/bi/scenarios/validate", scenario, timeout=60),
    )
    raw["scenario_import"] = retry_call(
        "scenario_import",
        lambda: http_json("POST", f"{base_url}/bi/scenarios/import", scenario, timeout=60),
    )
    return raw


def make_session(base_url: str, objective_id: str, dw_id: str) -> HttpResult:
    return retry_call(
        f"create_session:{dw_id}",
        lambda: http_json("POST", f"{base_url}/mcad/session/new", {"objective_id": objective_id, "dw_id": dw_id}, timeout=60),
    )


def execute_query(base_url: str, *, scenario: dict, query: dict, session_id: str, dw_id: str, objective_id: str, index: int) -> HttpResult:
    qid = str(query.get("id") or f"AW_Q{index}")
    qtype = str(query.get("query_type") or "mdx")
    qtext = str(query.get("mdx") or query.get("query") or query.get("sql") or "")
    payload = {
        "mdx": qtext,
        "query": qtext,
        "query_type": qtype,
        "query_id": qid,
        "objective_id": objective_id,
        "session_id": session_id,
        "dw_id": dw_id,
        "execution_mode": "v9_5_2_adventureworks_validation",
        "source_scenario_id": scenario.get("id"),
        "scenario_id": scenario.get("id"),
        "scenario_query_id": qid,
        "scenario_query_index": index,
        "allow_fallback": False,
        "max_rows": int(os.environ.get("MCAD_AW_DEMO_MAX_ROWS", "200")),
    }
    return retry_call(
        f"execute:{qid}",
        lambda: http_json("POST", f"{base_url}/bi/execute", payload, timeout=120),
        attempts=max(DEFAULT_RETRY_ATTEMPTS, 12),
    )


def decision_from_response(response: dict) -> str:
    return str(get_path(response, "decision", "decision", default="") or response.get("decision") or "").upper()


def evidence_parts(response: dict) -> tuple[dict, dict, dict]:
    ev = response.get("execution_evidence") if isinstance(response.get("execution_evidence"), dict) else {}
    exec_ev = ev.get("execution", {}) if isinstance(ev.get("execution"), dict) else {}
    mcad_gate = ev.get("mcad_gate", {}) if isinstance(ev.get("mcad_gate"), dict) else {}
    direct_result = response.get("direct_result") if isinstance(response.get("direct_result"), dict) else {}
    return ev, exec_ev, mcad_gate | {"_direct_result": direct_result}


def extract_step(index: int, query: dict, response: HttpResult, expected_decision: str, dw_id: str) -> dict:
    decision = decision_from_response(response)
    ev = response.get("execution_evidence") if isinstance(response.get("execution_evidence"), dict) else {}
    exec_ev = ev.get("execution", {}) if isinstance(ev.get("execution"), dict) else {}
    mcad_gate = ev.get("mcad_gate", {}) if isinstance(ev.get("mcad_gate"), dict) else {}
    direct_result = response.get("direct_result") if isinstance(response.get("direct_result"), dict) else {}
    result_summary = response.get("result") if isinstance(response.get("result"), dict) else {}
    path = exec_ev.get("execution_path") or response.get("execution_path") or direct_result.get("execution_path") or ""
    adapter = exec_ev.get("adapter_id") or response.get("adapter_id") or direct_result.get("adapter_id") or ""
    physical = exec_ev.get("physical_execution")
    if physical is None:
        physical = direct_result.get("physical_execution")
    if physical is None:
        physical = response.get("physical_execution")
    row_count = exec_ev.get("row_count")
    if row_count is None:
        row_count = direct_result.get("row_count")
    if row_count is None:
        row_count = result_summary.get("row_count")
    status_code = exec_ev.get("status_code") or direct_result.get("status_code") or response.get("status_code")
    response_digest = exec_ev.get("response_digest") or exec_ev.get("result_digest") or direct_result.get("response_digest") or direct_result.get("result_digest")
    expected = str(expected_decision or "").upper()
    checks: list[str] = []
    ok = True
    if response.status >= 400 or response.status == 0:
        ok = False
        checks.append(f"HTTP status not OK: {response.status}")
    if expected and decision != expected:
        ok = False
        checks.append(f"expected decision {expected}, got {decision or '∅'}")
    if expected == "ALLOW":
        if bool(physical) is not True:
            ok = False
            checks.append(f"expected physical_execution=True for ALLOW, got {physical}")
        if "adventureworks" not in str(adapter).lower() and "sql" not in str(path).lower() and "direct" not in str(path).lower():
            ok = False
            checks.append(f"expected AdventureWorks SQL Direct evidence, got path={path} adapter={adapter}")
        try:
            if row_count is None or int(row_count) <= 0:
                ok = False
                checks.append(f"expected row_count > 0 for ALLOW, got {row_count}")
        except Exception:
            ok = False
            checks.append(f"row_count is not numeric: {row_count}")
    elif expected == "BLOCK":
        if bool(physical) is not False:
            ok = False
            checks.append(f"expected physical_execution=False for BLOCK, got {physical}")
    requested_dw = exec_ev.get("requested_dw_id") or response.get("dw_id") or dw_id
    selected_dw = exec_ev.get("selected_dw_id") or response.get("selected_dw_id") or response.get("dw_id") or dw_id
    if expected == "ALLOW" and str(selected_dw) != str(dw_id):
        ok = False
        checks.append(f"expected selected_dw_id={dw_id}, got {selected_dw}")
    return {
        "index": index,
        "query_id": query.get("id") or f"AW_Q{index}",
        "label": query.get("label") or query.get("id") or f"AW_Q{index}",
        "pass": ok,
        "checks": checks,
        "http_status": response.status,
        "expected_decision": expected,
        "decision": decision,
        "reason": get_path(response, "decision", "decision_reason_code", default="") or get_path(response, "decision", "details", "decision_reason_code", default=""),
        "phi": get_path(response, "decision", "phi", default=None),
        "delta_phi": get_path(response, "decision", "delta_phi", default=None),
        "sat": get_path(response, "decision", "sat", default=None),
        "real": get_path(response, "decision", "real", default=None),
        "ceval": get_path(response, "decision", "ceval", default=None),
        "mcad_allowed": mcad_gate.get("allowed_by_mcad"),
        "physical_execution": physical,
        "execution_path": path,
        "adapter_id": adapter,
        "requested_dw_id": requested_dw,
        "selected_dw_id": selected_dw,
        "status_code": status_code,
        "elapsed_ms": exec_ev.get("elapsed_ms") or direct_result.get("elapsed_ms") or response.get("elapsed_ms"),
        "response_bytes": exec_ev.get("response_bytes") or direct_result.get("response_bytes"),
        "response_digest": response_digest,
        "row_count": row_count,
        "dataset": exec_ev.get("dataset") or direct_result.get("dataset") or "AdventureWorksDW",
        "generated_sql_present": bool(direct_result.get("generated_sql") or get_path(response, "result", "generated_sql", default="")),
        "response_digest_full": stable_digest(response),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "index", "query_id", "label", "pass", "http_status", "expected_decision", "decision", "reason",
        "phi", "delta_phi", "sat", "real", "ceval", "mcad_allowed", "physical_execution",
        "execution_path", "adapter_id", "requested_dw_id", "selected_dw_id", "status_code", "elapsed_ms",
        "response_bytes", "response_digest", "row_count", "dataset", "generated_sql_present", "checks",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in fields}
            out["checks"] = "; ".join(row.get("checks") or [])
            writer.writerow(out)


def write_markdown(path: Path, summary: dict, steps: list[dict]) -> None:
    lines = [
        "# MCAD V9.5.2 AdventureWorksDW Evidence Validation Pack",
        "",
        f"Generated at: `{summary.get('generated_at')}`",
        f"Base URL: `{summary.get('base_url')}`",
        f"Objective: `{summary.get('objective_id')}`",
        f"Scenario: `{summary.get('scenario_id')}`",
        f"DW: `{summary.get('dw_id')}`",
        "",
        "## Summary",
        "",
        f"- Overall status: **{summary.get('overall_status')}**",
        f"- Passed steps: **{summary.get('passed_steps')} / {summary.get('total_steps')}**",
        f"- Physical ALLOW executions: **{summary.get('physical_allow_count')}**",
        f"- BLOCK without physical execution: **{summary.get('block_no_execution_count')}**",
        f"- Output directory: `{summary.get('output_dir')}`",
        "",
        "## Validation Steps",
        "",
        "| # | Query | Pass | Expected | Decision | Reason | Physical | Path | Adapter | Rows | Digest |",
        "|---:|---|---:|---|---|---|---:|---|---|---:|---|",
    ]
    for s in steps:
        digest = str(s.get("response_digest") or "—")
        if digest != "—":
            digest = digest[:28] + "…"
        lines.append(
            "| {idx} | {qid} | {pass_} | {expected} | {decision} | {reason} | {physical} | {path} | {adapter} | {rows} | {digest} |".format(
                idx=s.get("index"),
                qid=s.get("query_id"),
                pass_="✅" if s.get("pass") else "❌",
                expected=s.get("expected_decision") or "—",
                decision=s.get("decision") or "—",
                reason=s.get("reason") or "—",
                physical=s.get("physical_execution"),
                path=s.get("execution_path") or "—",
                adapter=s.get("adapter_id") or "—",
                rows=s.get("row_count") if s.get("row_count") is not None else "—",
                digest=digest,
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This pack validates the real AdventureWorksDW SQL Server Direct path.",
        "ALLOW queries must pass through MCAD before physical SQL Server execution.",
        "BLOCK queries must remain non-physical (`physical_execution=false`).",
        "The scenario length is read dynamically from the JSON file; it is not fixed to Q1-Q6.",
        "",
    ])
    failures = [s for s in steps if not s.get("pass")]
    if failures:
        lines.extend(["## Failed Checks", ""])
        for s in failures:
            lines.append(f"- `{s.get('query_id')}`: " + "; ".join(s.get("checks") or ["unspecified failure"]))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run MCAD AdventureWorksDW evidence validation.")
    parser.add_argument("repo_root", nargs="?", default=".", help="Repository root")
    parser.add_argument("--base-url", default=os.environ.get("MCAD_PROXY_BASE", os.environ.get("MCAD_PROXY_BASE_URL", "http://127.0.0.1:9000")), help="mcad-proxy base URL")
    parser.add_argument("--objective-file", default=DEFAULT_OBJECTIVE_FILE, help="Objective JSON file relative to repo root")
    parser.add_argument("--scenario-file", default=DEFAULT_SCENARIO_FILE, help="Scenario JSON file relative to repo root")
    parser.add_argument("--output-dir", default="", help="Optional output directory")
    parser.add_argument("--skip-import", action="store_true", help="Do not import objective/scenario before running")
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    base_url = args.base_url.rstrip("/")
    objective_path = (repo / args.objective_file).resolve()
    scenario_path = (repo / args.scenario_file).resolve()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.output_dir).resolve() if args.output_dir else repo / "bi-stack" / "demo-evidence" / "runs" / f"adventureworks_{timestamp}"
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw: dict[str, Any] = {}
    steps: list[dict] = []

    objective = load_json(objective_path)
    scenario = load_json(scenario_path)
    queries = scenario.get("queries") if isinstance(scenario.get("queries"), list) else []
    if not queries:
        raise SystemExit(f"[FAIL] scenario has no queries: {scenario_path}")

    objective_id = str(scenario.get("objective_id") or objective.get("id") or "")
    dw_id = str(scenario.get("dw_id") or objective.get("dw_id") or DEFAULT_DW_ID)
    scenario_id = str(scenario.get("id") or scenario_path.stem)

    raw["health"] = retry_call("proxy_health", lambda: http_json("GET", f"{base_url}/health", timeout=30))
    raw["datawarehouses"] = retry_call("datawarehouses", lambda: http_json("GET", f"{base_url}/mcad/datawarehouses?include_disabled=true", timeout=30))
    raw["adventureworks_dw_health"] = retry_call("adventureworks_dw_health", lambda: http_json("GET", f"{base_url}/mcad/datawarehouses/{dw_id}/health", timeout=60))
    raw["adventureworks_dw_metadata"] = retry_call("adventureworks_dw_metadata", lambda: http_json("GET", f"{base_url}/mcad/datawarehouses/{dw_id}/metadata", timeout=60))

    if not args.skip_import:
        raw.update(import_objective_and_scenario(base_url, objective, scenario))
        for import_key in ("objective_import", "scenario_validate", "scenario_import"):
            import_resp = raw.get(import_key, {})
            if not (isinstance(import_resp, dict) and int(import_resp.get("_http_status", 0) or 0) < 400 and import_resp.get("ok")):
                for key, val in raw.items():
                    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in key)
                    write_json(raw_dir / f"{safe}.json", val)
                write_json(out / "adventureworks_summary.json", {
                    "contract_version": "mcad.v9_5_2a.adventureworks_import_validation_fix.v1",
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "overall_status": "FAIL",
                    "reason": f"{import_key} failed",
                    "failed_import_response": import_resp,
                    "output_dir": str(out),
                    "raw_response_dir": str(raw_dir),
                })
                raise SystemExit(f"[FAIL] {import_key} failed; see {raw_dir / (import_key + '.json')}")

    session_resp = make_session(base_url, objective_id, dw_id)
    raw["session"] = session_resp
    session_id = get_path(session_resp, "active", "session_id") or get_path(session_resp, "session", "session_id") or ""
    if not session_id:
        write_json(raw_dir / "session.json", session_resp)
        raise SystemExit("[FAIL] could not create AdventureWorks validation session")

    for idx, query in enumerate(queries, start=1):
        expected = str(query.get("expected_decision") or "").upper() or None
        resp = execute_query(base_url, scenario=scenario, query=query, session_id=str(session_id), dw_id=dw_id, objective_id=objective_id, index=idx)
        key = f"{idx:02d}_{query.get('id') or 'query'}"
        raw[key] = resp
        steps.append(extract_step(idx, query, resp, expected or "", dw_id))

    raw["evidence_archive_current"] = http_json("GET", f"{base_url}/mcad/evidence/current/archive", timeout=60)
    raw["session_report_json"] = http_json("GET", f"{base_url}/mcad/reports/current/session", timeout=60)
    raw["session_metrics_json"] = http_json("GET", f"{base_url}/mcad/metrics/current/session", timeout=60)

    for key, val in raw.items():
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in key)
        write_json(raw_dir / f"{safe}.json", val)

    passed = sum(1 for s in steps if s.get("pass"))
    physical_allow_count = sum(1 for s in steps if s.get("expected_decision") == "ALLOW" and s.get("physical_execution") is True)
    block_no_execution_count = sum(1 for s in steps if s.get("expected_decision") == "BLOCK" and s.get("physical_execution") is False)
    summary = {
        "contract_version": "mcad.v9_5_2.adventureworks_evidence_validation.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base_url,
        "repo_root": str(repo),
        "output_dir": str(out),
        "objective_id": objective_id,
        "scenario_id": scenario_id,
        "dw_id": dw_id,
        "dataset": scenario.get("dataset") or objective.get("dataset") or "AdventureWorksDW",
        "scenario_query_count": len(queries),
        "overall_status": "PASS" if passed == len(steps) else "FAIL",
        "passed_steps": passed,
        "total_steps": len(steps),
        "physical_allow_count": physical_allow_count,
        "block_no_execution_count": block_no_execution_count,
        "steps": steps,
        "raw_response_dir": str(raw_dir),
    }

    write_json(out / "adventureworks_summary.json", summary)
    write_csv(out / "adventureworks_steps.csv", steps)
    write_markdown(out / "adventureworks_summary.md", summary, steps)
    (out / "adventureworks_response_digests.txt").write_text("\n".join(str(s.get("response_digest_full") or "") for s in steps) + "\n", encoding="utf-8")

    latest_file = repo / "bi-stack" / "demo-evidence" / "latest_adventureworks_path.txt"
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    latest_file.write_text(str(out) + "\n", encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("overall_status", "passed_steps", "total_steps", "physical_allow_count", "block_no_execution_count", "output_dir")}, indent=2))
    print(f"Summary markdown: {out / 'adventureworks_summary.md'}")
    print(f"Summary CSV:      {out / 'adventureworks_steps.csv'}")
    print(f"Raw responses:    {raw_dir}")
    return 0 if summary["overall_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
