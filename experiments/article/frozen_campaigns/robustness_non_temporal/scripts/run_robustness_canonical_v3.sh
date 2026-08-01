#!/usr/bin/env bash
# Canonical MCAD robustness campaign V3.
# This script is autonomous and does not depend on any file under /tmp.

set +e
set -u
set -o pipefail

REPO="/workspaces/MCAD_improve3"
VENV="/workspaces/.venvs/mcad-phase3-lock-validation"
PYTHON="$VENV/bin/python"

EXPECTED_BRANCH="fix/robustness-explainability-recovery-20260731T173824Z"
EXPECTED_HEAD="185290880a75d6df17c03aad6abbb44ca3818bf0"
EXPLAINABILITY_COMMIT="232423bb429148b770ace619367731ee6fdee66b"

SOURCE="backend/harness/run_robustness_benchmark.py"
CFG_FM="backend/harness/scenarios_robustness_foodmart.yaml"
CFG_AW="backend/harness/scenarios_robustness_adventureworks.yaml"
TEST_EXPLAIN="backend/harness/tests/test_robustness_explainability_equivalence.py"
TEST_META="backend/harness/tests/test_robustness_meta_provenance.py"
DIAGNOSTIC_RUN="/workspaces/mcad_robustness_candidate_20260731T182355Z"

REPEATS=30
SEED=42
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_BASENAME="mcad_robustness_canonical_${STAMP}"
RUN_ROOT="/workspaces/${RUN_BASENAME}"
RESULTS_DIR="$RUN_ROOT/results"
VALIDATION_DIR="$RUN_ROOT/validation"
PROVENANCE_DIR="$RUN_ROOT/provenance"
RUNTIME_DIR="$RUN_ROOT/runtime"
ARCHIVE="/workspaces/${RUN_BASENAME}.tar.gz"
ARCHIVE_SHA="${ARCHIVE}.sha256"
EXTRACT_ROOT="/workspaces/${RUN_BASENAME}_extract_check"
FREEZE_JSON="/workspaces/${RUN_BASENAME}_FREEZE.json"
FREEZE_MD="/workspaces/${RUN_BASENAME}_FREEZE.md"
FREEZE_SHA="/workspaces/${RUN_BASENAME}_FREEZE.sha256"
PACKAGING_LOG_PREFIX="/workspaces/${RUN_BASENAME}_packaging"

export PYTHONPATH="$REPO"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export MPLBACKEND=Agg
export MCAD_TMP_DIR="$RUNTIME_DIR"

repository_gate_exit_status=1
run_root_initialization_exit_status=1
provenance_capture_exit_status=1
preflight_compile_exit_status=1
preflight_diff_check_exit_status=1
preflight_tests_exit_status=1
robustness_campaign_exit_status=1
robustness_output_validation_exit_status=1
repository_clean_after_campaign_exit_status=1
diagnostic_run_unchanged_exit_status=1
manifest_creation_exit_status=1
internal_checksum_validation_exit_status=1
candidate_archive_creation_exit_status=1
candidate_archive_checksum_exit_status=1
candidate_archive_extract_exit_status=1
candidate_archive_internal_validation_exit_status=1
freeze_certificate_creation_exit_status=1
robustness_canonical_final_exit_status=1
scientific_freeze=false
next_stage="inspect_repository_gate_failure"

branch=""
head_before=""
head_after=""
tree_before=""
tree_after=""
diagnostic_digest_before=""
diagnostic_digest_after=""
archive_digest=""

section() {
  printf '\n========================================================================\n'
  printf '%s\n' "$1"
  printf '========================================================================\n'
}

dir_digest() {
  local directory="$1"
  (
    cd "$directory" || exit 1
    find . -type f -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 -r sha256sum \
      | sha256sum \
      | awk '{print $1}'
  )
}

section "1. REPOSITORY AND SOURCE GATE"

cd "$REPO" || {
  echo "[ERROR] Cannot enter repository: $REPO"
  cd /workspaces || true
}

