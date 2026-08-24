#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
E0_HEAD = "b88cc576ec547ebbb71edee181dddda866cf3a33"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

EXPECTED_OBJECTS = {
    R3 / "docs/STAGE_PLAN.md": "a80c68a2e29fd9e8e8807b085b7dad88dc29dcc9",
    R3 / "config/r3_protocol.json": "2f3a219793d25eaf0e8970c4cff824fdabab90d8",
    R3 / "config/r3_d0_confirmatory_primary_arm_order_schedule.csv": "6b53ab6d271425b9e5113bdd405775f05c6d65df",
    R3 / "config/r3_e0_xmla_emondrian_static_activation_contract.json": "bb207362e15c2873a2424d2ee89fef34455cee32",
    R3 / "results/e0_xmla_emondrian_static_inventory.json": "c296346274934cb41839a73cc0ce41b75ae83f7f",
    R3 / "results/e0_static_verifier_recovery.json": "ee7211f94e01d1c18589303b6295433783ac9496",
    Path("bi-stack/docker-compose.yml"): "210d4fbb7d09ef2f4a8ad664f34278fb51185a4e",
    Path("bi-stack/mcad-proxy/datawarehouses.yaml"): "e0584b8d349b3faea53b857ebc2d3f98a0a95ca2",
    Path("bi-stack/emondrian-adventureworks/Dockerfile"): "4d0a3c95c51e14f9d916cae24eefe748a11ff486",
    Path("bi-stack/emondrian-adventureworks/WEB-INF/datasources.xml"): "60cedf95c00cdb22c15adf415c3b2e43087ff42b",
    Path("bi-stack/emondrian-adventureworks/WEB-INF/schema/AdventureWorksDW.xml"): "f19236cdb243446f7bbd65f1d567d2d31ac6202b",
}

EXPECTED_TREES = {
    Path("bi-stack/emondrian-adventureworks"): "dd1d7df52e0ccaed007b05e9d051a8e5e9350bf7",
    Path("bi-stack/demo-evidence/final-evidence/adventureworks_xmla_full_20260620_184313"): "d9f46eb647ac4ecc3d577914a044da656d527244",
}


