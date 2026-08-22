from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE_PARENT = "8c328b036c498637aebd877f19160265f29625f7"
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def git_bytes(*args: str, cwd: Path) -> bytes:
    return subprocess.check_output(["git", *args], cwd=cwd)


def fn_source(tree: ast.AST, source: str, name: str) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(source, node)
            if seg is None:
                fail(f"source_segment_missing:{name}")
            return seg
    fail(f"function_missing:{name}")
    return ""


def extract_helper_functions(tree: ast.Module, names: set[str]) -> dict[str, Any]:
    selected: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            selected.append(node)
            found.add(node.name)
    missing = names - found
    if missing:
        fail("accounting_helper_missing:" + ",".join(sorted(missing)))
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, Any] = {"Any": Any}
    exec(compile(module, "<r3-accounting-unit>", "exec"), ns, ns)
    return ns


def verify_nvac_accounting_unit(tree: ast.Module) -> None:
    helpers = extract_helper_functions(
        tree,
        {
            "_r3_get_path",
            "_r3_canonical_nvac_evidence",
            "_r3_probe_records",
            "_r3_probe_identity",
            "_r3_nvac_accounting",
        },
    )
    accounting = helpers["_r3_nvac_accounting"]

    raw = {
        "physical_execution": True,
        "response_bytes": 321,
        "elapsed_ms": 9,
        "response_digest": "sha256:probe-one",
        "generated_sql": "SELECT 1",
        "adapter_id": "adventureworks_direct",
        "dw_id": "adventureworks_sql_direct",
    }
    probe = {
        "probe_attempted": True,
        "cache_hit": False,
        "probe_url": "http://mcad-proxy:9000/bi/nvac-probe",
        "probe_query": "SELECT {[Measures].[SalesAmount]} ON COLUMNS FROM [Adventure Works DW]",
        "probe_measure": "SalesAmount",
        "elapsed_ms": 11,
        "non_empty": True,
        "count": 1,
        "raw_probe_summary": raw,
    }
    evidence = {"probe": probe}
    # The MCAD response deliberately aliases the same formal evidence under
    # sat_evidence.nvac_ok and nvac_evidence (and may also expose graph_update).
    duplicate_response = {
        "details": {
            "sat_evidence": {"nvac_ok": evidence},
            "nvac_evidence": evidence,
            "graph_update": {"nvac_evidence": evidence},
        }
    }
    out = accounting(duplicate_response)
    if out.get("canonical_evidence_source") != "details.nvac_evidence":
        fail("nvac_canonical_source_wrong")
    if out.get("physical_uncached_probe_count") != 1:
        fail("nvac_duplicate_representation_double_count")
    if out.get("backend_request_count_including_gate_probes") != 1:
        fail("nvac_backend_request_count_wrong")
    if out.get("physical_uncached_probe_response_bytes") != 321:
        fail("nvac_response_bytes_wrong")

    cache_probe = dict(probe)
    cache_probe["cache_hit"] = True
    cache_out = accounting({"details": {"nvac_evidence": {"probe": cache_probe}}})
    if cache_out.get("physical_uncached_probe_count") != 0:
        fail("nvac_cache_hit_counted_as_physical")
    if cache_out.get("physical_uncached_probe_response_bytes") != 0:
        fail("nvac_cache_hit_bytes_counted")

    none_out = accounting({"details": {"nvac_evidence": {"probe_attempted": False}}})
    if none_out.get("physical_uncached_probe_count") != 0:
        fail("nvac_nonprobe_counted")

    print("nvac_alias_representation_single_count=PASS")
    print("nvac_cache_hit_zero_physical_count=PASS")
    print("nvac_accounting_unit=PASS")


def main() -> None:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    r3 = repo / R3_REL
    protection_path = r3 / "config/r3_b2_legacy_protection.json"
    protection = json.loads(protection_path.read_text(encoding="utf-8"))

    if git("branch", "--show-current", cwd=repo) != BRANCH:
        fail("branch_changed")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_PARENT, "HEAD"],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0:
        fail("b1_parent_not_ancestor")
    print("b1_parent_ancestor=PASS")

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

    if protection.get("parent_head") != BASE_PARENT or protection.get("measurement_authorized") is not False:
        fail("legacy_protection_contract_invalid")
    nvac_contract = protection.get("nvac_accounting") if isinstance(protection.get("nvac_accounting"), dict) else {}
    if nvac_contract.get("alias_representations_count_as_one_physical_probe") is not True:
        fail("nvac_alias_dedup_contract_missing")
    if nvac_contract.get("representation_deduplication_required") is not True:
        fail("nvac_representation_dedup_not_required")
    print("nvac_accounting_contract=PASS")

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

    versioning_states: list[str] = []
    for rel, expected_sha in protection["r3_only_files"].items():
        p = repo / rel
        if not p.is_file() or sha256(p) != expected_sha:
            fail(f"r3_only_file_changed:{rel}")

        tracked = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if tracked:
            head_sha = sha256_bytes(git_bytes("show", f"HEAD:{rel}", cwd=repo))
            if head_sha == expected_sha:
                state = "COMMITTED"
            else:
                changed = subprocess.run(
                    ["git", "diff", "HEAD", "--quiet", "--", rel],
                    cwd=repo,
                ).returncode != 0
                if not changed:
                    fail(f"r3_only_head_hash_mismatch_without_worktree_patch:{rel}")
                state = "WORKTREE_PATCH"
        else:
            state = "UNTRACKED_PRECOMMIT"
        versioning_states.append(state)
        print(f"r3_only_{rel.replace('/', '_')}=PASS state={state}")

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

    verify_nvac_accounting_unit(tree)

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

    print("r3_runtime_versioning_states=" + ",".join(sorted(set(versioning_states))))
    print("historical_campaign_runtime_untouched=true")
    print("backend_started_by_verifier=false")
    print("measured_query_executed=false")
    print("commit_performed=false")
    print("push_performed=false")
    print("NO_BACKEND_EXECUTION_PERFORMED=true")
    print("R3_B2_ISOLATED_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
