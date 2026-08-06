#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/MCAD_improve3"
BASE="paper/phase3-controlled-execution"
EXPECTED_HEAD="dec3785432366fb64b68123419ac31f640476313"
OLD_BASE_HEAD="26c781aa7a60fdc392a42eca53709731283ae438"

E3="reports/article_experiments/sensitivity/e3_controlled_execution"
SPECS_REL="$E3/timing_setup/objective_count_stage10_portfolio/specs"
AMENDMENT_REL="$E3/planning/sa5_objective_count_stage10_timing_contract_amendment.json"
OUTPUT_ROOT_REL="$E3/timing_runs/objective_count_stage10_portfolio"

OLD_RECOVERY="/workspaces/sa5_objective_count_stage10_timing_execution_recovery_20260805T161701Z"
OLD_ADAPTED_DIR="$OLD_RECOVERY/adapted_execution_specs"
OLD_REBINDING_MANIFEST="$OLD_RECOVERY/execution_path_rebinding_manifest.json"
EXPECTED_OLD_REBINDING_MANIFEST_SHA="f81fe8a44ab037a429dd8ca7af853c2931a9d462348e4b78a4bbe091f76e5eaf"

DIAGNOSTIC_REPORT="/workspaces/sa5_corrected_rebinding_mismatch_diagnostic_20260806T095439Z/sa5_corrected_rebinding_mismatch_diagnostic.json"
EXPECTED_DIAGNOSTIC_REPORT_SHA="762d8c08f90015962cd52d71cbd67fbc7101f02eddba4492dee67315d251508f"

RESUME_ROOT="/workspaces/sa5_objective_count_stage10_timing_after_amendment_dec3785_v2"
ADAPTED_DIR="$RESUME_ROOT/reused_execution_specs"
LOG_DIR="$RESUME_ROOT/logs"
QUARANTINE_DIR="$RESUME_ROOT/quarantine"
ARCHIVE_DIR="$RESUME_ROOT/validated_replication_archives"
EXECUTION_SPEC_AUDIT="$RESUME_ROOT/reused_execution_spec_provenance.json"
CAMPAIGN_STATE="$RESUME_ROOT/timing_campaign_execution_state.json"

VENV="/workspaces/.venvs/mcad-bridge-reconciliation-20260801T180758Z/bin/python"
PYTHON="$VENV"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

RUNNER_MODULE="backend.harness.sensitivity_execution.run_timing_repetitions"
WARMUPS=10
MEASUREMENTS=100
ORDER_SEED=20260728
EXPECTED_ROWS=21120
HEARTBEAT_SECONDS=300
POLL_SECONDS=15

trap 'echo "[ERROR] Corrected timing continuation stopped at line $LINENO." >&2' ERR

mkdir -p \
  "$RESUME_ROOT" \
  "$ADAPTED_DIR" \
  "$LOG_DIR" \
  "$QUARANTINE_DIR" \
  "$ARCHIVE_DIR"

cd "$ROOT"

echo "=== 1. Exact post-merge continuation gate ==="

test "$(git branch --show-current)" = "$BASE"
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test -z "$(git status --porcelain)"

git fetch origin --prune --tags
test "$(git rev-parse "origin/$BASE")" = "$EXPECTED_HEAD"

test -z "$(
  pgrep -n -f 'python.*[r]un_timing_repetitions' || true
)"

test -d "$OLD_ADAPTED_DIR"
test -f "$OLD_REBINDING_MANIFEST"
test "$(
  sha256sum "$OLD_REBINDING_MANIFEST" |
  awk '{print $1}'
)" = "$EXPECTED_OLD_REBINDING_MANIFEST_SHA"

test -f "$DIAGNOSTIC_REPORT"
test "$(
  sha256sum "$DIAGNOSTIC_REPORT" |
  awk '{print $1}'
)" = "$EXPECTED_DIAGNOSTIC_REPORT_SHA"

echo "post_merge_continuation_gate=PASS"
echo "branch=$BASE"
echo "head=$EXPECTED_HEAD"
echo "repository_clean=true"
echo "active_timing_runner=false"
echo "pr39_already_merged=true"
echo "replication_000_reuse_authorized=true"
echo "replications_001_through_009_execution_authorized=true"

