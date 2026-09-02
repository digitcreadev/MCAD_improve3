#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
E10_HEAD = "7e12c7d831a7dd0bf2893dcf73ea87f676ec6514"
R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")

EXPECTED = {
    "e10_checkpoint": ("results/r3_e10_runtime_integrity_freeze_checkpoint.json", "31707c99daa88f2fc30cb982a0bb90d909e0a2eb46b99831d7ace22615efd453"),
    "e5_contract": ("config/r3_e5_xmla_executor_receipt_static_contract.json", "243558e64e352f7c37ec7b50f5cf7ffa17ee9ac5866a8e013d616b6cb2acd1cd"),
    "e5_schema": ("config/r3_e5_xmla_arm_receipt_schema.json", "7624d0ed5f206ee2aefb142e2b1a79f591e1150620ec5d06d69f91e5bd0b468c"),
    "e6": ("config/r3_e6_xmla_replication_inference_protocol.json", "2d08df7d7c30c1cf1edf3ab07c643bbe439e4a476ac2f21e420c73e41ff420f4"),
    "e7": ("config/r3_e7_xmla_inference_engine_static_contract.json", "20f67fbb3570b7ff694dcf72adf3c9af14071e5a80fa28fb62adbc1028806aee"),
}

BLOBS = {
    "bi-stack/mcad-proxy/r3_measurement_app.py": "376c1c16960565dec35648af8e9d24f136579ff4",
    "bi-stack/mcad-proxy/datawarehouses.yaml": "e0584b8d349b3faea53b857ebc2d3f98a0a95ca2",
    "bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py": "1e6ab0c1f3fb7bdb710d16cf214c6c845fcb667c",
    str(R3 / "implementation/r3_d0_confirmatory_plan.py"): "54750b314717dc370ca65f84ca765c338b4abb2c",
    str(R3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv"): "6b53ab6d271425b9e5113bdd405775f05c6d65df",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("r3_e11_executor_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load executor module")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/workspaces/MCAD_improve3")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.output).resolve()

    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git(repo, "rev-parse", "HEAD") != E10_HEAD:
        raise RuntimeError("E11 static verification must run on exact E10 parent before commit")

    frozen_sha = {}
    for label, (rel, expected) in EXPECTED.items():
        p = repo / R3 / rel
        actual = sha(p)
        if actual != expected:
            raise RuntimeError(f"{label} SHA changed: {actual}")
        frozen_sha[label] = actual

    frozen_blobs = {}
    for rel, expected in BLOBS.items():
        actual = git(repo, "hash-object", str(repo / rel))
        if actual != expected:
            raise RuntimeError(f"frozen blob changed for {rel}: {actual}")
        frozen_blobs[rel] = actual

    app = repo / R3 / "runtime/r3_e11_xmla_measurement_app.py"
    renderer = repo / R3 / "runtime/r3_e11_render_datawarehouses_overlay.py"
    dockerfile = repo / R3 / "runtime/r3_e11_proxy_overlay.Dockerfile"
    compose = repo / R3 / "runtime/r3_e11_measurement.compose.override.template.yml"
    executor = repo / R3 / "implementation/r3_e11_xmla_live_executor.py"
    contract = repo / R3 / "config/r3_e11_xmla_live_executor_static_contract.json"

    for p in (app, renderer, executor):
        compile(p.read_text(encoding="utf-8"), str(p), "exec")

    app_text = app.read_text(encoding="utf-8")
    if "app = frozen_r3.legacy.app" not in app_text:
        raise RuntimeError("E11 app is not bound to historical legacy.app")
    if "app = frozen_r3.app" in app_text:
        raise RuntimeError("invalid direct frozen_r3.app binding detected")
    tree = ast.parse(app_text)
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    required_strings = {
        "adventureworks_xmla",
        "xmla_mondrian",
        "/bi/r3/e11/measurement/gate-only",
        "/bi/r3/e11/measurement/full-execute",
        "mcad.nh_r3.e11.measurement_runtime.v1",
    }
    if not required_strings <= strings:
        raise RuntimeError("E11 runtime app contract strings missing")

    dock = dockerfile.read_text(encoding="utf-8")
    if "ARG BASE_IMAGE" not in dock or "FROM ${BASE_IMAGE}" not in dock:
        raise RuntimeError("E11 Dockerfile does not require explicit base image")
    if "r3_e11_xmla_measurement_app:app" not in dock:
        raise RuntimeError("E11 Dockerfile command not bound to E11 app")

    compose_text = compose.read_text(encoding="utf-8")
    for token in (
        "r3e-mcad-api",
        "r3e-mcad-proxy",
        "adventureworks_xmla",
        "http://r3e-emondrian-adventureworks:8080/emondrian/xmla",
        "R3E_E11_PROXY_IMAGE_REF",
    ):
        if token not in compose_text:
            raise RuntimeError(f"E11 compose template token missing: {token}")

    # Renderer changes exactly one semantic field in the historical registry.
    src = repo / "bi-stack/mcad-proxy/datawarehouses.yaml"
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "overlay.yaml"
        subprocess.run(
            [sys.executable, str(renderer), "--source", str(src), "--output", str(dst)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        before = yaml.safe_load(src.read_text(encoding="utf-8"))
        after = yaml.safe_load(dst.read_text(encoding="utf-8"))
        b_items = {x["id"]: x for x in before["datawarehouses"]}
        a_items = {x["id"]: x for x in after["datawarehouses"]}
        if set(b_items) != set(a_items):
            raise RuntimeError("overlay changed registry entity set")
        diffs = []
        for key in sorted(b_items):
            b = b_items[key]
            a = a_items[key]
            keys = set(b) | set(a)
            for field in sorted(keys):
                if b.get(field) != a.get(field):
                    diffs.append((key, field, b.get(field), a.get(field)))
        expected_diff = [
            (
                "adventureworks_xmla",
                "xmla_url",
                "http://emondrian-adventureworks:8080/emondrian/xmla",
                "http://r3e-emondrian-adventureworks:8080/emondrian/xmla",
            )
        ]
        if diffs != expected_diff:
            raise RuntimeError(f"unexpected registry overlay diffs: {diffs}")

    c = json.loads(contract.read_text(encoding="utf-8"))
    if c["contract_version"] != "mcad.nh_r3.e11.xmla_live_executor_static.v1":
        raise RuntimeError("unexpected E11 contract version")
    if c["parent_e10_head"] != E10_HEAD:
        raise RuntimeError("E11 contract not bound to E10")
    if c["execution_boundary"]["measurement_allowed"] is not False:
        raise RuntimeError("E11 contract unexpectedly authorizes measurement")
    if c["next"] != "R3-E12_RUNTIME_OVERLAY_MATERIALIZATION_AND_MECHANICAL_ENDPOINT_VALIDATION_NO_MEASUREMENT":
        raise RuntimeError("unexpected E11 next station")

    mod = load_module(executor)
    dry = mod.dry_run(repo)
    if dry["semantic_sessions"] != 300 or dry["arm_runs"] != 900 or dry["candidate_actions"] != 21600:
        raise RuntimeError("E11 dry-run plan shape mismatch")
    if dry["gate_evaluations_planned"] != 14400 or dry["full_backend_executions_planned"] != 14580:
        raise RuntimeError("E11 dry-run backend-count plan mismatch")
    if dry["warmup_template_count"] != 7 or dry["expected_receipts"] != 900:
        raise RuntimeError("E11 dry-run warmup/receipt count mismatch")
    if any(dry[k] for k in ("measurement_authorized", "measurement_executed", "backend_query_executed", "http_request_executed", "docker_command_executed", "effect_analysis_performed")):
        raise RuntimeError("E11 dry-run boundary violated")

    auth_path = repo / mod.AUTH_REL
    if auth_path.exists():
        raise RuntimeError("future E13 authorization unexpectedly exists during E11")
    try:
        mod.validate_future_authorization(repo)
    except RuntimeError as exc:
        if "authorization file absent" not in str(exc):
            raise
        refusal = str(exc)
    else:
        raise RuntimeError("E11 authorization refusal unexpectedly did not refuse")

    result = {
        "contract_version": "mcad.nh_r3.e11.xmla_live_executor_static_verification.v1",
        "parent_e10_head": E10_HEAD,
        "frozen_sha256_authorities": frozen_sha,
        "frozen_git_blob_authorities": frozen_blobs,
        "new_files": {
            str(p.relative_to(repo)): {"bytes": p.stat().st_size, "sha256": sha(p)}
            for p in (app, renderer, dockerfile, compose, executor, contract)
        },
        "runtime_overlay": {
            "historical_registry_mutated": False,
            "semantic_diff_count": 1,
            "semantic_diff": {
                "warehouse_id": "adventureworks_xmla",
                "field": "xmla_url",
                "new_value": "http://r3e-emondrian-adventureworks:8080/emondrian/xmla",
            },
            "derived_proxy_build_executed": False,
            "api_proxy_started": False,
        },
        "executor_dry_run": dry,
        "authorization_refusal_reason": refusal,
        "measurement_authorized": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "http_request_executed": False,
        "docker_command_executed": False,
        "effect_analysis_performed": False,
        "scientific_final_freeze_authorized": False,
        "next": "R3-E12_RUNTIME_OVERLAY_MATERIALIZATION_AND_MECHANICAL_ENDPOINT_VALIDATION_NO_MEASUREMENT",
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(dry, indent=2, sort_keys=True))
    print(f"verification_output={out}")
    print(f"verification_output_sha256={sha(out)}")
    print("R3_E11_LIVE_XMLA_EXECUTOR_STATIC_VERIFICATION=PASS_NO_BACKEND_IO")


if __name__ == "__main__":
    main()
