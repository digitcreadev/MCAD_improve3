#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-.}"
BASE_URL="${MCAD_PROXY_BASE:-http://127.0.0.1:9000}"
PY="${PYTHON:-python3}"

echo "=== MCAD V9.4.5a Dual-Path Demo Validation Pack ==="
echo "repo_root=${REPO_ROOT}"
echo "base_url=${BASE_URL}"
echo "retry_attempts=${MCAD_DEMO_RETRY_ATTEMPTS:-24}"
echo "retry_sleep_s=${MCAD_DEMO_RETRY_SLEEP_S:-1.0}"

auto_open_msg() {
  echo
  echo "Generated artifacts are written under: bi-stack/demo-evidence/runs/<timestamp>"
  echo "latest_path.txt points to the most recent run."
}

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[FAIL] Python interpreter not found: $PY" >&2
  exit 2
fi

"$PY" "$REPO_ROOT/bi-stack/scripts/run_dual_path_demo_validation.py" "$REPO_ROOT" --base-url "$BASE_URL"
auto_open_msg