def git_object(repo: Path, rel: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{rel.as_posix()}"],
        text=True,
    ).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    branch = subprocess.check_output(
        ["git", "-C", str(repo), "branch", "--show-current"], text=True
    ).strip()
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if branch != BRANCH:
        raise RuntimeError(f"wrong branch: {branch}")
    anc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", E0_HEAD, head],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if anc.returncode != 0:
        raise RuntimeError(f"E0 head is not ancestor of current HEAD: {head}")

    for rel, expected in EXPECTED_OBJECTS.items():
        actual = git_object(repo, rel)
        if actual != expected:
            raise RuntimeError(f"frozen object changed: {rel} -> {actual}")
    for rel, expected in EXPECTED_TREES.items():
        actual = git_object(repo, rel)
        if actual != expected:
            raise RuntimeError(f"frozen tree changed: {rel} -> {actual}")

    e0 = json.loads(
        (repo / R3 / "config/r3_e0_xmla_emondrian_static_activation_contract.json")
        .read_text(encoding="utf-8")
    )
    if e0.get("next") != "R3-E1_XMLA_ISOLATED_RUNTIME_PLAN_AND_STATIC_PREFLIGHT_NO_MEASUREMENT":
        raise RuntimeError("E0 handoff changed")
    if e0.get("scientific_role") != "SECONDARY_END_TO_END_CONFIRMATION":
        raise RuntimeError("E0 scientific role changed")
    e0_boundary = e0.get("execution_boundary") or {}
    if any(e0_boundary.get(k) is not False for k in (
        "docker_or_service_mutation_allowed",
        "backend_query_allowed",
        "measurement_allowed",
        "effect_analysis_allowed",
    )):
        raise RuntimeError("E0 no-execution boundary changed")

    protocol = json.loads((repo / R3 / "config/r3_protocol.json").read_text(encoding="utf-8"))
    secondary = protocol.get("secondary_backend") or {}
    if secondary.get("warehouse_id") != "adventureworks_xmla":
        raise RuntimeError("secondary warehouse changed")
    if secondary.get("adapter") != "xmla_mondrian":
        raise RuntimeError("secondary adapter changed")
    if secondary.get("role") != "secondary_end_to_end_confirmation":
        raise RuntimeError("secondary backend role changed")

    dockerfile = (repo / "bi-stack/emondrian-adventureworks/Dockerfile").read_text(encoding="utf-8")
    if "releases/latest/download/emondrian.war" not in dockerfile:
        raise RuntimeError("expected unpinned eMondrian latest-download signature changed")

    datasources = (repo / "bi-stack/emondrian-adventureworks/WEB-INF/datasources.xml").read_text(encoding="utf-8")
    if "jdbc:sqlserver://adventureworks-sqlserver:1433" not in datasources:
        raise RuntimeError("frozen historical datasource JDBC target changed")
    if "AdventureWorksDW2022" not in datasources:
        raise RuntimeError("frozen historical datasource database changed")

    plan = json.loads(
        (repo / R3 / "config/r3_e1_xmla_isolated_runtime_plan.json").read_text(encoding="utf-8")
    )
    if plan.get("contract_version") != "mcad.nh_r3.e1.xmla_isolated_runtime_plan.v1":
        raise RuntimeError("unexpected E1 plan contract")
    if plan.get("parent_e0_head") != E0_HEAD:
        raise RuntimeError("E1 parent mismatch")
    if plan.get("scientific_role") != "SECONDARY_END_TO_END_CONFIRMATION":
        raise RuntimeError("E1 scientific role changed")

    fr = plan.get("frozen_reuse") or {}
    if fr.get("confirmatory_test_sessions") != 300 or fr.get("arm_runs") != 900:
        raise RuntimeError("E1 frozen cohort cardinality changed")
    if fr.get("three_arms") != [
        "UNGATED_EXECUTE_ADMISSIBLE",
        "PERMISSIVE_GATED",
        "SAFE_PRUNING",
    ]:
        raise RuntimeError("E1 arm family changed")
    if fr.get("sql_direct_measurement_rerun") is not False:
        raise RuntimeError("SQL Direct rerun became allowed")
    if fr.get("historical_xmla_q1_q6_rerun") is not False:
        raise RuntimeError("historical XMLA rerun became allowed")

    iso = plan.get("isolated_runtime") or {}
    if iso.get("project_name") != "mcad-r3e-xmla1":
        raise RuntimeError("isolated project name changed")
    if iso.get("network_name") != "mcad-r3e-xmla1_r3e_internal":
        raise RuntimeError("isolated network changed")
    if iso.get("sql_data_volume_name") != "mcad-r3e-xmla1_r3e_sql_data":
        raise RuntimeError("isolated SQL volume changed")
    if iso.get("reuse_existing_runtime_containers") is not False:
        raise RuntimeError("existing runtime container reuse became allowed")
    if iso.get("protected_existing_runtime_mutation_allowed") is not False:
        raise RuntimeError("protected runtime mutation became allowed")
    if iso.get("host_ports") != {
        "emondrian": 18182,
        "mcad_api": 18100,
        "mcad_proxy": 19100,
        "sqlserver": 25333,
    }:
        raise RuntimeError("isolated host ports changed")

    image_policy = plan.get("image_policy") or {}
    if image_policy.get("emondrian_new_build_from_unpinned_latest_forbidden") is not True:
        raise RuntimeError("unpinned eMondrian build became allowed")
    if image_policy.get("emondrian_exact_local_image_discovery_required_before_materialization") is not True:
        raise RuntimeError("eMondrian exact-image discovery no longer required")

    overlay = plan.get("runtime_overlay_policy") or {}
    if overlay.get("repository_source_files_modified") is not False:
        raise RuntimeError("repository source modification became allowed")
    if overlay.get("datasources_xml_semantic_schema_change_allowed") is not False:
        raise RuntimeError("datasource semantic change became allowed")
    if overlay.get("credential_value_may_be_printed") is not False:
        raise RuntimeError("credential printing became allowed")
    if overlay.get("credential_value_may_be_committed") is not False:
        raise RuntimeError("credential commit became allowed")

    attrib = plan.get("resource_attribution") or {}
    if len(attrib.get("shared_r3_metrics_preserved") or []) != 8:
        raise RuntimeError("shared R3 metric family changed")
    if set(attrib.get("xmla_specific_additional_metrics") or []) != {
        "emondrian_cpu_usage_usec_delta",
        "emondrian_io_rbytes_delta",
        "emondrian_io_wbytes_delta",
    }:
        raise RuntimeError("XMLA-specific resource metrics changed")
    if attrib.get("new_global_claim_authorized") is not False:
        raise RuntimeError("new global claim became authorized")

    boundary = plan.get("execution_boundary") or {}
    for key in (
        "docker_or_service_mutation_allowed",
        "docker_build_allowed",
        "docker_create_start_restart_allowed",
        "backend_query_allowed",
        "database_restore_allowed",
        "measurement_allowed",
        "effect_analysis_allowed",
        "protected_historical_runtime_mutation_allowed",
        "r3_d_runtime_mutation_allowed",
    ):
        if boundary.get(key) is not False:
            raise RuntimeError(f"E1 execution boundary violated: {key}")

    preflight = json.loads(
        (repo / R3 / "results/e1_xmla_isolated_runtime_static_preflight.json").read_text(encoding="utf-8")
    )
    if preflight.get("inventory_version") != "mcad.nh_r3.e1.xmla_isolated_runtime_static_preflight.v1":
        raise RuntimeError("unexpected E1 preflight inventory")
    if preflight.get("runtime_objects_created") is not False:
        raise RuntimeError("runtime objects unexpectedly created in E1")
    if preflight.get("measurement_performed") is not False:
        raise RuntimeError("measurement unexpectedly performed in E1")
    if preflight.get("next") != "R3-E2_XMLA_ISOLATED_RUNTIME_DISCOVERY_AND_MATERIALIZATION_PREFLIGHT_READ_ONLY_NO_MEASUREMENT":
        raise RuntimeError("unexpected E1 handoff")

    print("e0_head_ancestor=true")
    print("r3_d_sql_direct_stage_frozen=true")
    print("secondary_backend_id=adventureworks_xmla")
    print("reuse_frozen_confirmatory_test_cohort_300=true")
    print("reuse_frozen_arm_order_schedule=true")
    print("planned_isolated_project=mcad-r3e-xmla1")
    print("planned_isolated_sql_volume=mcad-r3e-xmla1_r3e_sql_data")
    print("planned_host_ports=25333,18182,18100,19100")
    print("emondrian_unpinned_latest_build_detected=true")
    print("emondrian_unpinned_new_build_authorized=false")
    print("exact_local_emondrian_image_discovery_required=true")
    print("xmla_specific_resource_attribution_metrics=3")
    print("historical_xmla_q1_q6_rerun_authorized=false")
    print("sql_direct_measurement_rerun_authorized=false")
    print("runtime_objects_created=false")
    print("docker_or_service_mutation_performed=false")
    print("backend_query_executed=false")
    print("database_restore_performed=false")
    print("measurement_performed=false")
    print("effect_analysis_performed=false")
    print("R3_E1_XMLA_ISOLATED_RUNTIME_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
