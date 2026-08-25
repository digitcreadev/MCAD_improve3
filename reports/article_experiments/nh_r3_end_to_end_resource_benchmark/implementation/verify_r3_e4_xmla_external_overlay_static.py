#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
E3C = R3 / "config/r3_e3c_emondrian_pinned_build_inputs.json"
E1 = R3 / "config/r3_e1_xmla_isolated_runtime_plan.json"
CONTRACT = R3 / "config/r3_e4_xmla_external_overlay_static_contract.json"
DOCKERFILE = R3 / "runtime/r3_e4_emondrian_pinned.Dockerfile"
COMPOSE = R3 / "runtime/r3_e4_xmla_isolated_compose.template.yml"
DATASOURCES = R3 / "runtime/r3_e4_datasources.xml.template"
RECEIPT = R3 / "results/e4_xmla_external_overlay_static_receipt.json"

PARENT = "43c0e5855909b045fbc1e0395d697a9794f02c10"
TOMCAT = "sha256:81be7f8d435228148a6419d5e967e6c31f094ec3a492055b42c66d2bb775627c"
WAR_SHA = "100895f17acd4e4d3e3af58c2fbd442d95ca71fb969169d4c1a66acb974c52db"
JDBC_SHA = "3b1a70145dbaff98daa70022791e15becfb2b9534cc9e8cfaa1bdba6a3edeb8e"
WEBINF_SHA = "cb2b90d9627202df6063cb61037b161de231d9f91630b835dd514f141f8abb50"

def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

def main() -> None:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    e3c = json.loads(E3C.read_text(encoding="utf-8"))
    e1 = json.loads(E1.read_text(encoding="utf-8"))
    r = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert c["contract_version"] == "mcad.nh_r3.e4.xmla_external_overlay_static.v1"
    assert c["parent_e3c_head"] == PARENT
    assert git("rev-parse", f"{PARENT}^{{commit}}") == PARENT
    subprocess.check_call(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", PARENT, "HEAD"])

    assert e3c["emondrian"]["asset_sha256"] == WAR_SHA
    assert e3c["tomcat"]["linux_amd64_manifest_digest"] == TOMCAT
    assert e3c["mssql_jdbc"]["asset_sha256"] == JDBC_SHA
    assert e3c["web_inf"]["manifest_sha256"] == WEBINF_SHA
    assert e3c["new_r3e_reproducible_runtime"]["must_not_claim_byte_identity_with_historical_emondrian_image"] is True

    iso = c["isolated_runtime"]
    assert iso["project_name"] == e1["isolated_runtime"]["project_name"] == "mcad-r3e-xmla1"
    assert iso["network_name"] == e1["isolated_runtime"]["network_name"]
    assert iso["sql_data_volume_name"] == e1["isolated_runtime"]["sql_data_volume_name"]
    assert iso["services"]["sqlserver"] == e1["isolated_runtime"]["containers"]["sqlserver"]
    assert iso["services"]["emondrian"] == e1["isolated_runtime"]["containers"]["emondrian"]
    assert iso["services"]["mcad_api"] == e1["isolated_runtime"]["containers"]["mcad_api"]
    assert iso["services"]["mcad_proxy"] == e1["isolated_runtime"]["containers"]["mcad_proxy"]
    assert iso["host_ports"] == e1["isolated_runtime"]["host_ports"]

    df = DOCKERFILE.read_text(encoding="utf-8")
    assert f"FROM tomcat@{TOMCAT}" in df
    assert "COPY emondrian.war /tmp/emondrian.war" in df
    assert "COPY WEB-INF/" in df
    assert "COPY mssql-jdbc-12.6.1.jre11.jar" in df
    assert "releases/latest" not in df
    assert not re.search(r"(?m)^\s*(ADD|RUN\s+.*(?:curl|wget))\b.*https?://", df)

    ds = DATASOURCES.read_text(encoding="utf-8")
    assert "jdbc:sqlserver://r3e-adventureworks-sqlserver:1433" in ds
    assert "JdbcPassword=__R3_AW_SA_PASSWORD__" in ds
    assert "AdventureWorksDW2022" in ds
    assert "<DataSourceName>AdventureWorksDW</DataSourceName>" in ds
    assert "<Catalog name=\"AdventureWorksDW\">" in ds
    assert "__R3_AW_SA_PASSWORD__" in ds

    cp = COMPOSE.read_text(encoding="utf-8")
    for token in [
        "name: mcad-r3e-xmla1",
        "r3e-adventureworks-sqlserver:",
        "r3e-emondrian-adventureworks:",
        "r3e-mcad-api:",
        "r3e-mcad-proxy:",
        "25333:1433",
        "18182:8080",
        "18100:8000",
        "19100:9000",
        "mcad-r3e-xmla1_r3e_internal",
        "mcad-r3e-xmla1_r3e_sql_data",
        "R3E_SQLSERVER_IMAGE_REF",
        "R3E_EMONDRIAN_IMAGE_REF",
        "R3E_MCAD_API_IMAGE_REF",
        "R3E_MCAD_PROXY_IMAGE_REF",
        "R3_AW_SA_PASSWORD",
    ]:
        assert token in cp, token

    assert "MCAD_AwDWDemo" not in cp
    assert "MCAD_AwDWDemo" not in ds

    boundary = c["execution_boundary"]
    for key, value in boundary.items():
        if key.endswith("_allowed"):
            assert value is False, key

    assert r["parent_e3c_head"] == PARENT
    assert r["plan_class"] == "STATIC_NO_DOCKER_NO_BACKEND"
    assert r["bundle_dependency_for_this_station"] is False
    assert r["materialization_authorized"] is False
    assert r["runtime_secret_value_embedded"] is False

    assert git("rev-parse", "HEAD:bi-stack/emondrian-adventureworks") == "dd1d7df52e0ccaed007b05e9d051a8e5e9350bf7"

    print("e3c_pinned_input_authority=PASS")
    print("e1_runtime_topology_equivalence=PASS")
    print("pinned_emondrian_dockerfile_template=PASS")
    print("datasources_mechanical_overlay_template=PASS")
    print("isolated_compose_static_topology=PASS")
    print("credential_literal_embedded=false")
    print("bundle_dependency_for_this_station=false")
    print("docker_build_authorized=false")
    print("materialization_authorized=false")
    print("backend_query_authorized=false")
    print("measurement_authorized=false")
    print("historical_emondrian_tree_unchanged=PASS")
    print("R3_E4_XMLA_EXTERNAL_OVERLAY_STATIC_VERIFY=PASS")

if __name__ == "__main__":
    main()
