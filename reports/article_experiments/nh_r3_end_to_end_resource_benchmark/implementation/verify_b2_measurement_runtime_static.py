from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PARENT = "8c328b036c498637aebd877f19160265f29625f7"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
R3_REL = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
EXPECTED_B1 = {
    "config/r3_b1_measurement_preregistration.json": "2a0453d1ae58465d027c43f1792cbb91b60f6df65dc50544274cbbffdfed166f",
    "config/r3_b1_arm_order_schedule.csv": "6076e70364a55fecaf55bc9a7c2b7ce767ac2562a661c27bafb78f2768544c7e",
    "docs/R3_B1_MEASUREMENT_PREREGISTRATION.md": "8b4d326e66eb8438d509822f1cd06aad031fbf785fd3d377461d96e18cac31ec",
    "results/MCAD_NH_R3_B1_PREREGISTRATION_FREEZE.json": "a4c1f29a4d0639fbbdd5bf7d77a65d383ec2184953db6044f160c3983a8a06f8",
}


def fail(msg: str) -> None:
    raise SystemExit(f"R3_B2_ISOLATED_STATIC_VERIFY=FAIL reason={msg}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def fn_source(tree: ast.AST, source: str, name: str) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(source, node)
            if seg is None:
                fail(f"source_segment_missing:{name}")
            return seg
    fail(f"function_missing:{name}")
    return ""


def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    r3 = repo / R3_REL
    protection = json.loads((r3 / "config/r3_b2_legacy_protection.json").read_text(encoding="utf-8"))

    if git("branch", "--show-current", cwd=repo) != BRANCH:
        fail("branch_changed")
    if git("rev-parse", "HEAD", cwd=repo) != PARENT:
        fail("parent_head_changed")

    for rel, expected in EXPECTED_B1.items():
        p = r3 / rel
        if not p.is_file() or sha256(p) != expected:
            fail(f"b1_artifact_changed:{rel}")
        print(f"b1_artifact_{rel.replace('/', '_')}=PASS")

    declared = (r3 / "results/MCAD_NH_R3_B1_PREREGISTRATION_FREEZE_SHA256.txt").read_text(encoding="utf-8").split()[0]
    if declared != EXPECTED_B1["results/MCAD_NH_R3_B1_PREREGISTRATION_FREEZE.json"]:
        fail("b1_declared_freeze_changed")
    print("b1_declared_freeze=PASS")

    b1 = json.loads((r3 / "config/r3_b1_measurement_preregistration.json").read_text(encoding="utf-8"))
    if b1["authorization"]["measured_pilot_authorized"] is not False:
        fail("measured_pilot_became_authorized")
    if b1["scientific_authority"]["live_gate_may_relabel_frozen_action"] is not False:
        fail("live_gate_relabel_became_authorized")
    print("b1_scientific_authority=PASS")

    if protection.get("parent_head") != PARENT or protection.get("measurement_authorized") is not False:
        fail("legacy_protection_contract_invalid")

    for rel, expected_blob in protection["protected_legacy_blobs"].items():
        actual_blob = git("hash-object", rel, cwd=repo)
        if actual_blob != expected_blob:
            fail(f"protected_legacy_blob_changed:{rel}:{actual_blob}")
        tracked_blob = git("rev-parse", f"HEAD:{rel}", cwd=repo)
        if tracked_blob != expected_blob:
            fail(f"protected_head_blob_changed:{rel}:{tracked_blob}")
        print(f"protected_legacy_{rel.replace('/', '_')}=PASS")

    protected = list(protection["protected_legacy_blobs"].keys())
    subprocess.run(["git", "diff", "--exit-code", "--", *protected], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    print("protected_legacy_worktree_diff=NONE")

    for rel, expected_sha in protection["r3_only_files"].items():
        p = repo / rel
        if not p.is_file() or sha256(p) != expected_sha:
            fail(f"r3_only_file_changed:{rel}")
        if subprocess.run(["git", "cat-file", "-e", f"HEAD:{rel}"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            fail(f"r3_only_file_already_in_parent:{rel}")
        print(f"r3_only_{rel.replace('/', '_')}=PASS")

    runtime = repo / "bi-stack/mcad-proxy/r3_measurement_app.py"
    source = runtime.read_text(encoding="utf-8")
    try:
        compile(source, str(runtime), "exec")
        tree = ast.parse(source)
    except SyntaxError as exc:
        fail(f"runtime_syntax:{exc}")

    if '@legacy.app.post("/bi/r3/measurement/gate-only")' not in source:
        fail("gate_route_missing")
    if '@legacy.app.post("/bi/r3/measurement/full-execute")' not in source:
        fail("full_execute_route_missing")

    gate = fn_source(tree, source, "r3_measurement_gate_only")
    full = fn_source(tree, source, "r3_measurement_full_execute")
    if "legacy.MCAD_EVAL_URL" not in gate or "requests.post" not in gate:
        fail("gate_does_not_call_mcad_eval")
    if "get_gateway().execute" in gate or "MCAD_CKG_URL" in gate:
        fail("gate_contains_forbidden_full_execution_or_ckg_update")
    if '"full_candidate_execution_performed": False' not in gate:
        fail("gate_missing_no_full_execution_marker")
    if '"full_result_ckg_update_performed": False' not in gate:
        fail("gate_missing_no_ckg_marker")
    if "legacy.get_gateway().execute" not in full:
        fail("full_execute_does_not_call_gateway")
    if "MCAD_EVAL_URL" in full or "MCAD_CKG_URL" in full:
        fail("full_execute_contains_forbidden_eval_or_ckg")
    if '"allow_fallback": False' not in full:
        fail("full_execute_missing_fallback_false")
    print("gate_only_separation=PASS")
    print("full_execute_separation=PASS")

    legacy_docker = (repo / "bi-stack/mcad-proxy/Dockerfile").read_text(encoding="utf-8")
    expected_r3_docker = legacy_docker.replace(
        "COPY app.py /app/app.py\n",
        "COPY app.py /app/app.py\nCOPY r3_measurement_app.py /app/r3_measurement_app.py\n",
        1,
    ).replace(
        'CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]',
        'CMD ["uvicorn", "r3_measurement_app:app", "--host", "0.0.0.0", "--port", "9000"]',
        1,
    )
    actual_r3_docker = (repo / "bi-stack/mcad-proxy/Dockerfile.r3-b2").read_text(encoding="utf-8")
    if actual_r3_docker != expected_r3_docker:
        fail("r3_dockerfile_not_exact_isolated_derivative")
    print("isolated_r3_dockerfile=PASS")

    override = (repo / "bi-stack/docker-compose.r3-b2.override.yml").read_text(encoding="utf-8")
    required = [
        "dockerfile: Dockerfile.r3-b2",
        "r3_measurement_app:app",
        "mcad-proxy:",
    ]
    if not all(token in override for token in required):
        fail("r3_compose_override_invalid")
    if "app:app" in override.replace("r3_measurement_app:app", ""):
        fail("legacy_entrypoint_in_r3_override")
    print("isolated_r3_compose_override=PASS")

    print("historical_campaign_runtime_untouched=true")
    print("backend_started_by_verifier=false")
    print("measured_query_executed=false")
    print("commit_performed=false")
    print("push_performed=false")
    print("NO_BACKEND_EXECUTION_PERFORMED=true")
    print("R3_B2_ISOLATED_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
