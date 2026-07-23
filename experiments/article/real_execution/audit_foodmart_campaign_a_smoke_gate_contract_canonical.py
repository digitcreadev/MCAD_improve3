#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = ROOT / "reports/article_experiments/foodmart_campaign_a_smoke_runtime"


def latest_run_dir() -> Path:
    runs = sorted(
        RUNTIME_ROOT.glob("foodmart_campaign_a_smoke_v2_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
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


def find_raw_file(run_dir: Path, scenario_id: str, query_role: str) -> Path | None:
    raw_dir = run_dir / "raw"
    if not raw_dir.exists():
        return None

    candidates = sorted(raw_dir.glob(f"{scenario_id}_*{query_role}.json"))
    if candidates:
        return candidates[0]

    for p in sorted(raw_dir.glob(f"{scenario_id}_*.json")):
        if query_role in p.name:
            return p

    return None


def walk(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            yield p, k, v
            yield from walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")


def decision_fields(raw: dict[str, Any]) -> tuple[str, str]:
    d = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}

    decision = str(
        d.get("decision")
        or raw.get("decision")
        or ""
    ).upper()

    reason = (
        d.get("decision_reason_code")
        or d.get("reason_code")
        or d.get("reason")
        or raw.get("decision_reason_code")
        or raw.get("reason_code")
        or raw.get("reason")
        or ""
    )

    return decision, str(reason)


def final_business_execution(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Canonical final BI/business execution evidence.

    This intentionally reads only execution_evidence.execution plus top-level
    final execution fallbacks. It does not read nvac_evidence.probe because
    NVAC probes are auxiliary feasibility probes, not final user BI execution.
    """
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

    explicit_physical = norm_bool(exe.get("physical_execution"))

    execution_trace_present = bool(
        path
        and adapter
        and str(status) == "200"
        and digest
    )

    physical = bool(
        explicit_physical is True
        or execution_trace_present
    )

    return {
        "explicit_business_physical_execution": explicit_physical,
        "business_execution_trace_present": execution_trace_present,
        "business_query_physical_execution": physical,
        "business_execution_path": path,
        "business_adapter_id": adapter,
        "business_status_code": status,
        "business_response_digest": digest,
    }


def count_nvac_probe_physical_true(raw: dict[str, Any]) -> int:
    count = 0
    for path, key, value in walk(raw):
        if (
            key == "physical_execution"
            and "nvac_evidence" in path
            and "raw_probe_summary" in path
            and norm_bool(value) is True
        ):
            count += 1
    return count


def nvac_probe_adapter_paths(raw: dict[str, Any]) -> list[str]:
    paths = []
    for path, key, value in walk(raw):
        if (
            key == "adapter_id"
            and "nvac_evidence" in path
            and "raw_probe_summary" in path
            and value not in (None, "")
        ):
            paths.append(f"{path}={value}")
    return paths


def main() -> int:
    run_dir = latest_run_dir()
    by_query = run_dir / "foodmart_campaign_a_smoke_v2_by_query.csv"

    if not by_query.exists():
        raise SystemExit(f"[FAIL] Missing query CSV: {by_query}")

    source_rows = read_csv(by_query)

    canonical_rows: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for row in source_rows:
        raw_file = find_raw_file(run_dir, row["scenario_id"], row["query_role"])

        if not raw_file:
            out = {
                **row,
                "canonical_audit_error": "raw_file_not_found",
                "canonical_gate_contract_ok": False,
            }
            canonical_rows.append(out)
            violations.append(out)
            continue

        raw = json.loads(raw_file.read_text(encoding="utf-8"))

        decision, reason = decision_fields(raw)
        business = final_business_execution(raw)

        business_physical = bool(business["business_query_physical_execution"])
        business_path = business["business_execution_path"]
        business_adapter = business["business_adapter_id"]

        blocked_before_business = (
            decision == "BLOCK"
            and business_physical is False
            and not business_path
            and not business_adapter
        )

        canonical_gate_contract_ok = (
            (decision == "ALLOW" and business_physical is True)
            or (decision == "BLOCK" and blocked_before_business is True)
        )

        out = {
            **row,
            "canonical_decision": decision,
            "canonical_reason": reason,
            "explicit_business_physical_execution": business["explicit_business_physical_execution"],
            "business_execution_trace_present": business["business_execution_trace_present"],
            "business_query_physical_execution": business["business_query_physical_execution"],
            "blocked_before_business_execution": blocked_before_business,
            "business_execution_path": business["business_execution_path"],
            "business_adapter_id": business["business_adapter_id"],
            "business_status_code": business["business_status_code"],
            "business_response_digest": business["business_response_digest"],
            "nvac_probe_physical_true_count": count_nvac_probe_physical_true(raw),
            "nvac_probe_adapter_paths": " | ".join(nvac_probe_adapter_paths(raw)[:6]),
            "canonical_gate_contract_ok": canonical_gate_contract_ok,
            "raw_file": str(raw_file.relative_to(ROOT)),
        }

        canonical_rows.append(out)

        if not canonical_gate_contract_ok:
            violations.append(out)

    allow_rows = [r for r in canonical_rows if r.get("canonical_decision") == "ALLOW"]
    block_rows = [r for r in canonical_rows if r.get("canonical_decision") == "BLOCK"]

    summary = {
        "ok": len(violations) == 0,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "query_count": len(canonical_rows),
        "allow_count": len(allow_rows),
        "block_count": len(block_rows),
        "allow_business_physical_execution_count": sum(
            1 for r in allow_rows if r.get("business_query_physical_execution") is True
        ),
        "allow_execution_trace_present_count": sum(
            1 for r in allow_rows if r.get("business_execution_trace_present") is True
        ),
        "block_business_physical_execution_count": sum(
            1 for r in block_rows if r.get("business_query_physical_execution") is True
        ),
        "blocked_before_business_execution_count": sum(
            1 for r in block_rows if r.get("blocked_before_business_execution") is True
        ),
        "block_with_nvac_probe_physical_true_count": sum(
            1 for r in block_rows if int(r.get("nvac_probe_physical_true_count") or 0) > 0
        ),
        "canonical_gate_contract_ok_count": len(canonical_rows) - len(violations),
        "canonical_gate_contract_violation_count": len(violations),
        "interpretation": (
            "The final BI/business query gate contract is satisfied. "
            "ALLOW queries have final business execution traces; BLOCK queries are blocked before final business execution. "
            "NVAC probe executions are auxiliary evidence probes and are reported separately."
            if not violations
            else "Some final BI/business queries violate the gate contract."
        ),
    }

    out_summary = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_audit.json"
    out_rows = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_by_query.csv"
    out_violations = run_dir / "foodmart_campaign_a_smoke_v2_gate_contract_canonical_violations.csv"

    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out_rows, canonical_rows)
    write_csv(out_violations, violations)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
