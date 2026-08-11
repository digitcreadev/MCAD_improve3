#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/MCAD_improve3"
BASE="paper/phase3-controlled-execution"
EXPECTED_HEAD="ff89d89339e1d5fa4fdffd1ee95d16037550bbec"

PYTHON="/workspaces/.venvs/mcad-bridge-reconciliation-20260801T180758Z/bin/python"
CONTROLLER="/workspaces/execute_sa5_stage30_timing_segmented_v1.py"
CONFIG="/workspaces/sa5_stage30_checkpoint.env"

E3="reports/article_experiments/sensitivity/e3_controlled_execution"
WORK="$E3/stage30_work/objective_count_stage30_ff89d89"
OUT="$E3/audits/objective_count/timing_stage30/precision_analysis"

PRECISION_START="$OUT/SA5_STAGE30_PRECISION_STARTED.json"

LIVE_DEST="reproducibility_checkpoints/sa5_objective_count_stage30_live"

LOCK="/workspaces/sa5_stage30_auto_checkpoint.lock"

test -f "$CONFIG"
# shellcheck source=/dev/null
source "$CONFIG"

exec 9>"$LOCK"

if ! flock -n 9; then
    echo "[ERROR] another Stage-30 orchestrator holds $LOCK"
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

    for rep in $(seq 20 29); do
        token="$(printf '%03d' "$rep")"

        if test -f \
            "$ROOT/$WORK/done/timing_rep_${token}.json"
        then
            n=$((n + 1))
        fi
    done

    printf '%s\n' "$n"
}

completed_rep_csv() {
    local out=""
    local rep token

    for rep in $(seq 20 29); do
        token="$(printf '%03d' "$rep")"

        if test -f \
            "$ROOT/$WORK/done/timing_rep_${token}.json"
        then
            if test -n "$out"; then
                out="${out},"
            fi

            out="${out}${rep}"
        fi
    done

    printf '%s\n' "$out"
}

first_pending_rep() {
    local rep token

    for rep in $(seq 20 29); do
        token="$(printf '%03d' "$rep")"

        if ! test -f \
            "$ROOT/$WORK/done/timing_rep_${token}.json"
        then
            printf '%s\n' "$rep"
            return 0
        fi
    done

    return 1
}

ensure_no_science_processes() {
    local timing precision

    timing="$(
        pgrep -af \
            'python.*[r]un_timing_repetitions' \
        || true
    )"

    precision="$(
        pgrep -af \
            'python.*[a]nalyze_clustered_timing_precision' \
        || true
    )"

    if test -n "$timing" || test -n "$precision"; then
        echo "[ERROR] checkpoint requested while science is active"
        echo "timing=${timing:-none}"
        echo "precision=${precision:-none}"
        return 1
    fi
}

quarantine_incomplete_output_if_needed() {
    local rep="$1"

    local token
    local output_dir
    local done_marker
    local complete
    local rows
    local stamp
    local target

    token="$(printf '%03d' "$rep")"

    output_dir="$ROOT/$WORK/timing_runs/objective_count_rep_${token}_portfolio_timing_stage30"
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
            awk \
                'END {print NR > 0 ? NR - 1 : 0}' \
                "$output_dir/timing_observations.csv"
        )"

        if test "$rows" -eq 21120; then
            echo "[ERROR] rep $token appears complete but lacks done marker"
            echo "[ERROR] refusing automatic rerun"
            return 41
        fi
    fi

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"

    target="$ROOT/$WORK/interrupted/rep_${token}_incomplete_${stamp}"

    mkdir -p "$(dirname "$target")"

    echo "quarantine_replication=$token"
    echo "quarantine_source=$output_dir"
    echo "quarantine_target=$target"

    mv "$output_dir" "$target"

    {
        echo "schema=mcad-sa5-stage30-interrupted-timing-v1"
        echo "captured_at_utc=$(utcnow)"
        echo "replication=$rep"
        echo "canonical_head=$EXPECTED_HEAD"
        echo "reason=incomplete_output_without_done_marker_before_resume"
    } > "${target}.provenance.txt"

    export QUARANTINE_OCCURRED=1
}

