from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/workspaces/MCAD_improve3")
BASE = "paper/phase3-controlled-execution"
EXPECTED_HEAD = "ff89d89339e1d5fa4fdffd1ee95d16037550bbec"

EXPECTED_ORIGINS = {
    "https://github.com/digitcreadev/MCAD_improve3",
    "https://github.com/digitcreadev/MCAD_improve3.git",
    "git@github.com:digitcreadev/MCAD_improve3.git",
}

E3 = Path(
    "reports/article_experiments/sensitivity/e3_controlled_execution"
)
PLAN = E3 / "planning"
PRECISION_REL = (
    E3 / "audits/objective_count/timing_stage30/precision_analysis"
)

M5D = Path(
    "/workspaces/"
    "m5d_sa5_stage30_final_precision_build_20260813T013804Z"
)

STAGE20_INPUT = (
    M5D / "stage20_combined_measurement_observations_reconstructed.csv"
)
STAGE30_INPUT = (
    M5D / "stage30_combined_measurement_observations.csv"
)
TIMING_ADAPTER = (
    M5D / "stage30_precision_timing_report_adapter.json"
)
M5D_MANIFEST = M5D / "M5D_BUILD_MANIFEST.json"

STAGE20_INPUT_SHA = (
    "7f7665d3ec870b8d22e51eb69bea9432"
    "eb6c2255eb30b077e9df3092dae7713c"
)
STAGE30_INPUT_SHA = (
    "6542c6c014b99a2a6db08ca1bb54e41"
    "c0712643f5e342f3d51ed6826eca49ae5"
)
TIMING_ADAPTER_SHA = (
    "1f5dcfbea210c9ac9d7c3b94492e8164"
    "0421e5b2fdd32ca3e0030938f53de312"
)
M5D_MANIFEST_SHA = (
    "428f79e2ab2ec407648a94d3501743f4"
    "2752593be29bababdf1066a2dfd44935"
)

ANALYZER = Path(
    "backend/harness/sensitivity_execution/"
    "analyze_clustered_timing_precision_v2_factor_compatible.py"
)
ANALYZER_SHA = (
    "841d3f59f7195c262befc8a32602eae6"
    "8d8a28538631c8c21dd7af8c1c00923f"
)

PREREG = (
    PLAN / "sa5_objective_count_stage30_extension_preregistration.json"
)
PREREG_SHA = (
    "c405da9045d286778c8bf479c7cd93b0"
    "fbc263b6163f2553f738a77d3a6e7ba0"
)

LEVELS = [1, 2, 5, 10, 20, 50]
STEPS = list(range(1, 33))

OPERATOR_CONFIRMATION = (
    "Oui, j’autorise l’exécution unique de l’analyse finale de précision "
    "SA5 Stage-30 à partir des artefacts M5D validés, conformément au "
    "protocole préenregistré, sans rerun et sans Stage-40."
)