if [ "$(pwd)" = "$REPO" ]; then
  branch="$(git branch --show-current 2>/dev/null)"
  head_before="$(git rev-parse HEAD 2>/dev/null)"
  tree_before="$(git rev-parse HEAD^{tree} 2>/dev/null)"

  echo "repository=$REPO"
  echo "branch=$branch"
  echo "head=$head_before"
  echo "tree=$tree_before"
  git status --short --branch

  gate=0

  [ "$branch" = "$EXPECTED_BRANCH" ] || {
    echo "[ERROR] Unexpected branch."
    echo "expected_branch=$EXPECTED_BRANCH"
    echo "actual_branch=$branch"
    gate=1
  }

  [ "$head_before" = "$EXPECTED_HEAD" ] || {
    echo "[ERROR] Unexpected HEAD."
    echo "expected_head=$EXPECTED_HEAD"
    echo "actual_head=$head_before"
    gate=1
  }

  if [ -n "$(git status --porcelain)" ]; then
    echo "[ERROR] Repository is not clean."
    gate=1
  fi

  git merge-base --is-ancestor "$EXPLAINABILITY_COMMIT" HEAD
  explainability_ancestor_status=$?
  echo "explainability_commit_is_ancestor_exit_status=$explainability_ancestor_status"
  [ "$explainability_ancestor_status" -eq 0 ] || gate=1

  [ -x "$PYTHON" ] || {
    echo "[ERROR] Missing Python environment: $PYTHON"
    gate=1
  }

  for required in \
    "$SOURCE" \
    "$CFG_FM" \
    "$CFG_AW" \
    "$TEST_EXPLAIN" \
    "$TEST_META"; do
    if [ ! -f "$required" ]; then
      echo "[ERROR] Missing required file: $required"
      gate=1
    fi
  done

  [ -d "$DIAGNOSTIC_RUN" ] || {
    echo "[ERROR] Missing diagnostic run: $DIAGNOSTIC_RUN"
    gate=1
  }

  [ ! -e "$RUN_ROOT" ] || {
    echo "[ERROR] New run root already exists: $RUN_ROOT"
    gate=1
  }

  [ ! -e "$ARCHIVE" ] || {
    echo "[ERROR] New archive already exists: $ARCHIVE"
    gate=1
  }

  [ ! -e "$EXTRACT_ROOT" ] || {
    echo "[ERROR] Extraction directory already exists: $EXTRACT_ROOT"
    gate=1
  }

  seed_contract_count="$(grep -F "'seed': args.seed," "$SOURCE" | wc -l | tr -d ' ')"
  echo "seed_metadata_contract_line_count=$seed_contract_count"
  [ "$seed_contract_count" = "1" ] || gate=1

  repository_gate_exit_status=$gate
fi

echo "repository_gate_exit_status=$repository_gate_exit_status"

section "2. INITIALIZE NEW EXTERNAL RUN"

if [ "$repository_gate_exit_status" -eq 0 ]; then
  mkdir -p \
    "$RESULTS_DIR" \
    "$VALIDATION_DIR" \
    "$PROVENANCE_DIR/source_snapshot" \
    "$RUNTIME_DIR"
  run_root_initialization_exit_status=$?

  if [ "$run_root_initialization_exit_status" -eq 0 ]; then
    diagnostic_digest_before="$(dir_digest "$DIAGNOSTIC_RUN")"
    digest_status=$?
    [ "$digest_status" -eq 0 ] || run_root_initialization_exit_status=1
  fi
fi

echo "run_root=$RUN_ROOT"
echo "results_dir=$RESULTS_DIR"
echo "diagnostic_run_digest_before=$diagnostic_digest_before"
echo "run_root_initialization_exit_status=$run_root_initialization_exit_status"

section "3. CAPTURE PROVENANCE AND REAL CLI CONTRACT"

if [ "$run_root_initialization_exit_status" -eq 0 ]; then
  provenance_status=0

  cp "$0" "$PROVENANCE_DIR/$(basename "$0")" || provenance_status=1

  {
    echo "repository=$REPO"
    echo "branch=$branch"
    echo "head=$head_before"
    echo "tree=$tree_before"
    echo "expected_head=$EXPECTED_HEAD"
    echo "repeats=$REPEATS"
    echo "seed=$SEED"
    echo "diagnostic_run=$DIAGNOSTIC_RUN"
    echo "diagnostic_run_digest_before=$diagnostic_digest_before"
    echo "run_root=$RUN_ROOT"
    echo "utc_started=$STAMP"
  } > "$PROVENANCE_DIR/campaign_identity.env" || provenance_status=1

  git status --porcelain=v1 > "$PROVENANCE_DIR/git_status_before.txt" || provenance_status=1
  git status --short --branch > "$PROVENANCE_DIR/git_status_branch_before.txt" || provenance_status=1
  git log -10 --oneline --decorate > "$PROVENANCE_DIR/git_log_before.txt" || provenance_status=1
  git remote -v > "$PROVENANCE_DIR/git_remotes.txt" || provenance_status=1

  "$PYTHON" --version > "$PROVENANCE_DIR/python_version.txt" 2>&1 || provenance_status=1
  "$PYTHON" -m pip --version > "$PROVENANCE_DIR/pip_version.txt" 2>&1 || provenance_status=1
  "$PYTHON" -m pip freeze > "$PROVENANCE_DIR/pip_freeze.txt" 2>&1 || provenance_status=1
  "$PYTHON" -m pip check > "$PROVENANCE_DIR/pip_check.txt" 2>&1 || provenance_status=1

  "$PYTHON" "$SOURCE" --help > "$PROVENANCE_DIR/runner_help.txt" 2>&1 || provenance_status=1

  for flag in --config --run-root --results-dir --repeats --seed; do
    grep -q -- "$flag" "$PROVENANCE_DIR/runner_help.txt" || {
      echo "[ERROR] CLI flag missing from --help: $flag"
      provenance_status=1
    }
  done

  cp --parents \
    "$SOURCE" \
    "$CFG_FM" \
    "$CFG_AW" \
    "$TEST_EXPLAIN" \
    "$TEST_META" \
    "$PROVENANCE_DIR/source_snapshot" || provenance_status=1

  sha256sum \
    "$SOURCE" \
    "$CFG_FM" \
    "$CFG_AW" \
    "$TEST_EXPLAIN" \
    "$TEST_META" \
    > "$PROVENANCE_DIR/source_files.sha256" || provenance_status=1

  provenance_capture_exit_status=$provenance_status
