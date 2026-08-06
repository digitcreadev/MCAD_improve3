#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-setup}"

SOURCE_REPO="/workspaces/MCAD_improve3"
EXPECTED_SOURCE_BRANCH="paper/phase3-controlled-execution"
EXPECTED_SOURCE_HEAD="dec3785432366fb64b68123419ac31f640476313"

CHECKPOINT_BRANCH="evidence/sa5-objective-count-stage10-timing-checkpoints-20260806"
CHECKPOINT_WORKTREE="/workspaces/MCAD_improve3_sa5_checkpoint"
BACKUP_ROOT_REL="reproducibility_checkpoints/sa5_objective_count_stage10_timing"
BACKUP_ROOT="$CHECKPOINT_WORKTREE/$BACKUP_ROOT_REL"

E3_REL="reports/article_experiments/sensitivity/e3_controlled_execution"
OUTPUT_ROOT_REL="$E3_REL/timing_runs/objective_count_stage10_portfolio"
OUTPUT_ROOT="$SOURCE_REPO/$OUTPUT_ROOT_REL"

AMENDMENT_REL="$E3_REL/planning/sa5_objective_count_stage10_timing_contract_amendment.json"
AUTHORIZATION_REL="$E3_REL/planning/sa5_objective_count_stage10_timing_execution_authorization.json"
SETUP_ROOT_REL="$E3_REL/timing_setup/objective_count_stage10_portfolio"

RECOVERY_ROOT="/workspaces/sa5_objective_count_stage10_timing_execution_recovery_20260805T161701Z"
REBINDING_MANIFEST="$RECOVERY_ROOT/execution_path_rebinding_manifest.json"
ADAPTED_SPECS="$RECOVERY_ROOT/adapted_execution_specs"

POST_AMENDMENT_ROOT="/workspaces/sa5_objective_count_stage10_timing_after_amendment_dec3785_v2"
REUSE_PROVENANCE="$POST_AMENDMENT_ROOT/reused_execution_spec_provenance.json"
CAMPAIGN_STATE="$POST_AMENDMENT_ROOT/timing_campaign_execution_state.json"
RUNNER_LOG_ROOT="$POST_AMENDMENT_ROOT/logs"

PR39_ROOT="/workspaces/sa5_objective_count_stage10_timing_after_amendment_e01589e"
PR39_MERGE_AUDIT="$PR39_ROOT/pr39_merge_audit.json"

DIAGNOSTIC_ROOT="/workspaces/sa5_corrected_rebinding_mismatch_diagnostic_20260806T095439Z"
DIAGNOSTIC_REPORT="$DIAGNOSTIC_ROOT/sa5_corrected_rebinding_mismatch_diagnostic.json"

RUNNER_INTERFACE_ROOT="/workspaces/sa5_objective_count_timing_runner_interface_20260805T154913Z"
RUNNER_HELP="$RUNNER_INTERFACE_ROOT/run_timing_repetitions_help.txt"

CONTINUATION_SCRIPT="/workspaces/resume_sa5_replications_001_009_after_execution_schema_fix.sh"
THIS_SCRIPT="$(readlink -f "$0")"

WATCH_LOG="/workspaces/sa5_checkpoint_watcher.log"
WATCH_PID_FILE="/workspaces/sa5_checkpoint_watcher.pid"
WATCH_LOCK="/workspaces/sa5_checkpoint_watcher.lock"
POLL_SECONDS=60

VENV_PYTHON="/workspaces/.venvs/mcad-bridge-reconciliation-20260801T180758Z/bin/python"
PYTHON="$VENV_PYTHON"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

trap 'echo "[ERROR] SA5 checkpoint archiver stopped at line $LINENO." >&2' ERR

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

copy_if_present() {
  local source="$1"
  local destination="$2"

  if [ -f "$source" ]; then
    mkdir -p "$(dirname "$destination")"
    cp -f "$source" "$destination"
  fi
}

sync_tree_if_present() {
  local source="$1"
  local destination="$2"

  if [ -d "$source" ]; then
    rm -rf "$destination"
    mkdir -p "$destination"
    cp -a "$source/." "$destination/"
  fi
}

