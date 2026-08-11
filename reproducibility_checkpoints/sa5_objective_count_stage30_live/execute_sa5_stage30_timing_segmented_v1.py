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
EXPECTED_HEAD = "ff89d89339e1d5fa4fdffd1ee95d16037550bbec"

E3 = Path("reports/article_experiments/sensitivity/e3_controlled_execution")
PLAN = E3 / "planning"

PREREG = (
    PLAN / "sa5_objective_count_stage30_extension_preregistration.json"
)
PREREG_SHA = (
    "c405da9045d286778c8bf479c7cd93b0fbc263b6163f2553f738a77d3a6e7ba0"
)

PREREG_MD = (
    PLAN / "sa5_objective_count_stage30_extension_preregistration.md"
)
PREREG_MD_SHA = (
    "bd864771a112f0d9a9e97b2646430c13f8a03f056cfc3fc3f0d98b2d6dd2352f"
)

EXEC_PLAN = (
    PLAN / "sa5_objective_count_stage30_execution_plan.json"
)
EXEC_PLAN_SHA = (
    "d253f01d6c569c44c2ae920f72cd0a6ef25efdcca9ba6764ba3fc866120c1ae3"
)

TIMING_RUNNER = Path(
    "backend/harness/sensitivity_execution/run_timing_repetitions.py"
)
TIMING_RUNNER_SHA = (
    "6332cc63f8e50ee25df782b3b34b7110c7f5abb4af25bb6fcfd5cde5d18a7595"
)

STAGE10_CAMPAIGN = (
    E3 / "campaigns/objective_count_stage10_c8_nv32"
)
STAGE10_SPECS = E3 / "execution_specs"
STAGE10_TIMING_ROOT = (
    E3 / "timing_runs/objective_count_stage10_portfolio"
)

STAGE20_WORK = (
    E3 / "stage20_work/objective_count_stage20_fd7d87e"
)
STAGE20_FULL_CAMPAIGN = STAGE20_WORK / "full20_campaign"
STAGE20_FULL_WORKLOADS = (
    STAGE20_FULL_CAMPAIGN / "common_workloads"
)
STAGE20_TIMING_ROOT = STAGE20_WORK / "timing_runs"
STAGE20_DONE = STAGE20_WORK / "done"

WORK = (
    E3 / "stage30_work/objective_count_stage30_ff89d89"
)
FULL_CAMPAIGN = WORK / "full30_campaign"
FULL_WORKLOADS = FULL_CAMPAIGN / "common_workloads"
SUFFIX_SPECS = WORK / "execution_specs"
SUFFIX_RUNS = WORK / "functional_runs"
SUFFIX_TIMING = WORK / "timing_runs"
LOGS = WORK / "logs"
DONE = WORK / "done"
INTERRUPTED = WORK / "interrupted"

MATERIALIZATION_DONE = (
    WORK / "STAGE30_MATERIALIZATION_COMPLETE.json"
)

OUT = (
    E3 / "audits/objective_count/timing_stage30/precision_analysis"
)

STARTED = OUT / "SA5_STAGE30_EXECUTION_STARTED.json"
PRECISION_STARTED = OUT / "SA5_STAGE30_PRECISION_STARTED.json"

LEVELS = [1, 2, 5, 10, 20, 50]
STEPS = list(range(1, 33))