fi

echo "provenance_capture_exit_status=$provenance_capture_exit_status"
echo "runner_help=$PROVENANCE_DIR/runner_help.txt"
echo "source_checksums=$PROVENANCE_DIR/source_files.sha256"

section "4. PRE-CAMPAIGN COMPILATION AND TEST GATE"

if [ "$provenance_capture_exit_status" -eq 0 ]; then
  "$PYTHON" -m py_compile \
    "$SOURCE" \
    "$TEST_EXPLAIN" \
    "$TEST_META"
  preflight_compile_exit_status=$?

  git diff --check
  preflight_diff_check_exit_status=$?

  if [ "$preflight_compile_exit_status" -eq 0 ] && \
     [ "$preflight_diff_check_exit_status" -eq 0 ]; then
    "$PYTHON" -m pytest \
      backend/harness/tests \
      backend/tests/test_sat_clause_diagnostics.py \
      -q \
      -p no:cacheprovider \
      2>&1 | tee "$VALIDATION_DIR/preflight_tests.log"
    pipe_status=("${PIPESTATUS[@]}")
    preflight_tests_exit_status="${pipe_status[0]}"
    preflight_tests_tee_exit_status="${pipe_status[1]}"
    [ "$preflight_tests_tee_exit_status" -eq 0 ] || preflight_tests_exit_status=1
  fi
fi

echo "preflight_compile_exit_status=$preflight_compile_exit_status"
echo "preflight_diff_check_exit_status=$preflight_diff_check_exit_status"
echo "preflight_tests_exit_status=$preflight_tests_exit_status"

section "5. EXECUTE CANONICAL ROBUSTNESS CAMPAIGN"

if [ "$preflight_compile_exit_status" -eq 0 ] && \
   [ "$preflight_diff_check_exit_status" -eq 0 ] && \
   [ "$preflight_tests_exit_status" -eq 0 ]; then

  "$PYTHON" "$SOURCE" \
    --config "$CFG_FM" \
    --config "$CFG_AW" \
    --run-root "$RUN_ROOT" \
    --results-dir results \
    --repeats "$REPEATS" \
    --seed "$SEED" \
    2>&1 | tee "$VALIDATION_DIR/robustness_campaign.log"

  campaign_pipe_status=("${PIPESTATUS[@]}")
  robustness_campaign_exit_status="${campaign_pipe_status[0]}"
  campaign_tee_status="${campaign_pipe_status[1]}"
  [ "$campaign_tee_status" -eq 0 ] || robustness_campaign_exit_status=1
else
  echo "[SKIP] Campaign refused by preflight gate."
fi

echo "robustness_campaign_exit_status=$robustness_campaign_exit_status"
echo "robustness_campaign_log=$VALIDATION_DIR/robustness_campaign.log"

section "6. REPOSITORY AND DIAGNOSTIC-RUN IMMUTABILITY"

if [ "$run_root_initialization_exit_status" -eq 0 ]; then
  head_after="$(git rev-parse HEAD 2>/dev/null)"
  tree_after="$(git rev-parse HEAD^{tree} 2>/dev/null)"
  git status --porcelain=v1 > "$PROVENANCE_DIR/git_status_after.txt" 2>/dev/null

  diagnostic_digest_after="$(dir_digest "$DIAGNOSTIC_RUN")"
  diagnostic_after_status=$?

  if [ "$head_after" = "$EXPECTED_HEAD" ] && \
     [ "$tree_after" = "$tree_before" ] && \
     [ -z "$(git status --porcelain)" ]; then
    repository_clean_after_campaign_exit_status=0
  fi

  if [ "$diagnostic_after_status" -eq 0 ] && \
     [ -n "$diagnostic_digest_before" ] && \
     [ "$diagnostic_digest_after" = "$diagnostic_digest_before" ]; then
    diagnostic_run_unchanged_exit_status=0
  fi

  {
    echo "head_before=$head_before"
    echo "head_after=$head_after"
    echo "tree_before=$tree_before"
    echo "tree_after=$tree_after"
    echo "diagnostic_run_digest_before=$diagnostic_digest_before"
    echo "diagnostic_run_digest_after=$diagnostic_digest_after"
  } > "$PROVENANCE_DIR/post_campaign_identity.env"
