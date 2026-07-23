#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/workspaces/MCAD_improve3}"
SRC="$(cd "$(dirname "$0")" && pwd)/backend/harness"
DST="$REPO/backend/harness"

cd "$REPO"

if [[ -e "$DST" ]]; then
  echo "[ERROR] $DST already exists. Refusing to overwrite."
  exit 1
fi

cp -a "$SRC" "$DST"
find "$DST" -type d -name '__pycache__' -prune -exec rm -rf {} +

echo "[OK] Installed audited harness at $DST"
