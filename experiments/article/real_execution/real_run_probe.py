#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "experiments/article/real_execution/real_scenario_registry.json"
DEFAULT_CATALOG = ROOT / "experiments/article/real_execution/dataset_experimental_catalog.json"
OUT_ROOT = ROOT / "reports/article_experiments"


def stable_digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            if isinstance(parsed, dict):
                parsed["_http_status"] = resp.status
                return parsed
            return {"value": parsed, "_http_status": resp.status}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        if isinstance(parsed, dict):
            parsed["_http_status"] = exc.code
            return parsed
        return {"value": parsed, "_http_status": exc.code}
    except Exception as exc:
        return {"_http_status": 0, "error": str(exc)}


def scenario_queries(scenario_obj: Any) -> list[dict[str, Any]]:
    if isinstance(scenario_obj, list):
        return [x for x in scenario_obj if isinstance(x, dict)]
    if isinstance(scenario_obj, dict):
        for key in ("queries", "items", "steps"):
            if isinstance(scenario_obj.get(key), list):
                return [x for x in scenario_obj[key] if isinstance(x, dict)]
    return []


def scenario_id_from(path: Path, scenario_obj: Any) -> str:
    if isinstance(scenario_obj, dict):
        return str(
            scenario_obj.get("id")
            or scenario_obj.get("scenario_id")
            or scenario_obj.get("name")
            or path.stem
        )
    return path.stem


def objective_id_from(scenario_obj: Any, query: dict[str, Any]) -> str:
    if query.get("objective_id"):
        return str(query["objective_id"])
    if isinstance(scenario_obj, dict) and scenario_obj.get("objective_id"):
        return str(scenario_obj["objective_id"])
    return ""


def dw_id_from(scenario_obj: Any, query: dict[str, Any], fallback: str) -> str:
    if query.get("dw_id"):
        return str(query["dw_id"])
    if isinstance(scenario_obj, dict) and scenario_obj.get("dw_id"):
        return str(scenario_obj["dw_id"])
    return fallback


def query_text_from(query: dict[str, Any]) -> str:
    return str(
        query.get("mdx")
        or query.get("sql")
        or query.get("query")
        or query.get("query_text")
        or ""
    )


def expected_decision_from(query: dict[str, Any]) -> str:
    return str(
        query.get("expected_decision")
        or query.get("expected")
        or query.get("decision")
        or ""
    ).upper()


def decision_from_response(resp: dict[str, Any]) -> str:
    decision = resp.get("decision")
    if isinstance(decision, dict):
        return str(decision.get("decision") or decision.get("status") or "").upper()
    return str(decision or "").upper()


def pick_execution_fields(resp: dict[str, Any]) -> dict[str, Any]:
    ev = resp.get("execution_evidence") if isinstance(resp.get("execution_evidence"), dict) else {}
    exec_ev = ev.get("execution") if isinstance(ev.get("execution"), dict) else {}
    direct = resp.get("direct_result") if isinstance(resp.get("direct_result"), dict) else {}
    result = resp.get("result") if isinstance(resp.get("result"), dict) else {}

    physical = exec_ev.get("physical_execution")
    if physical is None:
        physical = direct.get("physical_execution")
    if physical is None:
        physical = resp.get("physical_execution")

    row_count = exec_ev.get("row_count")
    if row_count is None:
        row_count = direct.get("row_count")
    if row_count is None:
        row_count = result.get("row_count")

    cell_count = exec_ev.get("cell_count")
    if cell_count is None:
        cell_count = direct.get("cell_count")
    if cell_count is None:
        cell_count = result.get("cell_count")

    response_digest = (
        exec_ev.get("response_digest")
        or exec_ev.get("result_digest")
        or direct.get("response_digest")
        or direct.get("result_digest")
        or resp.get("response_digest")
        or resp.get("result_digest")
    )

    return {
        "physical_execution": physical,
        "blocked_before_execution": exec_ev.get("blocked_before_execution") or direct.get("blocked_before_execution") or resp.get("blocked_before_execution"),
        "execution_path": exec_ev.get("execution_path") or direct.get("execution_path") or resp.get("execution_path") or "",
        "adapter_id": exec_ev.get("adapter_id") or direct.get("adapter_id") or resp.get("adapter_id") or "",
        "requested_dw_id": exec_ev.get("requested_dw_id") or resp.get("dw_id") or "",
        "selected_dw_id": exec_ev.get("selected_dw_id") or resp.get("selected_dw_id") or resp.get("dw_id") or "",
        "row_count": row_count,
        "cell_count": cell_count,
        "elapsed_ms": exec_ev.get("elapsed_ms") or direct.get("elapsed_ms") or resp.get("elapsed_ms"),
        "response_bytes": exec_ev.get("response_bytes") or direct.get("response_bytes") or resp.get("response_bytes"),
        "response_digest": response_digest,
        "raw_response_digest": stable_digest(resp),
    }


