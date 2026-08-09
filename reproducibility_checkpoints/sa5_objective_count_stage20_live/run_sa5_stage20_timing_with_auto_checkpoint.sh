#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/MCAD_improve3"
BASE="paper/phase3-controlled-execution"
EXPECTED_HEAD="fd7d87e5658b63c0753a9686b43ec2e5e2d17344"

PYTHON="/workspaces/.venvs/mcad-bridge-reconciliation-20260801T180758Z/bin/python"
CONTROLLER="/workspaces/execute_sa5_stage20_once_v4_segmented.py"
EXPECTED_CONTROLLER_SHA="7862f3bbc58a604b0db2587e794dd8878c9770170a2186677ea97606f6652d25"

E3="reports/article_experiments/sensitivity/e3_controlled_execution"
WORK="$E3/stage20_work/objective_count_stage20_fd7d87e"
OUT="$E3/audits/objective_count/timing_stage20/precision_analysis"

PRECISION_START="$OUT/SA5_STAGE20_PRECISION_STARTED.json"
START_MARKER="$OUT/SA5_STAGE20_EXECUTION_STARTED.json"

CHECKPOINT_BRANCH="checkpoint/sa5-stage20-recovery-20260808T224049Z"
CHECKPOINT_WT="/workspaces/sa5_stage20_recovery_worktree_20260808T224049Z"
LIVE_DEST="reproducibility_checkpoints/sa5_objective_count_stage20_live"

LOCK="/workspaces/sa5_stage20_auto_checkpoint.lock"

QUARANTINE_OCCURRED=0
QUARANTINED_REP="none"

exec 9>"$LOCK"
if ! flock -n 9; then
    echo "[ERROR] another SA5 Stage-20 auto-checkpoint orchestrator holds $LOCK"
    exit 90
fi

utcnow() {
    date -u +'%Y-%m-%dT%H:%M:%SZ'
}

sha_file() {
    sha256sum "$1" | awk '{print $1}'
}

count_done() {
    local n=0
    local rep token
    for rep in $(seq 10 19); do
        token="$(printf '%03d' "$rep")"
        if test -f "$ROOT/$WORK/done/timing_rep_${token}.json"; then
            n=$((n + 1))
        fi
    done
    printf '%s\n' "$n"
}

completed_rep_csv() {
    local out=""
    local rep token
    for rep in $(seq 10 19); do
        token="$(printf '%03d' "$rep")"
        if test -f "$ROOT/$WORK/done/timing_rep_${token}.json"; then
            if test -n "$out"; then out="${out},"; fi
            out="${out}${rep}"
        fi
    done
    printf '%s\n' "$out"
}

first_pending_rep() {
    local rep token
    for rep in $(seq 10 19); do
        token="$(printf '%03d' "$rep")"
        if ! test -f "$ROOT/$WORK/done/timing_rep_${token}.json"; then
            printf '%s\n' "$rep"
            return 0
        fi
    done
    return 1
}

ensure_no_science_processes() {
    local timing precision
    timing="$(pgrep -af 'python.*[r]un_timing_repetitions' || true)"
    precision="$(pgrep -af 'python.*[a]nalyze_clustered_timing_precision' || true)"
    if test -n "$timing" || test -n "$precision"; then
        echo "[ERROR] checkpoint requested while scientific child is active"
        echo "timing=${timing:-none}"
        echo "precision=${precision:-none}"
        return 1
    fi
}

quarantine_incomplete_output_if_needed() {
    local rep="$1"
    local token output_dir done_marker complete rows stamp target

    token="$(printf '%03d' "$rep")"
    output_dir="$ROOT/$WORK/timing_runs/objective_count_rep_${token}_portfolio_timing_stage20"
    done_marker="$ROOT/$WORK/done/timing_rep_${token}.json"

    test ! -f "$done_marker" || return 0
    test -e "$output_dir" || return 0

    complete=true
    for name in \
        functional_references.json \
        timing_manifest.json \
        timing_observations.csv \
        timing_summary.json
    do
        test -s "$output_dir/$name" || complete=false
    done

    if test "$complete" = true; then
        rows="$(
            awk 'END {print NR > 0 ? NR - 1 : 0}' \
                "$output_dir/timing_observations.csv"
        )"
        if test "$rows" -eq 21120; then
            echo "[ERROR] rep ${token} appears complete but has no done marker."
            echo "[ERROR] refusing both quarantine and rerun; manual validation required."
            return 41
        fi
    fi

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    target="$ROOT/$WORK/interrupted/rep_${token}_incomplete_${stamp}"
    mkdir -p "$(dirname "$target")"

    echo "quarantine_replication=${token}"
    echo "quarantine_source=$output_dir"
    echo "quarantine_target=$target"

    mv "$output_dir" "$target"

    QUARANTINE_OCCURRED=1
    QUARANTINED_REP="$rep"

    {
        echo "schema=mcad-sa5-stage20-interrupted-timing-v1"
        echo "captured_at_utc=$(utcnow)"
        echo "replication=$rep"
        echo "reason=incomplete_output_without_done_marker_before_resume"
        echo "canonical_head=$EXPECTED_HEAD"
    } > "${target}.provenance.txt"

    echo "incomplete_replication_quarantined=true"
}