else
  echo "[SKIP] Immutability audit refused because the run root was not initialized."
fi

echo "head_after=$head_after"
echo "tree_after=$tree_after"
echo "repository_clean_after_campaign_exit_status=$repository_clean_after_campaign_exit_status"
echo "diagnostic_run_digest_after=$diagnostic_digest_after"
echo "diagnostic_run_unchanged_exit_status=$diagnostic_run_unchanged_exit_status"

section "7. INDEPENDENT SCIENTIFIC AND PROVENANCE VALIDATION"

if [ "$run_root_initialization_exit_status" -eq 0 ]; then
cat > "$PROVENANCE_DIR/validate_robustness_run.py" <<'PY'
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RESULTS = Path(os.environ["RESULTS_DIR"])
OUT_JSON = Path(os.environ["VALIDATION_JSON"])
OUT_MD = Path(os.environ["VALIDATION_MD"])
EXPECTED_HEAD = os.environ["EXPECTED_HEAD"]
SOURCE_TREE_UNCHANGED = os.environ.get("SOURCE_TREE_UNCHANGED") == "true"

checks: list[dict[str, Any]] = []


def add_check(name: str, actual: Any, expected: Any) -> None:
    checks.append(
        {
            "name": name,
            "actual": actual,
            "expected": expected,
            "ok": actual == expected,
        }
    )


def read_csv(name: str) -> list[dict[str, str]]:
    path = RESULTS / name
    if not path.is_file():
        add_check(f"file_present::{name}", False, True)
        return []
    add_check(f"file_present::{name}", True, True)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


expected_nonempty_files = [
    "robustness_report.md",
    "figures/robustness_false_allow_by_policy.png",
    "figures/robustness_false_block_by_policy.png",
    "figures/robustness_auc_phi_by_policy.png",
    "figures/robustness_false_allow_by_type.png",
    "figures/robustness_block_reason_distribution_mcad.png",
    "figures/robustness_explainable_block_rate_by_type.png",
]

for relative in expected_nonempty_files:
    path = RESULTS / relative
    add_check(f"nonempty_file::{relative}", path.is_file() and path.stat().st_size > 0, True)

sessions = read_csv("robustness_policy_session_metrics.csv")
steps = read_csv("robustness_policy_step_metrics.csv")
policy_summary = read_csv("robustness_policy_summary.csv")
by_type = read_csv("robustness_summary_by_scenario_type_and_policy.csv")
explain = read_csv("mcad_block_explainability_steps.csv")
explain_summary = read_csv("mcad_block_explainability_summary.csv")
reason_rows = read_csv("mcad_block_reason_distribution.csv")

expected_policies = {
    "mcad",
    "baseline_naive",
    "baseline_measure_overlap",
    "ablation_no_sat",
    "ablation_no_real",
    "ablation_ceval_any_intersection",
    "baseline_random_matched",
}
expected_scenarios = {
    "rb_fm_clause_diagnostics",
    "rb_fm_semantic_traps",
    "rb_fm_long_noisy_session",
    "rb_fm_borderline_recovery",
    "rb_aw_clause_diagnostics",
    "rb_aw_semantic_traps",
    "rb_aw_long_noisy_session",
    "rb_aw_borderline_recovery",
}
expected_types = {
    "adversarial_sat",
    "adversarial_semantic",
    "stress_long",
    "noisy_borderline",
}
expected_reason_distribution = {
    "agg_ok": 2,
    "grain_ok": 10,
    "measures_present": 2,
    "missing_requirement_set": 4,
    "slc_ok": 12,
    "time_ok": 2,
    "unit_ok": 2,
}

policies = {row.get("policy", "") for row in sessions}
scenarios = {row.get("scenario_id", "") for row in sessions}
scenario_types = {row.get("scenario_type", "") for row in sessions}
config_paths = {row.get("config_path", "") for row in sessions}
repeat_ids = {row.get("repeat_id", "") for row in sessions}

mcad_sessions = [row for row in sessions if row.get("policy") == "mcad"]
mcad_steps = [row for row in steps if row.get("policy") == "mcad"]
mcad_allows = [row for row in explain if as_bool(row.get("mcad_allow"))]
mcad_blocks = [row for row in explain if not as_bool(row.get("mcad_allow"))]
oracle_mismatches = [
    row
    for row in explain
    if as_bool(row.get("mcad_allow")) != as_bool(row.get("oracle_allow"))
]
unexplained_blocks = [
    row
    for row in mcad_blocks
    if not as_bool(row.get("explainable_block"))
]
unclassified_blocks = [
    row
    for row in mcad_blocks
    if row.get("primary_reason") == "unclassified_block"
]

reason_distribution = {
    row.get("primary_reason", ""): int(row.get("count") or 0)
    for row in reason_rows
}

