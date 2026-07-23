#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def truthy(v: Any) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "ok", "pass", "passed"}


def first(row: dict, names: list[str], default: str = "") -> str:
    for n in names:
        if n in row and row[n] not in ("", None, "None", "null"):
            return str(row[n])
    return default


def as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, dict):
        return [v]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            x = json.loads(s)
            if isinstance(x, list):
                return x
            return [x]
        except Exception:
            return [s]
    return [v]


def as_dict(v: Any) -> dict:
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            x = json.loads(v)
            return x if isinstance(x, dict) else {}
        except Exception:
            return {}
    return {}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if isinstance(e, dict):
                    e["_line_no"] = i
                    events.append(e)
            except Exception:
                continue
    return events


def event_sources(e: dict) -> list[dict]:
    out = [e]
    for k in ("payload", "event", "data", "ckg_event", "update_payload", "graph_update"):
        x = e.get(k)
        if isinstance(x, dict):
            out.append(x)
    return out


def get_any_event(e: dict, names: list[str], default: Any = None) -> Any:
    for src in event_sources(e):
        for n in names:
            if n in src and src[n] not in ("", None, "None", "null"):
                return src[n]
    return default


def event_digest(e: dict) -> str:
    return str(get_any_event(e, ["response_digest", "result_digest", "business_response_digest", "digest"], "") or "")


def event_decision(e: dict) -> str:
    return str(get_any_event(e, ["decision"], "") or "").upper()


def event_session_id(e: dict) -> str:
    return str(get_any_event(e, ["session_id", "session_instance_id", "sid"], "") or "")


def event_objective_id(e: dict) -> str:
    return str(get_any_event(e, ["objective_id", "objective"], "") or "")


def event_backend_id(e: dict) -> str:
    return str(get_any_event(e, ["backend_id", "adapter_id", "execution_path"], "") or "")


def event_useful_constraints(e: dict) -> list[str]:
    out: list[Any] = []
    for src in event_sources(e):
        out.extend(as_list(src.get("covered_constraints")))
        out.extend(as_list(src.get("calculable_constraints")))
        out.extend(as_list(src.get("partially_covered_constraints")))
        out.extend(as_list(src.get("realized_virtual_nodes")))
        out.extend(as_list(src.get("realized_nodes")))
        out.extend(as_list(src.get("real_node_ids")))

        urs = as_dict(src.get("useful_result_summary"))
        out.extend(as_list(urs.get("covered_constraints")))
        out.extend(as_list(urs.get("calculable_constraints")))
        out.extend(as_list(urs.get("linked_constraints")))
        out.extend(as_list(urs.get("realized_virtual_nodes")))

    cleaned = []
    for x in out:
        if isinstance(x, dict):
            cleaned.append(json.dumps(x, sort_keys=True, ensure_ascii=False))
        elif x not in ("", None):
            cleaned.append(str(x))
    return sorted(set(cleaned))


def event_has_useful_materialization(e: dict) -> bool:
    if event_decision(e) == "BLOCK":
        return False

    if event_useful_constraints(e):
        return True

    for src in event_sources(e):
        urs = as_dict(src.get("useful_result_summary"))
        if urs:
            try:
                if float(urs.get("useful_result_count_estimate") or 0) > 0:
                    return True
            except Exception:
                pass
            if as_list(urs.get("useful_preview_cells")):
                return True
            if as_list(urs.get("useful_preview_rows")):
                return True

        raw = as_dict(src.get("raw_result_summary"))
        try:
            if float(raw.get("row_count") or raw.get("cell_count") or 0) > 0:
                return True
        except Exception:
            pass

    return False


def build_indexes(events: list[dict]):
    by_session_obj_digest = defaultdict(list)
    by_obj_digest = defaultdict(list)
    by_digest = defaultdict(list)

    for e in events:
        digest = event_digest(e)
        if not digest:
            continue
        sid = event_session_id(e)
        oid = event_objective_id(e)

        by_digest[digest].append(e)
        if oid:
            by_obj_digest[(oid, digest)].append(e)
        if sid and oid:
            by_session_obj_digest[(sid, oid, digest)].append(e)

    return by_session_obj_digest, by_obj_digest, by_digest


