#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "http://localhost:9000"

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
INV = LIB / "plans/campaign_a_scenario_inventory.csv"
PLAN = LIB / "plans/campaign_a_session_plan.csv"

OUT_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_batches"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def http_json(method: str, path: str, payload: Any | None = None, timeout: int = 300) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)

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
        return {"ok": False, "http_error": e.code, "body": body}


def norm_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def find_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
        for v in obj.values():
            found = find_key(v, key)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_key(v, key)
            if found not in (None, ""):
                return found
    return None


def decision_fields(raw: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    d = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
    decision = str(d.get("decision") or find_key(raw, "decision") or "").upper()
    reason = (
        d.get("decision_reason_code")
        or d.get("reason_code")
        or d.get("reason")
        or find_key(raw, "decision_reason_code")
        or find_key(raw, "reason_code")
        or find_key(raw, "reason")
        or ""
    )
    return decision, str(reason), d


def final_business_execution(raw: dict[str, Any]) -> dict[str, Any]:
    ev = raw.get("execution_evidence") if isinstance(raw.get("execution_evidence"), dict) else {}
    exe = ev.get("execution") if isinstance(ev.get("execution"), dict) else {}

    path = exe.get("execution_path") or raw.get("execution_path")
    adapter = exe.get("adapter_id") or raw.get("adapter_id")
    status = exe.get("status_code") or raw.get("status_code")
    digest = (
        exe.get("response_digest")
        or exe.get("result_digest")
        or raw.get("response_digest")
        or raw.get("result_digest")
    )

    explicit = norm_bool(exe.get("physical_execution"))
    trace = bool(path and adapter and str(status) == "200" and digest)
    physical = bool(explicit is True or trace)

    return {
        "explicit_business_physical_execution": explicit,
        "business_execution_trace_present": trace,
        "business_query_physical_execution": physical,
        "business_execution_path": path,
        "business_adapter_id": adapter,
        "business_status_code": status,
        "business_response_digest": digest,
    }


def count_nvac_probe_physical_true(obj: Any, path: str = "$") -> int:
    count = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if (
                k == "physical_execution"
                and "nvac_evidence" in p
                and "raw_probe_summary" in p
                and norm_bool(v) is True
            ):
                count += 1
            count += count_nvac_probe_physical_true(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            count += count_nvac_probe_physical_true(v, f"{path}[{i}]")
    return count


def scenario_from_plan_row(row: dict[str, str], idx: int, inventory: list[dict[str, str]]) -> dict[str, str]:
    sid = (
        row.get("scenario_id")
        or row.get("template_scenario_id")
        or row.get("session_template_id")
        or row.get("scenario")
        or ""
    )

    if sid:
        for inv in inventory:
            if inv.get("scenario_id") == sid:
                return inv

    return inventory[idx % len(inventory)]


def query_sort_key(q: dict[str, Any]) -> str:
    return str(q.get("id") or q.get("logical_query_id") or q.get("query_id") or "")



def select_plan_rows(plan: list[dict[str, str]], *, limit: int, offset: int, sampling: str) -> list[dict[str, str]]:
    """
    sequential:
      take a contiguous slice from the session plan.

    stratified:
      take a balanced sample across planned session lengths 4..12.
      This avoids the first batch being composed only of length-4 sessions
      when the plan file is grouped by length.
    """
    if sampling == "sequential":
        out = []
        for i, row in enumerate(plan[offset: offset + limit], start=offset):
            r = dict(row)
            r["__plan_index"] = str(i)
            out.append(r)
        return out

    buckets: dict[int, list[tuple[int, dict[str, str]]]] = {}

    for i, row in enumerate(plan):
        length = int(row.get("planned_length") or row.get("length") or 8)
        buckets.setdefault(length, []).append((i, row))

    lengths = sorted(buckets)
    if not lengths:
        return []

    base = limit // len(lengths)
    rem = limit % len(lengths)

    selected: list[dict[str, str]] = []

    for pos, length in enumerate(lengths):
        n = base + (1 if pos < rem else 0)
        bucket = buckets[length]

        # Offset rotates inside each length bucket, so later batches can differ.
        start = offset % len(bucket)

        for j in range(n):
            original_index, row = bucket[(start + j) % len(bucket)]
            r = dict(row)
            r["__plan_index"] = str(original_index)
            selected.append(r)

    # Keep deterministic order by length, then original plan index.
    selected.sort(key=lambda r: (int(r.get("planned_length") or r.get("length") or 8), int(r["__plan_index"])))

    return selected

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--dw-id", default="foodmart")
    ap.add_argument("--sampling", choices=["sequential", "stratified"], default="sequential")
    ap.add_argument("--library-dir", default=str(LIB))
    ap.add_argument("--raw-policy", choices=["all", "anomalies", "none"], default="anomalies")
    args = ap.parse_args()

    lib_dir = Path(args.library_dir)
    campaign_id = "A_foodmart_deep_runtime_feasible" if "runtime_feasible" in str(lib_dir) else "A_foodmart_deep"
    inventory_path = lib_dir / "plans/campaign_a_scenario_inventory.csv"
    plan_path = lib_dir / "plans/campaign_a_session_plan.csv"

    if not inventory_path.exists():
        inventory_path = lib_dir / "plans/campaign_a_runtime_feasible_scenario_inventory.csv"
    if not plan_path.exists():
        plan_path = lib_dir / "plans/campaign_a_runtime_feasible_session_plan.csv"

    inventory = read_csv(inventory_path)
    plan = read_csv(plan_path)

    selected_plan = select_plan_rows(plan, limit=args.limit, offset=args.offset, sampling=args.sampling)

    run_id = datetime.now(timezone.utc).strftime(
        f"foodmart_campaign_a_batch_{args.limit}_%Y%m%dT%H%M%SZ"
    )
    out_dir = OUT_ROOT / run_id
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    query_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    gate_violations: list[dict[str, Any]] = []

    for local_i, plan_row in enumerate(selected_plan):
        global_i = int(plan_row.get("__plan_index", args.offset + local_i))
        inv = scenario_from_plan_row(plan_row, global_i, inventory)

        scenario_id = inv["scenario_id"]
        objective_id = inv["objective_id"]
        planned_length = int(plan_row.get("planned_length") or plan_row.get("length") or 8)

        scenario_path = ROOT / inv["scenario_file"]
        queries = json.loads(scenario_path.read_text(encoding="utf-8"))
        queries = sorted(queries, key=query_sort_key)[:planned_length]

        session_resp = http_json(
            "POST",
            "/mcad/session/new",
            {"objective_id": objective_id, "dw_id": args.dw_id},
            timeout=90,
        )

        session_id = (
            session_resp.get("active", {}).get("session_id")
            or session_resp.get("session", {}).get("session_id")
            or session_resp.get("session_id")
            or f"BATCH_SESSION_{global_i:04d}"
        )

        session_match_count = 0
        session_gate_ok_count = 0

        print(f"\n=== Session {local_i+1}/{len(selected_plan)} :: {scenario_id} :: length={planned_length} ===")

        for step_i, q in enumerate(queries, start=1):
            query_id = q.get("logical_query_id") or q.get("id") or f"{scenario_id}_Q{step_i:02d}"
            expected = str(q.get("expected_decision") or "").upper()

            payload = {
                "mdx": q.get("mdx"),
                "query_type": "mdx",
                "query_id": query_id,
                "objective_id": objective_id,
                "session_id": session_id,
                "dw_id": args.dw_id,
                "scenario_id": scenario_id,
                "source_scenario_id": scenario_id,
                "scenario_query_id": query_id,
                "scenario_query_index": q.get("id"),
                "scenario_source": "campaign_a_batch",
                "execution_mode": "campaign_a_batch",
                "allow_fallback": False,
            }

            t0 = time.time()
            resp = http_json("POST", "/bi/execute", payload, timeout=300)
            client_elapsed_ms = int((time.time() - t0) * 1000)

            raw_file = raw_dir / f"{global_i:04d}_{scenario_id}_{q.get('id', step_i)}.json"
            # Raw persistence is decided after decision/gate assessment.

            decision, reason, d = decision_fields(resp)
            business = final_business_execution(resp)

            strict_match = expected == decision
            session_context_match = strict_match or (
                expected == "ALLOW"
                and decision == "BLOCK"
                and reason.startswith("BLOCK_REDUNDANT")
            )

            blocked_before_business = (
                decision == "BLOCK"
                and business["business_query_physical_execution"] is False
                and not business["business_execution_path"]
                and not business["business_adapter_id"]
            )

            gate_ok = (
                (decision == "ALLOW" and business["business_query_physical_execution"] is True)
                or (decision == "BLOCK" and blocked_before_business is True)
            )

            row = {
                "run_id": run_id,
                "campaign_id": campaign_id,
                "batch_limit": args.limit,
                "global_session_index": global_i,
                "local_session_index": local_i,
                "session_id": session_id,
                "scenario_id": scenario_id,
                "objective_id": objective_id,
                "planned_length": planned_length,
                "step_index": step_i,
                "dw_id": args.dw_id,
                "query_id": query_id,
                "query_role": q.get("query_role"),
                "expected_decision": expected,
                "actual_decision": decision,
                "decision_reason": reason,
                "strict_match": strict_match,
                "session_context_match": session_context_match,
                "canonical_gate_contract_ok": gate_ok,
                "business_query_physical_execution": business["business_query_physical_execution"],
                "blocked_before_business_execution": blocked_before_business,
                "business_execution_trace_present": business["business_execution_trace_present"],
                "business_execution_path": business["business_execution_path"],
                "business_adapter_id": business["business_adapter_id"],
                "business_status_code": business["business_status_code"],
                "business_response_digest": business["business_response_digest"],
                "nvac_probe_physical_true_count": count_nvac_probe_physical_true(resp),
                "phi": d.get("phi"),
                "sat": d.get("sat"),
                "real": d.get("real"),
                "ceval": d.get("ceval"),
                "http_error": resp.get("http_error"),
                "client_elapsed_ms": client_elapsed_ms,
                "raw_file": "",
            }

            should_save_raw = (
                args.raw_policy == "all"
                or (
                    args.raw_policy == "anomalies"
                    and (
                        not session_context_match
                        or not gate_ok
                        or bool(resp.get("http_error"))
                    )
                )
            )

            if should_save_raw:
                write_json(raw_file, resp)
                row["raw_file"] = str(raw_file.relative_to(ROOT))

            query_rows.append(row)

            if session_context_match:
                session_match_count += 1
            else:
                mismatches.append(row)

            if gate_ok:
                session_gate_ok_count += 1
            else:
                gate_violations.append(row)

            print(
                f"{step_i:02d} {q.get('id')} expected={expected} "
                f"decision={decision} context={session_context_match} "
                f"gate={gate_ok} reason={reason}"
            )

        session_rows.append({
            "run_id": run_id,
            "global_session_index": global_i,
            "local_session_index": local_i,
            "session_id": session_id,
            "scenario_id": scenario_id,
            "objective_id": objective_id,
            "planned_length": planned_length,
            "executed_query_count": len(queries),
            "session_context_match_count": session_match_count,
            "session_context_match_rate": session_match_count / len(queries) if queries else 0.0,
            "canonical_gate_contract_ok_count": session_gate_ok_count,
            "canonical_gate_contract_ok_rate": session_gate_ok_count / len(queries) if queries else 0.0,
        })

    total = len(query_rows)
    allow_rows = [r for r in query_rows if r["actual_decision"] == "ALLOW"]
    block_rows = [r for r in query_rows if r["actual_decision"] == "BLOCK"]

    reason_counts = Counter(str(r["decision_reason"]) for r in query_rows)

    summary = {
        "ok": total > 0 and not mismatches and not gate_violations and not any(r.get("http_error") for r in query_rows),
        "run_id": run_id,
        "campaign_id": campaign_id,
        "dw_id": args.dw_id,
        "offset": args.offset,
        "requested_session_limit": args.limit,
        "sampling": args.sampling,
        "raw_policy": args.raw_policy,
        "executed_session_count": len(session_rows),
        "executed_query_count": total,
        "strict_match_count": sum(1 for r in query_rows if r["strict_match"] is True),
        "strict_match_rate": sum(1 for r in query_rows if r["strict_match"] is True) / total if total else 0.0,
        "session_context_match_count": sum(1 for r in query_rows if r["session_context_match"] is True),
        "session_context_match_rate": sum(1 for r in query_rows if r["session_context_match"] is True) / total if total else 0.0,
        "allow_count": len(allow_rows),
        "block_count": len(block_rows),
        "allow_business_physical_execution_count": sum(1 for r in allow_rows if r["business_query_physical_execution"] is True),
        "block_business_physical_execution_count": sum(1 for r in block_rows if r["business_query_physical_execution"] is True),
        "blocked_before_business_execution_count": sum(1 for r in block_rows if r["blocked_before_business_execution"] is True),
        "canonical_gate_contract_ok_count": sum(1 for r in query_rows if r["canonical_gate_contract_ok"] is True),
        "canonical_gate_contract_violation_count": len(gate_violations),
        "http_error_count": sum(1 for r in query_rows if r.get("http_error")),
        "mismatch_count": len(mismatches),
        "decision_reason_counts": dict(reason_counts),
        "output_dir": str(out_dir.relative_to(ROOT)),
    }

    write_json(out_dir / "campaign_a_batch_summary.json", summary)
    write_csv(out_dir / "campaign_a_batch_by_query.csv", query_rows)
    write_csv(out_dir / "campaign_a_batch_by_session.csv", session_rows)
    write_csv(out_dir / "campaign_a_batch_mismatches.csv", mismatches)
    write_csv(out_dir / "campaign_a_batch_gate_violations.csv", gate_violations)

    print("\n=== Batch summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