add_check("session_rows", len(sessions), 1680)
add_check("step_rows", len(steps), 9660)
add_check("policy_summary_rows", len(policy_summary), 7)
add_check("summary_by_type_policy_rows", len(by_type), 28)
add_check("policy_count", len(policies), 7)
add_check("policy_set", sorted(policies), sorted(expected_policies))
add_check("scenario_count", len(scenarios), 8)
add_check("scenario_set", sorted(scenarios), sorted(expected_scenarios))
add_check("scenario_type_count", len(scenario_types), 4)
add_check("scenario_type_set", sorted(scenario_types), sorted(expected_types))
add_check("config_path_count", len(config_paths), 2)
add_check("repeat_id_count", len(repeat_ids), 30)
add_check("mcad_session_rows", len(mcad_sessions), 240)
add_check("mcad_step_rows", len(mcad_steps), 1380)
add_check("explainability_rows", len(explain), 46)
add_check("explainability_summary_rows", len(explain_summary), 4)
add_check("mcad_allow_count", len(mcad_allows), 12)
add_check("mcad_block_count", len(mcad_blocks), 34)
add_check("oracle_mismatch_count", len(oracle_mismatches), 0)
add_check("unexplained_block_count", len(unexplained_blocks), 0)
add_check("unclassified_block_count", len(unclassified_blocks), 0)
add_check("reason_total", sum(reason_distribution.values()), 34)
add_check("reason_distribution", reason_distribution, expected_reason_distribution)
add_check("source_commit", EXPECTED_HEAD, "185290880a75d6df17c03aad6abbb44ca3818bf0")
add_check("source_tree_unchanged", SOURCE_TREE_UNCHANGED, True)

meta_path = RESULTS / "robustness_meta.json"
if meta_path.is_file():
    add_check("file_present::robustness_meta.json", True, True)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
else:
    add_check("file_present::robustness_meta.json", False, True)
    metadata = []

add_check("metadata_entry_count", len(metadata), 2)
add_check("metadata_seed_values", sorted({entry.get("seed") for entry in metadata}, key=repr), [42])
add_check("metadata_repeat_values", sorted({entry.get("repeats") for entry in metadata}, key=repr), [30])
add_check("metadata_scenario_counts", sorted((entry.get("n_scenarios") for entry in metadata), key=repr), [4, 4])
add_check(
    "metadata_config_paths",
    sorted((entry.get("config_path") for entry in metadata), key=repr),
    sorted(
        [
            "backend/harness/scenarios_robustness_foodmart.yaml",
            "backend/harness/scenarios_robustness_adventureworks.yaml",
        ]
    ),
)

all_ok = all(item["ok"] for item in checks)
report = {
    "schema": "mcad.robustness.canonical.validation.v1",
    "results_dir": str(RESULTS),
    "source_commit": EXPECTED_HEAD,
    "scientific_validation_pass": all_ok,
    "checks": checks,
}
OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    "# MCAD canonical robustness validation",
    "",
    f"- Results: `{RESULTS}`",
    f"- Source commit: `{EXPECTED_HEAD}`",
    f"- Scientific validation: **{'PASS' if all_ok else 'FAIL'}**",
    "",
    "| Check | Actual | Expected | Status |",
    "|---|---:|---:|---|",
]
for item in checks:
    lines.append(
        f"| {item['name']} | `{item['actual']}` | `{item['expected']}` | "
        f"{'PASS' if item['ok'] else 'FAIL'} |"
    )
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

if not all_ok:
    failed = [item["name"] for item in checks if not item["ok"]]
    print("validation_failed_checks=" + ",".join(failed))
    raise SystemExit(1)

print("robustness_scientific_validation=PASS")
PY

validator_creation_status=$?
else
  validator_creation_status=1
  echo "[SKIP] Validator creation refused because the run root was not initialized."
fi

if [ "$validator_creation_status" -eq 0 ] && \
   [ "$robustness_campaign_exit_status" -eq 0 ] && \
   [ "$repository_clean_after_campaign_exit_status" -eq 0 ] && \
   [ "$diagnostic_run_unchanged_exit_status" -eq 0 ]; then

  RESULTS_DIR="$RESULTS_DIR" \
  VALIDATION_JSON="$VALIDATION_DIR/robustness_validation.json" \
  VALIDATION_MD="$VALIDATION_DIR/robustness_validation.md" \
  EXPECTED_HEAD="$EXPECTED_HEAD" \
  SOURCE_TREE_UNCHANGED=true \
  "$PYTHON" "$PROVENANCE_DIR/validate_robustness_run.py" \
    2>&1 | tee "$VALIDATION_DIR/robustness_validation.log"

  validation_pipe_status=("${PIPESTATUS[@]}")
  robustness_output_validation_exit_status="${validation_pipe_status[0]}"
  validation_tee_status="${validation_pipe_status[1]}"
  [ "$validation_tee_status" -eq 0 ] || robustness_output_validation_exit_status=1
