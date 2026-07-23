#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
DOC="$ROOT/bi-stack/docs/MCAD_ARTICLE_V2_RESULTS_INTERPRETATION.md"

fail(){ echo "[FAIL] $1" >&2; exit 1; }
ok(){ echo "[OK] $1"; }

[ -f "$DOC" ] || fail "results interpretation document exists"

grep -q "MCAD-Gate detects, explains and controls" "$DOC" || fail "central contribution is stated"
grep -q "Campaign A" "$DOC" || fail "Campaign A is documented"
grep -q "Campaign B" "$DOC" || fail "Campaign B is documented"
grep -q "Campaign C" "$DOC" || fail "Campaign C is documented"
grep -q "coverage preservation ratio: 1.0000" "$DOC" || fail "coverage preservation result is included"
grep -q "execution reduction ratio: 0.7467" "$DOC" || fail "execution reduction result is included"
grep -q "non-contributive execution reduction ratio: 1.0000" "$DOC" || fail "non-contributive reduction result is included"
grep -q "false-allow reduction ratio: 1.0000" "$DOC" || fail "false allow reduction result is included"
grep -q "controlled analytical sessions" "$DOC" || fail "controlled workload limitation is included"
grep -q "MCAD-Gate does not aim to maximize final coverage" "$DOC" || fail "correct interpretation is included"

ok "MCAD Article V2 results interpretation document is complete"

echo
echo "=== MCAD Article V2 results interpretation OK ==="
