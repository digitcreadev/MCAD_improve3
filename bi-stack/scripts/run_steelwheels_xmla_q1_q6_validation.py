import json
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://localhost:9000"
OBJECTIVE_ID = "O_STEELWHEELS_EMEA_CLASSIC_CARS_MONTH_SALES_QUANTITY"
DW_ID = "steelwheels_xmla"
OBJ_PATH = Path("bi-stack/objectives/objective_steelwheels_emea_classic_cars_month_sales_quantity.json")
SCENARIO_PATH = Path("bi-stack/direct-scenarios/steelwheels_xmla_emea_classic_cars_q1_q6.json")
REPORT_PATH = Path("bi-stack/reports/steelwheels_xmla_q1_q6_mcad_execute_check.json")

def http_json(method, path, payload=None, timeout=300):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        parsed["_http_status"] = e.code
        return parsed

def pick_execution_summary(resp):
    direct = resp.get("direct_result") if isinstance(resp.get("direct_result"), dict) else {}
    ev = resp.get("execution_evidence") if isinstance(resp.get("execution_evidence"), dict) else {}
    ev_exec = ev.get("execution") if isinstance(ev.get("execution"), dict) else {}
    summary = direct.get("raw_result_summary") or direct.get("summary") or direct.get("result_summary") or direct
    if not isinstance(summary, dict):
        summary = {}
    return direct, ev_exec, summary

print("=== STEELWHEELS XMLA Q1-Q6 /bi/execute STRICT VALIDATION ===")

objective = json.loads(OBJ_PATH.read_text(encoding="utf-8"))
scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))

print("--- import objective ---")
imp_obj = http_json("POST", "/mcad/objectives/import", objective)
print(json.dumps({"ok": imp_obj.get("ok"), "status": imp_obj.get("status"), "objective_ids": imp_obj.get("objective_ids")}, indent=2))

print("--- import XMLA scenario ---")
imp_sc = http_json("POST", "/bi/scenarios/import", scenario)
print(json.dumps({"ok": imp_sc.get("ok"), "status": imp_sc.get("status"), "scenario_ids": imp_sc.get("scenario_ids"), "warnings": imp_sc.get("warnings")}, indent=2))

print("--- create XMLA session ---")
session = http_json("POST", "/mcad/session/new", {"objective_id": OBJECTIVE_ID, "dw_id": DW_ID})
session_id = session.get("session_id") or session.get("id") or (session.get("session") or {}).get("id") or (session.get("active") or {}).get("session_id")
print(json.dumps({"session_ok": session.get("ok"), "session_id": session_id, "objective_id": OBJECTIVE_ID, "dw_id": DW_ID}, indent=2))

rows = []
raw = []
scenario_instance_id = "SW_XMLA_Q1_Q6_" + str(int(time.time()))

print("--- execute XMLA Q1-Q6 ---")
for idx, q in enumerate(scenario["queries"], start=1):
    payload = {
        "mdx": q["mdx"],
        "query_type": q.get("query_type", "mdx"),
        "query_id": q["id"],
        "objective_id": OBJECTIVE_ID,
        "dw_id": DW_ID,
        "session_id": session_id,
        "source_scenario_id": scenario["id"],
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "scenario_instance_id": scenario_instance_id,
        "scenario_query_index": idx,
        "scenario_query_id": q["id"],
        "allow_fallback": False
    }

    resp = http_json("POST", "/bi/execute", payload, timeout=300)

    decision_obj = resp.get("decision") if isinstance(resp.get("decision"), dict) else {}
    decision = str(decision_obj.get("decision") or "").upper()
    reason = decision_obj.get("decision_reason_code") or (decision_obj.get("details") or {}).get("decision_reason_code")

    direct, ev_exec, summary = pick_execution_summary(resp)

    physical = summary.get("physical_execution")
    if physical is None:
        physical = direct.get("physical_execution")
    if physical is None:
        physical = ev_exec.get("physical_execution")

    adapter_id = resp.get("adapter_id") or direct.get("adapter_id") or summary.get("adapter_id") or ev_exec.get("adapter_id")
    selected_dw_id = direct.get("selected_dw_id") or direct.get("dw_id") or summary.get("dw_id") or resp.get("dw_id")

    expected = str(q.get("expected_decision")).upper()
    expected_reason = q.get("expected_reason_code")

    row = {
        "index": idx,
        "id": q["id"],
        "expected": expected,
        "got": decision,
        "expected_reason_code": expected_reason,
        "reason_code": reason,
        "reason_ok": reason == expected_reason,
        "phi": decision_obj.get("phi"),
        "sat": decision_obj.get("sat"),
        "real": decision_obj.get("real"),
        "ceval": decision_obj.get("ceval"),
        "physical_execution": physical,
        "adapter_id": adapter_id,
        "selected_dw_id": selected_dw_id,
        "xmla_response_type": summary.get("xmla_response_type"),
        "xmla_valid_response": summary.get("xmla_valid_response"),
        "xmla_has_fault": summary.get("xmla_has_fault"),
        "xmla_fault_excerpt": summary.get("xmla_fault_excerpt"),
        "response_digest": summary.get("response_digest"),
        "response_bytes": summary.get("response_bytes")
    }

    if expected == "ALLOW":
        row["ok"] = (
            decision == expected
            and row["reason_ok"]
            and physical is True
            and adapter_id == "xmla_mondrian"
            and selected_dw_id == DW_ID
            and summary.get("xmla_response_type") == "ExecuteResponse"
            and summary.get("xmla_valid_response") is True
            and summary.get("xmla_has_fault") is False
        )
    else:
        row["ok"] = (
            decision == expected
            and row["reason_ok"]
            and physical is False
            and adapter_id is None
            and selected_dw_id == DW_ID
        )

    rows.append(row)
    raw.append({"query": q, "response": resp})

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(json.dumps({
    "objective_id": OBJECTIVE_ID,
    "dw_id": DW_ID,
    "scenario_id": scenario["id"],
    "scenario_instance_id": scenario_instance_id,
    "session_id": session_id,
    "strict_symmetric": True,
    "all_ok": all(r["ok"] for r in rows),
    "results": rows,
    "raw": raw
}, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

print("idx | expected | got   | ok | reason_ok | physical | adapter       | reason")
print("----|----------|-------|----|-----------|----------|---------------|-------------------------------")
for r in rows:
    print(f"{r['index']:>3} | {r['expected']:<8} | {r['got']:<5} | {str(r['ok']):<4} | {str(r['reason_ok']):<9} | {str(r['physical_execution']):<8} | {str(r['adapter_id']):<13} | {r['reason_code']}")

print()
print(json.dumps({"all_ok": all(r["ok"] for r in rows), "report": str(REPORT_PATH)}, indent=2))
