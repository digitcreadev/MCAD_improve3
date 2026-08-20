#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_R1="b12034c9658a23ad2cb588237bb462148478f6e32d42e9494019611367eecdfb"
PARENT="$ROOT/parent/MCAD_NH_R1_ALL_DELIVERABLES.zip"
echo "=== NH-R2 preflight ==="
python3 --version
git --version || true
ACTUAL="$(sha256sum "$PARENT" | awk '{print $1}')"
echo "parent_r1_sha256=$ACTUAL"
[[ "$ACTUAL" == "$EXPECTED_R1" ]] || { echo "parent_r1_gate=FAIL"; exit 2; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
unzip -q "$PARENT" -d "$TMP"
FREEZE="$(find "$TMP" -name MCAD_NH_R1_FREEZE.json -print -quit)"
FZH="$(sha256sum "$FREEZE" | awk '{print $1}')"
echo "r1_freeze_sha256=$FZH"
[[ "$FZH" == "68538940e73d6ee8b9927f142d80abce3a8e097b6595c32ea14fbb88fb43937a" ]] || { echo "r1_freeze_gate=FAIL"; exit 3; }
python3 - "$ROOT" <<'PYREF'
import hashlib, pathlib, sys, zipfile, tempfile
root=pathlib.Path(sys.argv[1]); z=root/'parent'/'MCAD_NH_R1_ALL_DELIVERABLES.zip'
with tempfile.TemporaryDirectory() as d:
    with zipfile.ZipFile(z) as Z: Z.extractall(d)
    ref=next(pathlib.Path(d).rglob('implementation/reference_model.py')); local=root/'implementation'/'reference_model.py'
    a=hashlib.sha256(ref.read_bytes()).hexdigest(); b=hashlib.sha256(local.read_bytes()).hexdigest()
    print('parent_reference_model_sha256='+a); print('local_reference_model_sha256='+b)
    if a!=b: raise SystemExit('reference model mismatch')
PYREF
echo "preflight=PASS"