else
  echo "[SKIP] Output validation refused because an earlier invariant failed."
fi

echo "validator_creation_exit_status=$validator_creation_status"
echo "robustness_output_validation_exit_status=$robustness_output_validation_exit_status"
echo "validation_json=$VALIDATION_DIR/robustness_validation.json"
echo "validation_markdown=$VALIDATION_DIR/robustness_validation.md"

section "8. CREATE INVENTORY, MANIFEST AND INTERNAL CHECKSUMS"

if [ "$robustness_output_validation_exit_status" -eq 0 ]; then
  RUN_ROOT="$RUN_ROOT" \
  RUN_BASENAME="$RUN_BASENAME" \
  EXPECTED_HEAD="$EXPECTED_HEAD" \
  REPEATS="$REPEATS" \
  SEED="$SEED" \
  "$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["RUN_ROOT"])
excluded = {"FILE_INVENTORY.tsv", "MANIFEST.json", "SHA256SUMS"}
entries = []

for path in sorted(root.rglob("*")):
    if not path.is_file() or path.name in excluded:
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entries.append(
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest,
        }
    )

inventory = root / "FILE_INVENTORY.tsv"
inventory.write_text(
    "path\tsize_bytes\tsha256\n"
    + "".join(
        f"{entry['path']}\t{entry['size_bytes']}\t{entry['sha256']}\n"
        for entry in entries
    ),
    encoding="utf-8",
)

manifest = {
    "schema": "mcad.robustness.canonical.manifest.v1",
    "run_id": os.environ["RUN_BASENAME"],
    "source_commit": os.environ["EXPECTED_HEAD"],
    "repeats": int(os.environ["REPEATS"]),
    "seed": int(os.environ["SEED"]),
    "scientific_validation": "PASS",
    "freeze_scope": "robustness_non_temporal",
    "latency_claim_authorized": False,
    "global_scientific_freeze": False,
    "file_count": len(entries),
    "files": entries,
}
(root / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(f"manifest_payload_file_count={len(entries)}")
PY
  manifest_creation_exit_status=$?

  if [ "$manifest_creation_exit_status" -eq 0 ]; then
    (
      cd "$RUN_ROOT" || exit 1
      find . -type f ! -name SHA256SUMS -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 -r sha256sum \
        > SHA256SUMS
    )
    checksum_creation_status=$?

    if [ "$checksum_creation_status" -eq 0 ]; then
      (
        cd "$RUN_ROOT" || exit 1
        sha256sum -c SHA256SUMS
      ) > "${PACKAGING_LOG_PREFIX}_internal_checksum_validation.log" 2>&1
      internal_checksum_validation_exit_status=$?
    fi
  fi
fi

echo "manifest_creation_exit_status=$manifest_creation_exit_status"
echo "internal_checksum_validation_exit_status=$internal_checksum_validation_exit_status"
echo "manifest=$RUN_ROOT/MANIFEST.json"
echo "inventory=$RUN_ROOT/FILE_INVENTORY.tsv"
echo "sha256sums=$RUN_ROOT/SHA256SUMS"

section "9. CREATE AND VERIFY DETACHED CANONICAL ARCHIVE"

if [ "$manifest_creation_exit_status" -eq 0 ] && \
   [ "$internal_checksum_validation_exit_status" -eq 0 ]; then

  (
    cd /workspaces || exit 1
    tar -czf "$(basename "$ARCHIVE")" "$RUN_BASENAME"
  )
  candidate_archive_creation_exit_status=$?

  if [ "$candidate_archive_creation_exit_status" -eq 0 ]; then
    (
      cd /workspaces || exit 1
      sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE_SHA")"
      sha256sum -c "$(basename "$ARCHIVE_SHA")"
    ) > "${PACKAGING_LOG_PREFIX}_archive_checksum_validation.log" 2>&1
    candidate_archive_checksum_exit_status=$?
    archive_digest="$(awk '{print $1}' "$ARCHIVE_SHA" 2>/dev/null)"
  fi

  if [ "$candidate_archive_checksum_exit_status" -eq 0 ]; then
    mkdir "$EXTRACT_ROOT"
    extract_mkdir_status=$?
    if [ "$extract_mkdir_status" -eq 0 ]; then
      tar -xzf "$ARCHIVE" -C "$EXTRACT_ROOT"
      candidate_archive_extract_exit_status=$?
    fi
  fi

  if [ "$candidate_archive_extract_exit_status" -eq 0 ]; then
    EXTRACTED_RUN="$EXTRACT_ROOT/$RUN_BASENAME"
    extracted_checksum_status=1
    extracted_diff_status=1
    extracted_validation_status=1

    if [ -d "$EXTRACTED_RUN" ]; then
      (
        cd "$EXTRACTED_RUN" || exit 1
        sha256sum -c SHA256SUMS
      ) > "${PACKAGING_LOG_PREFIX}_extracted_checksum_validation.log" 2>&1
      extracted_checksum_status=$?

      diff -qr "$RUN_ROOT" "$EXTRACTED_RUN" \
        > "${PACKAGING_LOG_PREFIX}_extracted_tree_diff.log" 2>&1
      extracted_diff_status=$?

      EXTRACTED_RUN="$EXTRACTED_RUN" "$PYTHON" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["EXTRACTED_RUN"])
