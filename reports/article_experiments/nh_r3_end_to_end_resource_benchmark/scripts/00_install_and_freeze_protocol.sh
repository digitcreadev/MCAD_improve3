#!/usr/bin/env bash
REPO="${1:-/workspaces/MCAD_improve3}"
EXPECTED_BRANCH="paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
EXPECTED_HEAD="21ae791c850c019f07554e006ce9db82e1ac8769"
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$KIT_ROOT/payload/nh_r3_end_to_end_resource_benchmark"
DST="$REPO/reports/article_experiments/nh_r3_end_to_end_resource_benchmark"

cd "$REPO" || { echo "R3_PROTOCOL_INSTALL=FAIL repo"; exit 1; }
echo "=== MCAD-NH-R3 R3-A PROTOCOL INSTALL/FREEZE ==="
echo "branch=$(git branch --show-current)"
echo "head=$(git rev-parse HEAD)"
git status --short --branch

OK=1
[[ "$(git branch --show-current)" == "$EXPECTED_BRANCH" ]] && echo "BRANCH_GATE=PASS" || { echo "BRANCH_GATE=FAIL"; OK=0; }
[[ "$(git rev-parse HEAD)" == "$EXPECTED_HEAD" ]] && echo "HEAD_GATE=PASS" || { echo "HEAD_GATE=FAIL"; OK=0; }
[[ -z "$(git status --porcelain=v1)" ]] && echo "CLEAN_TREE_GATE=PASS" || { echo "CLEAN_TREE_GATE=FAIL"; OK=0; }
[[ ! -e "$DST" ]] && echo "DEST_ABSENCE_GATE=PASS" || { echo "DEST_ABSENCE_GATE=FAIL path=$DST"; OK=0; }

if [[ "$OK" -ne 1 ]]; then
  echo "R3_PROTOCOL_INSTALL=FAIL pre_mutation_gate"
  exit 2
fi

mkdir -p "$(dirname "$DST")"
cp -a "$SRC" "$DST"

python "$DST/implementation/build_binding_plan.py" "$REPO"
BUILD_STATUS=$?
echo "binding_build_exit_status=$BUILD_STATUS"

python "$DST/implementation/verify_protocol.py" "$REPO"
VERIFY_STATUS=$?
echo "protocol_verify_exit_status=$VERIFY_STATUS"

# deterministic protocol freeze over config/docs/templates/implementation + generated binding plan hash
python - "$DST" <<'PY'
from pathlib import Path
import hashlib, json, sys
root=Path(sys.argv[1])
files=[]
for sub in ("config","docs","templates","implementation"):
    files += [p for p in (root/sub).rglob("*") if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")]
files=sorted(files, key=lambda p:p.relative_to(root).as_posix())
binding=(root/"results/BINDING_PLAN_SHA256.txt").read_text().split()[0]
h=hashlib.sha256()
manifest=[]
for p in files:
    rel=p.relative_to(root).as_posix()
    dig=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest.append({"path":rel,"sha256":dig})
    h.update(rel.encode()+b"\0"+dig.encode()+b"\0")
h.update(b"BINDING_PLAN_SHA256\0"+binding.encode()+b"\0")
freeze={"freeze_id":"MCAD-NH-R3-A-PROTOCOL-FREEZE-1","parent_r2_commit":"21ae791c850c019f07554e006ce9db82e1ac8769",
        "binding_plan_sha256":binding,"files":manifest,"resource_claims":"NOT_PROMOTED","measured_backend_runs":0}
fp=root/"results/MCAD_NH_R3_A_PROTOCOL_FREEZE.json"
fp.write_text(json.dumps(freeze,indent=2,sort_keys=True)+"\n")
digest=hashlib.sha256(fp.read_bytes()).hexdigest()
(root/"results/MCAD_NH_R3_A_PROTOCOL_FREEZE_SHA256.txt").write_text(digest+"  MCAD_NH_R3_A_PROTOCOL_FREEZE.json\n")
print("r3_a_protocol_freeze_sha256="+digest)
PY

echo
echo "--- installed result files ---"
find "$DST/results" -maxdepth 1 -type f -printf '%f\t%s bytes\n' | sort

echo
echo "--- key outputs ---"
cat "$DST/results/BINDING_PLAN_SHA256.txt"
cat "$DST/results/MCAD_NH_R3_A_PROTOCOL_FREEZE_SHA256.txt"
cat "$DST/results/binding_summary.json"

echo
echo "--- post-install git state (reports/ is ignored, so clean is expected) ---"
git status --short --branch
echo "NO_DOCKER_SERVICE_STARTED=true"
echo "NO_MEASURED_BACKEND_QUERY_EXECUTED=true"
echo "NO_RESOURCE_CLAIMS_PROMOTED=true"
echo "NO_COMMIT_PERFORMED=true"
echo "NO_PUSH_PERFORMED=true"

if [[ "$BUILD_STATUS" -eq 0 && "$VERIFY_STATUS" -eq 0 ]]; then
  echo "R3_PROTOCOL_INSTALL=PASS"
else
  echo "R3_PROTOCOL_INSTALL=FAIL"
  exit 3
fi