def find_objective_file(objective_id: str) -> Path | None:
    if not objective_id:
        return None
    for path in (ROOT / "bi-stack/objectives").glob("*.json"):
        try:
            obj = load_json(path)
        except Exception:
            continue
        found = str(obj.get("id") or obj.get("objective_id") or "")
        if found == objective_id:
            return path
    return None


def import_objective_if_available(base: str, objective_id: str) -> dict[str, Any]:
    path = find_objective_file(objective_id)
    if path is None:
        return {
            "objective_id": objective_id,
            "imported": False,
            "reason": "objective file not found",
        }

    obj = load_json(path)
    resp = http_json("POST", f"{base}/mcad/objectives/import", obj, timeout=120)
    return {
        "objective_id": objective_id,
        "objective_file": str(path.relative_to(ROOT)),
        "imported": int(resp.get("_http_status", 0)) < 400,
        "http_status": resp.get("_http_status"),
        "response_digest": stable_digest(resp),
    }


def import_scenario(base: str, scenario_obj: Any, scenario_path: Path) -> dict[str, Any]:
    resp_validate = http_json("POST", f"{base}/bi/scenarios/validate", scenario_obj, timeout=120)
    resp_import = http_json("POST", f"{base}/bi/scenarios/import", scenario_obj, timeout=120)
    return {
        "scenario_path": str(scenario_path.relative_to(ROOT)),
        "validate_status": resp_validate.get("_http_status"),
        "import_status": resp_import.get("_http_status"),
        "validate_digest": stable_digest(resp_validate),
        "import_digest": stable_digest(resp_import),
        "ok": int(resp_import.get("_http_status", 0)) < 400,
    }


def create_session(base: str, objective_id: str, dw_id: str) -> dict[str, Any]:
    payload = {"objective_id": objective_id, "dw_id": dw_id}
    resp = http_json("POST", f"{base}/mcad/session/new", payload, timeout=120)
    active = resp.get("active") if isinstance(resp.get("active"), dict) else {}
    session_id = active.get("session_id") or resp.get("session_id") or active.get("id") or ""
    return {
        "ok": int(resp.get("_http_status", 0)) < 400,
        "http_status": resp.get("_http_status"),
        "session_id": session_id,
        "response_digest": stable_digest(resp),
        "raw": resp,
    }