checkpoint_remote() {
    local reason="$1"
    local completed_csv="$2"
    local completed_count="$3"
    local latest_rep="$4"

    ensure_no_science_processes

    test -d "$ROOT/$WORK"

    echo
    echo "=== AUTO CHECKPOINT: $reason ==="

    git -C "$ROOT" fetch origin --prune

    test "$(
        git -C "$ROOT" branch --show-current
    )" = "$BASE"

    test "$(
        git -C "$ROOT" rev-parse HEAD
    )" = "$EXPECTED_HEAD"

    test "$(
        git -C "$ROOT" rev-parse "origin/$BASE"
    )" = "$EXPECTED_HEAD"

    test -z "$(
        git -C "$ROOT" status --porcelain
    )"

    test -d "$CHECKPOINT_WT"

    test "$(
        git -C "$CHECKPOINT_WT" branch --show-current
    )" = "$CHECKPOINT_BRANCH"

    git -C "$ROOT" \
        fetch origin "$CHECKPOINT_BRANCH"

    local remote_before
    local local_before

    remote_before="$(
        git -C "$ROOT" \
            rev-parse "origin/$CHECKPOINT_BRANCH"
    )"

    local_before="$(
        git -C "$CHECKPOINT_WT" rev-parse HEAD
    )"

    test "$local_before" = "$remote_before"

    test -z "$(
        git -C "$CHECKPOINT_WT" status --porcelain
    )"

    local tmp
    local archive
    local chunks
    local manifest
    local archive_sha
    local archive_size
    local manifest_sha
    local sequence

    tmp="$(
        mktemp -d \
            /workspaces/sa5_stage30_live_checkpoint_XXXXXXXX
    )"

    archive="$tmp/sa5_stage30_runtime_latest.tar.gz"
    chunks="$tmp/chunks"
    manifest="$tmp/checkpoint_manifest.json"

    mkdir -p "$chunks"

    find "$ROOT/$WORK" \
        -type f \
        -print0 |
    sort -z |
    xargs -0 -r sha256sum \
        > "$tmp/stage30_work_files.sha256"

    : > "$tmp/stage30_precision_area_files.sha256"

    if test -d "$ROOT/$OUT"; then
        find "$ROOT/$OUT" \
            -type f \
            -print0 |
        sort -z |
        xargs -0 -r sha256sum \
            > "$tmp/stage30_precision_area_files.sha256"
    fi

    TAR_INPUTS=("$WORK")

    if test -e "$ROOT/$OUT"; then
        TAR_INPUTS+=("$OUT")
    fi

    tar \
        -C "$ROOT" \
        -czf "$archive" \
        "${TAR_INPUTS[@]}"

    archive_sha="$(sha_file "$archive")"
    archive_size="$(stat -c '%s' "$archive")"

    tar -tzf "$archive" \
        > "$tmp/archive_file_list.txt"

    split \
        -b 20M \
        -d \
        -a 3 \
        "$archive" \
        "$chunks/sa5_stage30_runtime_latest.tar.gz.part"

    sha256sum "$chunks"/* \
        > "$tmp/chunks.sha256"

    sequence=1

    if git -C "$CHECKPOINT_WT" \
        show \
        "HEAD:$LIVE_DEST/checkpoint_manifest.json" \
        > "$tmp/previous_manifest.json" \
        2>/dev/null
    then
        sequence="$(
            "$PYTHON" \
                - "$tmp/previous_manifest.json" <<'PY'
import json
import sys

data = json.load(
    open(
        sys.argv[1],
        encoding="utf-8",
    )
)

print(
    int(
        data.get(
            "checkpoint_sequence",
            0,
        )
    )
    + 1
)
PY
        )"
    fi

    export CP_MANIFEST="$manifest"
    export CP_SEQUENCE="$sequence"
    export CP_REASON="$reason"
    export CP_COMPLETED_CSV="$completed_csv"
    export CP_COMPLETED_COUNT="$completed_count"
    export CP_LATEST_REP="$latest_rep"
    export CP_ARCHIVE_SHA="$archive_sha"
    export CP_ARCHIVE_SIZE="$archive_size"
    export CP_CHUNKS="$chunks"
    export CP_HEAD="$EXPECTED_HEAD"
    export CP_BRANCH="$CHECKPOINT_BRANCH"
    export CP_CONTROLLER_SHA="$CONTROLLER_SHA"

    "$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

manifest = Path(os.environ["CP_MANIFEST"])
chunks = Path(os.environ["CP_CHUNKS"])

def sha(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()

csv = os.environ["CP_COMPLETED_CSV"].strip()

completed = (
    []
    if not csv
    else [
        int(x)
        for x in csv.split(",")
    ]
)

latest_raw = os.environ["CP_LATEST_REP"].strip()

latest = (
    None
    if latest_raw in {"", "none"}
    else int(latest_raw)
)

chunk_rows = [
    {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    for path in sorted(chunks.iterdir())
    if path.is_file()
]

payload = {
    "schema_version":
        "mcad-sa5-objective-count-stage30-live-checkpoint-v1",

    "status":
        "stage30_live_checkpoint_verified_locally",

    "created_at_utc":
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),

    "checkpoint_sequence":
        int(os.environ["CP_SEQUENCE"]),

    "checkpoint_reason":
        os.environ["CP_REASON"],

    "checkpoint_branch":
        os.environ["CP_BRANCH"],

    "canonical_head":
        os.environ["CP_HEAD"],

    "controller_sha256":
        os.environ["CP_CONTROLLER_SHA"],

    "operator_confirmation_received":
        True,

    "scientific_state": {
        "stage20_prefix_replications_reused":
            list(range(20)),

        "stage30_timing_replications_complete":
            completed,

        "stage30_timing_completed_count":
            int(os.environ["CP_COMPLETED_COUNT"]),

        "latest_completed_stage30_timing_replication":
            latest,

        "stage30_precision_started":
            False,

        "stage30_precision_analysis_performed":
            False,

        "maximum_protocol_stage":
            30,

        "stage_beyond_30_authorized":
            False,
    },

    "archive": {
        "sha256":
            os.environ["CP_ARCHIVE_SHA"],

        "size_bytes":
            int(os.environ["CP_ARCHIVE_SIZE"]),

        "chunk_count":
            len(chunk_rows),

        "chunks":
            chunk_rows,
    },

    "resume_policy": {
        "reuse_completed_functional_replications":
            True,

        "reuse_completed_timing_replications":
            True,

        "quarantine_incomplete_timing_output_before_resume":
            True,

        "precision_must_not_start_until_all_10_suffix_timings_are_remotely_checkpointed":
            True,
    },
}

manifest.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)
PY

    manifest_sha="$(sha_file "$manifest")"

    local dest="$CHECKPOINT_WT/$LIVE_DEST"

    rm -rf "$dest"
    mkdir -p "$dest/chunks"

    cp "$manifest" \
        "$dest/checkpoint_manifest.json"

    cp "$tmp/archive_file_list.txt" \
        "$dest/archive_file_list.txt"

    cp "$tmp/stage30_work_files.sha256" \
        "$dest/stage30_work_files.sha256"

    cp "$tmp/stage30_precision_area_files.sha256" \
        "$dest/stage30_precision_area_files.sha256"

    cp "$tmp/chunks.sha256" \
        "$dest/chunks.sha256"

    cp "$CONTROLLER" \
        "$dest/execute_sa5_stage30_timing_segmented_v1.py"

    cp "$0" \
        "$dest/run_sa5_stage30_timing_with_auto_checkpoint_v1.sh"

    cp "$chunks"/* \
        "$dest/chunks/"

    git -C "$CHECKPOINT_WT" \
        add -f -- "$LIVE_DEST"

    git -C "$CHECKPOINT_WT" \
        diff --cached --check

    if git -C "$CHECKPOINT_WT" \
        diff --cached --quiet
    then
        echo "checkpoint_no_git_delta=true"
        rm -rf "$tmp"
        return 0
    fi

    local rep_label

    if test "$latest_rep" = "none"; then
        rep_label="operational-state"
    else
        rep_label="$(
            printf 'rep-%03d' "$latest_rep"
        )"
    fi

    git -C "$CHECKPOINT_WT" \
        commit \
        -m "checkpoint(sa5): preserve Stage-30 ${rep_label}"

    local commit

    commit="$(
        git -C "$CHECKPOINT_WT" rev-parse HEAD
    )"

    git -C "$CHECKPOINT_WT" \
        push origin "$CHECKPOINT_BRANCH"

    git -C "$ROOT" \
        fetch origin "$CHECKPOINT_BRANCH"

    local remote_head

    remote_head="$(
        git -C "$ROOT" \
            rev-parse "origin/$CHECKPOINT_BRANCH"
    )"

    test "$remote_head" = "$commit"

    local remote_manifest_sha

    remote_manifest_sha="$(
        git -C "$ROOT" \
            show \
            "origin/$CHECKPOINT_BRANCH:$LIVE_DEST/checkpoint_manifest.json" |
        sha256sum |
        awk '{print $1}'
    )"

    test "$remote_manifest_sha" = "$manifest_sha"

    local remote_archive

    remote_archive="/tmp/sa5_stage30_remote_latest.tar.gz"

    rm -f "$remote_archive"

    local chunk_name

    while IFS= read -r chunk_name; do

        git -C "$ROOT" \
            show \
            "origin/$CHECKPOINT_BRANCH:$LIVE_DEST/chunks/$chunk_name" \
            >> "$remote_archive"

    done < <(
        "$PYTHON" \
            - "$manifest" <<'PY'
import json
import sys

data = json.load(
    open(
        sys.argv[1],
        encoding="utf-8",
    )
)

for item in data["archive"]["chunks"]:
    print(item["filename"])
PY
    )

    local remote_archive_sha

    remote_archive_sha="$(
        sha_file "$remote_archive"
    )"

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

echo "=== 1. Global Stage-30 auto-checkpoint gate ==="

cd "$ROOT"

git fetch origin --prune

test "$(git branch --show-current)" = "$BASE"

test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"

test "$(
    git rev-parse "origin/$BASE"
)" = "$EXPECTED_HEAD"

test -z "$(git status --porcelain)"

test -x "$PYTHON"
test -f "$CONTROLLER"

ACTUAL_CONTROLLER_SHA="$(
    sha_file "$CONTROLLER"
)"

echo "controller_sha256=$ACTUAL_CONTROLLER_SHA"

test "$ACTUAL_CONTROLLER_SHA" = "$CONTROLLER_SHA"

test ! -e "$ROOT/$PRECISION_START"

ensure_no_science_processes

test -d "$CHECKPOINT_WT"

test "$(
    git -C "$CHECKPOINT_WT" branch --show-current
)" = "$CHECKPOINT_BRANCH"

test -z "$(
    git -C "$CHECKPOINT_WT" status --porcelain
)"

git fetch origin "$CHECKPOINT_BRANCH"

test "$(
    git -C "$CHECKPOINT_WT" rev-parse HEAD
)" = "$(
    git rev-parse "origin/$CHECKPOINT_BRANCH"
)"

echo "global_gate=PASS"
echo "checkpoint_branch=$CHECKPOINT_BRANCH"
echo "checkpoint_remote_head=$(
    git rev-parse "origin/$CHECKPOINT_BRANCH"
)"
echo "precision_started=false"

echo
echo "=== 2. Automatic Stage-30 replication/checkpoint loop ==="

while true; do

    DONE_BEFORE="$(count_done)"
    COMPLETED_BEFORE="$(completed_rep_csv)"

    if test "$DONE_BEFORE" -eq 10; then

        echo "stage30_timing_suffix_complete=true"
        echo "completed_timing_replications=$COMPLETED_BEFORE"
        echo "precision_started=false"

        echo \
"next_stage=final_stage30_precision_from_fully_checkpointed_timing"

        break
    fi

    REP="$(first_pending_rep)"
    TOKEN="$(printf '%03d' "$REP")"

    echo
    echo "=== NEXT STAGE-30 TIMING REPLICATION $TOKEN ==="
    echo "completed_before=${COMPLETED_BEFORE:-none}"

    LOG="$ROOT/$WORK/logs/timing_rep_${TOKEN}.log"

    if test -f "$LOG"; then
        echo "--- prior log tail rep $TOKEN ---"
        tail -n 40 "$LOG" || true
        echo "--- end prior log tail ---"
    fi

    QUARANTINE_OCCURRED=0
    export QUARANTINE_OCCURRED

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

        echo \
"interrupted_rep_${TOKEN}_remote_preservation=PASS"
    fi

    echo "timing_rep_${TOKEN}_automatic_segment=START"

    set +e

    SA5_STAGE30_SEGMENTED_TIMING=1 \
        "$PYTHON" "$CONTROLLER"

    RC=$?

    set -e

    echo \
"timing_rep_${TOKEN}_controller_exit_status=$RC"

    if test "$RC" -ne 0; then

        echo \
"[ERROR] segmented Stage-30 controller stopped at rep $TOKEN"

        ensure_no_science_processes || true

        if test -d "$ROOT/$WORK"; then

            COMPLETED_NOW="$(completed_rep_csv)"
            COUNT_NOW="$(count_done)"

            LATEST_NOW="none"

            if test "$COUNT_NOW" -gt 0; then
                LATEST_NOW="$(
                    printf '%s\n' "$COMPLETED_NOW" |
                    awk -F, '{print $NF}'
                )"
            fi

            checkpoint_remote \
                "controller_failure_before_rep_${TOKEN}_completion" \
                "$COMPLETED_NOW" \
                "$COUNT_NOW" \
                "$LATEST_NOW"
        fi

        exit "$RC"
    fi

    DONE_AFTER="$(count_done)"
    COMPLETED_AFTER="$(completed_rep_csv)"

    test "$DONE_AFTER" -eq $((DONE_BEFORE + 1))

    test -f \
        "$ROOT/$WORK/done/timing_rep_${TOKEN}.json"

    echo \
"timing_rep_${TOKEN}_validated_complete=true"

    echo "completed_after=$COMPLETED_AFTER"

    checkpoint_remote \
        "timing_rep_${TOKEN}_validated_complete" \
        "$COMPLETED_AFTER" \
        "$DONE_AFTER" \
        "$REP"

    echo \
"timing_rep_${TOKEN}_remote_persistence=PASS"

    echo \
"next_replication_authorized_only_after_remote_checkpoint=true"
done

echo
echo "=== FINAL STAGE-30 TIMING STATE ==="

echo \
"sa5_stage30_timing_auto_checkpoint_orchestrator=PASS"

echo \
"completed_timing_replications=$(completed_rep_csv)"

echo \
"completed_timing_replication_count=$(count_done)"

echo "stage30_precision_started=false"

echo \
"stage30_precision_analysis_performed=false"

echo "maximum_protocol_stage=30"
echo "stage_beyond_30_authorized=false"

echo \
"canonical_head=$(git rev-parse HEAD)"

echo \
"checkpoint_remote_head=$(git rev-parse "origin/$CHECKPOINT_BRANCH")"

echo \
"next_stage=final_stage30_precision_after_timing_checkpoint_complete"
