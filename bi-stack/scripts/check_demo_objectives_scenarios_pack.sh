#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

ok(){ echo "[OK] $1"; }
fail(){ echo "[FAIL] $1" >&2; exit 1; }

MANIFEST="$ROOT/bi-stack/demo-packs/mcad_demo_aw_steelwheels_objectives_scenarios_pack.json"
LOADER="$ROOT/bi-stack/scripts/load_demo_objectives_scenarios.sh"

[ -f "$MANIFEST" ] || fail "demo pack manifest exists"
[ -x "$LOADER" ] || fail "load_demo_objectives_scenarios.sh exists and is executable"

python - "$ROOT" <<'PY'
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])
manifest = json.loads((root / "bi-stack/demo-packs/mcad_demo_aw_steelwheels_objectives_scenarios_pack.json").read_text(encoding="utf-8"))

objective_files = [root / p for p in manifest["objective_files"]]
scenario_files = [root / p for p in manifest["scenario_files"]]

assert len(objective_files) == 4, f"expected 4 objectives, got {len(objective_files)}"
assert len(scenario_files) == 8, f"expected 8 scenarios, got {len(scenario_files)}"

objective_ids = set()
for path in objective_files:
    assert path.exists(), f"missing objective file {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    oid = data["id"]
    assert oid not in objective_ids, f"duplicate objective id {oid}"
    objective_ids.add(oid)
    assert data["dataset"] in {"AdventureWorksDW", "SteelWheels"}, f"bad objective dataset {data['dataset']}"
    assert data["cube"] in {"Adventure Works DW", "SteelWheelsSales"}, f"bad cube {data['cube']}"
    assert len(data.get("constraints", [])) == 2, f"{oid}: expected 2 constraints"
    for c in data["constraints"]:
        assert c.get("requirement_sets"), f"{oid}/{c['id']}: missing requirement_sets"
        assert c.get("virtual_nodes"), f"{oid}/{c['id']}: missing virtual_nodes"

scenario_ids = set()
expected_decisions = ["ALLOW", "ALLOW", "BLOCK", "BLOCK", "BLOCK", "BLOCK"]
expected_reasons = [
    "ALLOW_NEW_TOTAL",
    "ALLOW_NEW_TOTAL",
    "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
    "BLOCK_OUT_OF_OBJECTIVE_SCOPE",
    "BLOCK_GRAIN_MISMATCH",
    "BLOCK_REDUNDANT_DPHI_ZERO",
]

for path in scenario_files:
    assert path.exists(), f"missing scenario file {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    sid = data["id"]
    assert sid not in scenario_ids, f"duplicate scenario id {sid}"
    scenario_ids.add(sid)
    assert data["objective_id"] in objective_ids, f"{sid}: unknown objective_id {data['objective_id']}"
    assert data["dataset"] in {"AdventureWorksDW", "SteelWheels"}, f"{sid}: bad dataset {data['dataset']}"
    assert data["query_count"] == 6, f"{sid}: query_count != 6"
    assert len(data["queries"]) == 6, f"{sid}: expected 6 queries"
    assert [q["expected_decision"] for q in data["queries"]] == expected_decisions, f"{sid}: decision sequence mismatch"
    assert [q.get("expected_reason_code") for q in data["queries"]] == expected_reasons, f"{sid}: reason sequence mismatch"
    if data["dw_id"] == "steelwheels_xmla":
        assert any("Descendants([Time].[Years]" in q["mdx"] for q in data["queries"][:2]), f"{sid}: XMLA month queries should use Descendants"

print("[OK] JSON structure, IDs, datasets, decisions and reasons are valid")
PY

grep -q "/mcad/objectives/import" "$LOADER" || fail "loader imports objectives"
grep -q "/bi/scenarios/import" "$LOADER" || fail "loader imports scenarios"

ok "demo pack loader is wired"

echo
echo "=== Demo objectives/scenarios pack OK ==="
