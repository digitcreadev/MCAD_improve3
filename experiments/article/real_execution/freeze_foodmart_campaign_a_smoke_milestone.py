#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

LIB = ROOT / "experiments/article/real_execution/foodmart_campaign_a_library"
RUNTIME_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_runtime"
SAMPLE_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_sample"
OUT_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_milestone"


def latest_run_dir() -> Path:
    runs = sorted(
        RUNTIME_ROOT.glob("foodmart_campaign_a_smoke_v2_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        raise SystemExit("[FAIL] No smoke v2 run directory found.")
    return runs[0]


def read_json(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"[FAIL] Missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"[FAIL] Missing CSV: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def yn(v: Any) -> str:
    if v is True or str(v).lower() == "true":
        return "yes"
    if v is False or str(v).lower() == "false":
        return "no"
    return str(v)


def main() -> int:
    run_dir = latest_run_dir()
    run_id = run_dir.name

    manifest = read_json(LIB / "manifest.json")
    installed = read_json(SAMPLE_ROOT / "installed_smoke_sample.json")

    smoke_summary = read_json(run_dir / "foodmart_campaign_a_smoke_v2_summary.json")
    gate_summary = read_json(run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_audit.json")

    by_query = read_csv(run_dir / "foodmart_campaign_a_smoke_v2_by_query.csv")
    gate_rows = read_csv(run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_by_query.csv")

    milestone_id = f"foodmart_campaign_a_smoke_milestone_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = OUT_ROOT / milestone_id
    out_dir.mkdir(parents=True, exist_ok=True)

    article_rows: list[dict[str, Any]] = []

    gate_by_query = {
        r["query_id"]: r
        for r in gate_rows
        if r.get("query_id")
    }

    for row in by_query:
        g = gate_by_query.get(row["query_id"], {})

        article_rows.append({
            "campaign_id": "A_foodmart_deep",
            "validation_level": "runtime_smoke_sample",
            "run_id": smoke_summary.get("run_id"),
            "scenario_id": row.get("scenario_id"),
            "objective_id": row.get("objective_id"),
            "session_id": row.get("session_id"),
            "dw_id": row.get("dw_id"),
            "query_id": row.get("query_id"),
            "query_role": row.get("query_role"),
            "expected_decision": row.get("expected_decision"),
            "actual_decision": row.get("decision"),
            "decision_reason": row.get("reason"),
            "strict_decision_match": row.get("strict_match"),
            "session_context_match": row.get("session_context_match"),
            "business_query_physical_execution": g.get("business_query_physical_execution"),
            "blocked_before_business_execution": g.get("blocked_before_business_execution"),
            "business_execution_trace_present": g.get("business_execution_trace_present"),
            "business_execution_path": g.get("business_execution_path"),
            "business_adapter_id": g.get("business_adapter_id"),
            "business_status_code": g.get("business_status_code"),
            "business_response_digest": g.get("business_response_digest"),
            "nvac_probe_physical_true_count": g.get("nvac_probe_physical_true_count"),
            "canonical_gate_contract_ok": g.get("canonical_gate_contract_ok"),
            "phi": row.get("phi"),
            "sat": row.get("sat"),
            "real": row.get("real"),
            "ceval": row.get("ceval"),
        })

    consolidated = {
        "ok": bool(smoke_summary.get("ok")) and bool(gate_summary.get("ok")),
        "milestone_id": milestone_id,
        "campaign_id": "A_foodmart_deep",
        "dataset_id": "foodmart",
        "runtime_backend": smoke_summary.get("dw_id"),
        "library_status": manifest.get("validation_status"),
        "library": {
            "scenario_count": manifest.get("scenario_count"),
            "objective_count": manifest.get("objective_count"),
            "candidate_query_count": manifest.get("candidate_query_count"),
            "planned_session_count": manifest.get("planned_session_count"),
            "planned_query_decision_count": manifest.get("planned_query_decision_count"),
            "planned_length_min": manifest.get("planned_length_min"),
            "planned_length_max": manifest.get("planned_length_max"),
            "planned_length_mean": manifest.get("planned_length_mean"),
            "cross_scenario_duplicate_hash_count": manifest.get("audit", {}).get("cross_scenario_duplicate_hash_count"),
            "within_scenario_redundant_duplicate_groups": manifest.get("audit", {}).get("within_scenario_redundant_duplicate_groups"),
        },
        "smoke_sample": {
            "sample_scenario_count": installed.get("sample_scenario_count"),
            "sample_query_count": installed.get("sample_query_count"),
            "executed_query_count": smoke_summary.get("executed_query_count"),
            "strict_match_count": smoke_summary.get("strict_match_count"),
            "strict_match_rate": smoke_summary.get("strict_match_rate"),
            "session_context_match_count": smoke_summary.get("session_context_match_count"),
            "session_context_match_rate": smoke_summary.get("session_context_match_rate"),
            "allow_count": smoke_summary.get("allow_count"),
            "block_count": smoke_summary.get("block_count"),
            "http_error_count": smoke_summary.get("http_error_count"),
            "mismatch_count": smoke_summary.get("mismatch_count"),
        },
        "canonical_gate_contract": {
            "query_count": gate_summary.get("query_count"),
            "allow_count": gate_summary.get("allow_count"),
            "block_count": gate_summary.get("block_count"),
            "allow_business_physical_execution_count": gate_summary.get("allow_business_physical_execution_count"),
            "allow_execution_trace_present_count": gate_summary.get("allow_execution_trace_present_count"),
            "block_business_physical_execution_count": gate_summary.get("block_business_physical_execution_count"),
            "blocked_before_business_execution_count": gate_summary.get("blocked_before_business_execution_count"),
            "block_with_nvac_probe_physical_true_count": gate_summary.get("block_with_nvac_probe_physical_true_count"),
            "canonical_gate_contract_ok_count": gate_summary.get("canonical_gate_contract_ok_count"),
            "canonical_gate_contract_violation_count": gate_summary.get("canonical_gate_contract_violation_count"),
            "interpretation": gate_summary.get("interpretation"),
        },
        "conclusion": (
            "FoodMart Campaign A library is generated, hardened, smoke-tested, and canonically validated "
            "on a representative runtime sample. The full 3000-session campaign is not executed yet."
        ),
        "source_run_dir": str(run_dir.relative_to(ROOT)),
    }

    write_json(out_dir / "foodmart_campaign_a_smoke_milestone_summary.json", consolidated)
    write_csv(out_dir / "foodmart_campaign_a_smoke_article_ready_by_query.csv", article_rows)

    md = f"""# FoodMart Campaign A — Smoke Runtime Validation Milestone

## Status

**Milestone status:** {'PASS' if consolidated['ok'] else 'FAIL'}

This milestone validates a representative FoodMart Campaign A runtime smoke sample. It does not claim that the full 3000-session Campaign A has already been executed.

## Library

- Scenario templates: {consolidated['library']['scenario_count']}
- Objectives: {consolidated['library']['objective_count']}
- Candidate queries: {consolidated['library']['candidate_query_count']}
- Planned sessions: {consolidated['library']['planned_session_count']}
- Planned query decisions: {consolidated['library']['planned_query_decision_count']}
- Planned session length: {consolidated['library']['planned_length_min']}..{consolidated['library']['planned_length_max']}, mean={consolidated['library']['planned_length_mean']}
- Cross-scenario exact duplicate hashes: {consolidated['library']['cross_scenario_duplicate_hash_count']}
- Within-scenario redundancy probes: {consolidated['library']['within_scenario_redundant_duplicate_groups']}

## Runtime smoke sample

- Runtime backend: {consolidated['runtime_backend']}
- Sample scenarios: {consolidated['smoke_sample']['sample_scenario_count']}
- Executed queries: {consolidated['smoke_sample']['executed_query_count']}
- Strict decision match: {consolidated['smoke_sample']['strict_match_count']} / {consolidated['smoke_sample']['executed_query_count']}
- Strict decision match rate: {consolidated['smoke_sample']['strict_match_rate']}
- Session-context match rate: {consolidated['smoke_sample']['session_context_match_rate']}
- ALLOW decisions: {consolidated['smoke_sample']['allow_count']}
- BLOCK decisions: {consolidated['smoke_sample']['block_count']}
- HTTP errors: {consolidated['smoke_sample']['http_error_count']}
- Mismatches: {consolidated['smoke_sample']['mismatch_count']}

## Canonical gate/execution contract

- ALLOW final business executions: {consolidated['canonical_gate_contract']['allow_business_physical_execution_count']} / {consolidated['canonical_gate_contract']['allow_count']}
- BLOCK final business executions: {consolidated['canonical_gate_contract']['block_business_physical_execution_count']} / {consolidated['canonical_gate_contract']['block_count']}
- BLOCK stopped before final business execution: {consolidated['canonical_gate_contract']['blocked_before_business_execution_count']} / {consolidated['canonical_gate_contract']['block_count']}
- Gate contract violations: {consolidated['canonical_gate_contract']['canonical_gate_contract_violation_count']}
- BLOCK rows with auxiliary NVAC probe execution: {consolidated['canonical_gate_contract']['block_with_nvac_probe_physical_true_count']}

## Interpretation

{consolidated['canonical_gate_contract']['interpretation']}

## Conclusion

{consolidated['conclusion']}
"""

    (out_dir / "foodmart_campaign_a_smoke_milestone_report.md").write_text(md, encoding="utf-8")

    archive = out_dir / "foodmart_campaign_a_smoke_milestone_evidence.zip"
    files_to_add = [
        LIB / "manifest.json",
        SAMPLE_ROOT / "installed_smoke_sample.json",
        run_dir / "foodmart_campaign_a_smoke_v2_summary.json",
        run_dir / "foodmart_campaign_a_smoke_v2_by_query.csv",
        run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_audit.json",
        run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_by_query.csv",
        out_dir / "foodmart_campaign_a_smoke_milestone_summary.json",
        out_dir / "foodmart_campaign_a_smoke_milestone_report.md",
        out_dir / "foodmart_campaign_a_smoke_article_ready_by_query.csv",
    ]

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files_to_add:
            if p.exists():
                z.write(p, p.relative_to(ROOT))

    print(json.dumps({
        "ok": consolidated["ok"],
        "milestone_id": milestone_id,
        "output_dir": str(out_dir.relative_to(ROOT)),
        "summary": str((out_dir / "foodmart_campaign_a_smoke_milestone_summary.json").relative_to(ROOT)),
        "report": str((out_dir / "foodmart_campaign_a_smoke_milestone_report.md").relative_to(ROOT)),
        "article_csv": str((out_dir / "foodmart_campaign_a_smoke_article_ready_by_query.csv").relative_to(ROOT)),
        "archive": str(archive.relative_to(ROOT)),
    }, indent=2, ensure_ascii=False))

    return 0 if consolidated["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
