from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/workspaces/MCAD_improve3").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE = "paper/phase3-controlled-execution"
EXPECTED_HEAD = "fd7d87e5658b63c0753a9686b43ec2e5e2d17344"

E3 = Path("reports/article_experiments/sensitivity/e3_controlled_execution")
PLAN = E3 / "planning"

PREREG = PLAN / "sa5_objective_count_stage20_extension_preregistration.json"
PREREG_SHA = "e27c3c4acb69608207b4cbe04da9f7748d4e4e935e2f634a4bd5a27252c7e148"
PREREG_MD = PLAN / "sa5_objective_count_stage20_extension_preregistration.md"
PREREG_MD_SHA = "b6cc60f6c75327affb98e31179eef6b684dc5f01e7d852c748bb5612d3dcfd1e"
EXEC_PLAN = PLAN / "sa5_objective_count_stage20_execution_plan.json"
EXEC_PLAN_SHA = "64ebee568a11bd6427bfbfa5f219a224e167ca9d3aab5106f21b0ce08969b1a1"

ANALYZER = Path(
    "backend/harness/sensitivity_execution/"
    "analyze_clustered_timing_precision_v2_factor_compatible.py"
)
ANALYZER_SHA = "841d3f59f7195c262befc8a32602eae68d8a28538631c8c21dd7af8c1c00923f"

TIMING_RUNNER = Path(
    "backend/harness/sensitivity_execution/run_timing_repetitions.py"
)
TIMING_RUNNER_SHA = "6332cc63f8e50ee25df782b3b34b7110c7f5abb4af25bb6fcfd5cde5d18a7595"

STAGE10_CAMPAIGN = E3 / "campaigns/objective_count_stage10_c8_nv32"
STAGE10_WORKLOADS = STAGE10_CAMPAIGN / "common_workloads"
STAGE10_SPECS = E3 / "execution_specs"
STAGE10_TIMING_ROOT = E3 / "timing_runs/objective_count_stage10_portfolio"

# All Stage-20 runtime material is kept under ignored reports/ paths so that:
# 1) the canonical tracked tree remains unchanged during science;
# 2) a later persistence step can force-add only the evidence that must be frozen.
WORK = E3 / "stage20_work/objective_count_stage20_fd7d87e"
FULL_CAMPAIGN = WORK / "full20_campaign"
FULL_WORKLOADS = FULL_CAMPAIGN / "common_workloads"
SUFFIX_SPECS = WORK / "execution_specs"
SUFFIX_RUNS = WORK / "functional_runs"
SUFFIX_TIMING = WORK / "timing_runs"
LOGS = WORK / "logs"
DONE = WORK / "done"

MATERIALIZATION_DONE = WORK / "STAGE20_MATERIALIZATION_COMPLETE.json"

OUT = E3 / "audits/objective_count/timing_stage20/precision_analysis"
STARTED = OUT / "SA5_STAGE20_EXECUTION_STARTED.json"
PRECISION_STARTED = OUT / "SA5_STAGE20_PRECISION_STARTED.json"
ANALYZER_LOG = OUT / "sa5_stage20_precision_analyzer.log"
INTERVALS = OUT / "sa5_stage20_precision_intervals.csv"
REPORT_JSON = OUT / "sa5_stage20_precision_report.json"
REPORT_MD = OUT / "sa5_stage20_precision_report.md"
MANIFEST = OUT / "SA5_STAGE20_EXECUTION_MANIFEST.json"
SUFFIX_MANIFEST = OUT / "SA5_STAGE20_SUFFIX_EVIDENCE_MANIFEST.json"

COMBINED_OBS = WORK / "stage20_combined_measurement_observations.csv"
TIMING_ADAPTER = WORK / "stage20_precision_timing_report_adapter.json"

LEVELS = [1, 2, 5, 10, 20, 50]
STEPS = list(range(1, 33))
STAGE10_SEEDS = [
    101,
    202,
    1198202409,
    796786883,
    1126922093,
    809989256,
    618554674,
    1363159082,
    874332939,
    1767972531,
]
NEW_SEEDS = [
    630497049,
    1826704550,
    668799093,
    1989792316,
    625293714,
    578407288,
    1347026516,
    1457944287,
    134577186,
    1985010596,
]
STAGE20_SEEDS = STAGE10_SEEDS + NEW_SEEDS
NEW_REPS = list(range(10, 20))

SOURCE_HEADER = [
    "phase",
    "phase_round",
    "order_position",
    "observation_index",
    "cell_id",
    "canonical_instance_id",
    "factor_level",
    "replication_index",
    "seed",
    "step_position",
    "step_index",
    "step_id",
    "prefix_step_count",
    "fresh_state",
    "wall_latency_ns",
    "wall_latency_ms",
    "cpu_latency_ns",
    "cpu_latency_ms",
    "semantic_digest",
    "semantic_match",
]
OUT_HEADER = SOURCE_HEADER + [
    "formal_replication_index",
    "formal_structural_seed",
]

OPERATOR_CONFIRMATION = "oui, j’autorise l’exécution Stage-20 SA5"


def p(rel: Path) -> Path:
    return ROOT / rel


def utcnow() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_sha256(root: Path) -> str:
    h = hashlib.sha256()
    files = sorted(q for q in root.rglob("*") if q.is_file())
    for q in files:
        rel = q.relative_to(root).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        h.update(bytes.fromhex(sha256(q)))
    return h.hexdigest()