PREFIX_SEEDS = [
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

NEW_SEEDS = [
    1501822721,
    347859721,
    946029250,
    1737048803,
    2024145303,
    314054215,
    328361382,
    1316477741,
    1541512899,
    1430030072,
]

ALL_SEEDS = PREFIX_SEEDS + NEW_SEEDS
NEW_REPS = list(range(20, 30))

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

OPERATOR_CONFIRMATION = (
    "oui, j’autorise l’exécution Stage-30 SA5"
)

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



def prefix_timing_path(rep: int) -> Path:
    if 0 <= rep <= 9:
        return (
            p(STAGE10_TIMING_ROOT)
            / f"objective_count_rep_{rep:03d}_portfolio_timing_stage10"
            / "timing_observations.csv"
        )

    if 10 <= rep <= 19:
        return (
            p(STAGE20_TIMING_ROOT)
            / f"objective_count_rep_{rep:03d}_portfolio_timing_stage20"
            / "timing_observations.csv"
        )

    raise ValueError(rep)


print("=== 1. Exact merged Stage-30 authorization gate ===", flush=True)

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
        raise SystemExit(
            f"[ERROR] active scientific process detected: {pattern}"
        )

prereg = load_json(p(PREREG))
plan = load_json(p(EXEC_PLAN))

if prereg.get("status") != "preregistered_pending_merge":
    raise SystemExit("[ERROR] unexpected Stage-30 preregistration status")

authorization = prereg.get("authorization", {})
protocol = prereg.get("protocol", {})

if authorization.get(
    "explicit_operator_confirmation_after_merge_required"
) is not True:
    raise SystemExit("[ERROR] explicit confirmation contract mismatch")

if authorization.get("stage30_execution_authorized") is not False:
    raise SystemExit(
        "[ERROR] preregistration itself unexpectedly authorizes execution"
    )

expected_protocol = {
    "stage20_prefix_replications": list(range(20)),
    "stage30_new_replications": NEW_REPS,
    "stage30_total_replications": 30,
    "stage20_seeds": PREFIX_SEEDS,
    "stage30_new_seeds": NEW_SEEDS,
    "stage30_seeds": ALL_SEEDS,
    "prefix_reuse_required": True,
    "stage20_functional_rerun_authorized": False,
    "stage20_timing_rerun_authorized": False,
    "stage20_precision_rerun_authorized": False,
    "warmup_rows_per_seed_level_step": 10,
    "measurement_rows_per_seed_level_step": 100,
    "expected_stage30_combined_measurement_rows": 576000,
    "bootstrap_repetitions": 10000,
    "bootstrap_seed": 20260728,
    "confidence_level": 0.95,
    "median_relative_half_width_target": 0.10,
    "p95_relative_half_width_target": 0.15,
    "maximum_protocol_stage": 30,
    "stage_beyond_30_authorized": False,
}

for key, expected in expected_protocol.items():
    actual = protocol.get(key)
    if actual != expected:
        raise SystemExit(
            f"[ERROR] frozen Stage-30 contract mismatch: "
            f"{key}: {actual!r} != {expected!r}"
        )

if plan.get("status") != "preregistered_not_executed":
    raise SystemExit("[ERROR] unexpected Stage-30 execution-plan status")

if plan.get("execution_authorized") is not False:
    raise SystemExit(
        "[ERROR] execution plan unexpectedly self-authorizes Stage-30"
    )

if plan.get("execution_performed") is not False:
    raise SystemExit("[ERROR] execution plan already records execution")

print("stage30_authorization_gate=PASS")
print("operator_confirmation_received=true")
print(f"operator_confirmation={OPERATOR_CONFIRMATION}")
print("stage20_prefix_rerun_forbidden=true")
print("stage30_new_replications=20,21,22,23,24,25,26,27,28,29")
print("stage30_total_cluster_count=30")
print("maximum_protocol_stage=30")
print("stage_beyond_30_authorized=false")


print("\n=== 2. Materialize/revalidate exact detached full-30 design ===", flush=True)

if p(PRECISION_STARTED).exists():
    raise SystemExit(
        "[ERROR] Stage-30 precision start marker already exists. "
        "TIMING CONTROLLER MUST NEVER RUN AFTER PRECISION START."
    )

work = p(WORK)
full_campaign = p(FULL_CAMPAIGN)
full_workloads = p(FULL_WORKLOADS)
suffix_specs = p(SUFFIX_SPECS)
suffix_runs = p(SUFFIX_RUNS)
suffix_timing = p(SUFFIX_TIMING)
logs = p(LOGS)
done = p(DONE)
interrupted = p(INTERRUPTED)

if not p(MATERIALIZATION_DONE).exists():

    if work.exists():
        raise SystemExit(
            "[ERROR] Stage-30 work root exists without materialization marker; "
            "manual recovery review required."
        )

    if not p(STAGE20_FULL_CAMPAIGN).is_dir():
        raise SystemExit("[ERROR] immutable Stage-20 full campaign absent")

    if not p(STAGE20_FULL_WORKLOADS).is_dir():
        raise SystemExit("[ERROR] immutable Stage-20 workload prefix absent")

    prefix_audit = []

    for rep in range(20):
        source = prefix_timing_path(rep)

        if not source.is_file():
            raise SystemExit(
                f"[ERROR] missing immutable timing prefix rep={rep}: {source}"
            )

        row = validate_timing_csv(
            source,
            rep,
            PREFIX_SEEDS[rep],
        )

        prefix_audit.append(row)

        if 10 <= rep <= 19:
            done_path = (
                p(STAGE20_DONE)
                / f"timing_rep_{rep:03d}.json"
            )

            if not done_path.is_file():
                raise SystemExit(
                    f"[ERROR] Stage-20 done marker absent rep={rep}"
                )

            done_payload = load_json(done_path)

            if (
                done_payload.get("observations_sha256")
                != row["sha256"]
            ):
                raise SystemExit(
                    f"[ERROR] Stage-20 timing SHA mismatch rep={rep}"
                )

    if sum(
        x["measurement_row_count"]
        for x in prefix_audit
    ) != 384000:
        raise SystemExit(
            "[ERROR] immutable Stage-20 prefix measurement total mismatch"
        )

    if sum(
        x["warmup_row_count"]
        for x in prefix_audit
    ) != 38400:
        raise SystemExit(
            "[ERROR] immutable Stage-20 prefix warmup total mismatch"
        )

    for q in (
        full_campaign,
        suffix_specs,
        suffix_runs,
        suffix_timing,
        logs,
        done,
        interrupted,
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
            campaign_id="objective_count_stage10_c8_nv32",
            factor="objective_count",
            levels=tuple(LEVELS),
            seeds=tuple(ALL_SEEDS),
            baseline_constraint_count=8,
            baseline_virtual_node_count=32,
            output_dir=str(full_campaign),
        )
    )

    if tuple(manifest.levels) != tuple(LEVELS):
        raise SystemExit("[ERROR] generated Stage-30 levels mismatch")

    if tuple(manifest.seeds) != tuple(ALL_SEEDS):
        raise SystemExit("[ERROR] generated Stage-30 seed schedule mismatch")

    if manifest.replication_count != 30:
        raise SystemExit("[ERROR] generated Stage-30 replication count mismatch")

    if manifest.realised_instance_count != 180:
        raise SystemExit("[ERROR] generated Stage-30 instance count mismatch")

    workload_manifest = prepare_common_workloads(
        full_campaign,
        full_workloads,
    )

    if workload_manifest.get("workload_count") != 30:
        raise SystemExit("[ERROR] Stage-30 workload count mismatch")

    if workload_manifest.get("workload_length") != 32:
        raise SystemExit("[ERROR] Stage-30 workload length mismatch")

    entries = workload_manifest.get("entries", [])

    if [int(x["replication_index"]) for x in entries] != list(range(30)):
        raise SystemExit(
            "[ERROR] Stage-30 workload replication schedule mismatch"
        )

    if [int(x["seed"]) for x in entries] != ALL_SEEDS:
        raise SystemExit("[ERROR] Stage-30 workload seed schedule mismatch")

    def rows_by_key(
        csv_path: Path,
    ) -> dict[tuple[int, int], dict[str, str]]:
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            rows = list(csv.DictReader(f))

        return {
            (
                int(r["replication_index"]),
                int(r["factor_level"]),
            ): r
            for r in rows
        }

    old_rows = rows_by_key(
        p(STAGE20_FULL_CAMPAIGN) / "instances.csv"
    )

    new_rows = rows_by_key(
        full_campaign / "instances.csv"
    )

    for rep in range(20):

        for level in LEVELS:
            old = old_rows[(rep, level)]
            new = new_rows[(rep, level)]

            old_obj = (
                p(STAGE20_FULL_CAMPAIGN)
                / old["relative_instance_dir"]
                / "objectives.yaml"
            )

            new_obj = (
                full_campaign
                / new["relative_instance_dir"]
                / "objectives.yaml"
            )

            if old_obj.read_bytes() != new_obj.read_bytes():
                raise SystemExit(
                    "[ERROR] Stage-20 structural prefix changed "
                    f"rep={rep}, level={level}"
                )

        old_workload = (
            p(STAGE20_FULL_WORKLOADS)
            / f"replication_{rep:03d}_seed_{PREFIX_SEEDS[rep]}.json"
        )

        new_workload = (
            full_workloads
            / f"replication_{rep:03d}_seed_{PREFIX_SEEDS[rep]}.json"
        )

        if old_workload.read_bytes() != new_workload.read_bytes():
            raise SystemExit(
                f"[ERROR] Stage-20 workload prefix changed rep={rep}"
            )

    generated_rows = rows_by_key(
        full_campaign / "instances.csv"
    )

    base_spec = load_json(
        p(STAGE10_SPECS)
        / "objective_count_stage10_rep_000_canonical.json"
    )

    contract_version = base_spec["contract_version"]

    workload_entries = {
        int(x["replication_index"]): x
        for x in entries
    }

    for rep in NEW_REPS:

        seed = ALL_SEEDS[rep]

        selected_rows = [
            generated_rows[(rep, level)]
            for level in LEVELS
        ]

        workload_entry = workload_entries[rep]
        workload_filename = str(
            workload_entry["workload_path"]
        )

        workload_path = (
            full_workloads / workload_filename
        )

        run_dir = (
            suffix_runs
            / f"objective_count_stage30_rep_{rep:03d}_canonical"
        )

        payload = {
            "contract_version": contract_version,
            "execution_id": (
                f"sa5-objective-count-stage30-"
                f"rep_{rep:03d}-canonical-v1"
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

        spec_path = (
            suffix_specs
            / f"objective_count_stage30_rep_{rep:03d}_canonical.json"
        )

        write_json(spec_path, payload)
        validate_execution_spec(payload)

        inputs = load_execution_inputs(spec_path)

        if len(inputs.instances) != 6:
            raise SystemExit(
                f"[ERROR] Stage-30 spec instance count rep={rep}"
            )

        if [x.factor_level for x in inputs.instances] != LEVELS:
            raise SystemExit(
                f"[ERROR] Stage-30 level order rep={rep}"
            )

        if {
            x.replication_index
            for x in inputs.instances
        } != {rep}:
            raise SystemExit(
                f"[ERROR] Stage-30 replication identity rep={rep}"
            )

        if {
            x.seed
            for x in inputs.instances
        } != {seed}:
            raise SystemExit(
                f"[ERROR] Stage-30 seed identity rep={rep}"
            )

        if inputs.output_dir != run_dir.resolve():
            raise SystemExit(
                f"[ERROR] Stage-30 output path rep={rep}"
            )

    materialization_payload = {
        "schema_version":
            "mcad-sa5-objective-count-stage30-runtime-materialization-v1",
        "status":
            "stage30_runtime_materialization_complete",
        "created_at_utc": utcnow(),
        "canonical_head": EXPECTED_HEAD,
        "full30_replication_count": 30,
        "full30_instance_count": 180,
        "stage20_prefix_replication_count": 20,
        "stage20_prefix_structure_byte_identity": True,
        "stage20_prefix_workload_byte_identity": True,
        "stage20_prefix_measurement_row_count": 384000,
        "stage20_prefix_warmup_row_count": 38400,
        "prefix_timing_sha256_by_rep": {
            str(x["replication_index"]): x["sha256"]
            for x in prefix_audit
        },
        "new_suffix_replications": NEW_REPS,
        "new_suffix_seeds": NEW_SEEDS,
        "new_suffix_execution_spec_count": 10,
        "operator_confirmation": OPERATOR_CONFIRMATION,
        "timing_execution_performed": False,
        "precision_analysis_performed": False,
        "bootstrap_execution_performed": False,
        "maximum_protocol_stage": 30,
    }

    write_json(
        p(MATERIALIZATION_DONE),
        materialization_payload,
        exclusive=True,
    )

else:

    materialization_payload = load_json(
        p(MATERIALIZATION_DONE)
    )

    if (
        materialization_payload.get("canonical_head")
        != EXPECTED_HEAD
    ):
        raise SystemExit(
            "[ERROR] stale Stage-30 runtime materialization"
        )

    if (
        materialization_payload.get(
            "stage20_prefix_structure_byte_identity"
        )
        is not True
    ):
        raise SystemExit(
            "[ERROR] Stage-20 structural prefix identity absent"
        )

    if (
        materialization_payload.get(
            "stage20_prefix_workload_byte_identity"
        )
        is not True
    ):
        raise SystemExit(
            "[ERROR] Stage-20 workload prefix identity absent"
        )

    if (
        materialization_payload.get("new_suffix_seeds")
        != NEW_SEEDS
    ):
        raise SystemExit(
            "[ERROR] Stage-30 runtime seed schedule mismatch"
        )

    prefix_hashes = materialization_payload.get(
        "prefix_timing_sha256_by_rep",
        {},
    )

    for rep in range(20):

        path = prefix_timing_path(rep)

        expected = prefix_hashes.get(str(rep))

        if not expected:
            raise SystemExit(
                f"[ERROR] missing frozen prefix timing SHA rep={rep}"
            )

        if sha256(path) != expected:
            raise SystemExit(
                f"[ERROR] immutable prefix timing changed rep={rep}"
            )

    for rep in NEW_REPS:

        spec_path = (
            suffix_specs
            / f"objective_count_stage30_rep_{rep:03d}_canonical.json"
        )

        if not spec_path.is_file():
            raise SystemExit(
                f"[ERROR] missing Stage-30 runtime spec rep={rep}"
            )

print("stage30_runtime_materialization=PASS")
print("stage20_prefix_structure_byte_identity=true")
print("stage20_prefix_workload_byte_identity=true")
print("stage30_full_structural_source_replications=30")
print("stage30_new_suffix_spec_count=10")


print("\n=== 3. Mark Stage-30 suffix execution started ===", flush=True)

p(OUT).mkdir(parents=True, exist_ok=True)

if not p(STARTED).exists():

    write_json(
        p(STARTED),
        {
            "schema_version":
                "mcad-sa5-objective-count-stage30-execution-start-v1",
            "status":
                "stage30_suffix_execution_started",
            "started_at_utc": utcnow(),
            "canonical_branch": BASE,
            "canonical_head": EXPECTED_HEAD,
            "operator_confirmation_received": True,
            "operator_confirmation": OPERATOR_CONFIRMATION,
            "stage20_prefix_rerun_forbidden": True,
            "stage30_new_replications": NEW_REPS,
            "stage30_new_seeds": NEW_SEEDS,
            "stage30_precision_started": False,
            "stage30_precision_rerun_authorized": False,
            "maximum_protocol_stage": 30,
            "stage_beyond_30_authorized": False,
        },
        exclusive=True,
    )

else:

    started = load_json(p(STARTED))

    if started.get("canonical_head") != EXPECTED_HEAD:
        raise SystemExit(
            "[ERROR] stale Stage-30 execution marker"
        )

    if started.get("stage30_new_seeds") != NEW_SEEDS:
        raise SystemExit(
            "[ERROR] Stage-30 execution marker seed mismatch"
        )

    if (
        started.get("operator_confirmation")
        != OPERATOR_CONFIRMATION
    ):
        raise SystemExit(
            "[ERROR] Stage-30 operator confirmation mismatch"
        )

print("stage30_execution_start_marker=PASS")
print(
    f"stage30_execution_start_marker_sha256="
    f"{sha256(p(STARTED))}"
)


print("\n=== 4. Execute/validate functional suffix 20..29 ===", flush=True)

functional_rows = []

for rep in NEW_REPS:

    seed = ALL_SEEDS[rep]
    token = f"{rep:03d}"

    spec_path = (
        suffix_specs
        / f"objective_count_stage30_rep_{token}_canonical.json"
    )

    run_dir = (
        suffix_runs
        / f"objective_count_stage30_rep_{token}_canonical"
    )

    log_path = (
        logs / f"functional_rep_{token}.log"
    )

    done_path = (
        done / f"functional_rep_{token}.json"
    )

    if done_path.exists():

        done_payload = load_json(done_path)

        if done_payload.get("replication_index") != rep:
            raise SystemExit(
                f"[ERROR] stale functional marker rep={rep}"
            )

        row = validate_functional_done(
            rep,
            seed,
            run_dir,
        )

        if (
            row["tree_sha256"]
            != done_payload.get("tree_sha256")
        ):
            raise SystemExit(
                f"[ERROR] functional evidence changed rep={rep}"
            )

        print(
            f"functional_rep_{token}=REUSED_COMPLETE",
            flush=True,
        )

        functional_rows.append(row)
        continue

    if run_dir.exists():
        raise SystemExit(
            "[ERROR] functional output exists without completion "
            f"marker rep={rep}; manual review required"
        )

    cmd = [
        sys.executable,
        "-m",
        "backend.harness.sensitivity_execution.execute_controlled_family",
        str(spec_path),
    ]

    print(
        f"functional_rep_{token}=START",
        flush=True,
    )

    rc = heartbeat_process(
        cmd,
        log_path,
        label=f"functional_rep_{token}",
        heartbeat_seconds=30,
    )

    if rc != 0:
        raise SystemExit(
            f"[ERROR] Stage-30 functional execution failed "
            f"rep={rep}, rc={rc}; log={log_path}"
        )

    text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    for required in (
        "[OK] E3 controlled execution completed.",
        "[OK] selected_instance_count=6",
        "[OK] step_count=192",
    ):
        if required not in text:
            raise SystemExit(
                f"[ERROR] functional success token missing "
                f"rep={rep}: {required}"
            )

    row = validate_functional_done(
        rep,
        seed,
        run_dir,
    )

    write_json(
        done_path,
        {
            "status":
                "functional_replication_complete",
            "completed_at_utc": utcnow(),
            **row,
            "spec_sha256": sha256(spec_path),
            "log_sha256": sha256(log_path),
        },
        exclusive=True,
    )

    functional_rows.append(row)

    print(
        f"functional_rep_{token}=PASS",
        flush=True,
    )

if len(functional_rows) != 10:
    raise SystemExit(
        "[ERROR] Stage-30 functional suffix count mismatch"
    )

print("stage30_functional_suffix=PASS")
print("stage30_functional_suffix_replication_count=10")
print("stage20_functional_prefix_rerun=false")


print("\n=== 5. Execute/resume timing suffix 20..29 ===", flush=True)

timing_rows = []

for rep in NEW_REPS:

    seed = ALL_SEEDS[rep]
    token = f"{rep:03d}"

    spec_path = (
        suffix_specs
        / f"objective_count_stage30_rep_{token}_canonical.json"
    )

    output_dir = (
        suffix_timing
        / f"objective_count_rep_{token}_portfolio_timing_stage30"
    )

    log_path = (
        logs / f"timing_rep_{token}.log"
    )

    done_path = (
        done / f"timing_rep_{token}.json"
    )

    if done_path.exists():

        payload = load_json(done_path)

        if payload.get("replication_index") != rep:
            raise SystemExit(
                f"[ERROR] stale Stage-30 timing marker rep={rep}"
            )

        row = validate_timing_csv(
            output_dir / "timing_observations.csv",
            rep,
            seed,
        )

        if (
            row["sha256"]
            != payload.get("observations_sha256")
        ):
            raise SystemExit(
                f"[ERROR] Stage-30 timing observations changed "
                f"after completion rep={rep}"
            )

        print(
            f"timing_rep_{token}=REUSED_COMPLETE",
            flush=True,
        )

        timing_rows.append(row)
        continue

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    print(
        f"timing_rep_{token}=START_OR_RESUME",
        flush=True,
    )

    print(
        f"timing_rep_{token}_notice="
        "heartbeat every 300 seconds",
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
            f"[ERROR] Stage-30 timing stopped rep={rep}, rc={rc}. "
            "No precision has been started."
        )

    for required_name in (
        "functional_references.json",
        "timing_manifest.json",
        "timing_observations.csv",
        "timing_summary.json",
    ):
        if not (
            output_dir / required_name
        ).is_file():
            raise SystemExit(
                f"[ERROR] missing timing artifact "
                f"rep={rep}: {required_name}"
            )

    row = validate_timing_csv(
        output_dir / "timing_observations.csv",
        rep,
        seed,
    )

    write_json(
        done_path,
        {
            "status":
                "timing_replication_complete",
            "completed_at_utc": utcnow(),
            "replication_index": rep,
            "seed": seed,
            "observations_sha256": row["sha256"],
            "manifest_sha256":
                sha256(
                    output_dir
                    / "timing_manifest.json"
                ),
            "summary_sha256":
                sha256(
                    output_dir
                    / "timing_summary.json"
                ),
            "functional_references_sha256":
                sha256(
                    output_dir
                    / "functional_references.json"
                ),
            "log_sha256":
                sha256(log_path),
            "measurement_row_count": 19200,
            "warmup_row_count": 1920,
            "functional_mismatch_count": 0,
        },
        exclusive=True,
    )

    timing_rows.append(row)

    print(
        f"timing_rep_{token}=PASS",
        flush=True,
    )

    if (
        os.environ.get(
            "SA5_STAGE30_SEGMENTED_TIMING",
            "",
        )
        == "1"
    ):
        print(
            "stage30_segmented_timing_boundary=PASS",
            flush=True,
        )

        print(
            f"completed_timing_replication={rep}",
            flush=True,
        )

        print(
            "stage30_precision_analysis_performed=false",
            flush=True,
        )

        print(
            "stage30_precision_start_marker_created=false",
            flush=True,
        )

        print(
            "next_stage=checkpoint_then_resume_next_timing_replication",
            flush=True,
        )

        raise SystemExit(0)

if len(timing_rows) != 10:
    raise SystemExit(
        "[ERROR] Stage-30 timing suffix completion count mismatch"
    )

print("stage30_timing_suffix=PASS")
print("stage30_timing_suffix_replication_count=10")
print("stage30_suffix_measurement_rows=192000")
print("stage30_suffix_warmup_rows=19200")
print("stage20_timing_prefix_rerun=false")
print("stage30_precision_analysis_performed=false")
print("stage30_precision_start_marker_created=false")
print("maximum_protocol_stage=30")
print("stage_beyond_30_authorized=false")
print(
    "next_stage="
    "final_stage30_precision_after_all_timing_is_remotely_checkpointed"
)

