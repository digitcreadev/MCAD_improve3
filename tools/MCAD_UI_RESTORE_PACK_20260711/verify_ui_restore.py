#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TARGET_OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
TARGET_SCENARIO_ID = "adventureworks_sales_margin_territory_q1_q6"


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)
    print(f"[FAIL] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify MCAD UI source contracts and clean runtime prerequisites.")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    failures: list[str] = []

    ui = repo / "bi-stack/mcad-proxy/session_ui.html"
    proxy = repo / "bi-stack/mcad-proxy/app.py"
    api = repo / "bi-stack/mcad-api/app.py"
    data = repo / "bi-stack/mcad-api-data"
    target_obj = repo / "bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
    target_scenario = repo / "bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"

    for p in (ui, proxy, api, target_obj, target_scenario):
        if p.exists(): ok(f"{p.relative_to(repo)} exists")
        else: fail(f"{p.relative_to(repo)} missing", failures)

    if failures:
        return 1

    for p in (proxy, api):
        try:
            ast.parse(p.read_text(encoding="utf-8"))
            ok(f"Python syntax valid: {p.relative_to(repo)}")
        except SyntaxError as exc:
            fail(f"Python syntax invalid: {p.relative_to(repo)}: {exc}", failures)

    html = ui.read_text(encoding="utf-8")
    required_pages = ["overview", "analysis", "runner", "studio", "governance", "history", "reports", "demo"]
    for page in required_pages:
        if f'data-page="{page}"' in html:
            ok(f"UI page present: {page}")
        else:
            fail(f"UI page missing: {page}", failures)

    required_functions = [
        "createSession", "resumeSession", "analysisRun", "runWholeScenario",
        "renderGraph", "showDecisionDetails", "generateSessionReport",
        "generateMetricsDashboard", "runDualPathDemoValidation",
        "v943aHydrateEvidenceForActiveSession", "resetEffectiveSessionTrace",
    ]
    for fn in required_functions:
        if re.search(rf"\bfunction\s+{re.escape(fn)}\s*\(", html):
            ok(f"UI function present: {fn}")
        else:
            fail(f"UI function missing: {fn}", failures)

    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.S | re.I)
    js = "\n;\n".join(scripts)
    if shutil.which("node"):
        tmp = repo / ".tmp_mcad_ui_syntax_check.js"
        tmp.write_text(js, encoding="utf-8")
        try:
            cp = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
            if cp.returncode == 0:
                ok("session_ui JavaScript syntax is valid")
            else:
                fail(f"session_ui JavaScript syntax invalid: {cp.stderr.strip()}", failures)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        warn("node is unavailable; JavaScript syntax check skipped")

    # Runtime data checks
    for name in ("ckg_state.json", "decision_details.json", "imported_objectives.json", "ckg_events.jsonl"):
        p = data / name
        if p.exists(): ok(f"runtime file exists: {p.relative_to(repo)}")
        else: fail(f"runtime file missing: {p.relative_to(repo)}", failures)

    try:
        state = load_json(data / "ckg_state.json")
        history_count = len(state.get("history") or [])
        coverage_count = len(state.get("session_coverage") or {})
        if history_count == 0: ok("CKG runtime history is clean")
        else: warn(f"CKG runtime history is not clean: {history_count} entries")
        if coverage_count == 0: ok("CKG session coverage is clean")
        else: warn(f"CKG session coverage is not clean: {coverage_count} sessions")
    except Exception as exc:
        fail(f"ckg_state.json invalid: {exc}", failures)

    try:
        dd = load_json(data / "decision_details.json")
        if isinstance(dd, dict):
            if len(dd) == 0: ok("decision_details archive is clean")
            else: warn(f"decision_details contains {len(dd)} sessions; fresh UI run may be slow or contaminated")
        else:
            fail("decision_details.json root is not an object", failures)
    except Exception as exc:
        fail(f"decision_details.json invalid: {exc}", failures)

    try:
        imported = load_json(data / "imported_objectives.json")
        items = imported.get("objectives", []) if isinstance(imported, dict) else imported
        ids = [str(x.get("id")) for x in items if isinstance(x, dict)]
        if TARGET_OBJECTIVE_ID in ids:
            ok(f"target AdventureWorks objective is preloaded: {TARGET_OBJECTIVE_ID}")
        else:
            warn(f"target objective is not preloaded: {TARGET_OBJECTIVE_ID}")
        if len(ids) <= 10:
            ok(f"interactive objective catalog is compact: {len(ids)} imported objective(s)")
        else:
            warn(f"interactive objective catalog is large: {len(ids)} imported objectives")
    except Exception as exc:
        fail(f"imported_objectives.json invalid: {exc}", failures)

    try:
        obj = load_json(target_obj)
        if obj.get("id") == TARGET_OBJECTIVE_ID: ok("target objective file has expected id")
        else: fail("target objective file has unexpected id", failures)
    except Exception as exc:
        fail(f"target objective file invalid: {exc}", failures)

    try:
        sc = load_json(target_scenario)
        if sc.get("id") == TARGET_SCENARIO_ID: ok("target scenario file has expected id")
        else: fail("target scenario file has unexpected id", failures)
        qs = sc.get("queries") or []
        if len(qs) == 6: ok("target scenario contains exactly six queries")
        else: fail(f"target scenario query count is {len(qs)}, expected 6", failures)
        expected = [str(q.get("expected_decision") or "").upper() for q in qs]
        if expected == ["ALLOW", "ALLOW", "ALLOW", "BLOCK", "BLOCK", "BLOCK"]:
            ok("target scenario expected decision sequence is ALLOW×3 then BLOCK×3")
        else:
            fail(f"unexpected decision sequence: {expected}", failures)
    except Exception as exc:
        fail(f"target scenario file invalid: {exc}", failures)

    print(f"\nSummary: failures={len(failures)}")
    if failures:
        for item in failures:
            print(f" - {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
