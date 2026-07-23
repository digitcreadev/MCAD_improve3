#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_DIR = ROOT / "reports/article_experiments/ui_demo_export"


def read_json_from_zip(z: zipfile.ZipFile, name: str) -> Any:
    return json.loads(z.read(name).decode("utf-8", errors="replace"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def infer_dataset_id(*values: Any) -> str:
    txt = " ".join(str(v or "").lower() for v in values)
    if "adventureworks" in txt or "adventure works" in txt:
        return "adventureworks"
    if "steelwheels" in txt or "steel wheels" in txt:
        return "steelwheels"
    if "foodmart" in txt:
        return "foodmart"
    return ""


def infer_intended_backend_id(step: dict[str, Any]) -> str:
    txt = " ".join(str(step.get(k) or "").lower() for k in [
        "execution_path", "adapter_id", "requested_dw_id", "selected_dw_id", "name"
    ])
    if "xmla" in txt or "emondrian" in txt or str(step.get("requested_dw_id") or "").lower() == "foodmart":
        return "xmla_emondrian"
    if "sql_direct" in txt or "sqlserver_direct" in txt or "foodmart_sql_direct" in txt or "direct bi" in txt:
        return "sql_direct"
    return ""


def infer_physical_backend_id(step: dict[str, Any]) -> str:
    physical = norm_bool(step.get("physical_execution"))
    execution_path = str(step.get("execution_path") or "").lower()
    adapter_id = str(step.get("adapter_id") or "").lower()

    if physical is not True:
        return "not_executed"

    txt = " ".join([execution_path, adapter_id])
    if "xmla" in txt or "emondrian" in txt:
        return "xmla_emondrian"
    if "sql_direct" in txt or "sqlserver_direct" in txt or "direct" in txt:
        return "sql_direct"
    return ""


def infer_step_kind(step: dict[str, Any]) -> str:
    name = str(step.get("name") or "").lower()
    decision = str(step.get("decision") or "").upper()
    physical = norm_bool(step.get("physical_execution"))
    execution_path = str(step.get("execution_path") or "").lower()

    if "compatibility guard" in name or "dw compatibility" in name:
        return "compatibility_guard_no_execution"
    if decision == "BLOCK" and physical is False:
        return "mcad_block_no_execution"
    if decision == "ALLOW" and physical is True:
        return "physical_allow_execution"
    if execution_path == "not_executed":
        return "guard_no_execution"
    return "other"


def infer_blocked_before_execution(step: dict[str, Any]) -> bool:
    explicit = norm_bool(step.get("blocked_before_execution"))
    if explicit is not None:
        return explicit

    decision = str(step.get("decision") or "").upper()
    physical = norm_bool(step.get("physical_execution"))
    execution_path = str(step.get("execution_path") or "").lower()
    status_code = str(step.get("status_code") or step.get("http_status") or "")

    if decision == "BLOCK" and physical is False:
        return True
    if execution_path in {"", "not_executed", "not-executed"} and physical is False:
        return True
    if status_code.startswith("4") and physical is False:
        return True
    return False


def as_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except Exception:
        return None


def as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v))
    except Exception:
        return None


