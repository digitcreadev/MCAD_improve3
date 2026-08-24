#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
R4_HEAD = "eae990ad9125896cb733261177a0d7dbb8ae934f"

EXPECTED = {
    "d0_protocol": "cd3c64c4e7c67226b8f635953e5a17bc5eca37eb",
    "d0_contract": "6c608b951bca9b262cc69bb7964a48cec79c62b1",
    "r4_contract": "9c836096dac1727fa859a0accc8800ac3c6de89d",
    "r4_driver": "8358bd8e5ca559f928e8da78e2de5dcc41bf687e",
}


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", R4_HEAD, "HEAD"],
        check=True,
    )

    checks = (
        (repo / R3 / "config/r3_d0_confirmatory_inference_protocol.json", EXPECTED["d0_protocol"]),
        (repo / R3 / "config/r3_d0_confirmatory_static_activation_contract.json", EXPECTED["d0_contract"]),
        (repo / R3 / "config/r3_d3_r4_replacement_execution_contract.json", EXPECTED["r4_contract"]),
        (repo / R3 / "implementation/r3_d3_r4_replacement_primary_one_shot.py", EXPECTED["r4_driver"]),
    )
    for path, expected in checks:
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"frozen authority changed: {path} -> {actual}")

    contract = json.loads(
        (repo / R3 / "config/r3_d4_confirmatory_inference_freeze_contract.json")
        .read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.d4.confirmatory_inference_freeze.v1":
        raise RuntimeError("unexpected D4 freeze contract")
    if contract.get("parent_r4_execution_kit_head") != R4_HEAD:
        raise RuntimeError("D4 not bound to R4 execution-kit head")

    src = contract.get("source_measurement") or {}
    expected_source = {
        "archive_name": "MCAD_R3_D3_REPLACEMENT_PRIMARY_RESULTS_20260823T224457Z.tar.gz",
        "archive_sha256": "8ac00f467d7fb2235e6a4df2850278e1893103279077178ffe610db995a91ff5",
        "semantic_sessions": 300,
        "arm_receipts": 900,
        "candidate_records": 21600,
        "gate_evaluations": 14400,
        "full_backend_executions": 14580,
        "fresh_gated_sessions": 600,
        "negative_cgroup_delta_arm_runs": 0,
        "warmup_templates": 7,
    }
    for key, value in expected_source.items():
        if src.get(key) != value:
            raise RuntimeError(f"D4 source binding mismatch: {key}")
    for key in (
        "interrupted_partial_receipts_reused",
        "resume_from_arm_298",
        "fallback_120_activated",
    ):
        if src.get(key) is not False:
            raise RuntimeError(f"D4 source anti-redo boundary violated: {key}")

    inf = contract.get("primary_inference") or {}
    if inf.get("comparison") != "SAFE_PRUNING - PERMISSIVE_GATED":
        raise RuntimeError("D4 primary comparison changed")
    if int(inf.get("sign_flip_replicates", -1)) != 100000:
        raise RuntimeError("D4 sign-flip replicate count changed")
    if int(inf.get("bootstrap_replicates", -1)) != 20000:
        raise RuntimeError("D4 bootstrap replicate count changed")
    if float(inf.get("holm_familywise_alpha", -1)) != 0.05:
        raise RuntimeError("D4 alpha changed")
    if inf.get("seed_namespace_sha256") != "a550a533086d3eafe6fa4512caab03a85b3c8a06b7efb7c805c4da841f5ef8e0":
        raise RuntimeError("D4 seed namespace changed")

    boundary = contract.get("execution_boundary") or {}
    for key in ("backend_query_allowed", "docker_or_service_mutation_allowed", "measurement_allowed"):
        if boundary.get(key) is not False:
            raise RuntimeError(f"D4 execution boundary violated: {key}")
    if boundary.get("effect_analysis_authorized") is not True:
        raise RuntimeError("D4 effect analysis not authorized")

    if contract.get("next_on_pass") != "R3-E0_XMLA_EMONDRIAN_END_TO_END_REPLICATION_STATIC_ACTIVATION_NO_MEASUREMENT":
        raise RuntimeError("unexpected D4 next stage")

    print("r4_execution_kit_head=" + R4_HEAD)
    print("source_archive_sha256=8ac00f467d7fb2235e6a4df2850278e1893103279077178ffe610db995a91ff5")
    print("primary_metrics=8")
    print("sign_flip_replicates=100000")
    print("bootstrap_replicates=20000")
    print("holm_familywise_alpha=0.05")
    print("backend_query_allowed=false")
    print("docker_or_service_mutation_allowed=false")
    print("measurement_allowed=false")
    print("effect_analysis_authorized=true")
    print("R3_D4_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
