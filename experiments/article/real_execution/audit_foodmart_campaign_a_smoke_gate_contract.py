#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_runtime"


def latest_run_dir() -> Path:
    runs = sorted(RUNTIME_ROOT.glob("foodmart_campaign_a_smoke_v2_*"), reverse=True)
    if not runs:
        raise SystemExit("[FAIL] No smoke v2 run directory found.")
    return runs[0]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def walk_key_paths(obj: Any, wanted: set[str], path: str = "$") -> list[dict[str, Any]]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if k in wanted:
                out.append({"path": p, "key": k, "value": v})
            out.extend(walk_key_paths(v, wanted, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(walk_key_paths(v, wanted, f"{path}[{i}]"))
    return out


def find_raw_file(run_dir: Path, scenario_id: str, query_role: str) -> Path | None:
    raw_dir = run_dir / "raw"
    if not raw_dir.exists():
        return None

    # Raw files are named: {scenario_id}_{Qxx_ROLE}.json
    candidates = sorted(raw_dir.glob(f"{scenario_id}_*{query_role}.json"))
    if candidates:
        return candidates[0]

    # Fallback.
    for p in sorted(raw_dir.glob(f"{scenario_id}_*.json")):
        if query_role in p.name:
            return p

    return None


def main() -> int:
    run_dir = latest_run_dir()
    by_query = run_dir / "foodmart_campaign_a_smoke_v2_by_query.csv"

    if not by_query.exists():
        raise SystemExit(f"[FAIL] Missing query CSV: {by_query}")

    rows = read_csv(by_query)

    audited = []
    raw_field_rows = []

    for row in rows:
        decision = str(row.get("decision") or "").upper()
        physical = norm_bool(row.get("physical_execution"))
        blocked = norm_bool(row.get("blocked_before_execution"))

        gate_contract_ok = (
            (decision == "ALLOW" and physical is True and blocked is False)
            or (decision == "BLOCK" and blocked is True)
        )

        raw_file = find_raw_file(run_dir, row["scenario_id"], row["query_role"])
        raw_rel = str(raw_file.relative_to(ROOT)) if raw_file else ""

        physical_paths = []
        blocked_paths = []
        execution_paths = []
        adapter_paths = []

        if raw_file and raw_file.exists():
            payload = json.loads(raw_file.read_text(encoding="utf-8"))
            fields = walk_key_paths(
                payload,
                {
                    "physical_execution",
                    "blocked_before_execution",
                    "execution_path",
                    "adapter_id",
                    "status_code",
                    "response_digest",
                    "decision",
                    "reason",
                    "reason_code",
                    "decision_reason_code",
                },
            )

            for f in fields:
                rr = {
                    "query_id": row["query_id"],
                    "scenario_id": row["scenario_id"],
                    "query_role": row["query_role"],
                    "decision": decision,
                    "field_path": f["path"],
                    "field_key": f["key"],
                    "field_value": f["value"],
                    "raw_file": raw_rel,
                }
                raw_field_rows.append(rr)

                if f["key"] == "physical_execution":
                    physical_paths.append(f"{f['path']}={f['value']}")
                elif f["key"] == "blocked_before_execution":
                    blocked_paths.append(f"{f['path']}={f['value']}")
                elif f["key"] == "execution_path":
                    execution_paths.append(f"{f['path']}={f['value']}")
                elif f["key"] == "adapter_id":
                    adapter_paths.append(f"{f['path']}={f['value']}")

        audited.append({
            **row,
            "gate_contract_ok": gate_contract_ok,
            "raw_file": raw_rel,
            "raw_physical_execution_paths": " | ".join(physical_paths),
            "raw_blocked_before_execution_paths": " | ".join(blocked_paths),
            "raw_execution_path_paths": " | ".join(execution_paths),
            "raw_adapter_id_paths": " | ".join(adapter_paths),
        })

    allow_rows = [r for r in audited if r["decision"] == "ALLOW"]
    block_rows = [r for r in audited if r["decision"] == "BLOCK"]

    violations = [r for r in audited if str(r["gate_contract_ok"]) != "True"]

    summary = {
        "ok": len(violations) == 0,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "query_count": len(audited),
        "allow_count": len(allow_rows),
        "block_count": len(block_rows),
        "gate_contract_ok_count": len(audited) - len(violations),
        "gate_contract_violation_count": len(violations),
        "allow_physical_count": sum(1 for r in allow_rows if norm_bool(r.get("physical_execution")) is True),
        "block_blocked_before_execution_count": sum(1 for r in block_rows if norm_bool(r.get("blocked_before_execution")) is True),
        "block_physical_execution_count_reported": sum(1 for r in block_rows if norm_bool(r.get("physical_execution")) is True),
        "diagnosis": (
            "Gate contract is satisfied for smoke v2."
            if not violations
            else "Decision semantics passed, but gate/execution evidence needs correction or stricter extraction."
        ),
    }

    out_summary = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_audit.json"
    out_rows = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_by_query.csv"
    out_violations = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_violations.csv"
    out_raw_fields = run_dir / "foodmart_campaign_a_smoke_v2_raw_field_paths.csv"

    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out_rows, audited)
    write_csv(out_violations, violations)
    write_csv(out_raw_fields, raw_field_rows)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
