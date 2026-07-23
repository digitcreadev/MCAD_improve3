from __future__ import annotations

import json
import time
from pathlib import Path

import requests


BASE = "http://localhost:9000"


def post_json(path: str, payload: dict) -> dict:
    r = requests.post(f"{BASE}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_json(path: str) -> dict:
    r = requests.get(f"{BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    scenario_path = Path("bi-stack/direct-scenarios/foodmart_q1_q6.json")

    if scenario_path.exists():
        scenarios = json.loads(scenario_path.read_text(encoding="utf-8"))
    else:
        scenarios = get_json("/bi/scenarios/foodmart_q1_q6").get("items", [])

    if not scenarios:
        print("ERROR: no Q1-Q6 scenarios found.")
        return 1

    print("Creating new MCAD session...")
    session = post_json(
        "/mcad/session/new",
        {
            "objective_id": "O_REAL_BEER_WA_MONTH",
            "dw_id": "foodmart",
        },
    )

    print("Active session:")
    print(json.dumps(session.get("active", {}), indent=2, ensure_ascii=False))

    results = []

    for item in scenarios:
        payload = {
            "mdx": item["mdx"],
            "query_type": item.get("query_type", "mdx"),
            "objective_id": item.get("objective_id", "O_REAL_BEER_WA_MONTH"),
            "dw_id": item.get("dw_id", "foodmart"),
        }

        r = post_json("/bi/execute", payload)

        decision = r.get("decision", {})
        got = str(decision.get("decision", "")).upper()
        expected = str(item.get("expected_decision", "")).upper()
        ok = got == expected

        row = {
            "id": item.get("id"),
            "label": item.get("label"),
            "expected": expected,
            "got": got,
            "ok": ok,
            "reason_code": decision.get("decision_reason_code")
            or decision.get("details", {}).get("decision_reason_code"),
            "phi": decision.get("phi"),
            "sat": decision.get("sat"),
            "real": decision.get("real"),
            "ceval": decision.get("ceval"),
        }

        results.append(row)

        print(
            f"{row['id']}: expected={expected} got={got} "
            f"ok={ok} reason={row['reason_code']} phi={row['phi']}"
        )

        time.sleep(0.2)

    graph = get_json("/mcad/graph/current")
    history = get_json("/mcad/history/current")

    out_dir = Path("bi-stack/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "base_url": BASE,
        "scenario": "foodmart_q1_q6",
        "results": results,
        "metrics": graph.get("metrics", {}),
        "history_count": len(history.get("items", [])),
        "history": history.get("items", []),
    }

    out_file = out_dir / "q1_q6_direct_check.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    all_ok = all(x["ok"] for x in results)
    has_history = len(history.get("items", [])) >= 6

    print("")
    print("Final metrics:")
    print(json.dumps(graph.get("metrics", {}), indent=2, ensure_ascii=False))
    print("")
    print(f"History count: {len(history.get('items', []))}")
    print(f"Report: {out_file}")

    if not all_ok:
        print("FAILED: at least one decision does not match the expected decision.")
        return 1

    if not has_history:
        print("FAILED: decision history contains fewer than 6 items.")
        return 1

    print("OK: Q1-Q6 direct BI check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