def find_matching_events(row: dict, indexes) -> list[dict]:
    by_session_obj_digest, by_obj_digest, by_digest = indexes

    sid = first(row, ["session_id", "session_instance_id", "session_template_id"], "")
    oid = first(row, ["objective_id"], "")
    digest = first(row, ["response_digest", "business_response_digest", "result_digest", "digest"], "")

    if not digest:
        return []

    if sid and oid and (sid, oid, digest) in by_session_obj_digest:
        return by_session_obj_digest[(sid, oid, digest)]
    if oid and (oid, digest) in by_obj_digest:
        return by_obj_digest[(oid, digest)]
    return by_digest.get(digest, [])


def is_guard_row(row: dict) -> bool:
    text = " ".join(
        first(row, [c], "")
        for c in ["step_kind", "step_name", "reason", "block_reason", "query_id"]
    ).lower()
    return "guard" in text or "compatibility" in text


def formal_fields_ok(row: dict) -> bool:
    return all(first(row, [c], "") not in ("", "None", "null") for c in ["sat", "real", "ceval", "phi"])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit UI-normalized article exports against the same CKG-first contract used for Campaign A."
    )
    ap.add_argument("--by-query", required=True, help="Path to article_ui_metrics_by_query.csv or equivalent.")
    ap.add_argument("--ckg-events", default="bi-stack/mcad-api-data/ckg_events.jsonl")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--campaign-id", default="")
    args = ap.parse_args()

    by_query_path = Path(args.by_query)
    if not by_query_path.is_absolute():
        by_query_path = ROOT / by_query_path

    ckg_path = Path(args.ckg_events)
    if not ckg_path.is_absolute():
        ckg_path = ROOT / ckg_path

    out_dir = Path(args.out_dir) if args.out_dir else by_query_path.parent / "ckg_first_audit"
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_csv(by_query_path)
    events = read_jsonl(ckg_path)
    indexes = build_indexes(events)

    audited_rows = []
    violations = []

    total = len(rows)
    allow_physical = 0
    block_rows = 0
    guard_rows = 0
    formal_complete = 0
    allow_physical_with_ckg_event = 0
    allow_physical_with_useful_ckg_event = 0
    block_with_useful_ckg_event = 0
    guard_with_useful_ckg_event = 0
    ckg_first_ok_count = 0

    for row in rows:
        decision = first(row, ["decision"], "").upper()
        physical = truthy(first(row, ["physical_execution"], ""))
        blocked_before = truthy(first(row, ["blocked_before_execution"], ""))
        guard = is_guard_row(row)

        if decision == "ALLOW" and physical:
            allow_physical += 1
        if decision == "BLOCK":
            block_rows += 1
        if guard:
            guard_rows += 1

        formal_ok = formal_fields_ok(row)
        if formal_ok:
            formal_complete += 1

        matches = find_matching_events(row, indexes)
        useful_matches = [e for e in matches if event_has_useful_materialization(e)]

        if decision == "ALLOW" and physical and matches:
            allow_physical_with_ckg_event += 1
        if decision == "ALLOW" and physical and useful_matches:
            allow_physical_with_useful_ckg_event += 1
        if decision == "BLOCK" and useful_matches:
            block_with_useful_ckg_event += 1
        if guard and useful_matches:
            guard_with_useful_ckg_event += 1

        ckg_event = useful_matches[0] if useful_matches else (matches[0] if matches else None)
        useful_constraints = event_useful_constraints(ckg_event) if ckg_event else []

        ckg_read_used = formal_ok and not guard
        ckg_trace_available = formal_ok and not guard
        ckg_write_eligible = decision == "ALLOW" and physical
        ckg_update_event_found = bool(matches)
        useful_evidence_created = bool(useful_matches)
        ckg_update_success = useful_evidence_created if ckg_write_eligible else False

        if guard:
            ckg_first_ok = (not physical) and (not useful_evidence_created)
        elif ckg_write_eligible:
            ckg_first_ok = ckg_trace_available and ckg_update_event_found and useful_evidence_created
        elif decision == "BLOCK":
            ckg_first_ok = ckg_trace_available and (not physical) and (blocked_before or not physical) and (not useful_evidence_created)
        else:
            ckg_first_ok = ckg_trace_available

        if ckg_first_ok:
            ckg_first_ok_count += 1
        else:
            violations.append({
                "session_id": first(row, ["session_id", "session_instance_id", "session_template_id"], ""),
                "objective_id": first(row, ["objective_id"], ""),
                "query_id": first(row, ["query_id"], ""),
                "decision": decision,
                "physical_execution": str(physical),
                "blocked_before_execution": str(blocked_before),
                "response_digest": first(row, ["response_digest", "result_digest", "digest"], ""),
                "reason": first(row, ["reason", "block_reason"], ""),
                "guard_row": str(guard),
                "formal_fields_ok": str(formal_ok),
                "ckg_update_event_found": str(ckg_update_event_found),
                "useful_evidence_created": str(useful_evidence_created),
            })

        audited = dict(row)
        audited.update({
            "ckg_read_used": str(ckg_read_used),
            "ckg_trace_available": str(ckg_trace_available),
            "ckg_write_eligible": str(ckg_write_eligible),
            "ckg_update_event_found": str(ckg_update_event_found),
            "ckg_update_match_count": str(len(matches)),
            "ckg_update_success": str(ckg_update_success),
            "useful_evidence_created": str(useful_evidence_created),
            "ckg_event_line": str(ckg_event.get("_line_no", "")) if ckg_event else "",
            "ckg_event_fingerprint": str(get_any_event(ckg_event, ["fingerprint"], "")) if ckg_event else "",
            "ckg_event_ts": str(get_any_event(ckg_event, ["ts", "timestamp", "created_at"], "")) if ckg_event else "",
            "ckg_event_backend_id": event_backend_id(ckg_event) if ckg_event else "",
            "ckg_covered_or_calculable_constraints": json.dumps(useful_constraints, ensure_ascii=False),
            "ckg_provenance_digest": str(
                get_any_event(ckg_event, ["provenance_digest", "fingerprint", "response_digest", "result_digest"], "")
            ) if ckg_event else "",
            "ckg_first_contract_ok": str(ckg_first_ok),
        })
        audited_rows.append(audited)

    out_csv = out_dir / "ui_ckg_first_by_query.csv"
    fieldnames = list(audited_rows[0].keys()) if audited_rows else []
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(audited_rows)

    violations_csv = out_dir / "ui_ckg_first_violations.csv"
    violation_fields = [
        "session_id", "objective_id", "query_id", "decision", "physical_execution",
        "blocked_before_execution", "response_digest", "reason", "guard_row",
        "formal_fields_ok", "ckg_update_event_found", "useful_evidence_created"
    ]
    with violations_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=violation_fields)
        w.writeheader()
        w.writerows(violations)

    summary = {
        "ok": len(violations) == 0,
        "campaign_id": args.campaign_id,
        "source_by_query": str(by_query_path.relative_to(ROOT)),
        "ckg_events_file": str(ckg_path.relative_to(ROOT)),
        "output_dir": str(out_dir.relative_to(ROOT)),
        "query_count": total,
        "ckg_events_count": len(events),
        "allow_physical_count": allow_physical,
        "block_count": block_rows,
        "guard_count": guard_rows,
        "formal_fields_complete_count": formal_complete,
        "allow_physical_with_ckg_event_count": allow_physical_with_ckg_event,
        "allow_physical_with_useful_ckg_event_count": allow_physical_with_useful_ckg_event,
        "block_with_useful_ckg_event_count": block_with_useful_ckg_event,
        "guard_with_useful_ckg_event_count": guard_with_useful_ckg_event,
        "ckg_first_contract_ok_count": ckg_first_ok_count,
        "ckg_first_contract_violation_count": len(violations),
        "outputs": {
            "by_query_enriched_csv": str(out_csv.relative_to(ROOT)),
            "violations_csv": str(violations_csv.relative_to(ROOT)),
            "summary_json": str((out_dir / "ui_ckg_first_summary.json").relative_to(ROOT)),
        },
        "interpretation": (
            "A valid UI CKG-first contract requires formal MCAD fields for MCAD decisions, "
            "a useful CKG event for every physically executed ALLOW, and no useful CKG evidence for BLOCK/guard rows."
        ),
    }

    (out_dir / "ui_ckg_first_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