validation = json.loads(
    (root / "validation" / "robustness_validation.json").read_text(encoding="utf-8")
)
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))

assert validation["scientific_validation_pass"] is True
assert validation["source_commit"] == "185290880a75d6df17c03aad6abbb44ca3818bf0"
assert manifest["scientific_validation"] == "PASS"
assert manifest["source_commit"] == validation["source_commit"]
assert manifest["repeats"] == 30
assert manifest["seed"] == 42
print("extracted_bundle_semantic_validation=PASS")
PY
      extracted_validation_status=$?
    fi

    if [ "$extracted_checksum_status" -eq 0 ] && \
       [ "$extracted_diff_status" -eq 0 ] && \
       [ "$extracted_validation_status" -eq 0 ]; then
      candidate_archive_internal_validation_exit_status=0
    fi

    echo "extracted_checksum_validation_exit_status=$extracted_checksum_status"
    echo "extracted_tree_diff_exit_status=$extracted_diff_status"
    echo "extracted_semantic_validation_exit_status=$extracted_validation_status"
  fi
fi

echo "candidate_archive_creation_exit_status=$candidate_archive_creation_exit_status"
echo "candidate_archive_checksum_exit_status=$candidate_archive_checksum_exit_status"
echo "candidate_archive_extract_exit_status=$candidate_archive_extract_exit_status"
echo "candidate_archive_internal_validation_exit_status=$candidate_archive_internal_validation_exit_status"
echo "candidate_archive=$ARCHIVE"
echo "candidate_archive_sha256=$archive_digest"
echo "candidate_archive_sha256_file=$ARCHIVE_SHA"
echo "candidate_archive_extract_root=$EXTRACT_ROOT"

section "10. FINAL FREEZE DECISION"

final_status=0
[ "$repository_gate_exit_status" -eq 0 ] || final_status=1
[ "$run_root_initialization_exit_status" -eq 0 ] || final_status=1
[ "$provenance_capture_exit_status" -eq 0 ] || final_status=1
[ "$preflight_compile_exit_status" -eq 0 ] || final_status=1
[ "$preflight_diff_check_exit_status" -eq 0 ] || final_status=1
[ "$preflight_tests_exit_status" -eq 0 ] || final_status=1
[ "$robustness_campaign_exit_status" -eq 0 ] || final_status=1
[ "$robustness_output_validation_exit_status" -eq 0 ] || final_status=1
[ "$repository_clean_after_campaign_exit_status" -eq 0 ] || final_status=1
[ "$diagnostic_run_unchanged_exit_status" -eq 0 ] || final_status=1
[ "$manifest_creation_exit_status" -eq 0 ] || final_status=1
[ "$internal_checksum_validation_exit_status" -eq 0 ] || final_status=1
[ "$candidate_archive_creation_exit_status" -eq 0 ] || final_status=1
[ "$candidate_archive_checksum_exit_status" -eq 0 ] || final_status=1
[ "$candidate_archive_extract_exit_status" -eq 0 ] || final_status=1
[ "$candidate_archive_internal_validation_exit_status" -eq 0 ] || final_status=1

robustness_canonical_final_exit_status=$final_status

if [ "$final_status" -eq 0 ]; then
  scientific_freeze=true
  next_stage="verify_and_publish_robustness_commits_without_merging"
else
  scientific_freeze=false
  if [ "$repository_gate_exit_status" -ne 0 ]; then
    next_stage="inspect_repository_gate_failure"
  elif [ "$preflight_tests_exit_status" -ne 0 ]; then
    next_stage="inspect_preflight_test_failure"
  elif [ "$robustness_campaign_exit_status" -ne 0 ]; then
    next_stage="inspect_robustness_campaign_log"
  elif [ "$repository_clean_after_campaign_exit_status" -ne 0 ]; then
    next_stage="inspect_repository_delta"
  elif [ "$diagnostic_run_unchanged_exit_status" -ne 0 ]; then
    next_stage="inspect_diagnostic_run_integrity"
  elif [ "$robustness_output_validation_exit_status" -ne 0 ]; then
    next_stage="inspect_exact_validation_failure"
  else
    next_stage="inspect_manifest_or_archive_failure"
  fi
fi

