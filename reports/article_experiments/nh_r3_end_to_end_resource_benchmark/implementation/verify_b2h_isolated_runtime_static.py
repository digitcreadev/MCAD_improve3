#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"
PARENT = "3ad3fd012af59bc686d7a3ad8178e7df122da96d"

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
CONTRACT = R3 / "config/r3_b2h_isolated_runtime_contract.json"
COMPOSE = R3 / "runtime/r3_isolated_runtime.compose.yml"
B2G = R3 / "config/r3_b2g_instrumentation_recovery_protocol.json"

EXPECTED_B2G_BLOB = "be6a8eab9ad2a74374ee7c3b333e4a22f0686743"
HISTORICAL_SQL_VOLUME = "bi-stack_adventureworks_sqlserver_data"
HISTORICAL_NETWORK = "mcad_net"
HISTORICAL_PORTS = {8000, 9000, 14333}
EXPECTED_IMAGES = {
    "r3-sqlserver": "mcr.microsoft.com/mssql/server:2022-latest",
    "r3-mcad-api": "bi-stack-mcad-api",
    "r3-mcad-proxy": "bi-stack-mcad-proxy",
}
EXPECTED_PORTS = {
    "r3-sqlserver": "127.0.0.1:24333:1433",
    "r3-mcad-api": "127.0.0.1:18000:8000",
    "r3-mcad-proxy": "127.0.0.1:19000:9000",
}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if git(repo, "branch", "--show-current") != BRANCH:
        raise SystemExit("wrong branch")
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", PARENT, "HEAD"], check=True)

    contract = json.loads((repo / CONTRACT).read_text(encoding="utf-8"))
    assert contract["contract_version"] == "mcad.nh_r3.b2h.isolated_runtime_design.v1"
    assert contract["parent_head"] == PARENT
    assert contract["historical_runtime_preservation"]["archive_sha256"] == (
        "a959a38f7135627ad82a2b9818fb124bbae517d5ec75c621c67126d9baae6d82"
    )
    assert contract["isolated_clone"]["compose_project_name"] == "mcad-r3-rerun1"
    assert contract["isolated_clone"]["no_build"] is True
    assert contract["isolated_clone"]["pull_policy"] == "never"
    assert contract["isolated_clone"]["historical_sql_volume_reuse_forbidden"] is True
    assert contract["isolated_clone"]["historical_container_reuse_forbidden"] is True
    assert contract["isolated_clone"]["historical_network_reuse_forbidden"] is True
    assert contract["isolated_clone"]["historical_rw_bind_mounts_forbidden"] is True
    assert contract["isolated_clone"]["loopback_only_host_ports"] is True
    assert contract["authorization"]["static_design_only"] is True
    assert contract["authorization"]["container_start_authorized_by_this_checkpoint"] is False
    assert contract["authorization"]["measured_execution_authorized_by_this_checkpoint"] is False
    assert contract["scientific_runtime"]["confirmatory_claim_authorized"] is False

    assert git(repo, "hash-object", str(B2G)) == EXPECTED_B2G_BLOB

    doc = yaml.safe_load((repo / COMPOSE).read_text(encoding="utf-8"))
    assert doc["name"] == "mcad-r3-rerun1"
    services = doc["services"]
    assert set(services) == {"r3-sqlserver", "r3-mcad-api", "r3-mcad-proxy"}

    for svc, image in EXPECTED_IMAGES.items():
        item = services[svc]
        assert item["image"] == image
        assert item.get("pull_policy") == "never"
        assert "build" not in item
        assert item["ports"] == [EXPECTED_PORTS[svc]]
        assert item["ports"][0].startswith("127.0.0.1:")

        host_port = int(item["ports"][0].split(":")[1])
        assert host_port not in HISTORICAL_PORTS

        assert item["networks"] == ["r3_internal"]

    assert "mcad_net" not in (doc.get("networks") or {})
    assert "r3_internal" in doc["networks"]
    assert HISTORICAL_SQL_VOLUME not in (doc.get("volumes") or {})
    assert set(doc["volumes"]) == {"r3_sql_data"}

    sql_vols = services["r3-sqlserver"]["volumes"]
    assert sql_vols == ["r3_sql_data:/var/opt/mssql"]
    assert not any("adventureworks/backups" in str(v) for v in sql_vols)

    api_vols = services["r3-mcad-api"]["volumes"]
    assert len(api_vols) == 2
    backend = next(v for v in api_vols if v["target"] == "/app/backend")
    api_data = next(v for v in api_vols if v["target"] == "/app/data")
    assert backend["read_only"] is True
    assert backend["source"].endswith("/backend")
    assert "${R3_REPO_ROOT:" in backend["source"]
    assert "${R3_RUNTIME_ROOT:" in api_data["source"]
    assert not api_data.get("read_only", False)

    proxy_vols = services["r3-mcad-proxy"]["volumes"]
    assert len(proxy_vols) == 2
    for v in proxy_vols:
        assert "${R3_RUNTIME_ROOT:" in v["source"]
        assert not v.get("read_only", False)

    raw = (repo / COMPOSE).read_text(encoding="utf-8")
    forbidden = [
        "bi-stack_adventureworks_sqlserver_data",
        "mcad_net",
        "0.0.0.0:8000",
        "0.0.0.0:9000",
        "0.0.0.0:14333",
        "/workspaces/MCAD_improve3/bi-stack/adventureworks/backups",
        "container_name:",
        "build:",
    ]
    for token in forbidden:
        if token in raw:
            raise SystemExit(f"forbidden historical-collision token in isolated compose: {token}")

    proxy_env = services["r3-mcad-proxy"]["environment"]
    assert proxy_env["MCAD_API_BASE"] == "http://r3-mcad-api:8000"
    assert proxy_env["MCAD_EVAL_URL"] == "http://r3-mcad-api:8000/eval"
    assert proxy_env["MCAD_CKG_URL"] == "http://r3-mcad-api:8000/ckg/update"
    assert proxy_env["ADVENTUREWORKS_SQLSERVER_HOST"] == "r3-sqlserver"
    assert proxy_env["ADVENTUREWORKS_SQLSERVER_DATABASE"] == "AdventureWorksDW2022"

    api_env = services["r3-mcad-api"]["environment"]
    assert api_env["MCAD_NVAC_PROBE_URL"] == "http://r3-mcad-proxy:9000/bi/nvac-probe"
    assert api_env["MCAD_OBJECTIVE_ID_DEFAULT"] == "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"

    print("parent_ancestry=PASS")
    print("b2g_recovery_authority=PASS")
    print("isolated_runtime_contract=PASS")
    print("isolated_compose_static_semantics=PASS")
    print("no_build_and_pull_policy_never=PASS")
    print("new_project_network_ports_volume=PASS")
    print("historical_sql_volume_reuse=FORBIDDEN")
    print("historical_container_reuse=FORBIDDEN")
    print("historical_rw_bind_mounts=NONE")
    print("historical_backend_mount=READ_ONLY_ONLY")
    print("container_start_performed=false")
    print("docker_command_executed_by_verifier=false")
    print("measured_execution_performed=false")
    print("confirmatory_claim_authorized=false")
    print("R3_B2H_ISOLATED_RUNTIME_STATIC_VERIFY=PASS")


if __name__ == "__main__":
    main()