echo
echo "=== 2. Validate the schema diagnosis and corrected planning contract ==="

export ROOT SPECS_REL AMENDMENT_REL OLD_BASE_HEAD EXPECTED_HEAD
export OLD_REBINDING_MANIFEST DIAGNOSTIC_REPORT
export OLD_ADAPTED_DIR ADAPTED_DIR EXECUTION_SPEC_AUDIT
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


root = Path(os.environ["ROOT"]).resolve()
specs_rel = Path(os.environ["SPECS_REL"])
amendment_path = root / os.environ["AMENDMENT_REL"]
old_base = os.environ["OLD_BASE_HEAD"]
expected_head = os.environ["EXPECTED_HEAD"]
old_manifest_path = Path(os.environ["OLD_REBINDING_MANIFEST"])
diagnostic_path = Path(os.environ["DIAGNOSTIC_REPORT"])
old_adapted_dir = Path(os.environ["OLD_ADAPTED_DIR"])
adapted_dir = Path(os.environ["ADAPTED_DIR"])
audit_path = Path(os.environ["EXECUTION_SPEC_AUDIT"])


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_git_json(ref: str, relative_path: str) -> Any:
    text = subprocess.check_output(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=root,
        text=True,
    )
    return json.loads(text)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_differences(
    left: Any,
    right: Any,
    path: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{
            "path": list(path),
            "left": left,
            "right": right,
            "kind": "type",
        }]

    if isinstance(left, dict):
        assert set(left) == set(right), path
        rows: list[dict[str, Any]] = []
        for key in sorted(left):
            rows.extend(
                scalar_differences(
                    left[key],
                    right[key],
                    path + (key,),
                )
            )
        return rows

    if isinstance(left, list):
        assert len(left) == len(right), path
        rows: list[dict[str, Any]] = []
        for index, (a, b) in enumerate(zip(left, right)):
            rows.extend(
                scalar_differences(a, b, path + (index,))
            )
        return rows

    if left != right:
        return [{
            "path": list(path),
            "left": left,
            "right": right,
            "kind": "scalar",
        }]

    return []


diagnostic = load_json(diagnostic_path)
aggregate = diagnostic["aggregate"]

assert diagnostic["source_commit"] == expected_head
assert diagnostic["old_source_commit"] == old_base
assert aggregate["old_to_adapted_key_set_difference_count"] == 10
assert aggregate["old_to_adapted_candidate_path_rebinding_count"] == 0
assert aggregate["old_to_adapted_other_scalar_difference_count"] == 0
assert aggregate["old_to_adapted_type_difference_count"] == 0
assert aggregate["old_to_adapted_list_length_difference_count"] == 0
assert aggregate["old_to_new_key_set_difference_count"] == 0
assert aggregate["old_to_new_other_scalar_difference_count"] == 20

old_manifest = load_json(old_manifest_path)
assert old_manifest["replication_count"] == 10
assert old_manifest["total_mapping_count"] == 30
assert old_manifest["timing_execution_performed"] is False
assert old_manifest["evaluator_called_during_rebinding"] is False
assert old_manifest["original_specs_modified"] is False
assert old_manifest["functional_outputs_modified"] is False

amendment = load_json(amendment_path)
assert amendment["corrected_contract"]["cells_per_factor"] == 32
assert amendment["corrected_contract"]["rows_per_factor"] == 3520
assert amendment["corrected_contract"]["rows_per_replication"] == 21120
assert amendment["corrected_contract"]["total_rows"] == 211200
assert amendment["post_merge_authorization"]["replication_000_reuse_authorized"] is True
assert amendment["post_merge_authorization"][
    "replications_001_through_009_execution_authorized"
] is True
assert amendment["outcome_blinding"]["timing_values_interpreted"] is False

spec_records = []
expected_changed_paths = {
    ("expected_observation_rows",): (15180, 21120),
    ("measured_repetitions_per_factor_level",): (2530, 3520),
}