ensure_source_gate() {
  command -v git >/dev/null
  command -v flock >/dev/null
  command -v sha256sum >/dev/null
  command -v "$PYTHON" >/dev/null

  cd "$SOURCE_REPO"

  test "$(git branch --show-current)" = "$EXPECTED_SOURCE_BRANCH"
  test "$(git rev-parse HEAD)" = "$EXPECTED_SOURCE_HEAD"
  test -z "$(git status --porcelain)"

  git fetch origin --prune --tags
  test "$(git rev-parse "origin/$EXPECTED_SOURCE_BRANCH")" = "$EXPECTED_SOURCE_HEAD"

  local runner_count
  runner_count="$(
    {
      pgrep -f 'python.*[r]un_timing_repetitions' 2>/dev/null ||
      true
    } |
      wc -l
  )"

  test "$runner_count" -le 1

  echo "source_gate=PASS"
  echo "source_branch=$EXPECTED_SOURCE_BRANCH"
  echo "source_head=$EXPECTED_SOURCE_HEAD"
  echo "active_timing_runner_count=$runner_count"
  echo "source_repository_clean=true"
}

ensure_checkpoint_worktree() {
  cd "$SOURCE_REPO"

  if [ -e "$CHECKPOINT_WORKTREE/.git" ]; then
    test "$(git -C "$CHECKPOINT_WORKTREE" branch --show-current)" = "$CHECKPOINT_BRANCH"
  elif git show-ref --verify --quiet "refs/heads/$CHECKPOINT_BRANCH"; then
    git worktree add "$CHECKPOINT_WORKTREE" "$CHECKPOINT_BRANCH"
  else
    git worktree add \
      -b "$CHECKPOINT_BRANCH" \
      "$CHECKPOINT_WORKTREE" \
      "$EXPECTED_SOURCE_HEAD"
  fi

  test "$(git -C "$CHECKPOINT_WORKTREE" branch --show-current)" = "$CHECKPOINT_BRANCH"

  echo "checkpoint_worktree_gate=PASS"
  echo "checkpoint_branch=$CHECKPOINT_BRANCH"
  echo "checkpoint_worktree=$CHECKPOINT_WORKTREE"
}

