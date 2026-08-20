#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
OUT="$ROOT/results"
rm -rf "$OUT"; mkdir -p "$OUT/logs"
{
  echo "run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo_root=$REPO_ROOT"
  echo "branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)"
  echo "head=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
  echo "status_before<<EOF"
  git -C "$REPO_ROOT" status --short --branch 2>/dev/null || true
  echo EOF
} | tee "$OUT/logs/run_context.log"
bash "$ROOT/scripts/00_preflight.sh" | tee "$OUT/logs/preflight.log"
python3 "$ROOT/implementation/run_campaign.py" --config "$ROOT/config/r2_campaign.json" --out "$OUT" --repo-root "$REPO_ROOT" | tee "$OUT/logs/campaign.log"
python3 "$ROOT/implementation/validate_results.py" "$OUT" | tee "$OUT/logs/validation.log"
python3 "$ROOT/implementation/build_semantic_digest.py" "$OUT" | tee "$OUT/logs/semantic_digest.log"
python3 "$ROOT/implementation/build_freeze.py" "$ROOT" "$OUT" | tee "$OUT/logs/freeze.log"
PACKAGE_OUTPUT="$(python3 "$ROOT/implementation/package_results.py" "$ROOT" "$OUT")"
printf '%s\n' "$PACKAGE_OUTPUT" | tee "$OUT/logs/package.log"
echo "=== NH-R2 COMPLETE ==="
cat "$OUT/gate_results.json"