def execute_query(
    base: str,
    *,
    scenario_id: str,
    scenario_path: Path,
    query: dict[str, Any],
    query_index: int,
    session_id: str,
    objective_id: str,
    dw_id: str,
) -> dict[str, Any]:
    qid = str(query.get("id") or query.get("query_id") or f"{scenario_id}_Q{query_index}")
    qtype = str(query.get("query_type") or query.get("language") or "mdx")
    qtext = query_text_from(query)

    payload = {
        "mdx": qtext,
        "query": qtext,
        "query_type": qtype,
        "query_id": qid,
        "objective_id": objective_id,
        "session_id": session_id,
        "dw_id": dw_id,
        "execution_mode": "article_real_run_probe",
        "source_scenario_id": scenario_id,
        "scenario_id": scenario_id,
        "scenario_query_id": qid,
        "scenario_query_index": query_index,
        "allow_fallback": False,
        "max_rows": 200,
    }

    started = time.perf_counter()
    resp = http_json("POST", f"{base}/bi/execute", payload, timeout=300)
    total_elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    expected = expected_decision_from(query)
    decision = decision_from_response(resp)
    fields = pick_execution_fields(resp)

    normalized = {
        "scenario_id": scenario_id,
        "scenario_path": str(scenario_path.relative_to(ROOT)),
        "query_index": query_index,
        "query_id": qid,
        "query_type": qtype,
        "objective_id": objective_id,
        "dw_id": dw_id,
        "expected_decision": expected,
        "decision": decision,
        "http_status": resp.get("_http_status"),
        "api_elapsed_ms": total_elapsed_ms,
        "execution_mode": "real",
        "evidence_origin": "bi-stack:/bi/execute",
        **fields,
    }

    problems: list[str] = []
    if int(resp.get("_http_status", 0)) >= 400 or int(resp.get("_http_status", 0)) == 0:
        problems.append(f"HTTP status not OK: {resp.get('_http_status')}")
    if expected and decision != expected:
        problems.append(f"decision mismatch: expected {expected}, got {decision}")

    if expected == "ALLOW":
        if fields.get("physical_execution") is not True:
            problems.append(f"ALLOW without physical_execution=True: {fields.get('physical_execution')}")
        if not fields.get("adapter_id"):
            problems.append("ALLOW missing adapter_id")
        if not fields.get("response_digest") and not fields.get("raw_response_digest"):
            problems.append("ALLOW missing response digest")
        row_count = fields.get("row_count")
        cell_count = fields.get("cell_count")
        if row_count is None and cell_count is None:
            problems.append("ALLOW missing row_count/cell_count")
    elif expected == "BLOCK":
        if fields.get("physical_execution") is not False:
            problems.append(f"BLOCK should have physical_execution=False, got {fields.get('physical_execution')}")

    normalized["pass"] = not problems
    normalized["problems"] = problems
    normalized["raw_response_digest"] = stable_digest(resp)

    return normalized | {"raw_response": resp}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:9000")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY.relative_to(ROOT)))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG.relative_to(ROOT)))
    parser.add_argument("--datasets", default="foodmart,adventureworks,steelwheels")
    parser.add_argument("--backends", default="sql_direct,xmla_emondrian")
    parser.add_argument("--max-scenarios-per-dataset-backend", type=int, default=1)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    registry = load_json(ROOT / args.registry)
    _catalog = load_json(ROOT / args.catalog)

    selected_datasets = [x.strip() for x in args.datasets.split(",") if x.strip()]
    selected_backends = [x.strip() for x in args.backends.split(",") if x.strip()]

    run_id = args.run_id or datetime.now(timezone.utc).strftime("real_run_probe_%Y%m%dT%H%M%SZ")
    run_dir = OUT_ROOT / run_id

    for sub in [
        "raw_executions",
        "non_execution_proofs",
        "api_responses",
        "imports",
        "sessions",
    ]:
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    query_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    import_rows: list[dict[str, Any]] = []
    all_problems: list[str] = []

    for dataset_id in selected_datasets:
        dataset_backends = registry.get(dataset_id, {})
        for backend_id in selected_backends:
            scenario_paths = dataset_backends.get(backend_id, [])
            if not scenario_paths:
                all_problems.append(f"No scenario path for {dataset_id}/{backend_id}")
                continue

            for rel_scenario_path in scenario_paths[: args.max_scenarios_per_dataset_backend]:
                scenario_path = ROOT / rel_scenario_path
                scenario_obj = load_json(scenario_path)
                scenario_id = scenario_id_from(scenario_path, scenario_obj)
                queries = scenario_queries(scenario_obj)

                if not queries:
                    all_problems.append(f"No queries in {rel_scenario_path}")
                    continue

                first_query = queries[0]
                objective_id = objective_id_from(scenario_obj, first_query)
                dw_id = dw_id_from(scenario_obj, first_query, dataset_id)

                obj_import = import_objective_if_available(args.base, objective_id)
                scen_import = import_scenario(args.base, scenario_obj, scenario_path)
                import_rows.append({
                    "dataset_id": dataset_id,
                    "backend_id": backend_id,
                    "scenario_id": scenario_id,
                    "objective_id": objective_id,
                    "dw_id": dw_id,
                    "objective_imported": obj_import.get("imported"),
                    "scenario_imported": scen_import.get("ok"),
                    "objective_http_status": obj_import.get("http_status"),
                    "scenario_import_status": scen_import.get("import_status"),
                })
                write_json(run_dir / "imports" / f"{dataset_id}_{backend_id}_{scenario_id}_objective.json", obj_import)
                write_json(run_dir / "imports" / f"{dataset_id}_{backend_id}_{scenario_id}_scenario.json", scen_import)

                session = create_session(args.base, objective_id, dw_id)
                write_json(run_dir / "sessions" / f"{dataset_id}_{backend_id}_{scenario_id}_session.json", session)
                if not session.get("ok"):
                    all_problems.append(f"Session creation failed for {scenario_id}: {session.get('http_status')}")
                    continue

                session_id = str(session.get("session_id") or "")
                allow_count = 0
                block_count = 0

                for idx, query in enumerate(queries, start=1):
                    objective_id_q = objective_id_from(scenario_obj, query) or objective_id
                    dw_id_q = dw_id_from(scenario_obj, query, dw_id)

                    result = execute_query(
                        args.base,
                        scenario_id=scenario_id,
                        scenario_path=scenario_path,
                        query=query,
                        query_index=idx,
                        session_id=session_id,
                        objective_id=objective_id_q,
                        dw_id=dw_id_q,
                    )

                    raw_response = result.pop("raw_response")
                    expected = result.get("expected_decision")
                    qid = result.get("query_id")

                    safe_name = f"{dataset_id}_{backend_id}_{scenario_id}_{idx}_{qid}".replace("/", "_")
                    write_json(run_dir / "api_responses" / f"{safe_name}.json", raw_response)

                    if expected == "ALLOW":
                        allow_count += 1
                        write_json(run_dir / "raw_executions" / f"{safe_name}.json", result)
                    else:
                        block_count += 1
                        write_json(run_dir / "non_execution_proofs" / f"{safe_name}.json", result)

                    row = {
                        "run_id": run_id,
                        "dataset_id": dataset_id,
                        "backend_id": backend_id,
                        "scenario_id": scenario_id,
                        "session_id": session_id,
                        **result,
                    }
                    query_rows.append(row)

                    if not result.get("pass"):
                        all_problems.extend([f"{scenario_id}/{qid}: {p}" for p in result.get("problems", [])])

                session_rows.append({
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "backend_id": backend_id,
                    "scenario_id": scenario_id,
                    "session_id": session_id,
                    "session_length": len(queries),
                    "expected_allow_count": allow_count,
                    "expected_block_count": block_count,
                })

    write_csv(run_dir / "article_metrics_by_query.csv", query_rows)
    write_csv(run_dir / "article_metrics_by_session.csv", session_rows)
    write_csv(run_dir / "real_import_summary.csv", import_rows)

    manifest = {
        "run_id": run_id,
        "protocol": "real_run_probe",
        "from_scratch": True,
        "reuse_previous_results": False,
        "real_backends_required": True,
        "real_backends_verified": not all_problems,
        "base": args.base,
        "datasets": selected_datasets,
        "backends": selected_backends,
        "query_decisions": len(query_rows),
        "sessions": len(session_rows),
        "problems": all_problems,
    }
    write_json(run_dir / "manifest.json", manifest)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))

    return 0 if not all_problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