def utcnow():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(
        "x" if exclusive else "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            obj,
            f,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def run(args, cwd=ROOT, check=True, capture=True):
    cp = subprocess.run(
        [str(x) for x in args],
        cwd=str(cwd),
        text=True,
        capture_output=capture,
    )

    if check and cp.returncode != 0:
        raise RuntimeError(
            "command failed rc="
            f"{cp.returncode}: {' '.join(map(str, args))}\n"
            f"stdout:\n{cp.stdout or ''}\n"
            f"stderr:\n{cp.stderr or ''}"
        )

    return cp


def gout(args, cwd=ROOT):
    return run(["git", *args], cwd=cwd).stdout.strip()


def require_sha(path, expected, label):
    if not path.is_file():
        raise SystemExit(
            f"[STOP] missing file {label}: {path}"
        )

    actual = sha(path)
    print(f"{label}_sha256={actual}")

    if actual != expected:
        raise SystemExit(
            f"[STOP] SHA mismatch {label}: "
            f"{actual} != {expected}"
        )


def flag(argv, name):
    if argv.count(name) != 1:
        raise SystemExit(
            f"[STOP] argv flag multiplicity invalid: {name}"
        )

    i = argv.index(name)

    if i + 1 >= len(argv):
        raise SystemExit(
            f"[STOP] argv missing value after {name}"
        )

    return argv[i + 1]


def replace_flag(argv, name, value):
    i = argv.index(name)
    argv[i + 1] = value


def resolve_arg(value):
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return p.resolve()


def find_argv(obj):
    candidates = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            if (
                x
                and all(isinstance(v, str) for v in x)
                and any(ANALYZER.name in v for v in x)
                and "--stage-size" in x
                and "--observations" in x
                and "--timing-report" in x
            ):
                candidates.append(list(x))

            for v in x:
                walk(v)

    walk(obj)

    unique = []
    seen = set()

    for x in candidates:
        t = tuple(x)
        if t not in seen:
            seen.add(t)
            unique.append(x)

    return unique


def bval(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        x = value.strip().lower()

        if x in {"true", "1", "yes"}:
            return True

        if x in {"false", "0", "no"}:
            return False

    return None


print("=" * 72)
print(
    "M5E — UNIQUE FINAL SA5 STAGE-30 PRECISION EXECUTION "
    "+ ORIGINAL-REPO PERSISTENCE"
)
print("=" * 72)

print(f"utc={utcnow()}")
print("operator_confirmation_received=true")
print("final_execution_invocation_limit=1")
print("rerun_authorized=false")
print("stage40_authorized=false")
print()


# ------------------------------------------------------------------
print("=== 1. Canonical + original GitHub repository gate ===")

run(
    ["git", "fetch", "origin", "--prune"],
    capture=False,
)

branch = gout(["branch", "--show-current"])
head = gout(["rev-parse", "HEAD"])
remote_head = gout(
    ["rev-parse", f"origin/{BASE}"]
)
status = gout(["status", "--porcelain"])
origin = gout(["remote", "get-url", "origin"])

print(f"branch={branch}")
print(f"head={head}")
print(f"remote_head={remote_head}")
print(f"origin={origin}")
print(
    "canonical_clean="
    f"{str(not bool(status)).lower()}"
)

if branch != BASE:
    raise SystemExit(
        "[STOP] wrong canonical branch"
    )

if head != EXPECTED_HEAD:
    raise SystemExit(
        "[STOP] wrong canonical HEAD"
    )

if remote_head != EXPECTED_HEAD:
    raise SystemExit(
        "[STOP] remote canonical HEAD moved"
    )

if status:
    raise SystemExit(
        "[STOP] canonical worktree is not clean"
    )

if origin not in EXPECTED_ORIGINS:
    raise SystemExit(
        "[STOP] origin is not "
        "digitcreadev/MCAD_improve3; "
        f"actual={origin}"
    )

print("canonical_origin_gate=PASS")
print()


# ------------------------------------------------------------------
print("=== 2. Permanent anti-rerun gate ===")

marker_rel = (
    PRECISION_REL /
    "SA5_STAGE30_PRECISION_STARTED.json"
)

history = gout(
    [
        "log",
        "--all",
        "--format=%H",
        "--",
        str(marker_rel),
    ]
)

if history:
    print(history)
    raise SystemExit(
        "[STOP] Stage-30 precision marker "
        "already exists in Git history. "
        "RERUN FORBIDDEN."
    )

candidate_markers = []

canonical_marker = ROOT / marker_rel

if canonical_marker.exists():
    candidate_markers.append(
        canonical_marker
    )

for wt in Path("/workspaces").glob(
    "sa5_stage30_final_precision_persist_*"
):
    p = wt / marker_rel

    if p.exists():
        candidate_markers.append(p)

if candidate_markers:
    for p in candidate_markers:
        print(
            f"existing_precision_marker={p}"
        )

    raise SystemExit(
        "[STOP] precision marker already exists; "
        "RERUN FORBIDDEN."
    )

proc = run(
    [
        "pgrep",
        "-af",
        (
            "[a]nalyze_clustered_timing_precision|"
            "[e]xecute_sa5_stage30_timing|"
            "[r]un_sa5_stage30_timing|"
            "objective_count.*[p]recision"
        ),
    ],
    check=False,
)

if (
    proc.returncode == 0
    and proc.stdout.strip()
):
    print(proc.stdout)

    raise SystemExit(
        "[STOP] active scientific process detected"
    )

print(
    "stage30_precision_marker_preexisting=false"
)
print(
    "active_scientific_process=false"
)
print("permanent_anti_rerun_gate=PASS")
print()


# ------------------------------------------------------------------
print("=== 3. Immutable identities + M5D gate ===")

require_sha(
    STAGE20_INPUT,
    STAGE20_INPUT_SHA,
    "m5d_stage20_reconstructed",
)

require_sha(
    STAGE30_INPUT,
    STAGE30_INPUT_SHA,
    "m5d_stage30_combined",
)

require_sha(
    TIMING_ADAPTER,
    TIMING_ADAPTER_SHA,
    "m5d_stage30_adapter",
)

require_sha(
    M5D_MANIFEST,
    M5D_MANIFEST_SHA,
    "m5d_build_manifest",
)

require_sha(
    ROOT / ANALYZER,
    ANALYZER_SHA,
    "stage30_analyzer",
)

require_sha(
    ROOT / PREREG,
    PREREG_SHA,
    "stage30_preregistration",
)

m5d_manifest = json.loads(
    M5D_MANIFEST.read_text(
        encoding="utf-8"
    )
)

candidates = find_argv(
    m5d_manifest
)

if len(candidates) != 1:
    raise SystemExit(
        "[STOP] expected exactly one "
        "future analyzer argv in M5D manifest; "
        f"found={len(candidates)}"
    )

m5d_argv = candidates[0]

for name, expected in {
    "--stage-size": "30",
    "--factor": "objective_count",
    "--levels": ",".join(
        map(str, LEVELS)
    ),
    "--steps": ",".join(
        map(str, STEPS)
    ),
}.items():

    actual = flag(
        m5d_argv,
        name,
    )

    if actual != expected:
        raise SystemExit(
            f"[STOP] M5D argv mismatch {name}: "
            f"{actual!r} != {expected!r}"
        )

numeric_contract = {
    "--measurements-per-cluster": 100,
    "--bootstrap-repetitions": 10000,
    "--bootstrap-seed": 20260728,
}

for name, expected in numeric_contract.items():
    if int(
        flag(
            m5d_argv,
            name,
        )
    ) != expected:

        raise SystemExit(
            f"[STOP] M5D numeric contract mismatch: "
            f"{name}"
        )

if abs(
    float(
        flag(
            m5d_argv,
            "--confidence-level",
        )
    )
    - 0.95
) > 1e-12:
    raise SystemExit(
        "[STOP] confidence-level mismatch"
    )

if abs(
    float(
        flag(
            m5d_argv,
            "--median-target",
        )
    )
    - 0.10
) > 1e-12:
    raise SystemExit(
        "[STOP] median target mismatch"
    )

if abs(
    float(
        flag(
            m5d_argv,
            "--p95-target",
        )
    )
    - 0.15
) > 1e-12:
    raise SystemExit(
        "[STOP] p95 target mismatch"
    )

if resolve_arg(
    flag(
        m5d_argv,
        "--observations",
    )
) != STAGE30_INPUT.resolve():

    raise SystemExit(
        "[STOP] Stage-30 observations path mismatch"
    )

if resolve_arg(
    flag(
        m5d_argv,
        "--timing-report",
    )
) != TIMING_ADAPTER.resolve():

    raise SystemExit(
        "[STOP] timing-adapter path mismatch"
    )

analyzer_items = [
    x
    for x in m5d_argv
    if ANALYZER.name in x
]

if len(analyzer_items) != 1:
    raise SystemExit(
        "[STOP] analyzer not uniquely bound in M5D argv"
    )

if resolve_arg(
    analyzer_items[0]
) != (
    ROOT / ANALYZER
).resolve():

    raise SystemExit(
        "[STOP] analyzer path mismatch"
    )

python_exec = (
    shutil.which(
        m5d_argv[0]
    )
    or m5d_argv[0]
)

if not Path(
    python_exec
).exists():

    raise SystemExit(
        "[STOP] M5D Python executable unavailable: "
        f"{m5d_argv[0]}"
    )

version = run(
    [
        python_exec,
        "--version",
    ],
    check=True,
)

python_version = (
    version.stdout.strip()
    or version.stderr.strip()
)

print(
    f"m5d_python_executable={python_exec}"
)
print(
    f"m5d_python_version={python_version}"
)
print(
    "m5d_future_analyzer_argv_gate=PASS"
)
print(
    "immutable_input_gate=PASS"
)
print()


# ------------------------------------------------------------------
print(
    "=== 4. Create isolated persistence worktree ==="
)

stamp_id = stamp()

persist_branch = (
    "paper/"
    "persist-sa5-stage30-final-precision-"
    f"{stamp_id}"
)

wt = Path(
    "/workspaces/"
    "sa5_stage30_final_precision_persist_"
    f"{stamp_id}"
)

validated_rel = Path(
    "reproducibility_checkpoints/"
    "sa5_objective_count_stage30_final_precision"
)

validated = (
    wt / validated_rel
)

precision = (
    wt / PRECISION_REL
)

plan = (
    wt / PLAN
)

if wt.exists():
    raise SystemExit(
        f"[STOP] worktree already exists: {wt}"
    )

run(
    [
        "git",
        "worktree",
        "add",
        "-b",
        persist_branch,
        str(wt),
        EXPECTED_HEAD,
    ],
    capture=False,
)

if gout(
    [
        "rev-parse",
        "HEAD",
    ],
    cwd=wt,
) != EXPECTED_HEAD:

    raise SystemExit(
        "[STOP] persistence worktree HEAD mismatch"
    )

validated.mkdir(
    parents=True,
    exist_ok=False,
)

precision.mkdir(
    parents=True,
    exist_ok=True,
)

plan.mkdir(
    parents=True,
    exist_ok=True,
)

print(
    f"persistence_branch={persist_branch}"
)
print(
    f"persistence_worktree={wt}"
)
print(
    "isolated_persistence_worktree=PASS"
)
print()


# ------------------------------------------------------------------
print(
    "=== 5. Materialize validated M5D inputs into repo ==="
)

shutil.copy2(
    M5D_MANIFEST,
    validated /
    M5D_MANIFEST.name,
)

shutil.copy2(
    TIMING_ADAPTER,
    validated /
    TIMING_ADAPTER.name,
)

shutil.copy2(
    Path(__file__),
    validated /
    "m5e_stage30_execute_and_persist.py",
)

write_json(
    validated /
    "M5D_FUTURE_ANALYZER_ARGV.json",
    {
        "schema_version":
            "mcad-sa5-stage30-m5d-future-analyzer-argv-v1",
        "source_manifest":
            str(M5D_MANIFEST),
        "source_manifest_sha256":
            M5D_MANIFEST_SHA,
        "argv":
            m5d_argv,
    },
)

archive_tmp = Path(
    "/workspaces/"
    f"sa5_stage30_validated_inputs_{stamp_id}.tar.gz"
)

with tarfile.open(
    archive_tmp,
    "w:gz",
) as tf:

    for src in (
        STAGE20_INPUT,
        STAGE30_INPUT,
        TIMING_ADAPTER,
        M5D_MANIFEST,
    ):
        tf.add(
            src,
            arcname=src.name,
            recursive=False,
        )

archive_sha = sha(
    archive_tmp
)

archive_size = (
    archive_tmp.stat().st_size
)

chunks = (
    validated / "chunks"
)

chunks.mkdir()

chunk_limit = (
    45 * 1024 * 1024
)

chunk_rows = []

with archive_tmp.open(
    "rb"
) as src:

    i = 0

    while True:
        data = src.read(
            chunk_limit
        )

        if not data:
            break

        out = (
            chunks /
            (
                "sa5_stage30_validated_inputs."
                f"tar.gz.part{i:03d}"
            )
        )

        out.write_bytes(
            data
        )

        chunk_rows.append(
            {
                "filename":
                    out.name,
                "sha256":
                    sha(out),
                "size_bytes":
                    out.stat().st_size,
            }
        )

        i += 1

h = hashlib.sha256()

for item in chunk_rows:

    p = (
        chunks /
        item["filename"]
    )

    with p.open("rb") as f:
        for block in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b"",
        ):
            h.update(block)

if h.hexdigest() != archive_sha:
    raise SystemExit(
        "[STOP] input-chunk reconstruction mismatch"
    )

archive_tmp.unlink()

validated_inputs = {
    "schema_version":
        "mcad-sa5-stage30-final-precision-validated-inputs-v1",
    "status":
        "validated_and_materialized_before_unique_precision_execution",
    "created_at_utc":
        utcnow(),
    "canonical_head":
        EXPECTED_HEAD,
    "m5d_build_root":
        str(M5D),
    "inputs": {
        "stage20_reconstructed": {
            "execution_path":
                str(STAGE20_INPUT),
            "sha256":
                STAGE20_INPUT_SHA,
            "size_bytes":
                STAGE20_INPUT.stat().st_size,
            "measurement_rows":
                384000,
        },
        "stage30_combined": {
            "execution_path":
                str(STAGE30_INPUT),
            "sha256":
                STAGE30_INPUT_SHA,
            "size_bytes":
                STAGE30_INPUT.stat().st_size,
            "measurement_rows":
                576000,
            "structural_seed_count":
                30,
        },
        "timing_adapter": {
            "execution_path":
                str(TIMING_ADAPTER),
            "sha256":
                TIMING_ADAPTER_SHA,
        },
        "m5d_manifest": {
            "execution_path":
                str(M5D_MANIFEST),
            "sha256":
                M5D_MANIFEST_SHA,
        },
    },
    "lossless_repository_materialization": {
        "archive_sha256":
            archive_sha,
        "archive_size_bytes":
            archive_size,
        "chunk_size_limit_bytes":
            chunk_limit,
        "chunk_count":
            len(chunk_rows),
        "chunks":
            chunk_rows,
        "raw_large_csv_committed_directly":
            False,
        "exact_bytes_recoverable_from_chunks":
            True,
    },
    "scientific_values_modified":
        False,
    "precision_analysis_performed":
        False,
}

write_json(
    validated /
    "VALIDATED_INPUTS.json",
    validated_inputs,
)

(
    validated /
    "chunks.sha256"
).write_text(
    "".join(
        (
            f"{x['sha256']}  "
            f"chunks/{x['filename']}\n"
        )
        for x in chunk_rows
    ),
    encoding="utf-8",
)

(
    validated /
    "RESTORE.md"
).write_text(
    "# SA5 Stage-30 final precision validated inputs\n\n"
    "The chunks contain the exact M5D inputs used by "
    "the unique Stage-30 precision execution.\n\n"
    f"- Archive SHA-256: `{archive_sha}`\n"
    f"- Chunk count: `{len(chunk_rows)}`\n"
    f"- Stage-20 reconstructed SHA-256: "
    f"`{STAGE20_INPUT_SHA}`\n"
    f"- Stage-30 combined SHA-256: "
    f"`{STAGE30_INPUT_SHA}`\n\n"
    "Reconstruct with:\n\n"
    "```bash\n"
    "cat chunks/sa5_stage30_validated_inputs.tar.gz.part* "
    "> /tmp/sa5_stage30_validated_inputs.tar.gz\n"
    f"echo '{archive_sha}  "
    "/tmp/sa5_stage30_validated_inputs.tar.gz' "
    "| sha256sum -c -\n"
    "tar -xzf "
    "/tmp/sa5_stage30_validated_inputs.tar.gz "
    "-C /tmp\n"
    "```\n",
    encoding="utf-8",
)

print(
    f"validated_input_archive_sha256={archive_sha}"
)
print(
    f"validated_input_archive_size_bytes={archive_size}"
)
print(
    "validated_input_archive_chunk_count="
    f"{len(chunk_rows)}"
)
print(
    "validated_input_materialization=PASS"
)
print()


# ------------------------------------------------------------------
print(
    "=== 6. Bind exact unique analyzer command ==="
)

intervals = (
    precision /
    "sa5_stage30_precision_intervals.csv"
)

report_json = (
    precision /
    "sa5_stage30_precision_report.json"
)

report_md = (
    precision /
    "sa5_stage30_precision_report.md"
)

log = (
    precision /
    "sa5_stage30_precision_analyzer.log"
)

started = (
    precision /
    "SA5_STAGE30_PRECISION_STARTED.json"
)

exit_record = (
    precision /
    "SA5_STAGE30_ANALYZER_EXIT.json"
)

validation = (
    precision /
    "SA5_STAGE30_PRECISION_VALIDATION.json"
)

execution_manifest = (
    precision /
    "SA5_STAGE30_PRECISION_EXECUTION_MANIFEST.json"
)

complete = (
    precision /
    "SA5_STAGE30_PRECISION_COMPLETE.json"
)

verdict = (
    precision /
    "SA5_STAGE30_FINAL_VERDICT.json"
)

decision_json = (
    plan /
    "sa5_objective_count_stage30_precision_decision.json"
)

decision_md = (
    plan /
    "sa5_objective_count_stage30_precision_decision.md"
)

for p in (
    started,
    exit_record,
    log,
    intervals,
    report_json,
    report_md,
    validation,
    execution_manifest,
    complete,
    verdict,
):

    if p.exists():
        raise SystemExit(
            f"[STOP] execution artifact exists: {p}"
        )

exec_argv = list(
    m5d_argv
)

exec_argv[0] = (
    str(python_exec)
)

replace_flag(
    exec_argv,
    "--intervals-csv",
    str(intervals),
)

replace_flag(
    exec_argv,
    "--report-json",
    str(report_json),
)

replace_flag(
    exec_argv,
    "--report-md",
    str(report_md),
)

write_json(
    validated /
    "EXECUTION_COMMAND.json",
    {
        "schema_version":
            "mcad-sa5-stage30-final-precision-execution-command-v1",
        "created_at_utc":
            utcnow(),
        "canonical_head":
            EXPECTED_HEAD,
        "source":
            "M5D_BUILD_MANIFEST future analyzer argv",
        "output_path_rebindings_only":
            True,
        "scientific_parameters_changed":
            False,
        "cwd":
            str(ROOT),
        "argv":
            exec_argv,
    },
)

# Recheck immutable scientific parameters after output rebinding.
if flag(
    exec_argv,
    "--stage-size",
) != "30":
    raise SystemExit(
        "[STOP] rebound stage-size changed"
    )

if flag(
    exec_argv,
    "--factor",
) != "objective_count":
    raise SystemExit(
        "[STOP] rebound factor changed"
    )

if resolve_arg(
    flag(
        exec_argv,
        "--observations",
    )
) != STAGE30_INPUT.resolve():

    raise SystemExit(
        "[STOP] rebound input changed"
    )

if resolve_arg(
    flag(
        exec_argv,
        "--timing-report",
    )
) != TIMING_ADAPTER.resolve():

    raise SystemExit(
        "[STOP] rebound adapter changed"
    )

print(
    "execution_command_binding=PASS"
)
print(
    "scientific_parameter_change=false"
)
print()


# ------------------------------------------------------------------
print(
    "=== 7. Persist validated inputs BEFORE scientific execution ==="
)

run(
    [
        "git",
        "add",
        "-f",
        "--",
        str(validated_rel),
    ],
    cwd=wt,
    capture=False,
)

run(
    [
        "git",
        "commit",
        "-m",
        (
            "chore(experiments): materialize SA5 "
            "Stage-30 final precision inputs"
        ),
    ],
    cwd=wt,
    capture=False,
)

pre_commit = gout(
    [
        "rev-parse",
        "HEAD",
    ],
    cwd=wt,
)

run(
    [
        "git",
        "push",
        "-u",
        "origin",
        persist_branch,
    ],
    cwd=wt,
    capture=False,
)

remote_row = run(
    [
        "git",
        "ls-remote",
        "origin",
        f"refs/heads/{persist_branch}",
    ]
).stdout.strip()

if (
    not remote_row
    or remote_row.split()[0]
    != pre_commit
):
    raise SystemExit(
        "[STOP] pre-execution remote persistence failed"
    )

print(
    f"pre_execution_persistence_commit={pre_commit}"
)
print(
    "validated_inputs_remote_persistence=PASS"
)
print()


# ------------------------------------------------------------------
print(
    "=== 8. IRREVERSIBLE MARKER + UNIQUE ANALYZER INVOCATION ==="
)

marker_payload = {
    "schema_version":
        "mcad-sa5-objective-count-stage30-final-precision-start-v1",
    "status":
        "stage30_final_precision_execution_started",
    "started_at_utc":
        utcnow(),
    "canonical_branch":
        BASE,
    "canonical_head":
        EXPECTED_HEAD,
    "persistence_branch":
        persist_branch,
    "origin":
        origin,
    "operator_confirmation_received":
        True,
    "operator_confirmation":
        OPERATOR_CONFIRMATION,
    "factor":
        "objective_count",
    "stage_size":
        30,
    "final_execution_invocation_number":
        1,
    "final_execution_invocation_limit":
        1,
    "rerun_authorized":
        False,
    "stage40_authorized":
        False,
    "analyzer": {
        "path":
            str(ROOT / ANALYZER),
        "sha256":
            ANALYZER_SHA,
    },
    "preregistration": {
        "path":
            str(ROOT / PREREG),
        "sha256":
            PREREG_SHA,
    },
    "m5d": {
        "manifest_path":
            str(M5D_MANIFEST),
        "manifest_sha256":
            M5D_MANIFEST_SHA,
        "stage30_input_path":
            str(STAGE30_INPUT),
        "stage30_input_sha256":
            STAGE30_INPUT_SHA,
        "stage30_measurement_rows":
            576000,
        "structural_seed_count":
            30,
        "timing_adapter_path":
            str(TIMING_ADAPTER),
        "timing_adapter_sha256":
            TIMING_ADAPTER_SHA,
    },
    "protocol": {
        "levels":
            LEVELS,
        "steps":
            STEPS,
        "measurements_per_cluster":
            100,
        "bootstrap_repetitions":
            10000,
        "bootstrap_seed":
            20260728,
        "confidence_level":
            0.95,
        "median_target":
            0.10,
        "p95_target":
            0.15,
        "maximum_protocol_stage":
            30,
    },
    "validated_input_repository_materialization": {
        "manifest":
            str(
                validated_rel /
                "VALIDATED_INPUTS.json"
            ),
        "archive_sha256":
            archive_sha,
        "chunk_count":
            len(chunk_rows),
    },
}

# From marker creation onward, no second analyzer invocation is allowed.
write_json(
    started,
    marker_payload,
    exclusive=True,
)

started_sha = sha(
    started
)

print(
    "stage30_precision_start_marker=PASS"
)
print(
    f"stage30_precision_start_marker_sha256={started_sha}"
)
print(
    "precision_boundary=STARTED"
)
print(
    "FROM_THIS_POINT_RERUN_FORBIDDEN=true",
    flush=True,
)

launch_exception = None
analyzer_rc = None

try:

    # Marker and invocation are deliberately adjacent.
    with log.open(
        "x",
        encoding="utf-8",
    ) as lf:

        cp = subprocess.run(
            exec_argv,
            cwd=str(ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            text=True,
        )

    analyzer_rc = (
        cp.returncode
    )

except Exception as exc:

    launch_exception = (
        f"{type(exc).__name__}: {exc}"
    )

exit_payload = {
    "schema_version":
        "mcad-sa5-stage30-final-precision-analyzer-exit-v1",
    "completed_at_utc":
        utcnow(),
    "invocation_attempted":
        True,
    "invocation_count":
        1,
    "rerun_authorized":
        False,
    "stage40_authorized":
        False,
    "analyzer_exit_status":
        analyzer_rc,
    "launch_exception":
        launch_exception,
    "start_marker_sha256":
        started_sha,
    "analyzer_log": {
        "path":
            str(log),
        "exists":
            log.exists(),
        "sha256":
            sha(log)
            if log.exists()
            else None,
        "size_bytes":
            log.stat().st_size
            if log.exists()
            else 0,
    },
}

write_json(
    exit_record,
    exit_payload,
    exclusive=True,
)

print(
    "final_scientific_analyzer_invocation_count=1"
)
print(
    f"analyzer_exit_status={analyzer_rc}"
)
print(
    f"analyzer_launch_exception={launch_exception}"
)
print(
    "rerun_forbidden=true"
)
print()


# ------------------------------------------------------------------
print(
    "=== 9. Validate completed outputs WITHOUT rerun ==="
)

errors = []

all_median = None
all_p95 = None
all_precision = None

report_status = None
report_sufficient = None
post_stage30_review = None

cell_count = None
interval_count = None


if launch_exception is not None:

    errors.append(
        "analyzer launch exception: "
        f"{launch_exception}"
    )

elif analyzer_rc != 0:

    errors.append(
        "analyzer returned nonzero status: "
        f"{analyzer_rc}"
    )

else:

    for p in (
        intervals,
        report_json,
        report_md,
    ):

        if (
            not p.is_file()
            or p.stat().st_size <= 0
        ):
            errors.append(
                f"missing/empty analyzer output: {p}"
            )


if not errors:

    try:

        report = json.loads(
            report_json.read_text(
                encoding="utf-8"
            )
        )

        report_status = (
            report.get("status")
        )

        if (
            report.get("stage_size")
            != 30
        ):
            errors.append(
                "report stage_size="
                f"{report.get('stage_size')!r}"
            )

        if (
            report.get(
                "structural_seed_count"
            )
            != 30
        ):
            errors.append(
                "report structural_seed_count="
                f"{report.get('structural_seed_count')!r}"
            )

        if (
            report.get(
                "inputs",
                {},
            ).get(
                "observation_count"
            )
            != 576000
        ):
            errors.append(
                "report observation_count="
                f"{report.get('inputs', {}).get('observation_count')!r}"
            )

        cells = (
            report.get(
                "cell_results"
            )
        )

        if not isinstance(
            cells,
            list,
        ):
            errors.append(
                "report cell_results missing/not-list"
            )
            cells = []

        cell_count = len(
            cells
        )

        if cell_count != 192:
            errors.append(
                f"report cell_count={cell_count}"
            )

        expected_pairs = {
            (level, step)
            for level in LEVELS
            for step in STEPS
        }

        pairs = set()
        gates = []

        for cell in cells:

            try:
                pair = (
                    int(
                        cell[
                            "factor_level"
                        ]
                    ),
                    int(
                        cell[
                            "step_index"
                        ]
                    ),
                )
            except Exception:
                errors.append(
                    "report cell missing "
                    "factor_level/step_index"
                )
                continue

            if pair in pairs:
                errors.append(
                    f"duplicate report cell={pair}"
                )

            pairs.add(pair)

            if cell.get(
                "factor"
            ) not in (
                None,
                "objective_count",
            ):
                errors.append(
                    f"report factor mismatch cell={pair}"
                )

            mt = bval(
                cell.get(
                    "median_target_met"
                )
            )

            pt = bval(
                cell.get(
                    "p95_target_met"
                )
            )

            at = bval(
                cell.get(
                    "all_cell_targets_met"
                )
            )

            if None in (
                mt,
                pt,
                at,
            ):
                errors.append(
                    "report boolean gate missing "
                    f"cell={pair}"
                )

            else:

                if at != (
                    mt and pt
                ):
                    errors.append(
                        "report cell gate inconsistency "
                        f"cell={pair}"
                    )

                gates.append(
                    (
                        pair,
                        mt,
                        pt,
                        at,
                    )
                )

        if (
            pairs
            and pairs
            != expected_pairs
        ):
            errors.append(
                "report canonical level-step set mismatch"
            )

        if len(gates) == 192:

            all_median = all(
                x[1]
                for x in gates
            )

            all_p95 = all(
                x[2]
                for x in gates
            )

            all_precision = all(
                x[3]
                for x in gates
            )

        with intervals.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            interval_rows = list(
                csv.DictReader(f)
            )

        interval_count = len(
            interval_rows
        )

        if interval_count != 192:

            errors.append(
                "interval row count="
                f"{interval_count}"
            )

        else:

            interval_pairs = set()

            for row in interval_rows:

                try:
                    pair = (
                        int(
                            row[
                                "factor_level"
                            ]
                        ),
                        int(
                            row[
                                "step_index"
                            ]
                        ),
                    )
                except Exception:
                    errors.append(
                        "interval row missing level/step"
                    )
                    continue

                interval_pairs.add(
                    pair
                )

                if row.get(
                    "factor"
                ) not in (
                    None,
                    "objective_count",
                ):
                    errors.append(
                        "interval factor mismatch "
                        f"cell={pair}"
                    )

                mt = bval(
                    row.get(
                        "median_target_met"
                    )
                )

                pt = bval(
                    row.get(
                        "p95_target_met"
                    )
                )

                at = bval(
                    row.get(
                        "all_cell_targets_met"
                    )
                )

                if None in (
                    mt,
                    pt,
                    at,
                ):
                    errors.append(
                        "interval boolean missing "
                        f"cell={pair}"
                    )

                elif at != (
                    mt and pt
                ):
                    errors.append(
                        "interval gate inconsistency "
                        f"cell={pair}"
                    )

            if (
                interval_pairs
                != expected_pairs
            ):
                errors.append(
                    "interval canonical level-step "
                    "set mismatch"
                )

        if (
            all_precision
            is not None
        ):

            expected_status = (
                "stage30_precision_targets_met"
                if all_precision
                else "stage30_precision_targets_not_met"
            )

            if (
                report_status
                != expected_status
            ):
                errors.append(
                    "report status mismatch: "
                    f"{report_status!r} != "
                    f"{expected_status!r}"
                )

            report_sufficient = (
                report.get(
                    "stage30_sufficient"
                )
            )

            if (
                report_sufficient
                is not all_precision
            ):
                errors.append(
                    "stage30_sufficient inconsistent "
                    "with cell gates"
                )

            if (
                report.get(
                    "all_median_targets_met"
                )
                is not all_median
            ):
                errors.append(
                    "all_median_targets_met inconsistent"
                )

            if (
                report.get(
                    "all_p95_targets_met"
                )
                is not all_p95
            ):
                errors.append(
                    "all_p95_targets_met inconsistent"
                )

            if (
                report.get(
                    "all_precision_targets_met"
                )
                is not all_precision
            ):
                errors.append(
                    "all_precision_targets_met inconsistent"
                )

            post_stage30_review = (
                report.get(
                    "post_stage30_review_required"
                )
            )

            if (
                post_stage30_review
                is not (
                    not all_precision
                )
            ):
                errors.append(
                    "post_stage30_review_required "
                    "inconsistent"
                )

    except Exception as exc:

        errors.append(
            "validation exception: "
            f"{type(exc).__name__}: {exc}"
        )


validation_pass = (
    not errors
)

write_json(
    validation,
    {
        "schema_version":
            "mcad-sa5-stage30-final-precision-validation-v1",
        "validated_at_utc":
            utcnow(),
        "validation_pass":
            validation_pass,
        "analyzer_exit_status":
            analyzer_rc,
        "launch_exception":
            launch_exception,
        "report_status":
            report_status,
        "canonical_cell_result_count":
            cell_count,
        "canonical_interval_row_count":
            interval_count,
        "all_median_targets_met":
            all_median,
        "all_p95_targets_met":
            all_p95,
        "all_precision_targets_met":
            all_precision,
        "stage30_sufficient":
            report_sufficient,
        "post_stage30_review_required":
            post_stage30_review,
        "errors":
            errors,
        "rerun_authorized":
            False,
        "stage40_authorized":
            False,
    },
    exclusive=True,
)

print(
    "scientific_output_validation="
    f"{'PASS' if validation_pass else 'FAIL'}"
)
print(
    f"canonical_cell_result_count={cell_count}"
)
print(
    f"canonical_interval_row_count={interval_count}"
)
print(
    f"report_status={report_status}"
)
print(
    f"all_median_targets_met={all_median}"
)
print(
    f"all_p95_targets_met={all_p95}"
)
print(
    f"all_precision_targets_met={all_precision}"
)
print(
    f"stage30_sufficient={report_sufficient}"
)
print(
    "post_stage30_review_required="
    f"{post_stage30_review}"
)

for error in errors:
    print(
        f"validation_error={error}"
    )

print()


# ------------------------------------------------------------------
print(
    "=== 10. Terminal Stage-30 decision ==="
)

result_files = {}

for p in (
    started,
    exit_record,
    log,
    intervals,
    report_json,
    report_md,
    validation,
):

    result_files[
        p.name
    ] = {
        "path":
            str(p),
        "exists":
            p.exists(),
        "size_bytes":
            p.stat().st_size
            if p.exists()
            else 0,
        "sha256":
            sha(p)
            if p.exists()
            else None,
    }


if validation_pass:

    sufficient = bool(
        all_precision
    )

    if sufficient:

        decision_status = (
            "stage30_precision_targets_met_terminal"
        )

        next_stage = (
            "freeze_objective_count_stage30_precision_"
            "then_integrate_publication"
        )

    else:

        decision_status = (
            "stage30_precision_targets_not_met_"
            "terminal_precision_limit"
        )

        next_stage = (
            "document_stage30_precision_limit_and_"
            "close_sa5_objective_count"
        )

    decision = {
        "schema_version":
            "mcad-sa5-objective-count-stage30-precision-decision-v1",
        "status":
            decision_status,
        "created_at_utc":
            utcnow(),
        "canonical_head_at_execution":
            EXPECTED_HEAD,
        "persistence_branch":
            persist_branch,
        "scientific_execution": {
            "analyzer_exit_status":
                0,
            "successful_precision_analysis_count":
                1,
            "successful_canonical_bootstrap_execution_count":
                1,
            "bootstrap_repetitions":
                10000,
            "bootstrap_seed":
                20260728,
            "confidence_level":
                0.95,
            "median_target":
                0.10,
            "p95_target":
                0.15,
            "structural_seed_cluster_count":
                30,
            "measurement_observation_count":
                576000,
            "canonical_cell_count":
                192,
        },
        "gate": {
            "all_median_targets_met":
                all_median,
            "all_p95_targets_met":
                all_p95,
            "all_precision_targets_met":
                all_precision,
            "stage30_sufficient":
                sufficient,
            "post_stage30_review_required":
                not sufficient,
        },
        "controls": {
            "stage30_rerun_forbidden":
                True,
            "stage40_authorized":
                False,
            "additional_timing_authorized":
                False,
            "additional_bootstrap_authorized":
                False,
            "bootstrap_parameter_changes_authorized":
                False,
            "threshold_changes_authorized":
                False,
            "manuscript_modified":
                False,
        },
        "next_stage":
            next_stage,
    }

    write_json(
        decision_json,
        decision,
        exclusive=True,
    )

    decision_md.write_text(
        "# SA5 objective-count Stage-30 precision decision\n\n"
        "- Unique Stage-30 precision execution: "
        "`PASS` (analyzer exit `0`).\n"
        "- Structural-seed clusters: `30`.\n"
        "- Measurement observations: `576000`.\n"
        "- Canonical bootstrap repetitions: `10000`.\n"
        "- Bootstrap seed: `20260728`.\n"
        f"- All median precision targets met: "
        f"`{str(all_median).lower()}`.\n"
        f"- All p95 precision targets met: "
        f"`{str(all_p95).lower()}`.\n"
        f"- All precision targets met: "
        f"`{str(all_precision).lower()}`.\n"
        f"- Stage-30 sufficient: "
        f"`{str(sufficient).lower()}`.\n"
        "- Stage-40 authorized: `false`.\n"
        "- Stage-30 rerun: `forbidden`.\n"
        f"- Next stage: `{next_stage}`.\n",
        encoding="utf-8",
    )

    write_json(
        complete,
        {
            "schema_version":
                "mcad-sa5-stage30-final-precision-complete-v1",
            "status":
                "stage30_final_precision_execution_complete",
            "completed_at_utc":
                utcnow(),
            "analyzer_exit_status":
                0,
            "validation_pass":
                True,
            "stage30_sufficient":
                sufficient,
            "all_precision_targets_met":
                all_precision,
            "successful_precision_analysis_count":
                1,
            "successful_canonical_bootstrap_execution_count":
                1,
            "rerun_forbidden":
                True,
            "stage40_authorized":
                False,
            "next_stage":
                next_stage,
        },
        exclusive=True,
    )

    write_json(
        verdict,
        {
            "schema_version":
                "mcad-sa5-stage30-final-verdict-v1",
            "status": (
                "stage30_precision_targets_met"
                if sufficient
                else "stage30_precision_targets_not_met"
            ),
            "created_at_utc":
                utcnow(),
            "terminal_stage":
                30,
            "stage30_sufficient":
                sufficient,
            "all_precision_targets_met":
                all_precision,
            "post_stage30_review_required":
                not sufficient,
            "rerun_forbidden":
                True,
            "additional_replications_authorized":
                False,
            "additional_bootstrap_authorized":
                False,
            "stage40_authorized":
                False,
            "next_stage":
                next_stage,
        },
        exclusive=True,
    )

    execution_status = (
        "stage30_precision_execution_complete"
    )

else:

    sufficient = None

    next_stage = (
        "inspect_persisted_completed_outputs_without_rerun"
    )

    if (
        launch_exception is not None
        or analyzer_rc != 0
    ):
        execution_status = (
            "stage30_precision_execution_failed"
        )

        next_stage = (
            "persist_failure_and_review_without_rerun"
        )

    else:
        execution_status = (
            "stage30_precision_execution_complete_"
            "but_validation_failed"
        )


write_json(
    execution_manifest,
    {
        "schema_version":
            "mcad-sa5-stage30-final-precision-execution-manifest-v1",
        "status":
            execution_status,
        "completed_at_utc":
            utcnow(),
        "canonical_head":
            EXPECTED_HEAD,
        "persistence_branch":
            persist_branch,
        "final_execution_invocation_count":
            1,
        "analyzer_exit_status":
            analyzer_rc,
        "launch_exception":
            launch_exception,
        "successful_precision_analysis_count": (
            1
            if (
                analyzer_rc == 0
                and launch_exception is None
            )
            else 0
        ),
        "successful_canonical_bootstrap_execution_count": (
            1
            if (
                analyzer_rc == 0
                and launch_exception is None
            )
            else 0
        ),
        "rerun_forbidden":
            True,
        "stage40_authorized":
            False,
        "input": {
            "path_at_execution":
                str(STAGE30_INPUT),
            "sha256":
                STAGE30_INPUT_SHA,
            "measurement_row_count":
                576000,
            "structural_seed_count":
                30,
            "repository_materialization_manifest":
                str(
                    validated_rel /
                    "VALIDATED_INPUTS.json"
                ),
            "repository_materialization_archive_sha256":
                archive_sha,
        },
        "execution_evidence":
            result_files,
        "validation": {
            "path":
                str(validation),
            "sha256":
                sha(validation),
            "validation_pass":
                validation_pass,
            "stage30_sufficient":
                sufficient,
            "all_precision_targets_met":
                all_precision,
        },
        "controls": {
            "absolute_timing_magnitudes_interpreted":
                False,
            "precision_statistics_computed": (
                analyzer_rc == 0
                and launch_exception is None
            ),
            "scientific_freeze":
                False,
            "manuscript_modified":
                False,
            "additional_analyzer_rerun_authorized":
                False,
            "additional_timing_execution_authorized":
                False,
            "stage40_authorized":
                False,
        },
        "next_stage":
            next_stage,
    },
    exclusive=True,
)

print(
    f"execution_manifest_status={execution_status}"
)
print(
    "stage30_terminal_decision_validated="
    f"{str(validation_pass).lower()}"
)
print(
    f"stage30_sufficient={sufficient}"
)
print(
    f"next_stage={next_stage}"
)
print(
    "stage40_authorized=false"
)
print(
    "rerun_forbidden=true"
)
print()


# ------------------------------------------------------------------
print(
    "=== 11. Transfer ALL evidence to original GitHub repo ==="
)

registry = (
    validated /
    "FINAL_ARTIFACT_SHA256SUMS"
)

paths = []

for base in (
    precision,
    validated,
):

    for p in sorted(
        base.rglob("*")
    ):
        if (
            p.is_file()
            and p != registry
        ):
            paths.append(p)

for p in (
    decision_json,
    decision_md,
):
    if p.exists():
        paths.append(p)

with registry.open(
    "w",
    encoding="utf-8",
) as f:

    for p in sorted(
        set(paths),
        key=lambda x: str(x),
    ):
        rel = p.relative_to(
            wt
        )

        f.write(
            f"{sha(p)}  {rel}\n"
        )

run(
    [
        "git",
        "add",
        "-f",
        "--",
        str(PRECISION_REL),
        str(validated_rel),
    ],
    cwd=wt,
    capture=False,
)

if decision_json.exists():

    run(
        [
            "git",
            "add",
            "-f",
            "--",
            str(
                decision_json.relative_to(
                    wt
                )
            ),
            str(
                decision_md.relative_to(
                    wt
                )
            ),
        ],
        cwd=wt,
        capture=False,
    )

staged = gout(
    [
        "diff",
        "--cached",
        "--name-only",
    ],
    cwd=wt,
).splitlines()

if not staged:
    raise SystemExit(
        "[STOP] no result staged. "
        "DO NOT RERUN ANALYZER."
    )

print(
    f"final_staged_file_count={len(staged)}"
)

for p in staged:
    print(
        f"staged={p}"
    )

run(
    [
        "git",
        "commit",
        "-m",
        (
            "evidence(experiments): persist SA5 "
            "Stage-30 final precision result"
        ),
    ],
    cwd=wt,
    capture=False,
)

final_commit = gout(
    [
        "rev-parse",
        "HEAD",
    ],
    cwd=wt,
)

run(
    [
        "git",
        "push",
        "origin",
        persist_branch,
    ],
    cwd=wt,
    capture=False,
)

remote = run(
    [
        "git",
        "ls-remote",
        "origin",
        f"refs/heads/{persist_branch}",
    ]
).stdout.strip()

if not remote:
    raise SystemExit(
        "[STOP] remote result branch not visible. "
        "DO NOT RERUN ANALYZER."
    )

remote_head = (
    remote.split()[0]
)

if remote_head != final_commit:
    raise SystemExit(
        "[STOP] remote result HEAD mismatch. "
        "DO NOT RERUN ANALYZER."
    )

print(
    f"final_persistence_commit={final_commit}"
)
print(
    f"remote_persistence_head={remote_head}"
)
print(
    "remote_result_materialization=PASS"
)
print()


# ------------------------------------------------------------------
print(
    "=== 12. Canonical preservation ==="
)

after_branch = gout(
    [
        "branch",
        "--show-current",
    ]
)

after_head = gout(
    [
        "rev-parse",
        "HEAD",
    ]
)

after_status = gout(
    [
        "status",
        "--porcelain",
    ]
)

print(
    f"canonical_branch_after={after_branch}"
)
print(
    f"canonical_head_after={after_head}"
)
print(
    "canonical_clean_after="
    f"{str(not bool(after_status)).lower()}"
)

if after_branch != BASE:
    raise SystemExit(
        "[STOP] canonical branch changed unexpectedly"
    )

if after_head != EXPECTED_HEAD:
    raise SystemExit(
        "[STOP] canonical HEAD changed unexpectedly"
    )

if after_status:
    raise SystemExit(
        "[STOP] canonical worktree changed unexpectedly"
    )

print(
    "canonical_preservation_gate=PASS"
)
print()


print("=" * 72)
print("M5E_FINAL")
print(
    "unique_stage30_precision_analyzer_invocation_count=1"
)
print(
    f"analyzer_exit_status={analyzer_rc}"
)
print(
    "scientific_output_validation="
    f"{'PASS' if validation_pass else 'FAIL'}"
)
print(
    f"report_status={report_status}"
)
print(
    f"all_median_targets_met={all_median}"
)
print(
    f"all_p95_targets_met={all_p95}"
)
print(
    f"all_precision_targets_met={all_precision}"
)
print(
    f"stage30_sufficient={sufficient}"
)
print(
    "rerun_forbidden=true"
)
print(
    "stage40_authorized=false"
)
print(
    f"persistence_branch={persist_branch}"
)
print(
    f"persistence_commit={final_commit}"
)
print(
    "target_repository=digitcreadev/MCAD_improve3"
)
print(
    "all_execution_results_materialized_to_original_repo=true"
)
print(
    f"next_stage={next_stage}"
)
print("=" * 72)


# A scientific FAIL caused by unmet precision targets still exits 0 here:
# it is a valid terminal experimental verdict.
#
# Nonzero exit below is reserved for execution/validation failure.
if launch_exception is not None:
    raise SystemExit(74)

if analyzer_rc != 0:
    raise SystemExit(
        analyzer_rc
        if analyzer_rc is not None
        else 75
    )

if not validation_pass:
    raise SystemExit(76)

