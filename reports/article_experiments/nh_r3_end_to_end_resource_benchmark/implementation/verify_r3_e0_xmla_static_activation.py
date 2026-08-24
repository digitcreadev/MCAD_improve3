#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
PARENT = "b1e0e6caf1fda43f970990027ec62cd1f1570d1c"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

EXPECTED_BLOBS = {
    "stage_plan": (R3 / "docs/STAGE_PLAN.md", "a80c68a2e29fd9e8e8807b085b7dad88dc29dcc9"),
    "r3_protocol": (R3 / "config/r3_protocol.json", "2f3a219793d25eaf0e8970c4cff824fdabab90d8"),
    "d4_recovery_receipt": (
        R3 / "results/d4_verifier_only_recovery_20260824T100706Z/verification_receipt.json",
        "4fdefe769e27ee2ae71f21515269dbe1daa03682",
    ),
    "dw_registry": (Path("bi-stack/mcad-proxy/datawarehouses.yaml"), "e0584b8d349b3faea53b857ebc2d3f98a0a95ca2"),
    "compose": (Path("bi-stack/docker-compose.yml"), "210d4fbb7d09ef2f4a8ad664f34278fb51185a4e"),
    "emondrian_dockerfile": (Path("bi-stack/emondrian-adventureworks/Dockerfile"), "4d0a3c95c51e14f9d916cae24eefe748a11ff486"),
    "emondrian_datasources": (Path("bi-stack/emondrian-adventureworks/WEB-INF/datasources.xml"), "60cedf95c00cdb22c15adf415c3b2e43087ff42b"),
    "emondrian_web_xml": (Path("bi-stack/emondrian-adventureworks/WEB-INF/web.xml"), "5e968e9a47b6caebe168cd7fa60ec5fccdedfa77"),
    "adventureworks_schema": (Path("bi-stack/emondrian-adventureworks/WEB-INF/schema/AdventureWorksDW.xml"), "f19236cdb243446f7bbd65f1d567d2d31ac6202b"),
}