def main() -> int:
    export_dir = DEFAULT_EXPORT_DIR
    bundle_path = export_dir / "demo_evidence_bundle.zip"
    if not bundle_path.exists():
        raise SystemExit(f"[FAIL] missing bundle: {bundle_path}")

    article_run_id = datetime.now(timezone.utc).strftime("ui_article_normalized_%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "reports/article_experiments" / article_run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle_path) as z:
        names = z.namelist()
        summary_name = next((n for n in names if n.endswith("dual_path_summary.json")), None)
        if not summary_name:
            raise SystemExit("[FAIL] dual_path_summary.json not found in bundle")

        summary = read_json_from_zip(z, summary_name)
        steps = summary.get("steps", [])
        if not isinstance(steps, list):
            raise SystemExit("[FAIL] summary.steps is not a list")

        raw_rows: list[dict[str, Any]] = []
        for n in names:
            if "/raw/" in n and n.endswith(".json"):
                try:
                    raw_rows.append({
                        "raw_file": n,
                        "payload": read_json_from_zip(z, n)
                    })
                except Exception:
                    pass

    query_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue

        decision = str(step.get("decision") or "").upper()
        physical = norm_bool(step.get("physical_execution"))
        blocked_before_execution = infer_blocked_before_execution(step)
        intended_backend_id = infer_intended_backend_id(step)
        physical_backend_id = infer_physical_backend_id(step)
        step_kind = infer_step_kind(step)
        dataset_id = infer_dataset_id(
            step.get("requested_dw_id"),
            step.get("selected_dw_id"),
            step.get("adapter_id"),
            step.get("name"),
            summary.get("scenario_id")
        )

        row = {
            "article_run_id": article_run_id,
            "campaign_id": "C_backend_portability_ui_demo",
            "source": "ui_demo_evidence_bundle",
            "dataset_id": dataset_id,
            "objective_id": summary.get("objective_id"),
            "session_template_id": summary.get("scenario_id"),
            "session_instance_id": summary.get("run_id") or Path(summary.get("output_dir", "")).name,
            "query_index": idx,
            "query_id": f"{summary.get('scenario_id','scenario')}_STEP_{idx:02d}",
            "step_name": step.get("name"),
            "expected_decision": decision,
            "decision": decision,
            "reason": step.get("reason"),
            "step_kind": step_kind,
            "backend_id": intended_backend_id,
            "intended_backend_id": intended_backend_id,
            "physical_backend_id": physical_backend_id,
            "requested_dw_id": step.get("requested_dw_id"),
            "selected_dw_id": step.get("selected_dw_id"),
            "execution_path": step.get("execution_path"),
            "adapter_id": step.get("adapter_id"),
            "physical_execution": physical,
            "blocked_before_execution": blocked_before_execution,
            "row_count": as_int(step.get("row_count")),
            "cell_count": as_int(step.get("cell_count")),
            "elapsed_ms": as_int(step.get("elapsed_ms")),
            "response_bytes": as_int(step.get("response_bytes")),
            "response_digest": step.get("response_digest") or step.get("response_digest_full"),
            "response_digest_full": step.get("response_digest_full"),
            "xmla_response_type": step.get("xmla_response_type"),
            "http_status": as_int(step.get("http_status")),
            "status_code": as_int(step.get("status_code")),
            "sat": as_float(step.get("sat")),
            "real": as_float(step.get("real")),
            "ceval": as_float(step.get("ceval")),
            "phi": as_float(step.get("phi")),
            "pass": norm_bool(step.get("pass")),
        }

        row["article_valid"] = (
            row["decision"] in {"ALLOW", "BLOCK"}
            and (
                row["decision"] == "BLOCK"
                or row["physical_execution"] is True
            )
            and (
                row["decision"] == "ALLOW"
                or row["blocked_before_execution"] is True
            )
        )

        query_rows.append(row)
        evidence_rows.append({
            "article_run_id": article_run_id,
            "query_id": row["query_id"],
            "source_bundle": str(bundle_path.relative_to(ROOT)),
            "normalized": row,
            "raw_step": step
        })

    session_row = {
        "article_run_id": article_run_id,
        "campaign_id": "C_backend_portability_ui_demo",
        "source": "ui_demo_evidence_bundle",
        "objective_id": summary.get("objective_id"),
        "session_template_id": summary.get("scenario_id"),
        "session_instance_id": summary.get("run_id") or Path(summary.get("output_dir", "")).name,
        "overall_status": summary.get("overall_status"),
        "passed_steps": summary.get("passed_steps"),
        "total_steps": summary.get("total_steps"),
        "query_count": len(query_rows),
        "allow_count": sum(1 for r in query_rows if r["decision"] == "ALLOW"),
        "block_count": sum(1 for r in query_rows if r["decision"] == "BLOCK"),
        "physical_allow_count": sum(1 for r in query_rows if r["decision"] == "ALLOW" and r["physical_execution"] is True),
        "blocked_no_execution_count": sum(1 for r in query_rows if r["decision"] == "BLOCK" and r["blocked_before_execution"] is True),
        "sql_direct_count": sum(1 for r in query_rows if r["physical_backend_id"] == "sql_direct"),
        "xmla_emondrian_count": sum(1 for r in query_rows if r["physical_backend_id"] == "xmla_emondrian"),
        "physical_sql_direct_count": sum(1 for r in query_rows if r["physical_backend_id"] == "sql_direct"),
        "physical_xmla_emondrian_count": sum(1 for r in query_rows if r["physical_backend_id"] == "xmla_emondrian"),
        "intended_sql_direct_count": sum(1 for r in query_rows if r["intended_backend_id"] == "sql_direct"),
        "intended_xmla_emondrian_count": sum(1 for r in query_rows if r["intended_backend_id"] == "xmla_emondrian"),
        "guard_no_execution_count": sum(1 for r in query_rows if r["step_kind"] == "compatibility_guard_no_execution"),
        "mcad_block_no_execution_count": sum(1 for r in query_rows if r["step_kind"] == "mcad_block_no_execution"),
        "all_article_valid": all(r["article_valid"] for r in query_rows)
    }

    campaign_summary = {
        "ok": session_row["all_article_valid"],
        "article_run_id": article_run_id,
        "input_bundle": str(bundle_path.relative_to(ROOT)),
        "output_dir": str(out_dir.relative_to(ROOT)),
        "campaign_id": "C_backend_portability_ui_demo",
        "method": "UI-instrumented dual-path evidence normalized for article artifacts",
        "session": session_row,
        "raw_json_files_in_bundle": len(raw_rows),
        "notes": [
            "This normalizes the UI-generated demo evidence bundle.",
            "blocked_before_execution is inferred when decision=BLOCK and physical_execution=false.",
            "For Campaign C full protocol, the same normalizer will be applied to all UI portability runs."
        ]
    }

    write_csv(out_dir / "article_ui_metrics_by_query.csv", query_rows)
    write_csv(out_dir / "article_ui_metrics_by_session.csv", [session_row])
    write_jsonl(out_dir / "article_ui_execution_evidence.jsonl", evidence_rows)
    write_json(out_dir / "article_ui_campaign_summary.json", campaign_summary)

    print(json.dumps(campaign_summary, indent=2, ensure_ascii=False))
    return 0 if campaign_summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