checkpoint_remote() {
    local reason="$1"
    local completed_csv="$2"
    local completed_count="$3"
    local latest_rep="$4"

    ensure_no_science_processes

    echo
    echo "=== AUTO CHECKPOINT: $reason ==="

    git -C "$ROOT" fetch origin --prune

    test "$(git -C "$ROOT" branch --show-current)" = "$BASE"
    test "$(git -C "$ROOT" rev-parse HEAD)" = "$EXPECTED_HEAD"
    test "$(git -C "$ROOT" rev-parse "origin/$BASE")" = "$EXPECTED_HEAD"
    test -z "$(git -C "$ROOT" status --porcelain)"

    test -d "$CHECKPOINT_WT"
    test "$(git -C "$CHECKPOINT_WT" branch --show-current)" = "$CHECKPOINT_BRANCH"

    git -C "$ROOT" fetch origin "$CHECKPOINT_BRANCH"
    local remote_before local_before
    remote_before="$(git -C "$ROOT" rev-parse "origin/$CHECKPOINT_BRANCH")"
    local_before="$(git -C "$CHECKPOINT_WT" rev-parse HEAD)"

    if test "$local_before" != "$remote_before"; then
        echo "[ERROR] checkpoint worktree is not synchronized with remote"
        echo "local_checkpoint_head=$local_before"
        echo "remote_checkpoint_head=$remote_before"
        return 51
    fi

    test -z "$(git -C "$CHECKPOINT_WT" status --porcelain)"

    local tmp archive chunks archive_sha archive_size manifest manifest_sha
    tmp="$(mktemp -d /workspaces/sa5_stage20_live_checkpoint_XXXXXXXX)"
    archive="$tmp/sa5_stage20_runtime_latest.tar.gz"
    chunks="$tmp/chunks"
    manifest="$tmp/checkpoint_manifest.json"
    mkdir -p "$chunks"

    find "$ROOT/$WORK" -type f -print0 |
        sort -z |
        xargs -0 sha256sum \
        > "$tmp/stage20_work_files.sha256"

    find "$ROOT/$OUT" -type f -print0 |
        sort -z |
        xargs -0 sha256sum \
        > "$tmp/stage20_precision_area_files.sha256"

    tar \
        -C "$ROOT" \
        -czf "$archive" \
        "$WORK" \
        "$OUT"

    archive_sha="$(sha_file "$archive")"
    archive_size="$(stat -c '%s' "$archive")"

    tar -tzf "$archive" > "$tmp/archive_file_list.txt"

    split \
        -b 20M \
        -d \
        -a 3 \
        "$archive" \
        "$chunks/sa5_stage20_runtime_latest.tar.gz.part"

    sha256sum "$chunks"/* > "$tmp/chunks.sha256"

    local sequence=1
    if git -C "$CHECKPOINT_WT" show "HEAD:$LIVE_DEST/checkpoint_manifest.json" \
        > "$tmp/previous_manifest.json" 2>/dev/null
    then
        sequence="$(
            "$PYTHON" - "$tmp/previous_manifest.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
print(int(p.get("checkpoint_sequence", 0)) + 1)
PY
        )"
    fi

    export AUTO_CP_MANIFEST="$manifest"
    export AUTO_CP_SEQUENCE="$sequence"
    export AUTO_CP_REASON="$reason"
    export AUTO_CP_COMPLETED_CSV="$completed_csv"
    export AUTO_CP_COMPLETED_COUNT="$completed_count"
    export AUTO_CP_LATEST_REP="$latest_rep"
    export AUTO_CP_ARCHIVE_SHA="$archive_sha"
    export AUTO_CP_ARCHIVE_SIZE="$archive_size"
    export AUTO_CP_CHUNKS="$chunks"
    export AUTO_CP_HEAD="$EXPECTED_HEAD"
    export AUTO_CP_BRANCH="$CHECKPOINT_BRANCH"
    export AUTO_CP_WORK="$WORK"
    export AUTO_CP_OUT="$OUT"

    "$PYTHON" - <<'PY'
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

manifest = Path(os.environ["AUTO_CP_MANIFEST"])
chunks = Path(os.environ["AUTO_CP_CHUNKS"])

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

csv = os.environ["AUTO_CP_COMPLETED_CSV"].strip()
completed = [] if not csv else [int(x) for x in csv.split(",")]
latest_raw = os.environ["AUTO_CP_LATEST_REP"].strip()
latest = None if latest_raw in {"", "none"} else int(latest_raw)

chunk_rows = [
    {
        "filename": p.name,
        "size_bytes": p.stat().st_size,
        "sha256": sha(p),
    }
    for p in sorted(chunks.iterdir())
    if p.is_file()
]

payload = {
    "schema_version": "mcad-sa5-objective-count-stage20-live-checkpoint-v1",
    "status": "stage20_live_checkpoint_verified_locally",
    "created_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "checkpoint_sequence": int(os.environ["AUTO_CP_SEQUENCE"]),
    "checkpoint_reason": os.environ["AUTO_CP_REASON"],
    "checkpoint_branch": os.environ["AUTO_CP_BRANCH"],
    "canonical_head": os.environ["AUTO_CP_HEAD"],
    "scientific_state": {
        "functional_replications_complete": list(range(10, 20)),
        "timing_replications_complete": completed,
        "timing_completed_count": int(os.environ["AUTO_CP_COMPLETED_COUNT"]),
        "latest_completed_timing_replication": latest,
        "precision_started": False,
        "precision_analysis_performed": False,
        "stage30_execution_authorized": False,
        "maximum_protocol_stage": 30,
    },
    "archive": {
        "sha256": os.environ["AUTO_CP_ARCHIVE_SHA"],
        "size_bytes": int(os.environ["AUTO_CP_ARCHIVE_SIZE"]),
        "chunk_count": len(chunk_rows),
        "chunks": chunk_rows,
    },
    "runtime_paths": {
        "stage20_work": os.environ["AUTO_CP_WORK"],
        "precision_area": os.environ["AUTO_CP_OUT"],
    },
    "resume_policy": {
        "reuse_completed_functional_replications": True,
        "reuse_completed_timing_replications": True,
        "quarantine_incomplete_timing_output_before_resume": True,
        "precision_must_not_be_rerun_after_precision_start_marker": True,
    },
}
manifest.write_text(
    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

    manifest_sha="$(sha_file "$manifest")"

    local dest="$CHECKPOINT_WT/$LIVE_DEST"
    rm -rf "$dest"
    mkdir -p "$dest/chunks"

    cp "$manifest" "$dest/checkpoint_manifest.json"
    cp "$tmp/archive_file_list.txt" "$dest/archive_file_list.txt"
    cp "$tmp/stage20_work_files.sha256" "$dest/stage20_work_files.sha256"
    cp "$tmp/stage20_precision_area_files.sha256" "$dest/stage20_precision_area_files.sha256"
    cp "$tmp/chunks.sha256" "$dest/chunks.sha256"
    cp "$CONTROLLER" "$dest/execute_sa5_stage20_once_v4_segmented.py"
    cp "$0" "$dest/run_sa5_stage20_timing_with_auto_checkpoint.sh"
    cp "$chunks"/* "$dest/chunks/"

    cat > "$dest/RESTORE.md" <<EOF
# SA5 objective_count Stage-20 live checkpoint

Checkpoint sequence: $sequence

Reason: $reason

Canonical commit:

\`\`\`
$EXPECTED_HEAD
\`\`\`

Completed Stage-20 timing replications:

\`\`\`
${completed_csv:-none}
\`\`\`

Archive SHA-256:

\`\`\`
$archive_sha
\`\`\`

Reconstruct with:

\`\`\`bash
cat chunks/sa5_stage20_runtime_latest.tar.gz.part* \\
  > /tmp/sa5_stage20_runtime_latest.tar.gz

echo "$archive_sha  /tmp/sa5_stage20_runtime_latest.tar.gz" \\
  | sha256sum -c -

tar -xzf /tmp/sa5_stage20_runtime_latest.tar.gz \\
  -C /workspaces/MCAD_improve3
\`\`\`

This is a recovery checkpoint. It is not the final scientific persistence/freeze.
EOF

    git -C "$CHECKPOINT_WT" add -f -- "$LIVE_DEST"
    git -C "$CHECKPOINT_WT" diff --cached --check

    if git -C "$CHECKPOINT_WT" diff --cached --quiet; then
        echo "[ERROR] checkpoint produced no Git delta"
        rm -rf "$tmp"
        return 52
    fi

    local rep_label
    if test "$latest_rep" = "none"; then
        rep_label="operational-state"
    else
        rep_label="$(printf 'rep-%03d' "$latest_rep")"
    fi

    git -C "$CHECKPOINT_WT" commit \
        -m "checkpoint(sa5): preserve Stage-20 ${rep_label}"

    local commit
    commit="$(git -C "$CHECKPOINT_WT" rev-parse HEAD)"

    git -C "$CHECKPOINT_WT" push origin "$CHECKPOINT_BRANCH"

    git -C "$ROOT" fetch origin "$CHECKPOINT_BRANCH"
    local remote_head
    remote_head="$(git -C "$ROOT" rev-parse "origin/$CHECKPOINT_BRANCH")"
    test "$remote_head" = "$commit"

    local remote_manifest_sha
    remote_manifest_sha="$(
        git -C "$ROOT" show \
            "origin/$CHECKPOINT_BRANCH:$LIVE_DEST/checkpoint_manifest.json" |
        sha256sum |
        awk '{print $1}'
    )"
    test "$remote_manifest_sha" = "$manifest_sha"

    local remote_archive="/tmp/sa5_stage20_remote_latest.tar.gz"
    rm -f "$remote_archive"

    local chunk_name
    while IFS= read -r chunk_name; do
        git -C "$ROOT" show \
            "origin/$CHECKPOINT_BRANCH:$LIVE_DEST/chunks/$chunk_name" \
            >> "$remote_archive"
    done < <(
        "$PYTHON" - "$manifest" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
for item in p["archive"]["chunks"]:
    print(item["filename"])
PY
    )

    local remote_archive_sha
    remote_archive_sha="$(sha_file "$remote_archive")"
    test "$remote_archive_sha" = "$archive_sha"
    tar -tzf "$remote_archive" >/dev/null

    echo "auto_checkpoint=PASS"
    echo "checkpoint_sequence=$sequence"
    echo "checkpoint_commit=$commit"
    echo "remote_checkpoint_head=$remote_head"
    echo "completed_timing_replications=${completed_csv:-none}"
    echo "archive_sha256=$archive_sha"
    echo "remote_archive_sha256=$remote_archive_sha"
    echo "canonical_branch_modified=false"

    rm -rf "$tmp"
}

echo "=== 1. Global Stage-20 auto-checkpoint gate ==="

cd "$ROOT"
git fetch origin --prune

test "$(git branch --show-current)" = "$BASE"
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test "$(git rev-parse "origin/$BASE")" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"

test -x "$PYTHON"
test -f "$CONTROLLER"
test "$(sha_file "$CONTROLLER")" = "$EXPECTED_CONTROLLER_SHA"

test -f "$START_MARKER"
test ! -e "$PRECISION_START"

ensure_no_science_processes

test -d "$CHECKPOINT_WT"
test "$(git -C "$CHECKPOINT_WT" branch --show-current)" = "$CHECKPOINT_BRANCH"
test -z "$(git -C "$CHECKPOINT_WT" status --porcelain)"

git fetch origin "$CHECKPOINT_BRANCH"
test "$(git -C "$CHECKPOINT_WT" rev-parse HEAD)" = \
     "$(git rev-parse "origin/$CHECKPOINT_BRANCH")"

echo "global_gate=PASS"
echo "checkpoint_branch=$CHECKPOINT_BRANCH"
echo "checkpoint_remote_head=$(git rev-parse "origin/$CHECKPOINT_BRANCH")"
echo "controller_sha256=$EXPECTED_CONTROLLER_SHA"
echo "precision_started=false"

echo
echo "=== 2. Automatic replication/checkpoint loop ==="

while true; do
    DONE_BEFORE="$(count_done)"
    COMPLETED_BEFORE="$(completed_rep_csv)"

    if test "$DONE_BEFORE" -eq 10; then
        echo "stage20_timing_suffix_complete=true"
        echo "completed_timing_replications=$COMPLETED_BEFORE"
        echo "precision_started=false"
        echo "next_stage=run_final_stage20_precision_from_fully_checkpointed_timing"
        break
    fi

    REP="$(first_pending_rep)"
    TOKEN="$(printf '%03d' "$REP")"

    echo
    echo "=== NEXT TIMING REPLICATION $TOKEN ==="
    echo "completed_before=${COMPLETED_BEFORE:-none}"

    LOG="$ROOT/$WORK/logs/timing_rep_${TOKEN}.log"
    if test -f "$LOG"; then
        echo "--- prior log tail for rep $TOKEN ---"
        tail -n 40 "$LOG" || true
        echo "--- end prior log tail ---"
    fi

    QUARANTINE_OCCURRED=0
    QUARANTINED_REP="none"
    quarantine_incomplete_output_if_needed "$REP"

    if test "$QUARANTINE_OCCURRED" -eq 1; then
        COMPLETED_PRE_RESUME="$(completed_rep_csv)"
        COUNT_PRE_RESUME="$(count_done)"
        LATEST_PRE_RESUME="none"
        if test "$COUNT_PRE_RESUME" -gt 0; then
            LATEST_PRE_RESUME="$(
                printf '%s\n' "$COMPLETED_PRE_RESUME" |
                awk -F, '{print $NF}'
            )"
        fi

        checkpoint_remote \
            "interrupted_rep_${TOKEN}_preserved_before_resume" \
            "$COMPLETED_PRE_RESUME" \
            "$COUNT_PRE_RESUME" \
            "$LATEST_PRE_RESUME"

        echo "interrupted_rep_${TOKEN}_remote_preservation=PASS"
        echo "new_science_after_remote_preservation=true"
    fi

    echo "timing_rep_${TOKEN}_automatic_segment=START"

    set +e
    SA5_STAGE20_SEGMENTED_TIMING=1 \
        "$PYTHON" "$CONTROLLER"
    RC=$?
    set -e

    echo "timing_rep_${TOKEN}_controller_exit_status=$RC"

    if test "$RC" -ne 0; then
        echo "[ERROR] segmented controller failed at rep $TOKEN"
        echo "[INFO] preserving post-failure runtime remotely before stopping"
        COMPLETED_NOW="$(completed_rep_csv)"
        COUNT_NOW="$(count_done)"
        LATEST="none"
        if test "$COUNT_NOW" -gt 0; then
            LATEST="$(
                printf '%s\n' "$COMPLETED_NOW" |
                awk -F, '{print $NF}'
            )"
        fi
        checkpoint_remote \
            "controller_failure_before_rep_${TOKEN}_completion" \
            "$COMPLETED_NOW" \
            "$COUNT_NOW" \
            "$LATEST"
        exit "$RC"
    fi

    DONE_AFTER="$(count_done)"
    COMPLETED_AFTER="$(completed_rep_csv)"

    test "$DONE_AFTER" -eq $((DONE_BEFORE + 1))
    test -f "$ROOT/$WORK/done/timing_rep_${TOKEN}.json"

    echo "timing_rep_${TOKEN}_validated_complete=true"
    echo "completed_after=$COMPLETED_AFTER"

    checkpoint_remote \
        "timing_rep_${TOKEN}_validated_complete" \
        "$COMPLETED_AFTER" \
        "$DONE_AFTER" \
        "$REP"

    echo "timing_rep_${TOKEN}_remote_persistence=PASS"
    echo "next_replication_authorized_only_after_remote_checkpoint=true"
done

echo
echo "=== FINAL ==="
echo "sa5_stage20_timing_auto_checkpoint_orchestrator=PASS"
echo "completed_timing_replications=$(completed_rep_csv)"
echo "completed_timing_replication_count=$(count_done)"
echo "stage20_precision_started=false"
echo "canonical_head=$(git rev-parse HEAD)"
echo "checkpoint_remote_head=$(git rev-parse "origin/$CHECKPOINT_BRANCH")"
echo "next_stage=final_stage20_precision_after_timing_checkpoint_complete"
