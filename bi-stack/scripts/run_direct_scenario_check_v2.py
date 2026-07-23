from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:9000")
    p.add_argument("--scenario-id", required=True)
    p.add_argument("--objective-id", required=True)
    p.add_argument("--dw-id", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=int, default=180)
    return p.parse_args()


def find_session_id(x):
    if isinstance(x, dict):
        for k in ("session_id", "id"):
            if x.get(k):
                return str(x[k])
        for k in ("active", "context", "session", "current"):
            sid = find_session_id(x.get(k))
            if sid:
                return sid
    return ""


def post_json(url, payload, timeout):
    r = requests.post(url, json=payload, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} on {url}: {json.dumps(data, ensure_ascii=False)[:1000]}")
    return data


def get_json(url, timeout):
    r = requests.get(url, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} on {url}: {json.dumps(data, ensure_ascii=False)[:1000]}")
    return data


def decision_value(data):
    d = data.get("decision")
    if isinstance(d, dict):
        return str(d.get("decision") or "")
    if isinstance(d, str):
        return d
    return str(data.get("status") or "")


def reason_value(data):
    d = data.get("decision")
    if isinstance(d, dict):
        return str(d.get("decision_reason_code") or d.get("reason_code") or d.get("decision_reason") or "")
    return str(data.get("decision_reason_code") or data.get("reason_code") or "")


def execution_info(data):
    if not isinstance(data, dict):
        return {}
    ev = data.get("execution_evidence")
    if isinstance(ev, dict) and isinstance(ev.get("execution"), dict):
        return ev["execution"]
    dr = data.get("direct_result")
    if isinstance(dr, dict):
        ev2 = dr.get("execution_evidence")
        if isinstance(ev2, dict) and isinstance(ev2.get("execution"), dict):
            return ev2["execution"]
        return dr
    for key in ("bi_result", "result", "execution_result"):
        x = data.get(key)
        if isinstance(x, dict):
            ev3 = x.get("execution_evidence")
            if isinstance(ev3, dict) and isinstance(ev3.get("execution"), dict):
                return ev3["execution"]
            if "physical_execution" in x or "attempted" in x or "status" in x:
                return x
    return {}


def physical_value(data):
    return execution_info(data).get("physical_execution")


def main():
    args = parse_args()
    base = args.base.rstrip("/")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    session_payload = {
        "objective_id": args.objective_id,
        "dw_id": args.dw_id,
    }
    session_response = post_json(f"{base}/mcad/session/new", session_payload, args.timeout)
    current_response = get_json(f"{base}/mcad/session/current", args.timeout)
    session_id = find_session_id(current_response) or find_session_id(session_response)

    scenario_response = get_json(f"{base}/bi/scenarios/{args.scenario_id}", args.timeout)
    scenario = scenario_response.get("scenario") or {}
    queries = scenario.get("queries") or scenario_response.get("items") or []

    if not queries:
        raise RuntimeError(f"No queries found for scenario {args.scenario_id}")

    results = []
    summary = []

    for idx, q in enumerate(queries, start=1):
        qid = str(q.get("query_id") or q.get("id") or f"Q{idx}")
        mdx = str(q.get("mdx") or q.get("query") or "")
        expected = str(q.get("expected_decision") or "").upper()

        payload = {
            "mdx": mdx,
            "query_type": q.get("query_type") or "mdx",
            "query_id": qid,
            "objective_id": args.objective_id,
            "dw_id": args.dw_id,
            "session_id": session_id,
            "source_scenario_id": args.scenario_id,
            "scenario_id": args.scenario_id,
            "scenario_name": scenario.get("name") or args.scenario_id,
            "scenario_source": "campaign_b_controlled_minimal",
            "scenario_query_index": idx - 1,
            "scenario_query_id": qid,
            "expected_decision": expected,
            "allow_fallback": False,
        }

        r = requests.post(f"{base}/bi/execute", json=payload, timeout=args.timeout)
        try:
            data = r.json()
        except Exception:
            data = {"raw_text": r.text}

        decision = decision_value(data).upper()
        reason = reason_value(data)
        physical = physical_value(data)
        ok = bool(expected) and decision == expected

        ex = execution_info(data)
        row = {
            "step": idx,
            "query_id": qid,
            "expected_decision": expected,
            "decision": decision,
            "ok_vs_expected": ok,
            "reason": reason,
            "physical_execution": physical,
            "execution_attempted": ex.get("attempted"),
            "execution_status": ex.get("status"),
            "adapter_id": ex.get("adapter_id"),
            "execution_path": ex.get("execution_path"),
            "row_count": ex.get("row_count"),
            "execution_error": ex.get("error"),
            "http_status": r.status_code,
        }
        summary.append(row)
        results.append({"query": q, "payload": payload, "response": data})

        print(f"{idx}. {qid}: decision={decision} expected={expected} ok={ok} physical={physical} reason={reason}")

    report = {
        "ok": all(x["ok_vs_expected"] for x in summary),
        "scenario_id": args.scenario_id,
        "objective_id": args.objective_id,
        "dw_id": args.dw_id,
        "session_id": session_id,
        "summary": summary,
        "session_response": session_response,
        "current_response": current_response,
        "scenario_response": scenario_response,
        "results": results,
    }

    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if report["ok"]:
        print(f"OK: {args.scenario_id}. See {out}")
        return 0

    print(f"FAILED: {args.scenario_id}. See {out}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