def write_json(path: Path, payload: dict[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as f:
        json.dump(
            payload,
            f,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        f.write("\n")
        f.flush()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: list[str]) -> str:
    cp = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    return cp.stdout.strip()


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def verify_sha(rel: Path, expected: str) -> None:
    q = p(rel)
    if not q.is_file():
        raise SystemExit(f"[ERROR] missing required file: {rel}")
    actual = sha256(q)
    if actual != expected:
        raise SystemExit(
            f"[ERROR] SHA mismatch for {rel}: actual={actual}, expected={expected}"
        )


def heartbeat_process(
    cmd: list[str],
    log_path: Path,
    *,
    label: str,
    heartbeat_seconds: int = 300,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if log_path.exists() else "w"
    with log_path.open(mode, encoding="utf-8") as log:
        if mode == "a":
            log.write("\n=== RESUMED INVOCATION ===\n")
        log.flush()
        started = time.monotonic()
        next_heartbeat = started
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"},
        )
        while True:
            rc = proc.poll()
            if rc is not None:
                return int(rc)
            now = time.monotonic()
            if now >= next_heartbeat:
                elapsed = int(now - started)
                print(
                    f"{label}_heartbeat elapsed_seconds={elapsed} pid={proc.pid}",
                    flush=True,
                )
                next_heartbeat = now + heartbeat_seconds
            time.sleep(2)


def validate_timing_csv(path: Path, rep: int, seed: int) -> dict[str, Any]:
    counts: Counter[tuple[str, int, int]] = Counter()
    rows = 0
    measurement = 0
    warmup = 0
    semantic_false = 0
    measurement_fresh_false = 0
    observed_reps: set[int] = set()
    observed_seeds: set[int] = set()
    observed_levels: set[int] = set()
    observed_steps: set[int] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SOURCE_HEADER:
            raise SystemExit(
                f"[ERROR] timing header mismatch rep={rep}: {reader.fieldnames}"
            )
        for row in reader:
            rows += 1
            phase = row["phase"].strip()
            level = int(row["factor_level"])
            step = int(row["step_index"])
            r = int(row["replication_index"])
            s = int(row["seed"])
            observed_reps.add(r)
            observed_seeds.add(s)
            observed_levels.add(level)
            observed_steps.add(step)
            counts[(phase, level, step)] += 1

            if not truthy(row["semantic_match"]):
                semantic_false += 1

            if phase == "measurement":
                measurement += 1
                if not truthy(row["fresh_state"]):
                    measurement_fresh_false += 1
            elif phase == "warmup":
                warmup += 1
            else:
                raise SystemExit(
                    f"[ERROR] unexpected timing phase rep={rep}: {phase!r}"
                )

    if rows != 21120:
        raise SystemExit(f"[ERROR] rep {rep} timing rows={rows}, expected=21120")
    if measurement != 19200:
        raise SystemExit(
            f"[ERROR] rep {rep} measurement rows={measurement}, expected=19200"
        )
    if warmup != 1920:
        raise SystemExit(f"[ERROR] rep {rep} warmup rows={warmup}, expected=1920")
    if observed_reps != {rep}:
        raise SystemExit(
            f"[ERROR] rep identity mismatch: expected={rep}, actual={observed_reps}"
        )
    if observed_seeds != {seed}:
        raise SystemExit(
            f"[ERROR] seed mismatch rep={rep}: expected={seed}, actual={observed_seeds}"
        )
    if observed_levels != set(LEVELS):
        raise SystemExit(f"[ERROR] level set mismatch rep={rep}")
    if observed_steps != set(STEPS):
        raise SystemExit(f"[ERROR] step set mismatch rep={rep}")
    if semantic_false != 0:
        raise SystemExit(
            f"[ERROR] semantic mismatch rows rep={rep}: {semantic_false}"
        )
    if measurement_fresh_false != 0:
        raise SystemExit(
            f"[ERROR] non-fresh measurement rows rep={rep}: "
            f"{measurement_fresh_false}"
        )

    for level in LEVELS:
        for step in STEPS:
            if counts[("measurement", level, step)] != 100:
                raise SystemExit(
                    f"[ERROR] measurement balance rep={rep}, level={level}, "
                    f"step={step}: {counts[('measurement', level, step)]}"
                )
            if counts[("warmup", level, step)] != 10:
                raise SystemExit(
                    f"[ERROR] warmup balance rep={rep}, level={level}, "
                    f"step={step}: {counts[('warmup', level, step)]}"
                )

    return {
        "replication_index": rep,
        "seed": seed,
        "row_count": rows,
        "measurement_row_count": measurement,
        "warmup_row_count": warmup,
        "functional_mismatch_count": semantic_false,
        "measurement_fresh_false_count": measurement_fresh_false,
        "sha256": sha256(path),
    }


def validate_functional_done(rep: int, seed: int, run_dir: Path) -> dict[str, Any]:
    required = [
        run_dir / "execution_manifest.json",
        run_dir / "campaign_metrics.json",
        run_dir / "instance_results.csv",
    ]
    for q in required:
        if not q.is_file() or q.stat().st_size == 0:
            raise SystemExit(
                f"[ERROR] incomplete functional evidence rep={rep}: {q}"
            )

    with (run_dir / "instance_results.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 6:
        raise SystemExit(
            f"[ERROR] functional instance count rep={rep}: {len(rows)}"
        )

    instance_dirs = [
        q for q in (run_dir / "instances").glob("*/*")
        if q.is_dir()
    ]
    if len(instance_dirs) != 6:
        raise SystemExit(
            f"[ERROR] functional instance directories rep={rep}: "
            f"{len(instance_dirs)}"
        )

    for q in instance_dirs:
        for name in ("audit.json", "execution_manifest.json", "metrics.json", "timeline.json"):
            if not (q / name).is_file():
                raise SystemExit(
                    f"[ERROR] missing functional instance artifact rep={rep}: "
                    f"{q / name}"
                )

    return {
        "replication_index": rep,
        "seed": seed,
        "file_count": sum(1 for q in run_dir.rglob("*") if q.is_file()),
        "tree_sha256": tree_sha256(run_dir),
    }


print("=== 1. Exact merged Stage-20 authorization gate ===", flush=True)

run(["git", "fetch", "origin", "--prune"])
if run(["git", "branch", "--show-current"]) != BASE:
    raise SystemExit("[ERROR] wrong canonical branch")
if run(["git", "rev-parse", "HEAD"]) != EXPECTED_HEAD:
    raise SystemExit("[ERROR] wrong canonical HEAD")
if run(["git", "rev-parse", f"origin/{BASE}"]) != EXPECTED_HEAD:
    raise SystemExit("[ERROR] remote canonical HEAD moved")
if run(["git", "status", "--porcelain"]):
    raise SystemExit("[ERROR] tracked/untracked repository state is not clean")

verify_sha(PREREG, PREREG_SHA)
verify_sha(PREREG_MD, PREREG_MD_SHA)
verify_sha(EXEC_PLAN, EXEC_PLAN_SHA)
verify_sha(ANALYZER, ANALYZER_SHA)
verify_sha(TIMING_RUNNER, TIMING_RUNNER_SHA)

for pattern in (
    "python.*[r]un_timing_repetitions",
    "python.*[a]nalyze_clustered_timing_precision",
):
    cp = subprocess.run(
        ["pgrep", "-f", pattern],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if cp.returncode == 0 and cp.stdout.strip():
        raise SystemExit(f"[ERROR] active scientific process detected: {pattern}")

prereg = load_json(p(PREREG))
plan = load_json(p(EXEC_PLAN))

if prereg.get("status") != "pending_merge":
    raise SystemExit("[ERROR] unexpected Stage-20 preregistration status")
authorization = prereg.get("authorization", {})
protocol = prereg.get("protocol", {})

if authorization.get("effective_after_merge") is not True:
    raise SystemExit("[ERROR] Stage-20 authorization is not effective after merge")
if authorization.get(
    "explicit_operator_confirmation_after_merge_required"
) is not True:
    raise SystemExit("[ERROR] explicit confirmation contract mismatch")

expected_protocol = {
    "stage20_total_replications": 20,
    "stage20_new_replications": NEW_REPS,
    "stage20_seeds": STAGE20_SEEDS,
    "stage20_new_seeds": NEW_SEEDS,
    "prefix_reuse_required": True,
    "prefix_functional_rerun_authorized": False,
    "prefix_timing_rerun_authorized": False,
    "warmup_rows_per_seed_level_step": 10,
    "measurement_rows_per_seed_level_step": 100,
    "expected_stage20_combined_measurement_rows": 384000,
    "bootstrap_repetitions": 10000,
    "bootstrap_seed": 20260728,
    "confidence_level": 0.95,
    "median_relative_half_width_target": 0.10,
    "p95_relative_half_width_target": 0.15,
    "maximum_protocol_stage": 30,
    "stage30_execution_authorized_now": False,
}
for key, expected in expected_protocol.items():
    if protocol.get(key) != expected:
        raise SystemExit(
            f"[ERROR] frozen Stage-20 contract mismatch: {key}: "
            f"{protocol.get(key)!r} != {expected!r}"
        )

if plan.get("execution_performed") is not False:
    raise SystemExit("[ERROR] Stage-20 plan already records execution")
if plan.get("protocol", {}).get("stage20_seeds") != STAGE20_SEEDS:
    raise SystemExit("[ERROR] Stage-20 execution plan seed schedule mismatch")

print("stage20_authorization_gate=PASS")
print("operator_confirmation_received=true")
print(f"operator_confirmation={OPERATOR_CONFIRMATION}")
print("stage10_prefix_rerun_forbidden=true")
print("stage20_new_replications=10,11,12,13,14,15,16,17,18,19")
print("stage20_total_cluster_count=20")
print("stage20_combined_measurement_rows=384000")
print("bootstrap_repetitions=10000")
print("maximum_protocol_stage=30")


print("\n=== 2. Revalidate immutable Stage-10 timing prefix ===", flush=True)

prefix_files = sorted(
    p(STAGE10_TIMING_ROOT).glob(
        "objective_count_rep_*_portfolio_timing_stage10/timing_observations.csv"
    )
)
if len(prefix_files) != 10:
    raise SystemExit(
        f"[ERROR] expected 10 Stage-10 timing CSVs, got {len(prefix_files)}"
    )

prefix_audit: list[dict[str, Any]] = []
for rep, source in enumerate(prefix_files):
    prefix_audit.append(
        validate_timing_csv(source, rep, STAGE10_SEEDS[rep])
    )

if sum(x["measurement_row_count"] for x in prefix_audit) != 192000:
    raise SystemExit("[ERROR] Stage-10 prefix measurement total mismatch")
if sum(x["warmup_row_count"] for x in prefix_audit) != 19200:
    raise SystemExit("[ERROR] Stage-10 prefix warmup total mismatch")

print("stage10_prefix_timing_gate=PASS")
print("stage10_prefix_replication_count=10")
print("stage10_prefix_measurement_rows=192000")
print("stage10_prefix_warmup_rows=19200")
print("stage10_prefix_modified=false")


print("\n=== 3. Materialize and validate detached full-20 structural source ===", flush=True)

if p(PRECISION_STARTED).exists():
    raise SystemExit(
        "[ERROR] SA5 Stage-20 precision start marker already exists. "
        "DO NOT RERUN THIS CONTROLLER."
    )

work = p(WORK)
full_campaign = p(FULL_CAMPAIGN)
full_workloads = p(FULL_WORKLOADS)
suffix_specs = p(SUFFIX_SPECS)
suffix_runs = p(SUFFIX_RUNS)
suffix_timing = p(SUFFIX_TIMING)
logs = p(LOGS)
done = p(DONE)

if not p(MATERIALIZATION_DONE).exists():
    if p(STARTED).exists():
        raise SystemExit(
            "[ERROR] Stage-20 execution marker exists but materialization "
            "completion marker is absent; manual review required."
        )

    if work.exists():
        shutil.rmtree(work)

    for q in (
        full_campaign,
        suffix_specs,
        suffix_runs,
        suffix_timing,
        logs,
        done,
    ):
        q.mkdir(parents=True, exist_ok=True)

    from backend.harness.sensitivity_generator.families.controlled_families import (
        ControlledFamilySpec,
        generate_controlled_family,
    )
    from backend.harness.sensitivity_execution.tools.prepare_objective_count_stage10_common_workloads_v2 import (
        prepare_common_workloads,
    )
    from backend.harness.sensitivity_execution.execute_controlled_family import (
        load_execution_inputs,
    )
    from backend.harness.sensitivity_execution.validate_execution_spec import (
        validate_execution_spec,
    )

    manifest = generate_controlled_family(
        ControlledFamilySpec(
            # Stage-20 is a replication extension of the same objective-count
            # design. Keep the scientific campaign id stable; only the
            # replication schedule is extended.
            campaign_id="objective_count_stage10_c8_nv32",
            factor="objective_count",
            levels=tuple(LEVELS),
            seeds=tuple(STAGE20_SEEDS),
            baseline_constraint_count=8,
            baseline_virtual_node_count=32,
            output_dir=str(full_campaign),
        )
    )

    if tuple(manifest.levels) != tuple(LEVELS):
        raise SystemExit("[ERROR] generated Stage-20 level set mismatch")
    if tuple(manifest.seeds) != tuple(STAGE20_SEEDS):
        raise SystemExit("[ERROR] generated Stage-20 seed schedule mismatch")
    if manifest.replication_count != 20:
        raise SystemExit("[ERROR] generated Stage-20 replication count mismatch")
    if manifest.realised_instance_count != 120:
        raise SystemExit("[ERROR] generated Stage-20 instance count mismatch")

    workload_manifest = prepare_common_workloads(
        full_campaign,
        full_workloads,
    )
    if workload_manifest.get("workload_count") != 20:
        raise SystemExit(
            "[ERROR] Stage-20 common-workload count mismatch: "
            f"{workload_manifest.get('workload_count')}"
        )
    if workload_manifest.get("workload_length") != 32:
        raise SystemExit("[ERROR] Stage-20 workload length mismatch")
    entries = workload_manifest.get("entries", [])
    if [int(x["replication_index"]) for x in entries] != list(range(20)):
        raise SystemExit("[ERROR] Stage-20 workload replication schedule mismatch")
    if [int(x["seed"]) for x in entries] != STAGE20_SEEDS:
        raise SystemExit("[ERROR] Stage-20 workload seed schedule mismatch")

    # Strong prefix preservation proof: the regenerated first ten structures
    # and common workloads must be byte-identical to the committed Stage-10
    # evidence. The committed prefix itself is never regenerated or modified.
    def rows_by_key(csv_path: Path) -> dict[tuple[int, int], dict[str, str]]:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return {
            (int(r["replication_index"]), int(r["factor_level"])): r
            for r in rows
        }

    old_rows = rows_by_key(p(STAGE10_CAMPAIGN) / "instances.csv")
    new_rows = rows_by_key(full_campaign / "instances.csv")

    for rep in range(10):
        for level in LEVELS:
            old = old_rows[(rep, level)]
            new = new_rows[(rep, level)]
            old_obj = p(STAGE10_CAMPAIGN) / old["relative_instance_dir"] / "objectives.yaml"
            new_obj = full_campaign / new["relative_instance_dir"] / "objectives.yaml"
            if old_obj.read_bytes() != new_obj.read_bytes():
                raise SystemExit(
                    f"[ERROR] Stage-10 structural prefix mismatch rep={rep}, "
                    f"level={level}"
                )

        old_workload = (
            p(STAGE10_WORKLOADS)
            / f"replication_{rep:03d}_seed_{STAGE10_SEEDS[rep]}.json"
        )
        new_workload = (
            full_workloads
            / f"replication_{rep:03d}_seed_{STAGE10_SEEDS[rep]}.json"
        )
        if old_workload.read_bytes() != new_workload.read_bytes():
            raise SystemExit(
                f"[ERROR] Stage-10 workload prefix mismatch rep={rep}"
            )

    generated_rows = rows_by_key(full_campaign / "instances.csv")
    base_spec = load_json(
        p(STAGE10_SPECS) / "objective_count_stage10_rep_000_canonical.json"
    )
    contract_version = base_spec["contract_version"]

    workload_entries = {
        int(x["replication_index"]): x
        for x in entries
    }

    for rep in NEW_REPS:
        seed = STAGE20_SEEDS[rep]
        selected_rows = [
            generated_rows[(rep, level)]
            for level in LEVELS
        ]
        workload_entry = workload_entries[rep]
        workload_filename = str(workload_entry["workload_path"])
        workload_path = full_workloads / workload_filename
        run_dir = suffix_runs / f"objective_count_stage20_rep_{rep:03d}_canonical"

        payload = {
            "contract_version": contract_version,
            "execution_id": (
                f"sa5-objective-count-stage20-rep_{rep:03d}-canonical-v1"
            ),
            "campaign_dir": str(full_campaign.resolve()),
            "workload_path": str(workload_path.resolve()),
            "output_dir": str(run_dir.resolve()),
            "instance_selection": {
                "instance_ids": [
                    row["relative_instance_dir"]
                    for row in selected_rows
                ]
            },
            "continue_on_instance_failure": False,
        }

        spec_path = suffix_specs / f"objective_count_stage20_rep_{rep:03d}_canonical.json"
        write_json(spec_path, payload)
        validate_execution_spec(payload)
        inputs = load_execution_inputs(spec_path)

        if len(inputs.instances) != 6:
            raise SystemExit(f"[ERROR] spec instance count rep={rep}")
        if [x.factor_level for x in inputs.instances] != LEVELS:
            raise SystemExit(f"[ERROR] spec level order rep={rep}")
        if {x.replication_index for x in inputs.instances} != {rep}:
            raise SystemExit(f"[ERROR] spec replication identity rep={rep}")
        if {x.seed for x in inputs.instances} != {seed}:
            raise SystemExit(f"[ERROR] spec seed identity rep={rep}")
        if inputs.output_dir != run_dir.resolve():
            raise SystemExit(f"[ERROR] spec output path rep={rep}")

    materialization_payload = {
        "schema_version":
            "mcad-sa5-objective-count-stage20-runtime-materialization-v1",
        "status": "stage20_runtime_materialization_complete",
        "created_at_utc": utcnow(),
        "canonical_head": EXPECTED_HEAD,
        "full20_replication_count": 20,
        "full20_instance_count": 120,
        "stage10_prefix_replication_count": 10,
        "stage10_prefix_structure_byte_identity": True,
        "stage10_prefix_workload_byte_identity": True,
        "new_suffix_replications": NEW_REPS,
        "new_suffix_seeds": NEW_SEEDS,
        "new_suffix_execution_spec_count": 10,
        "scientific_execution_performed": False,
        "timing_execution_performed": False,
        "precision_analysis_performed": False,
    }
    write_json(p(MATERIALIZATION_DONE), materialization_payload, exclusive=True)
else:
    materialization_payload = load_json(p(MATERIALIZATION_DONE))
    if materialization_payload.get("canonical_head") != EXPECTED_HEAD:
        raise SystemExit("[ERROR] stale Stage-20 runtime materialization")
    if materialization_payload.get(
        "stage10_prefix_structure_byte_identity"
    ) is not True:
        raise SystemExit("[ERROR] Stage-10 prefix identity not established")
    if materialization_payload.get("new_suffix_seeds") != NEW_SEEDS:
        raise SystemExit("[ERROR] runtime suffix seed schedule mismatch")
    for rep in NEW_REPS:
        spec_path = suffix_specs / f"objective_count_stage20_rep_{rep:03d}_canonical.json"
        if not spec_path.is_file():
            raise SystemExit(f"[ERROR] missing runtime spec rep={rep}")

print("stage20_runtime_materialization=PASS")
print("stage10_prefix_structure_byte_identity=true")
print("stage10_prefix_workload_byte_identity=true")
print("stage20_full_structural_source_replications=20")
print("stage20_new_suffix_spec_count=10")
print("scientific_execution_performed=false")


print("\n=== 4. Mark Stage-20 suffix execution as started ===", flush=True)

p(OUT).mkdir(parents=True, exist_ok=True)

if not p(STARTED).exists():
    write_json(
        p(STARTED),
        {
            "schema_version":
                "mcad-sa5-objective-count-stage20-execution-start-v1",
            "status": "stage20_suffix_execution_started",
            "started_at_utc": utcnow(),
            "canonical_branch": BASE,
            "canonical_head": EXPECTED_HEAD,
            "operator_confirmation_received": True,
            "operator_confirmation": OPERATOR_CONFIRMATION,
            "stage10_prefix_rerun_forbidden": True,
            "stage20_new_replications": NEW_REPS,
            "stage20_new_seeds": NEW_SEEDS,
            "stage20_precision_started": False,
            "stage20_rerun_on_precision_failure_authorized": False,
        },
        exclusive=True,
    )
else:
    started = load_json(p(STARTED))
    if started.get("canonical_head") != EXPECTED_HEAD:
        raise SystemExit("[ERROR] stale Stage-20 execution marker")
    if started.get("stage20_new_seeds") != NEW_SEEDS:
        raise SystemExit("[ERROR] Stage-20 execution marker seed mismatch")

print("stage20_execution_start_marker=PASS")
print(f"stage20_execution_start_marker_sha256={sha256(p(STARTED))}")
print("stage20_suffix_execution_started=true")
print(
    "suffix_execution_resumption_policy="
    "completed_functional_reps_skipped;timing_uses_reuse_successful"
)


print("\n=== 5. Execute/validate functional suffix replications 10..19 ===", flush=True)

functional_rows: list[dict[str, Any]] = []

for rep in NEW_REPS:
    seed = STAGE20_SEEDS[rep]
    token = f"{rep:03d}"
    spec_path = suffix_specs / f"objective_count_stage20_rep_{token}_canonical.json"
    run_dir = suffix_runs / f"objective_count_stage20_rep_{token}_canonical"
    log_path = logs / f"functional_rep_{token}.log"
    done_path = done / f"functional_rep_{token}.json"

    if done_path.exists():
        done_payload = load_json(done_path)
        if done_payload.get("replication_index") != rep:
            raise SystemExit(f"[ERROR] stale functional done marker rep={rep}")
        row = validate_functional_done(rep, seed, run_dir)
        if row["tree_sha256"] != done_payload.get("tree_sha256"):
            raise SystemExit(
                f"[ERROR] functional evidence changed after completion rep={rep}"
            )
        print(f"functional_rep_{token}=REUSED_COMPLETE", flush=True)
        functional_rows.append(row)
        continue

    if run_dir.exists():
        raise SystemExit(
            f"[ERROR] functional output exists without completion marker rep={rep}. "
            "Do not delete or rerun automatically; review required."
        )

    cmd = [
        sys.executable,
        "-m",
        "backend.harness.sensitivity_execution.execute_controlled_family",
        str(spec_path),
    ]
    print(f"functional_rep_{token}=START", flush=True)
    rc = heartbeat_process(
        cmd,
        log_path,
        label=f"functional_rep_{token}",
        heartbeat_seconds=30,
    )
    if rc != 0:
        raise SystemExit(
            f"[ERROR] functional suffix execution failed rep={rep}, rc={rc}; "
            f"log={log_path}"
        )

    text = log_path.read_text(encoding="utf-8", errors="replace")
    required_log_tokens = [
        "[OK] E3 controlled execution completed.",
        "[OK] selected_instance_count=6",
        "[OK] step_count=192",
    ]
    for item in required_log_tokens:
        if item not in text:
            raise SystemExit(
                f"[ERROR] functional success token missing rep={rep}: {item}"
            )

    row = validate_functional_done(rep, seed, run_dir)
    write_json(
        done_path,
        {
            "status": "functional_replication_complete",
            "completed_at_utc": utcnow(),
            **row,
            "spec_sha256": sha256(spec_path),
            "log_sha256": sha256(log_path),
        },
        exclusive=True,
    )
    functional_rows.append(row)
    print(f"functional_rep_{token}=PASS", flush=True)

if len(functional_rows) != 10:
    raise SystemExit("[ERROR] functional suffix completion count mismatch")

print("stage20_functional_suffix=PASS")
print("stage20_functional_suffix_replication_count=10")
print("stage10_functional_prefix_rerun=false")


print("\n=== 6. Execute/resume timing suffix replications 10..19 ===", flush=True)

timing_rows: list[dict[str, Any]] = []

for rep in NEW_REPS:
    seed = STAGE20_SEEDS[rep]
    token = f"{rep:03d}"
    spec_path = suffix_specs / f"objective_count_stage20_rep_{token}_canonical.json"
    output_dir = suffix_timing / f"objective_count_rep_{token}_portfolio_timing_stage20"
    log_path = logs / f"timing_rep_{token}.log"
    done_path = done / f"timing_rep_{token}.json"

    if done_path.exists():
        payload = load_json(done_path)
        if payload.get("replication_index") != rep:
            raise SystemExit(f"[ERROR] stale timing done marker rep={rep}")
        row = validate_timing_csv(
            output_dir / "timing_observations.csv",
            rep,
            seed,
        )
        if row["sha256"] != payload.get("observations_sha256"):
            raise SystemExit(
                f"[ERROR] timing observations changed after completion rep={rep}"
            )
        print(f"timing_rep_{token}=REUSED_COMPLETE", flush=True)
        timing_rows.append(row)
        continue

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "backend.harness.sensitivity_execution.run_timing_repetitions",
        str(spec_path),
        "--output-dir",
        str(output_dir),
        "--warmups",
        "10",
        "--measurements",
        "100",
        "--order-seed",
        "20260728",
        "--reuse-successful",
    ]

    print(f"timing_rep_{token}=START_OR_RESUME", flush=True)
    print(
        f"timing_rep_{token}_notice="
        "this replication can take a long time; heartbeat every 300s",
        flush=True,
    )
    rc = heartbeat_process(
        cmd,
        log_path,
        label=f"timing_rep_{token}",
        heartbeat_seconds=300,
    )
    if rc != 0:
        raise SystemExit(
            f"[ERROR] timing suffix execution stopped rep={rep}, rc={rc}; "
            "the same controller may be relaunched BEFORE the precision-start "
            "marker to resume with --reuse-successful."
        )

    for required_name in (
        "functional_references.json",
        "timing_manifest.json",
        "timing_observations.csv",
        "timing_summary.json",
    ):
        if not (output_dir / required_name).is_file():
            raise SystemExit(
                f"[ERROR] missing timing artifact rep={rep}: {required_name}"
            )

    row = validate_timing_csv(
        output_dir / "timing_observations.csv",
        rep,
        seed,
    )
    write_json(
        done_path,
        {
            "status": "timing_replication_complete",
            "completed_at_utc": utcnow(),
            "replication_index": rep,
            "seed": seed,
            "observations_sha256": row["sha256"],
            "manifest_sha256": sha256(output_dir / "timing_manifest.json"),
            "summary_sha256": sha256(output_dir / "timing_summary.json"),
            "functional_references_sha256": sha256(
                output_dir / "functional_references.json"
            ),
            "log_sha256": sha256(log_path),
            "measurement_row_count": 19200,
            "warmup_row_count": 1920,
            "functional_mismatch_count": 0,
        },
        exclusive=True,
    )
    timing_rows.append(row)
    print(f"timing_rep_{token}=PASS", flush=True)

if len(timing_rows) != 10:
    raise SystemExit("[ERROR] timing suffix completion count mismatch")

print("stage20_timing_suffix=PASS")
print("stage20_timing_suffix_replication_count=10")
print("stage20_suffix_measurement_rows=192000")
print("stage20_suffix_warmup_rows=19200")
print("stage20_suffix_functional_mismatch_count=0")
print("stage10_timing_prefix_rerun=false")


print("\n=== 7. Build exact combined Stage-20 lossless precision input ===", flush=True)

combined_path = p(COMBINED_OBS)
adapter_path = p(TIMING_ADAPTER)
combined_path.parent.mkdir(parents=True, exist_ok=True)

source_by_rep: dict[int, Path] = {}
for rep in range(10):
    source_by_rep[rep] = (
        p(STAGE10_TIMING_ROOT)
        / f"objective_count_rep_{rep:03d}_portfolio_timing_stage10"
        / "timing_observations.csv"
    )
for rep in NEW_REPS:
    source_by_rep[rep] = (
        suffix_timing
        / f"objective_count_rep_{rep:03d}_portfolio_timing_stage20"
        / "timing_observations.csv"
    )

counts: Counter[tuple[int, int, int]] = Counter()
seed_by_rep: dict[int, set[int]] = defaultdict(set)
measurement_total = 0
fresh_false = 0
semantic_false = 0

with combined_path.open("w", encoding="utf-8", newline="") as out_f:
    writer = csv.DictWriter(
        out_f,
        fieldnames=OUT_HEADER,
        lineterminator="\n",
    )
    writer.writeheader()

    for rep in range(20):
        source = source_by_rep[rep]
        with source.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != SOURCE_HEADER:
                raise SystemExit(
                    f"[ERROR] combined-source header mismatch rep={rep}"
                )
            for row in reader:
                if row["phase"].strip() != "measurement":
                    continue
                r = int(row["replication_index"])
                seed = int(row["seed"])
                level = int(row["factor_level"])
                step = int(row["step_index"])
                if r != rep:
                    raise SystemExit(
                        f"[ERROR] combined source rep mismatch {r} != {rep}"
                    )
                seed_by_rep[r].add(seed)
                counts[(r, level, step)] += 1
                measurement_total += 1
                if not truthy(row["fresh_state"]):
                    fresh_false += 1
                if not truthy(row["semantic_match"]):
                    semantic_false += 1

                output_row = dict(row)
                output_row["formal_replication_index"] = row["replication_index"]
                output_row["formal_structural_seed"] = row["seed"]
                writer.writerow(output_row)

if measurement_total != 384000:
    raise SystemExit(
        f"[ERROR] Stage-20 combined measurement rows={measurement_total}"
    )
if fresh_false != 0:
    raise SystemExit(
        f"[ERROR] Stage-20 combined non-fresh measurements={fresh_false}"
    )
if semantic_false != 0:
    raise SystemExit(
        f"[ERROR] Stage-20 combined semantic mismatches={semantic_false}"
    )
if set(seed_by_rep) != set(range(20)):
    raise SystemExit("[ERROR] Stage-20 combined replication set mismatch")
for rep in range(20):
    if seed_by_rep[rep] != {STAGE20_SEEDS[rep]}:
        raise SystemExit(
            f"[ERROR] Stage-20 combined seed mismatch rep={rep}"
        )
for rep in range(20):
    for level in LEVELS:
        for step in STEPS:
            if counts[(rep, level, step)] != 100:
                raise SystemExit(
                    f"[ERROR] combined cell balance rep={rep}, level={level}, "
                    f"step={step}: {counts[(rep, level, step)]}"
                )

combined_sha = sha256(combined_path)

timing_adapter = {
    "schema_version":
        "mcad-sa5-objective-count-stage20-precision-timing-adapter-v1",
    "status": "stage20_formal_timing_execution_success",
    "created_at_utc": utcnow(),
    "canonical_head": EXPECTED_HEAD,
    "factor": "objective_count",
    "stage_size": 20,
    "combined_totals": {
        "run_count": 20,
        "successful_run_count": 20,
        "cell_count": 3840,
        "measurement_observation_count": 384000,
        "functional_mismatch_count": 0,
        # Compatibility alias for the historical analyzer contract.
        # It denotes exact sample-count balance (100 observations per
        # seed/level/step cell), NOT positional order equality.
        "exactly_balanced_run_count": 20,
        "structural_seed_count": 20,
    },
    "compatibility_alias_semantics": {
        "exactly_balanced_run_count":
            "sample_count_balance_only_not_positional_order_balance"
    },
    "stage10_prefix_reused_without_rerun": True,
    "stage20_suffix_replications": NEW_REPS,
    "measurement_values_modified": False,
    "timing_magnitudes_interpreted": False,
}
write_json(adapter_path, timing_adapter)

print("stage20_combined_lossless_input=PASS")
print("combined_measurement_rows=384000")
print("combined_structural_seed_count=20")
print("combined_canonical_level_step_cells=192")
print(f"combined_input_sha256={combined_sha}")
print(f"timing_adapter_sha256={sha256(adapter_path)}")
print("scientific_latency_values_modified=false")
print("absolute_timing_magnitudes_interpreted=false")


print("\n=== 8. Permanently mark UNIQUE Stage-20 precision execution ===", flush=True)

if p(PRECISION_STARTED).exists():
    raise SystemExit(
        "[ERROR] precision start marker already exists. DO NOT RERUN."
    )
for q in (ANALYZER_LOG, INTERVALS, REPORT_JSON, REPORT_MD, MANIFEST):
    if p(q).exists():
        raise SystemExit(
            f"[ERROR] Stage-20 precision artifact already exists: {q}. DO NOT RERUN."
        )

write_json(
    p(PRECISION_STARTED),
    {
        "schema_version":
            "mcad-sa5-objective-count-stage20-precision-start-v1",
        "status": "stage20_precision_execution_started",
        "started_at_utc": utcnow(),
        "canonical_head": EXPECTED_HEAD,
        "operator_confirmation_received": True,
        "operator_confirmation": OPERATOR_CONFIRMATION,
        "stage20_structural_seed_count": 20,
        "stage20_measurement_row_count": 384000,
        "combined_input_sha256": combined_sha,
        "timing_adapter_sha256": sha256(adapter_path),
        "bootstrap_repetitions": 10000,
        "bootstrap_seed": 20260728,
        "confidence_level": 0.95,
        "median_target": 0.10,
        "p95_target": 0.15,
        "stage20_precision_invocation_limit": 1,
        "stage20_precision_rerun_authorized": False,
    },
    exclusive=True,
)

print("stage20_precision_start_marker=PASS")
print(f"stage20_precision_start_marker_sha256={sha256(p(PRECISION_STARTED))}")
print("stage20_unique_precision_execution_started=true")
print("FROM THIS POINT: DO NOT RELAUNCH THIS CONTROLLER OR THE PRECISION ANALYZER.")


print("\n=== 9. UNIQUE Stage-20 clustered precision bootstrap ===", flush=True)

cmd = [
    sys.executable,
    str(p(ANALYZER)),
    "--stage-size", "20",
    "--factor", "objective_count",
    "--observations", str(combined_path),
    "--timing-report", str(adapter_path),
    "--intervals-csv", str(p(INTERVALS)),
    "--report-json", str(p(REPORT_JSON)),
    "--report-md", str(p(REPORT_MD)),
    "--levels", ",".join(map(str, LEVELS)),
    "--steps", ",".join(map(str, STEPS)),
    "--measurements-per-cluster", "100",
    "--bootstrap-repetitions", "10000",
    "--bootstrap-seed", "20260728",
    "--confidence-level", "0.95",
    "--median-target", "0.10",
    "--p95-target", "0.15",
]

print("stage20_precision_analyzer_invocation_count=1")
print("stage20_bootstrap_repetitions=10000")
print(
    "stage20_precision_notice="
    "bootstrap can take tens of minutes; heartbeat every 300s",
    flush=True,
)

rc = heartbeat_process(
    cmd,
    p(ANALYZER_LOG),
    label="stage20_precision",
    heartbeat_seconds=300,
)

print(f"stage20_analyzer_exit_status={rc}")
print(f"stage20_analyzer_log_sha256={sha256(p(ANALYZER_LOG))}")

if rc != 0:
    write_json(
        p(MANIFEST),
        {
            "schema_version":
                "mcad-sa5-objective-count-stage20-execution-manifest-v1",
            "status": "stage20_precision_execution_failed",
            "completed_at_utc": utcnow(),
            "canonical_head": EXPECTED_HEAD,
            "stage20_precision_analyzer_invocation_count": 1,
            "analyzer_exit_status": rc,
            "rerun_forbidden": True,
            "scientific_freeze": False,
            "combined_input_sha256": combined_sha,
            "analyzer_log_sha256": sha256(p(ANALYZER_LOG)),
            "next_stage":
                "persist_stage20_failure_and_review_without_rerun",
        },
        exclusive=True,
    )
    print("stage20_scientific_precision_execution=FAIL")
    print("stage20_precision_rerun_forbidden=true")
    print("scientific_freeze=false")
    raise SystemExit(rc)


print("\n=== 10. Validate Stage-20 scientific result and stopping rule ===", flush=True)

for q in (INTERVALS, REPORT_JSON, REPORT_MD):
    if not p(q).is_file() or p(q).stat().st_size == 0:
        raise SystemExit(
            f"[ERROR] analyzer exited 0 but output is missing/empty: {q}. "
            "DO NOT RERUN."
        )

report = load_json(p(REPORT_JSON))

if report.get("stage_size") != 20:
    raise SystemExit("[ERROR] report stage size mismatch; DO NOT RERUN")
if report.get("structural_seed_count") != 20:
    raise SystemExit("[ERROR] report structural seed count mismatch; DO NOT RERUN")
if report.get("inputs", {}).get("observation_count") != 384000:
    raise SystemExit("[ERROR] report observation count mismatch; DO NOT RERUN")

cells = report.get("cell_results")
if not isinstance(cells, list) or len(cells) != 192:
    raise SystemExit("[ERROR] Stage-20 result cell count mismatch; DO NOT RERUN")

with p(INTERVALS).open("r", encoding="utf-8-sig", newline="") as f:
    interval_rows = sum(1 for _ in csv.DictReader(f))
if interval_rows != 192:
    raise SystemExit("[ERROR] Stage-20 interval row count mismatch; DO NOT RERUN")

status = report.get("status")
stage20_sufficient = report.get("stage20_sufficient")
extension_to_stage30 = report.get("extension_to_stage30_required")

if status not in {
    "stage20_precision_targets_met",
    "stage20_precision_targets_not_met",
}:
    raise SystemExit(
        f"[ERROR] unexpected Stage-20 result status={status!r}; DO NOT RERUN"
    )
if not isinstance(stage20_sufficient, bool):
    raise SystemExit("[ERROR] missing Stage-20 sufficiency boolean; DO NOT RERUN")
if not isinstance(extension_to_stage30, bool):
    raise SystemExit("[ERROR] missing Stage-30 extension boolean; DO NOT RERUN")
if extension_to_stage30 == stage20_sufficient:
    raise SystemExit("[ERROR] inconsistent Stage-20 stopping booleans; DO NOT RERUN")

expected_status = (
    "stage20_precision_targets_met"
    if stage20_sufficient
    else "stage20_precision_targets_not_met"
)
if status != expected_status:
    raise SystemExit("[ERROR] Stage-20 status/boolean mismatch; DO NOT RERUN")

print("stage20_scientific_output_validation=PASS")
print("successful_stage20_precision_analysis_count=1")
print("successful_stage20_canonical_bootstrap_execution_count=1")
print("stage20_canonical_cell_result_count=192")
print("stage20_interval_row_count=192")
print(f"report_status={status}")
print(f"stage20_sufficient={str(stage20_sufficient).lower()}")
print(
    "extension_to_stage30_required="
    f"{str(extension_to_stage30).lower()}"
)

for key in (
    "all_median_targets_met",
    "all_p95_targets_met",
    "all_precision_targets_met",
    "latency_claim_authorized",
    "scientific_freeze",
):
    if isinstance(report.get(key), bool):
        print(f"report_boolean_{key}={str(report[key]).lower()}")


print("\n=== 11. Write Stage-20 evidence manifests ===", flush=True)

suffix_evidence = {
    "schema_version":
        "mcad-sa5-objective-count-stage20-suffix-evidence-manifest-v1",
    "status": "stage20_suffix_execution_complete",
    "created_at_utc": utcnow(),
    "canonical_head": EXPECTED_HEAD,
    "work_root": str(WORK),
    "stage10_prefix_reused_without_rerun": True,
    "stage20_new_replications": NEW_REPS,
    "stage20_new_seeds": NEW_SEEDS,
    "functional_replications": [
        {
            "replication_index": rep,
            "done_marker": str(
                DONE / f"functional_rep_{rep:03d}.json"
            ),
            "done_marker_sha256": sha256(
                p(DONE) / f"functional_rep_{rep:03d}.json"
            ),
        }
        for rep in NEW_REPS
    ],
    "timing_replications": [
        {
            "replication_index": rep,
            "timing_dir": str(
                SUFFIX_TIMING
                / f"objective_count_rep_{rep:03d}_portfolio_timing_stage20"
            ),
            "done_marker": str(
                DONE / f"timing_rep_{rep:03d}.json"
            ),
            "done_marker_sha256": sha256(
                p(DONE) / f"timing_rep_{rep:03d}.json"
            ),
        }
        for rep in NEW_REPS
    ],
    "combined_lossless_input": {
        "path": str(COMBINED_OBS),
        "sha256": combined_sha,
        "measurement_row_count": 384000,
        "persist_large_combined_input_in_git": False,
    },
    "timing_adapter": {
        "path": str(TIMING_ADAPTER),
        "sha256": sha256(adapter_path),
    },
}
write_json(p(SUFFIX_MANIFEST), suffix_evidence, exclusive=True)

if stage20_sufficient:
    next_stage = "persist_then_freeze_sa5_and_exit_campaign"
else:
    next_stage = "persist_then_preregister_stage30_once"

final_manifest = {
    "schema_version":
        "mcad-sa5-objective-count-stage20-execution-manifest-v1",
    "status": "stage20_precision_execution_complete",
    "completed_at_utc": utcnow(),
    "canonical_head": EXPECTED_HEAD,
    "operator_confirmation": OPERATOR_CONFIRMATION,
    "stage10_prefix_reused_without_rerun": True,
    "stage20_suffix_functional_replication_count": 10,
    "stage20_suffix_timing_replication_count": 10,
    "stage20_combined_structural_seed_count": 20,
    "stage20_combined_measurement_row_count": 384000,
    "stage20_precision_analyzer_invocation_count": 1,
    "successful_stage20_precision_analysis_count": 1,
    "successful_stage20_canonical_bootstrap_execution_count": 1,
    "bootstrap_repetitions": 10000,
    "rerun_forbidden": True,
    "result": {
        "status": status,
        "stage20_sufficient": stage20_sufficient,
        "extension_to_stage30_required": extension_to_stage30,
        "all_median_targets_met": report.get("all_median_targets_met"),
        "all_p95_targets_met": report.get("all_p95_targets_met"),
        "all_precision_targets_met": report.get("all_precision_targets_met"),
    },
    "evidence": {
        "execution_start_marker_sha256": sha256(p(STARTED)),
        "precision_start_marker_sha256": sha256(p(PRECISION_STARTED)),
        "suffix_manifest_sha256": sha256(p(SUFFIX_MANIFEST)),
        "combined_input_sha256": combined_sha,
        "timing_adapter_sha256": sha256(adapter_path),
        "analyzer_log_sha256": sha256(p(ANALYZER_LOG)),
        "intervals_sha256": sha256(p(INTERVALS)),
        "report_json_sha256": sha256(p(REPORT_JSON)),
        "report_md_sha256": sha256(p(REPORT_MD)),
    },
    "scientific_freeze": False,
    "stage30_execution_authorized": False,
    "maximum_protocol_stage": 30,
    "next_stage": next_stage,
}
write_json(p(MANIFEST), final_manifest, exclusive=True)

print("stage20_suffix_evidence_manifest=PASS")
print(f"stage20_suffix_evidence_manifest_sha256={sha256(p(SUFFIX_MANIFEST))}")
print("stage20_execution_manifest=PASS")
print(f"stage20_execution_manifest_sha256={sha256(p(MANIFEST))}")


print("\n=== FINAL SA5 STAGE-20 STATE ===")
print("sa5_stage20_scientific_execution=PASS")
print("stage10_prefix_rerun=false")
print("stage20_precision_analyzer_invocation_count=1")
print("successful_stage20_precision_analysis_count=1")
print("successful_stage20_canonical_bootstrap_execution_count=1")
print("stage20_precision_rerun_forbidden=true")
print(f"stage20_sufficient={str(stage20_sufficient).lower()}")
print(
    "extension_to_stage30_required="
    f"{str(extension_to_stage30).lower()}"
)
print("scientific_freeze=false")
print("stage30_execution_authorized=false")
print("maximum_protocol_stage=30")
print(f"next_stage={next_stage}")