for index in range(10):
    source_name = (
        f"objective_count_rep_{index:03d}_"
        "portfolio_timing_stage10.json"
    )
    source_rel = (specs_rel / source_name).as_posix()

    old_spec = load_git_json(old_base, source_rel)
    new_spec = load_json(root / source_rel)

    diffs = scalar_differences(old_spec, new_spec)
    assert len(diffs) == 2, (index, diffs)

    observed = {
        tuple(row["path"]): (row["left"], row["right"])
        for row in diffs
    }
    assert observed == expected_changed_paths, (index, observed)

    adapted_name = (
        f"objective_count_stage10_rep_{index:03d}_"
        "path_rebound.json"
    )
    old_adapted_path = old_adapted_dir / adapted_name
    new_adapted_path = adapted_dir / adapted_name

    assert old_adapted_path.is_file()

    shutil.copy2(old_adapted_path, new_adapted_path)
    assert sha(old_adapted_path) == sha(new_adapted_path)

    adapted = load_json(new_adapted_path)
    assert isinstance(adapted, dict)

    adapted_keys = sorted(adapted)
    required_execution_keys = {
        "campaign_dir",
        "contract_version",
        "execution_id",
        "instance_selection",
        "output_dir",
        "workload_path",
    }
    missing_execution_keys = sorted(
        required_execution_keys - set(adapted)
    )
    assert not missing_execution_keys, (
        index,
        missing_execution_keys,
        adapted_keys,
    )

    # Additional top-level keys are retained rather than rejected.
    # The exact SHA and load_execution_inputs validation are the
    # authoritative execution-contract checks.
    spec_records.append({
        "replication": index,
        "planning_spec": source_rel,
        "planning_spec_sha256": sha(root / source_rel),
        "planning_contract_changes_from_old_base": diffs,
        "reused_execution_spec": str(new_adapted_path),
        "reused_execution_spec_sha256": sha(new_adapted_path),
        "execution_spec_top_level_keys": adapted_keys,
        "required_execution_keys_present": True,
        "additional_execution_keys": sorted(
            set(adapted) - required_execution_keys
        ),
    })

module = importlib.import_module(
    "backend.harness.sensitivity_execution.run_timing_repetitions"
)
loader = getattr(module, "load_execution_inputs")

for record in spec_records:
    loader(Path(record["reused_execution_spec"]))

payload = {
    "schema_version":
        "mcad-sa5-reused-execution-spec-provenance-v1",
    "status": "validation_pass",
    "source_commit": expected_head,
    "old_source_commit": old_base,
    "old_rebinding_manifest": {
        "path": str(old_manifest_path),
        "sha256": sha(old_manifest_path),
        "replication_count": old_manifest["replication_count"],
        "total_mapping_count": old_manifest["total_mapping_count"],
    },
    "diagnostic": {
        "path": str(diagnostic_path),
        "sha256": sha(diagnostic_path),
        "old_to_adapted_key_set_difference_count":
            aggregate["old_to_adapted_key_set_difference_count"],
        "old_to_adapted_candidate_path_rebinding_count":
            aggregate["old_to_adapted_candidate_path_rebinding_count"],
        "old_to_new_other_scalar_difference_count":
            aggregate["old_to_new_other_scalar_difference_count"],
    },
    "decision": {
        "reuse_old_path_rebound_execution_specs_unchanged": True,
        "reason": (
            "The committed timing specifications and the detached "
            "runner execution specifications are distinct schemas. "
            "The amendment changed only two planning-contract scalars "
            "per replication and did not change runner inputs or paths."
        ),
        "timing_evaluator_called_during_validation": False,
    },
    "records": spec_records,
}

audit_path.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n",
    encoding="utf-8",
)

print("execution_spec_reuse_validation=PASS")
print("planning_spec_count=10")
print("planning_contract_scalar_change_count=20")
print("reused_execution_spec_count=10")
print("all_reused_execution_specs_sha_identical=true")
print("all_reused_execution_inputs_loadable=true")
print("timing_evaluator_called_during_validation=false")
print(f"execution_spec_audit={audit_path}")
print(f"execution_spec_audit_sha256={sha(audit_path)}")
PY

echo
echo "=== 3. Define structural bundle validation ==="