write_static_checkpoint_surface() {
  mkdir -p \
    "$BACKUP_ROOT/repository" \
    "$BACKUP_ROOT/planning" \
    "$BACKUP_ROOT/control_plane" \
    "$BACKUP_ROOT/environment" \
    "$BACKUP_ROOT/orchestration" \
    "$BACKUP_ROOT/replications"

  printf '%s\n' "$EXPECTED_SOURCE_BRANCH" \
    > "$BACKUP_ROOT/repository/source_branch.txt"
  printf '%s\n' "$EXPECTED_SOURCE_HEAD" \
    > "$BACKUP_ROOT/repository/source_commit.txt"

  git -C "$SOURCE_REPO" rev-parse "$EXPECTED_SOURCE_HEAD^{tree}" \
    > "$BACKUP_ROOT/repository/source_tree.txt"

  git -C "$SOURCE_REPO" log \
    --oneline \
    --decorate \
    --graph \
    --max-count=80 \
    "$EXPECTED_SOURCE_HEAD" \
    > "$BACKUP_ROOT/repository/git_log.txt"

  git -C "$SOURCE_REPO" show \
    --stat \
    --summary \
    "$EXPECTED_SOURCE_HEAD" \
    > "$BACKUP_ROOT/repository/source_commit_summary.txt"

  copy_if_present \
    "$SOURCE_REPO/$AMENDMENT_REL" \
    "$BACKUP_ROOT/planning/sa5_objective_count_stage10_timing_contract_amendment.json"

  copy_if_present \
    "$SOURCE_REPO/$AUTHORIZATION_REL" \
    "$BACKUP_ROOT/planning/sa5_objective_count_stage10_timing_execution_authorization.json"

  sync_tree_if_present \
    "$SOURCE_REPO/$SETUP_ROOT_REL" \
    "$BACKUP_ROOT/planning/timing_setup"

  copy_if_present \
    "$REBINDING_MANIFEST" \
    "$BACKUP_ROOT/control_plane/execution_path_rebinding_manifest.json"

  sync_tree_if_present \
    "$ADAPTED_SPECS" \
    "$BACKUP_ROOT/control_plane/adapted_execution_specs"

  copy_if_present \
    "$REUSE_PROVENANCE" \
    "$BACKUP_ROOT/control_plane/reused_execution_spec_provenance.json"

  copy_if_present \
    "$CAMPAIGN_STATE" \
    "$BACKUP_ROOT/control_plane/timing_campaign_execution_state.json"

  copy_if_present \
    "$PR39_MERGE_AUDIT" \
    "$BACKUP_ROOT/control_plane/pr39_merge_audit.json"

  copy_if_present \
    "$DIAGNOSTIC_REPORT" \
    "$BACKUP_ROOT/control_plane/corrected_rebinding_mismatch_diagnostic.json"

  copy_if_present \
    "$RUNNER_HELP" \
    "$BACKUP_ROOT/control_plane/run_timing_repetitions_help.txt"

  copy_if_present \
    "$CONTINUATION_SCRIPT" \
    "$BACKUP_ROOT/orchestration/resume_sa5_replications_001_009_after_execution_schema_fix.sh"

  copy_if_present \
    "$THIS_SCRIPT" \
    "$BACKUP_ROOT/orchestration/checkpoint_archiver.sh"

  {
    date -u '+captured_at_utc=%Y-%m-%dT%H:%M:%SZ'
    uname -a
  } > "$BACKUP_ROOT/environment/platform.txt"

  {
    echo "python_executable=$PYTHON"
    "$PYTHON" --version
  } > "$BACKUP_ROOT/environment/python_version.txt" 2>&1

  "$PYTHON" -m pip freeze \
    > "$BACKUP_ROOT/environment/pip_freeze.txt" 2>&1 || true

  git --version \
    > "$BACKUP_ROOT/environment/git_version.txt"

  if command -v lscpu >/dev/null 2>&1; then
    lscpu > "$BACKUP_ROOT/environment/lscpu.txt"
  fi

  if command -v free >/dev/null 2>&1; then
    free -h > "$BACKUP_ROOT/environment/memory.txt"
  fi

  cat > "$BACKUP_ROOT/README.md" <<EOF
# SA5 objective-count Stage-10 timing checkpoints

This directory is a detached, repository-tracked persistence surface for the
SA5 objective-count Stage-10 timing campaign.

Source branch: \`$EXPECTED_SOURCE_BRANCH\`
Source commit: \`$EXPECTED_SOURCE_HEAD\`

## Scientific controls

- Replication files are copied only after structural validation.
- Validation reads structural CSV columns only:
  \`cell_id\`, \`phase\`, \`phase_round\`, and \`factor_level\`.
- Timing-value columns are not interpreted.
- Precision analysis, bootstrap analysis, and manuscript modification remain
  outside this checkpoint process.
- Each completed replication is committed and pushed separately on
  \`$CHECKPOINT_BRANCH\`.

## Recovery

A new clone can check out \`$CHECKPOINT_BRANCH\`. The repository history,
planning contract, execution specifications, detached control-plane metadata,
environment inventory, and every checkpointed replication will be available
under this directory.

The active scientific branch is deliberately not advanced while the timing
runner is operating. This avoids invalidating the exact-HEAD resume gate.
EOF

  (
    cd "$BACKUP_ROOT"
    find . \
      -type f \
      ! -path './replications/*' \
      ! -name 'STATIC_SHA256SUMS' \
      -print0 |
      sort -z |
      xargs -0 sha256sum \
      > STATIC_SHA256SUMS
  )

  echo "static_checkpoint_surface=PASS"
}

validate_replication() {
  local replication="$1"
  local source_dir="$2"
  local validation_output="$3"

  "$PYTHON" - \
    "$replication" \
    "$source_dir" \
    "$SOURCE_REPO/$AMENDMENT_REL" \
    "$validation_output" <<'PY'
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


replication = int(sys.argv[1])
source_dir = Path(sys.argv[2])
amendment_path = Path(sys.argv[3])
validation_output = Path(sys.argv[4])


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


expected_names = {
    "functional_references.json",
    "timing_manifest.json",
    "timing_observations.csv",
    "timing_summary.json",
}

if not source_dir.is_dir():
    raise SystemExit(2)

actual_names = {
    path.name
    for path in source_dir.iterdir()
    if path.is_file()
}

if actual_names != expected_names:
    raise SystemExit(3)

manifest_path = source_dir / "timing_manifest.json"
observations_path = source_dir / "timing_observations.csv"
summary_path = source_dir / "timing_summary.json"
references_path = source_dir / "functional_references.json"

manifest = load_json(manifest_path)
summary = load_json(summary_path)
references = load_json(references_path)

assert isinstance(manifest, dict)
assert isinstance(summary, dict)
assert isinstance(references, dict)

assert manifest["status"] == "success"
assert manifest["functional_mismatch_count"] == 0
assert manifest["configuration"]["warmups"] == 10
assert manifest["configuration"]["measurements"] == 100

outputs = manifest["outputs"]
declared = {
    outputs["timing_observations_csv"]:
        outputs["timing_observations_sha256"],
    outputs["functional_references_json"]:
        outputs["functional_references_sha256"],
    outputs["timing_summary_json"]:
        outputs["timing_summary_sha256"],
}

for name, expected_sha in declared.items():
    path = source_dir / name
    assert path.is_file()
    assert sha(path) == expected_sha

row_count = 0
phase_counts: Counter[str] = Counter()
factor_counts: Counter[str] = Counter()
cell_counts: Counter[str] = Counter()
cell_phase_counts: dict[str, Counter[str]] = defaultdict(Counter)
cell_phase_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)

with observations_path.open(
    "r",
    encoding="utf-8",
    newline="",
) as handle:
    reader = csv.DictReader(handle)

    required = {
        "cell_id",
        "phase",
        "phase_round",
        "factor_level",
    }
    assert required.issubset(set(reader.fieldnames or []))

    for row in reader:
        row_count += 1
        cell = row["cell_id"]
        phase = row["phase"]
        factor = row["factor_level"]
        phase_round = int(row["phase_round"])

        phase_counts[phase] += 1
        factor_counts[factor] += 1
        cell_counts[cell] += 1
        cell_phase_counts[cell][phase] += 1
        cell_phase_rounds[(cell, phase)].add(phase_round)

assert row_count == 21120
assert phase_counts == {
    "warmup": 1920,
    "measurement": 19200,
}
assert len(factor_counts) == 6
assert set(factor_counts.values()) == {3520}
assert len(cell_counts) == 192
assert set(cell_counts.values()) == {110}

for cell in cell_counts:
    assert cell_phase_counts[cell] == {
        "warmup": 10,
        "measurement": 100,
    }
    assert len(cell_phase_rounds[(cell, "warmup")]) == 10
    assert len(cell_phase_rounds[(cell, "measurement")]) == 100

order_balance = summary["order_balance"]
assert isinstance(order_balance, list)
assert len(order_balance) == 192
assert all(item["near_balance"] is True for item in order_balance)

computed_exact = all(
    item["exact_full_balance"] is True
    for item in order_balance
)
assert manifest["all_cells_exactly_balanced"] == computed_exact

if replication == 0:
    amendment = load_json(amendment_path)
    evidence = amendment["replication_000_evidence"]
    assert sha(manifest_path) == evidence["manifest_sha256"]
    assert sha(summary_path) == evidence["summary_sha256"]
    assert sha(observations_path) == evidence["observations_sha256"]

payload = {
    "schema_version":
        "mcad-sa5-replication-checkpoint-validation-v1",
    "status": "structural_validation_pass",
    "replication": replication,
    "validated_at_utc":
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source_directory": str(source_dir),
    "structural_contract": {
        "csv_rows": row_count,
        "unique_cells": len(cell_counts),
        "rows_per_factor": sorted(set(factor_counts.values()))[0],
        "warmup_rows": phase_counts["warmup"],
        "measurement_rows": phase_counts["measurement"],
        "functional_mismatch_count": 0,
        "order_near_balance_all_true": True,
    },
    "files": {
        path.name: {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(source_dir.iterdir())
        if path.is_file()
    },
    "scientific_controls": {
        "timing_value_columns_accessed": False,
        "timing_values_interpreted": False,
        "precision_analysis_performed": False,
        "bootstrap_analysis_performed": False,
        "manuscript_modified": False,
    },
}

validation_output.parent.mkdir(parents=True, exist_ok=True)
validation_output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n",
    encoding="utf-8",
)
PY
}

update_ledger() {
  export BACKUP_ROOT EXPECTED_SOURCE_BRANCH EXPECTED_SOURCE_HEAD CHECKPOINT_BRANCH

  "$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


backup_root = Path(os.environ["BACKUP_ROOT"])
replications_root = backup_root / "replications"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


entries = []

for index in range(10):
    rep_dir = replications_root / f"rep_{index:03d}"
    validation_path = rep_dir / "VALIDATION.json"

    if validation_path.is_file():
        validation = load_json(validation_path)
        entries.append({
            "replication": index,
            "status": "checkpointed",
            "directory":
                rep_dir.relative_to(backup_root).as_posix(),
            "validation":
                validation_path.relative_to(backup_root).as_posix(),
            "validated_at_utc":
                validation["validated_at_utc"],
            "files": validation["files"],
        })
    else:
        entries.append({
            "replication": index,
            "status": "pending",
        })

completed = sum(
    entry["status"] == "checkpointed"
    for entry in entries
)

payload = {
    "schema_version": "mcad-sa5-checkpoint-ledger-v1",
    "updated_at_utc":
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source_branch": os.environ["EXPECTED_SOURCE_BRANCH"],
    "source_commit": os.environ["EXPECTED_SOURCE_HEAD"],
    "checkpoint_branch": os.environ["CHECKPOINT_BRANCH"],
    "completed_replication_count": completed,
    "expected_replication_count": 10,
    "status": (
        "complete"
        if completed == 10
        else "in_progress"
    ),
    "replications": entries,
    "scientific_controls": {
        "timing_values_interpreted": False,
        "precision_analysis_performed": False,
        "bootstrap_analysis_performed": False,
        "manuscript_modified": False,
    },
}

ledger_path = backup_root / "CHECKPOINT_LEDGER.json"
ledger_path.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n",
    encoding="utf-8",
)

status_lines = [
    "# SA5 timing checkpoint status",
    "",
    f"Source commit: `{payload['source_commit']}`",
    f"Checkpoint branch: `{payload['checkpoint_branch']}`",
    f"Completed replications: **{completed}/10**",
    "",
    "| Replication | Status |",
    "|---:|:---|",
]

for entry in entries:
    status_lines.append(
        f"| {entry['replication']:03d} | {entry['status']} |"
    )

status_lines.extend([
    "",
    "Timing values have not been interpreted by this checkpoint process.",
    "",
])

(backup_root / "CHECKPOINT_STATUS.md").write_text(
    "\n".join(status_lines),
    encoding="utf-8",
)

print(f"completed_replication_count={completed}")
PY
}

commit_checkpoint_changes() {
  local message="$1"

  git -C "$CHECKPOINT_WORKTREE" add "$BACKUP_ROOT_REL"

  if git -C "$CHECKPOINT_WORKTREE" diff --cached --quiet; then
    echo "checkpoint_commit=NO_CHANGES"
    return 0
  fi

  git -C "$CHECKPOINT_WORKTREE" commit -m "$message"
  git -C "$CHECKPOINT_WORKTREE" push -u origin "$CHECKPOINT_BRANCH"

  if git -C "$CHECKPOINT_WORKTREE" remote get-url rescue >/dev/null 2>&1; then
    git -C "$CHECKPOINT_WORKTREE" push -u rescue "$CHECKPOINT_BRANCH"
    echo "rescue_remote_push=PASS"
  else
    echo "rescue_remote_push=SKIPPED_REMOTE_NOT_CONFIGURED"
  fi

  echo "checkpoint_commit=PASS"
  echo "checkpoint_head=$(git -C "$CHECKPOINT_WORKTREE" rev-parse HEAD)"
}

checkpoint_replication() {
  local index="$1"
  local rep
  rep="$(printf '%03d' "$index")"

  local source_dir="$OUTPUT_ROOT/objective_count_rep_${rep}_portfolio_timing_stage10"
  local destination_dir="$BACKUP_ROOT/replications/rep_${rep}"
  local temp_dir="$BACKUP_ROOT/replications/.rep_${rep}.tmp.$$"
  local validation_temp="/tmp/sa5_rep_${rep}_checkpoint_validation_$$.json"

  if [ -f "$destination_dir/VALIDATION.json" ]; then
    return 0
  fi

  if [ ! -d "$source_dir" ]; then
    return 0
  fi

  set +e
  validate_replication \
    "$index" \
    "$source_dir" \
    "$validation_temp"
  local validation_status=$?
  set -e

  if [ "$validation_status" -ne 0 ]; then
    rm -f "$validation_temp"
    echo "replication_${rep}_checkpoint_state=NOT_YET_STRUCTURALLY_COMPLETE"
    return 0
  fi

  rm -rf "$temp_dir"
  mkdir -p "$temp_dir"

  cp -f \
    "$source_dir/functional_references.json" \
    "$source_dir/timing_manifest.json" \
    "$source_dir/timing_observations.csv" \
    "$source_dir/timing_summary.json" \
    "$temp_dir/"

  mv "$validation_temp" "$temp_dir/VALIDATION.json"

  if [ -f "$RUNNER_LOG_ROOT/rep_${rep}.log" ]; then
    cp -f \
      "$RUNNER_LOG_ROOT/rep_${rep}.log" \
      "$temp_dir/runner.log"
  fi

  (
    cd "$temp_dir"
    find . \
      -maxdepth 1 \
      -type f \
      ! -name 'SHA256SUMS' \
      -print0 |
      sort -z |
      xargs -0 sha256sum \
      > SHA256SUMS
  )

  mv "$temp_dir" "$destination_dir"

  copy_if_present \
    "$CAMPAIGN_STATE" \
    "$BACKUP_ROOT/control_plane/timing_campaign_execution_state.json"

  copy_if_present \
    "$REUSE_PROVENANCE" \
    "$BACKUP_ROOT/control_plane/reused_execution_spec_provenance.json"

  update_ledger

  commit_checkpoint_changes \
    "evidence(timing): checkpoint SA5 replication ${rep}"

  echo "replication_${rep}_checkpoint=PASS"
}

watch_loop() {
  exec 9>"$WATCH_LOCK"

  if ! flock -n 9; then
    echo "[ERROR] Another SA5 checkpoint watcher is already active." >&2
    exit 1
  fi

  echo "$$" > "$WATCH_PID_FILE"

  trap 'rm -f "$WATCH_PID_FILE"' EXIT

  ensure_source_gate
  ensure_checkpoint_worktree
  write_static_checkpoint_surface
  update_ledger
  commit_checkpoint_changes \
    "chore(reproducibility): initialize SA5 timing checkpoint surface"

  echo "checkpoint_watcher=STARTED"
  echo "watcher_pid=$$"
  echo "watch_log=$WATCH_LOG"
  echo "checkpoint_branch=$CHECKPOINT_BRANCH"

  while true; do
    for index in $(seq 0 9); do
      checkpoint_replication "$index"
    done

    completed="$(
      "$PYTHON" - "$BACKUP_ROOT/CHECKPOINT_LEDGER.json" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text())
print(value["completed_replication_count"])
PY
    )"

    echo "checkpoint_poll_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "checkpoint_completed_replication_count=$completed"

    if [ "$completed" -eq 10 ]; then
      copy_if_present \
        "$CAMPAIGN_STATE" \
        "$BACKUP_ROOT/control_plane/timing_campaign_execution_state.json"

      update_ledger
      commit_checkpoint_changes \
        "evidence(timing): complete SA5 ten-replication checkpoint"

      echo "checkpoint_campaign=COMPLETE"
      echo "checkpoint_branch=$CHECKPOINT_BRANCH"
      echo "checkpoint_head=$(git -C "$CHECKPOINT_WORKTREE" rev-parse HEAD)"
      break
    fi

    sleep "$POLL_SECONDS"
  done
}

setup_mode() {
  echo "=== 1. Source and parallel-execution gate ==="
  ensure_source_gate

  echo
  echo "=== 2. Create or reuse detached checkpoint worktree ==="
  ensure_checkpoint_worktree

  echo
  echo "=== 3. Materialize static reproducibility surface ==="
  write_static_checkpoint_surface
  update_ledger
  commit_checkpoint_changes \
    "chore(reproducibility): initialize SA5 timing checkpoint surface"

  echo
  echo "=== 4. Start or reuse checkpoint watcher ==="

  if [ -f "$WATCH_PID_FILE" ]; then
    existing_pid="$(cat "$WATCH_PID_FILE" 2>/dev/null || true)"

    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
      echo "checkpoint_watcher=ALREADY_ACTIVE"
      echo "watcher_pid=$existing_pid"
      echo "watch_log=$WATCH_LOG"
      return 0
    fi
  fi

  nohup \
    env -u BASH_ENV \
    bash \
    --noprofile \
    --norc \
    "$THIS_SCRIPT" \
    --watch \
    >> "$WATCH_LOG" 2>&1 &

  watcher_pid=$!
  echo "$watcher_pid" > "$WATCH_PID_FILE"

  sleep 2

  if kill -0 "$watcher_pid" 2>/dev/null; then
    echo "checkpoint_watcher=STARTED"
    echo "watcher_pid=$watcher_pid"
    echo "watch_log=$WATCH_LOG"
    echo "checkpoint_branch=$CHECKPOINT_BRANCH"
    echo "checkpoint_worktree=$CHECKPOINT_WORKTREE"
    echo "backup_root=$BACKUP_ROOT"
  else
    echo "[ERROR] Checkpoint watcher did not remain active." >&2
    tail -n 120 "$WATCH_LOG" || true
    exit 1
  fi

  echo
  echo "=== 5. Current checkpoint status ==="
  cat "$BACKUP_ROOT/CHECKPOINT_STATUS.md"

  echo
  echo "=== 6. Current source repository state ==="
  git -C "$SOURCE_REPO" status --short --branch
  echo "source_head_unchanged=$(git -C "$SOURCE_REPO" rev-parse HEAD)"
}

case "$MODE" in
  setup)
    setup_mode
    ;;
  --watch)
    watch_loop
    ;;
  --status)
    echo "checkpoint_branch=$CHECKPOINT_BRANCH"
    echo "checkpoint_worktree=$CHECKPOINT_WORKTREE"
    echo "backup_root=$BACKUP_ROOT"

    if [ -f "$WATCH_PID_FILE" ]; then
      watcher_pid="$(cat "$WATCH_PID_FILE" 2>/dev/null || true)"
      echo "watcher_pid=$watcher_pid"

      if [ -n "$watcher_pid" ] && kill -0 "$watcher_pid" 2>/dev/null; then
        echo "watcher_active=true"
      else
        echo "watcher_active=false"
      fi
    else
      echo "watcher_active=false"
    fi

    if [ -f "$BACKUP_ROOT/CHECKPOINT_LEDGER.json" ]; then
      cat "$BACKUP_ROOT/CHECKPOINT_STATUS.md"
    fi

    tail -n 80 "$WATCH_LOG" 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 [setup|--watch|--status]" >&2
    exit 2
    ;;
esac