if [ "$final_status" -eq 0 ]; then
  FREEZE_JSON="$FREEZE_JSON" \
  FREEZE_MD="$FREEZE_MD" \
  RUN_ROOT="$RUN_ROOT" \
  ARCHIVE="$ARCHIVE" \
  ARCHIVE_SHA="$ARCHIVE_SHA" \
  ARCHIVE_DIGEST="$archive_digest" \
  EXPECTED_HEAD="$EXPECTED_HEAD" \
  "$PYTHON" - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "schema": "mcad.robustness.canonical.freeze-certificate.v1",
    "issued_at_utc": datetime.now(timezone.utc).isoformat(),
    "scientific_freeze": True,
    "freeze_scope": "robustness_non_temporal",
    "global_scientific_freeze": False,
    "latency_claim_authorized": False,
    "source_commit": os.environ["EXPECTED_HEAD"],
    "run_root": os.environ["RUN_ROOT"],
    "archive": os.environ["ARCHIVE"],
    "archive_sha256_file": os.environ["ARCHIVE_SHA"],
    "archive_sha256": os.environ["ARCHIVE_DIGEST"],
    "repeats": 30,
    "seed": 42,
    "campaign_status": 0,
    "output_validation_status": 0,
    "repository_clean_status": 0,
    "diagnostic_run_unchanged_status": 0,
    "manifest_status": 0,
    "internal_checksum_status": 0,
    "archive_creation_status": 0,
    "archive_checksum_status": 0,
    "archive_extract_status": 0,
    "archive_internal_validation_status": 0,
}
Path(os.environ["FREEZE_JSON"]).write_text(
    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
Path(os.environ["FREEZE_MD"]).write_text(
    "# MCAD canonical robustness freeze certificate\n\n"
    "- Robustness scientific freeze: **true**\n"
    "- Freeze scope: `robustness_non_temporal`\n"
    "- Global scientific freeze: **false**\n"
    "- Latency claim authorized: **false**\n"
    f"- Source commit: `{payload['source_commit']}`\n"
    f"- Run root: `{payload['run_root']}`\n"
    f"- Archive: `{payload['archive']}`\n"
    f"- Archive SHA-256: `{payload['archive_sha256']}`\n"
    "- Repeats: `30`\n"
    "- Seed: `42`\n",
    encoding="utf-8",
)
PY
  freeze_certificate_creation_exit_status=$?

  if [ "$freeze_certificate_creation_exit_status" -eq 0 ]; then
    (
      cd /workspaces || exit 1
      sha256sum \
        "$(basename "$FREEZE_JSON")" \
        "$(basename "$FREEZE_MD")" \
        > "$(basename "$FREEZE_SHA")"
      sha256sum -c "$(basename "$FREEZE_SHA")"
    ) > /workspaces/"${RUN_BASENAME}_FREEZE_checksum_validation.log" 2>&1
    freeze_certificate_creation_exit_status=$?
  fi

  if [ "$freeze_certificate_creation_exit_status" -ne 0 ]; then
    robustness_canonical_final_exit_status=1
    scientific_freeze=false
    next_stage="inspect_freeze_certificate_failure"
  fi
fi

echo "robustness_campaign_exit_status=$robustness_campaign_exit_status"
echo "robustness_output_validation_exit_status=$robustness_output_validation_exit_status"
echo "repository_clean_after_campaign_exit_status=$repository_clean_after_campaign_exit_status"
echo "diagnostic_run_unchanged_exit_status=$diagnostic_run_unchanged_exit_status"
echo "manifest_creation_exit_status=$manifest_creation_exit_status"
echo "internal_checksum_validation_exit_status=$internal_checksum_validation_exit_status"
echo "candidate_archive_creation_exit_status=$candidate_archive_creation_exit_status"
echo "candidate_archive_checksum_exit_status=$candidate_archive_checksum_exit_status"
echo "candidate_archive_extract_exit_status=$candidate_archive_extract_exit_status"
echo "candidate_archive_internal_validation_exit_status=$candidate_archive_internal_validation_exit_status"
echo "freeze_certificate_creation_exit_status=$freeze_certificate_creation_exit_status"
echo "robustness_canonical_final_exit_status=$robustness_canonical_final_exit_status"
echo "scientific_freeze=$scientific_freeze"
echo "freeze_scope=robustness_non_temporal"
echo "global_scientific_freeze=false"
echo "latency_claim_authorized=false"
echo "next_stage=$next_stage"
echo "run_root=$RUN_ROOT"
echo "archive=$ARCHIVE"
echo "archive_sha256_file=$ARCHIVE_SHA"
echo "freeze_certificate_json=$FREEZE_JSON"
echo "freeze_certificate_markdown=$FREEZE_MD"
echo "freeze_certificate_sha256_file=$FREEZE_SHA"

section "11. FINAL REPOSITORY STATE"

cd "$REPO" || true
git status --short --branch
git log -5 --oneline --decorate

exit "$robustness_canonical_final_exit_status"