HISTORICAL_XMLA_DIR = Path(
    "bi-stack/demo-evidence/final-evidence/adventureworks_xmla_full_20260620_184313"
)


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sh(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    branch = sh("git", "-C", str(repo), "branch", "--show-current")
    head = sh("git", "-C", str(repo), "rev-parse", "HEAD")
    if branch != BRANCH:
        raise RuntimeError(f"wrong branch: {branch}")
    ancestor = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT, head],
        text=True,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise RuntimeError(f"R3-D4 frozen head is not ancestor of current HEAD: {head}")

    for label, (rel, expected) in EXPECTED_BLOBS.items():
        path = repo / rel
        if not path.is_file():
            raise RuntimeError(f"missing frozen authority: {rel}")
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"frozen authority changed: {label} -> {actual}")

    stage_plan = (repo / R3 / "docs/STAGE_PLAN.md").read_text(encoding="utf-8")
    if "R3-E: XMLA/eMondrian end-to-end replication." not in stage_plan:
        raise RuntimeError("R3-E stage-plan role changed")

    protocol = json.loads((repo / R3 / "config/r3_protocol.json").read_text(encoding="utf-8"))
    secondary = protocol.get("secondary_backend") or {}
    if secondary.get("warehouse_id") != "adventureworks_xmla":
        raise RuntimeError("secondary warehouse changed")
    if secondary.get("adapter") != "xmla_mondrian":
        raise RuntimeError("secondary adapter changed")
    if secondary.get("role") != "secondary_end_to_end_confirmation":
        raise RuntimeError("secondary backend role changed")
    if protocol.get("sampling", {}).get("confirmatory_test") != "all frozen test sessions; expected 300 sessions":
        raise RuntimeError("frozen confirmatory cohort rule changed")

    receipt = json.loads(
        (repo / R3 / "results/d4_verifier_only_recovery_20260824T100706Z/verification_receipt.json")
        .read_text(encoding="utf-8")
    )
    if receipt.get("status") != "PASS_EXISTING_D4_OUTPUTS_VERIFIED_AND_FROZEN":
        raise RuntimeError("R3-D stage is not frozen")
    if receipt.get("confirmed_metric_count") != 6:
        raise RuntimeError("D4 confirmed endpoint count changed")
    if receipt.get("global_system_benefit_claim_authorized") is not False:
        raise RuntimeError("D4 global-claim boundary changed")

    registry = (repo / "bi-stack/mcad-proxy/datawarehouses.yaml").read_text(encoding="utf-8")
    for token in (
        "id: adventureworks_xmla",
        "adapter: xmla_mondrian",
        "physical_query_language: xmla_mdx",
        "xmla_url: http://emondrian-adventureworks:8080/emondrian/xmla",
        "datasource_info: AdventureWorksDW",
    ):
        if token not in registry:
            raise RuntimeError(f"AdventureWorks XMLA registry token missing: {token}")

    compose = (repo / "bi-stack/docker-compose.yml").read_text(encoding="utf-8")
    for token in (
        "emondrian-adventureworks:",
        "build: ./emondrian-adventureworks",
        "- 8082:8080",
    ):
        if token not in compose:
            raise RuntimeError(f"AdventureWorks eMondrian compose token missing: {token}")

    if not (repo / HISTORICAL_XMLA_DIR).is_dir():
        raise RuntimeError("historical AdventureWorks XMLA proof directory missing")
    request_files = sorted((repo / HISTORICAL_XMLA_DIR).glob("*.request.json"))
    response_files = sorted((repo / HISTORICAL_XMLA_DIR).glob("*.response.json"))
    if len(request_files) < 6 or len(response_files) < 6:
        raise RuntimeError("historical AdventureWorks XMLA proof is incomplete")

    contract = json.loads(
        (repo / R3 / "config/r3_e0_xmla_emondrian_static_activation_contract.json")
        .read_text(encoding="utf-8")
    )
    if contract.get("contract_version") != "mcad.nh_r3.e0.xmla_emondrian_static_activation.v1":
        raise RuntimeError("unexpected E0 contract")
    if contract.get("parent_r3_d4_frozen_head") != PARENT:
        raise RuntimeError("E0 contract parent mismatch")
    boundary = contract.get("execution_boundary") or {}
    for key in (
        "docker_or_service_mutation_allowed",
        "backend_query_allowed",
        "measurement_allowed",
        "effect_analysis_allowed",
        "protected_historical_runtime_mutation_allowed",
    ):
        if boundary.get(key) is not False:
            raise RuntimeError(f"E0 execution boundary violated: {key}")

    repl = contract.get("replication_boundary") or {}
    expected_bool = {
        "reuse_frozen_r3_semantic_binding": True,
        "reuse_frozen_confirmatory_test_cohort_300": True,
        "reuse_frozen_three_arms": True,
        "reuse_partial_or_interrupted_sql_direct_receipts": False,
        "rerun_sql_direct_measurement": False,
        "rerun_historical_xmla_q1_q6_path_proof": False,
        "effect_size_tuning": False,
        "scientific_redesign": False,
    }
    for key, value in expected_bool.items():
        if repl.get(key) is not value:
            raise RuntimeError(f"E0 replication boundary mismatch: {key}")

    if contract.get("next") != "R3-E1_XMLA_ISOLATED_RUNTIME_PLAN_AND_STATIC_PREFLIGHT_NO_MEASUREMENT":
        raise RuntimeError("unexpected E0 next stage")

    print("r3_d_sql_direct_stage_frozen=true")
    print("d4_confirmed_metric_count=6")
    print("d4_global_system_benefit_claim_authorized=false")
    print("secondary_backend_id=adventureworks_xmla")
    print("secondary_backend_adapter=xmla_mondrian")
    print("historical_adventureworks_xmla_path_proof_present=true")
    print("historical_xmla_q1_q6_rerun_authorized=false")
    print("r3_e_new_role=RESOURCE_REPLICATION_UNDER_FROZEN_R3_PROTOCOL")
    print("reuse_frozen_confirmatory_test_cohort_300=true")
    print("rerun_sql_direct_measurement=false")
    print("docker_or_service_mutation_performed=false")
    print("backend_query_executed=false")
    print("measurement_performed=false")
    print("effect_analysis_performed=false")
    print("R3_E0_XMLA_EMONDRIAN_STATIC_ACTIVATION_VERIFY=PASS")


if __name__ == "__main__":
    main()