validate_bundle() {
  local replication="$1"
  local output_dir="$2"
  local require_amendment_sha="$3"

  "$PYTHON" - \
    "$replication" \
    "$output_dir" \
    "$ROOT/$AMENDMENT_REL" \
    "$require_amendment_sha" <<'PY'
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


replication = int(sys.argv[1])
output_dir = Path(sys.argv[2])
amendment_path = Path(sys.argv[3])
require_amendment_sha = sys.argv[4] == "true"


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
actual_names = {
    path.name
    for path in output_dir.iterdir()
    if path.is_file()
}
assert actual_names == expected_names, (actual_names, expected_names)

manifest_path = output_dir / "timing_manifest.json"
observations_path = output_dir / "timing_observations.csv"
summary_path = output_dir / "timing_summary.json"
references_path = output_dir / "functional_references.json"

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
    path = output_dir / name
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

if require_amendment_sha:
    amendment = load_json(amendment_path)
    evidence = amendment["replication_000_evidence"]
    assert sha(manifest_path) == evidence["manifest_sha256"]
    assert sha(summary_path) == evidence["summary_sha256"]
    assert sha(observations_path) == evidence["observations_sha256"]

print(f"replication_{replication:03d}_bundle_validation=PASS")
print(f"replication_{replication:03d}_csv_rows={row_count}")
print(f"replication_{replication:03d}_unique_cells={len(cell_counts)}")
print(f"replication_{replication:03d}_rows_per_factor=3520")
print(f"replication_{replication:03d}_functional_mismatch_count=0")
print(
    f"replication_{replication:03d}_order_near_balance_all_true=true"
)
print(
    f"replication_{replication:03d}_manifest_sha256={sha(manifest_path)}"
)
print(
    f"replication_{replication:03d}_observations_sha256={sha(observations_path)}"
)
print(
    f"replication_{replication:03d}_summary_sha256={sha(summary_path)}"
)
print(
    f"replication_{replication:03d}_references_sha256={sha(references_path)}"
)
PY
}

write_campaign_state() {
  export OUTPUT_ROOT_REL CAMPAIGN_STATE EXPECTED_HEAD

  "$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


root = Path(os.environ["ROOT"]).resolve()
output_root = root / os.environ["OUTPUT_ROOT_REL"]
state_path = Path(os.environ["CAMPAIGN_STATE"])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


replications = []

for index in range(10):
    output_dir = output_root / (
        f"objective_count_rep_{index:03d}_"
        "portfolio_timing_stage10"
    )

    expected = [
        output_dir / "functional_references.json",
        output_dir / "timing_manifest.json",
        output_dir / "timing_observations.csv",
        output_dir / "timing_summary.json",
    ]

    complete = all(path.is_file() for path in expected)
    replications.append({
        "replication": index,
        "output_dir": output_dir.relative_to(root).as_posix(),
        "complete_file_set_present": complete,
        "files": (
            {
                path.name: {
                    "size_bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
                for path in expected
            }
            if complete
            else {}
        ),
    })

complete_count = sum(
    row["complete_file_set_present"]
    for row in replications
)

payload = {
    "schema_version":
        "mcad-sa5-objective-count-timing-execution-state-v2",
    "status": (
        "all_replications_structurally_complete"
        if complete_count == 10
        else "campaign_in_progress"
    ),
    "source_commit": os.environ["EXPECTED_HEAD"],
    "completed_replication_file_set_count": complete_count,
    "replications": replications,
    "scientific_controls": {
        "timing_values_interpreted": False,
        "precision_analysis_performed": False,
        "bootstrap_analysis_performed": False,
        "manuscript_modified": False,
    },
}

state_path.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n",
    encoding="utf-8",
)

print(f"campaign_state={state_path}")
print(f"completed_replication_file_set_count={complete_count}")
print(f"campaign_state_sha256={sha(state_path)}")
PY
}

echo
echo "=== 4. Validate and archive replication 000 ==="

REP000_DIR="$ROOT/$OUTPUT_ROOT_REL/objective_count_rep_000_portfolio_timing_stage10"
validate_bundle 0 "$REP000_DIR" true

