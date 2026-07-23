#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
DOC="$ROOT/bi-stack/docs/MCAD_ARTICLE_V2_CONTRIBUTIONS_AND_METRICS.md"

fail(){ echo "[FAIL] $1" >&2; exit 1; }
ok(){ echo "[OK] $1"; }

[ -f "$DOC" ] || fail "V2 contribution/metrics document exists"

python - "$DOC" <<'PY'
from pathlib import Path
import sys

doc = Path(sys.argv[1]).read_text(encoding="utf-8")

checks = [
    ("central MCAD-Gate contribution is stated", "MCAD-Gate detects, explains and controls"),
    ("formal chain is stated", "QP → SAT(QP) → Real(QP) → Ceval(QP,O) → S*(QP,O) → φ(QP,O)"),
    ("classification metrics are included", "precision_block"),
    ("coverage preservation metric is included", "coverage_preservation_ratio"),
    ("execution-control metrics are included", "execution_reduction_rate"),
    ("explanation metrics are included", "explanation_coverage_rate"),
    ("runtime metrics are included", "decision_latency_p95_ms"),
    ("backend contract metrics are included", "contract_violation_count"),
    ("core campaign is described", "Campaign A"),
    ("multi-dataset campaign is described", "Campaign B"),
    ("backend portability campaign is described", "Campaign C"),
    ("MCAD-Guide is positioned as future work", "future MCAD-Guide"),
]

for label, needle in checks:
    if needle not in doc:
        raise SystemExit(f"[FAIL] {label}")

print("[OK] V2 contribution and metrics framing is complete")
PY

echo
echo "=== MCAD Article V2 framing OK ==="