REP000_ARCHIVE="$ARCHIVE_DIR/objective_count_rep_000_portfolio_timing_stage10.tar.gz"

if [ ! -f "$REP000_ARCHIVE" ]; then
  tar \
    -C "$(dirname "$REP000_DIR")" \
    -I 'gzip -1' \
    -cf "$REP000_ARCHIVE" \
    "$(basename "$REP000_DIR")"
  sha256sum "$REP000_ARCHIVE" > "$REP000_ARCHIVE.sha256"
fi

echo "replication_000_reuse=AUTHORIZED_AND_VALIDATED"
echo "replication_000_validated_archive=$REP000_ARCHIVE"
echo "replication_000_validated_archive_sha256=$(
  sha256sum "$REP000_ARCHIVE" |
  awk '{print $1}'
)"

write_campaign_state

echo
echo "=== 5. Execute or reuse replications 001 through 009 ==="

for REP in $(seq 1 9); do
  REP_PAD="$(printf '%03d' "$REP")"

  SPEC="$ADAPTED_DIR/objective_count_stage10_rep_${REP_PAD}_path_rebound.json"
  OUTPUT_DIR="$ROOT/$OUTPUT_ROOT_REL/objective_count_rep_${REP_PAD}_portfolio_timing_stage10"
  LOG="$LOG_DIR/rep_${REP_PAD}.log"

  test -f "$SPEC"

  echo
  echo "--- timing replication $REP_PAD ---"
  echo "reused_execution_spec=$SPEC"
  echo "output_dir=${OUTPUT_DIR#"$ROOT/"}"
  echo "expected_observation_rows=$EXPECTED_ROWS"

  REUSE=false

  if [ -d "$OUTPUT_DIR" ]; then
    set +e
    validate_bundle "$REP" "$OUTPUT_DIR" false \
      > "$RESUME_ROOT/rep_${REP_PAD}_preexisting_validation.log" \
      2>&1
    VALIDATION_STATUS=$?
    set -e

    if [ "$VALIDATION_STATUS" -eq 0 ]; then
      REUSE=true
      cat "$RESUME_ROOT/rep_${REP_PAD}_preexisting_validation.log"
      echo "replication_${REP_PAD}_reuse=PASS"
    else
      QUARANTINE="$QUARANTINE_DIR/rep_${REP_PAD}_incomplete_$(date -u +%Y%m%dT%H%M%SZ)"
      mv "$OUTPUT_DIR" "$QUARANTINE"
      echo "quarantined_replication_${REP_PAD}=$QUARANTINE"
    fi
  fi

  if [ "$REUSE" = true ]; then
    write_campaign_state
    continue
  fi

  mkdir -p "$(dirname "$OUTPUT_DIR")"

  set +e
  "$PYTHON" \
    -m "$RUNNER_MODULE" \
    "$SPEC" \
    --output-dir "${OUTPUT_DIR#"$ROOT/"}" \
    --warmups "$WARMUPS" \
    --measurements "$MEASUREMENTS" \
    --order-seed "$ORDER_SEED" \
    --reuse-successful \
    > "$LOG" 2>&1 &
  RUNNER_PID=$!
  set -e

  START_EPOCH="$(date +%s)"
  NEXT_HEARTBEAT="$HEARTBEAT_SECONDS"

  echo "replication_${REP_PAD}_runner_pid=$RUNNER_PID"
  echo "heartbeat_interval_seconds=$HEARTBEAT_SECONDS"

  while kill -0 "$RUNNER_PID" 2>/dev/null; do
    sleep "$POLL_SECONDS"

    if ! kill -0 "$RUNNER_PID" 2>/dev/null; then
      break
    fi

    NOW_EPOCH="$(date +%s)"
    ELAPSED="$((NOW_EPOCH - START_EPOCH))"

    if [ "$ELAPSED" -lt "$NEXT_HEARTBEAT" ]; then
      continue
    fi

    STATE="$(
      ps -p "$RUNNER_PID" -o stat= |
      awk '{$1=$1; print}'
    )"

    CPU_PERCENT="$(
      ps -p "$RUNNER_PID" -o %cpu= |
      awk '{$1=$1; print}'
    )"

    CPU_TICKS="$(
      awk '{print $14 + $15}' "/proc/$RUNNER_PID/stat"
    )"

    LOG_BYTES="$(
      stat -c '%s' "$LOG" 2>/dev/null ||
      echo 0
    )"

    LAST_LOG_LINE="$(
      tail -n 1 "$LOG" 2>/dev/null ||
      true
    )"

    echo "timing_heartbeat_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "replication=$REP_PAD"
    echo "runner_pid=$RUNNER_PID"
    echo "elapsed_seconds=$ELAPSED"
    echo "process_state=$STATE"
    echo "process_cpu_percent=$CPU_PERCENT"
    echo "cpu_ticks=$CPU_TICKS"
    echo "log_bytes=$LOG_BYTES"
    echo "last_log_line=$LAST_LOG_LINE"
    echo "heartbeat_kind=runner_progress_observation"

    NEXT_HEARTBEAT="$((NEXT_HEARTBEAT + HEARTBEAT_SECONDS))"
  done

  set +e
  wait "$RUNNER_PID"
  RUNNER_STATUS=$?
  set -e

  echo "replication_${REP_PAD}_runner_exit_status=$RUNNER_STATUS"

  if [ "$RUNNER_STATUS" -ne 0 ]; then
    echo "=== Last 80 runner log lines ==="
    tail -n 80 "$LOG" || true
    exit "$RUNNER_STATUS"
  fi

  validate_bundle "$REP" "$OUTPUT_DIR" false

  ARCHIVE="$ARCHIVE_DIR/objective_count_rep_${REP_PAD}_portfolio_timing_stage10.tar.gz"

  tar \
    -C "$(dirname "$OUTPUT_DIR")" \
    -I 'gzip -1' \
    -cf "$ARCHIVE" \
    "$(basename "$OUTPUT_DIR")"

  sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"

  echo "replication_${REP_PAD}_validated_archive=$ARCHIVE"
  echo "replication_${REP_PAD}_validated_archive_sha256=$(
    sha256sum "$ARCHIVE" |
    awk '{print $1}'
  )"

  write_campaign_state
done

echo
echo "=== 6. Final ten-replication structural validation ==="

for REP in $(seq 0 9); do
  REP_PAD="$(printf '%03d' "$REP")"
  OUTPUT_DIR="$ROOT/$OUTPUT_ROOT_REL/objective_count_rep_${REP_PAD}_portfolio_timing_stage10"

  if [ "$REP" -eq 0 ]; then
    validate_bundle "$REP" "$OUTPUT_DIR" true
  else
    validate_bundle "$REP" "$OUTPUT_DIR" false
  fi
done

write_campaign_state

COMPLETED_COUNT="$(
  "$PYTHON" - "$CAMPAIGN_STATE" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text())
print(value["completed_replication_file_set_count"])
PY
)"

test "$COMPLETED_COUNT" -eq 10
test -z "$(git status --porcelain)"
test -z "$(
  pgrep -n -f 'python.*[r]un_timing_repetitions' || true
)"

echo
echo "=== 7. Final campaign execution state ==="
echo "sa5_timing_execution_after_amendment=PASS"
echo "source_commit=$EXPECTED_HEAD"
echo "completed_replication_count=10"
echo "rows_per_replication=21120"
echo "total_structural_rows=211200"
echo "replication_000_reused=true"
echo "replications_001_through_009_executed_or_reused=true"
echo "timing_values_interpreted=false"
echo "precision_analysis_performed=false"
echo "bootstrap_analysis_performed=false"
echo "manuscript_modified=false"
echo "execution_spec_audit=$EXECUTION_SPEC_AUDIT"
echo "execution_spec_audit_sha256=$(
  sha256sum "$EXECUTION_SPEC_AUDIT" |
  awk '{print $1}'
)"
echo "campaign_state=$CAMPAIGN_STATE"
echo "campaign_state_sha256=$(
  sha256sum "$CAMPAIGN_STATE" |
  awk '{print $1}'
)"
echo "next_stage=freeze_and_commit_timing_evidence_before_precision_analysis"

git status --short --branch
