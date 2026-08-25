#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
CONTRACT = R3 / "config/r3_e3c_emondrian_pinned_build_inputs.json"
FREEZE = R3 / "results/e3b_emondrian_pinning_discovery_freeze.json"
WEBINF = R3 / "results/e3c_emondrian_web_inf_sha256s.txt"
HIST = ROOT / "bi-stack/emondrian-adventureworks/Dockerfile"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

def main() -> None:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    f = json.loads(FREEZE.read_text(encoding="utf-8"))

    assert c["contract_version"] == "mcad.nh_r3.e3c.emondrian_pinned_build_inputs.v1"
    assert c["parent_head"] == "918ea6d4eb3f0a517b637dcef6c033f12a724d01"
    assert c["historical_runtime_claim_boundary"]["historical_exact_runtime_reconstruction_claim_authorized"] is False
    assert c["new_r3e_reproducible_runtime"]["build_allowed_in_e3c"] is False
    assert c["new_r3e_reproducible_runtime"]["materialization_allowed_in_e3c"] is False

    assert git("rev-parse", f"{c['parent_head']}^{{commit}}") == c["parent_head"]
    subprocess.check_call(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", c["parent_head"], "HEAD"])

    assert git("rev-parse", "HEAD:bi-stack/emondrian-adventureworks/Dockerfile") == "4d0a3c95c51e14f9d916cae24eefe748a11ff486"
    assert sha256(HIST) == "859a11f7db99748802149dfa207c4f1d9d73690a19a80cb8285d469c37037414"

    assert c["emondrian"]["release_tag"] == "v9.3.0.6"
    assert c["emondrian"]["tag_commit"] == "d2006c162fcc6c4e7ec90a0c03485056696134ad"
    assert c["emondrian"]["asset_sha256"] == "100895f17acd4e4d3e3af58c2fbd442d95ca71fb969169d4c1a66acb974c52db"
    assert c["emondrian"]["asset_bytes"] == 52732089
    assert c["emondrian"]["github_release_immutable"] is False
    assert c["tomcat"]["linux_amd64_manifest_digest"] == "sha256:81be7f8d435228148a6419d5e967e6c31f094ec3a492055b42c66d2bb775627c"
    assert c["tomcat"]["target_platform"] == "linux/amd64"
    assert c["mssql_jdbc"]["asset_sha256"] == "3b1a70145dbaff98daa70022791e15becfb2b9534cc9e8cfaa1bdba6a3edeb8e"
    assert c["mssql_jdbc"]["asset_bytes"] == 1470328
    assert c["web_inf"]["file_count"] == 6
    assert sha256(WEBINF) == "cb2b90d9627202df6063cb61037b161de231d9f91630b835dd514f141f8abb50"

    for line in WEBINF.read_text(encoding="utf-8").splitlines():
        expected, rel = line.split(None, 1)
        rel = rel.strip()
        assert sha256(ROOT / rel) == expected, rel

    assert f["receipt_sha256"] == c["e3b_discovery_authority"]["receipt_sha256"]
    assert f["transaction_manifest_sha256"] == c["e3b_discovery_authority"]["external_transaction_manifest_sha256"]
    assert f["facts"]["emondrian_war_sha256"] == c["emondrian"]["asset_sha256"]
    assert f["facts"]["jdbc_sha256"] == c["mssql_jdbc"]["asset_sha256"]
    assert f["facts"]["tomcat_linux_amd64_digest"] == c["tomcat"]["linux_amd64_manifest_digest"]
    assert f["facts"]["web_inf_manifest_sha256"] == c["web_inf"]["manifest_sha256"]

    boundary = c["execution_boundary"]
    assert all(boundary[k] is False for k in [
        "repository_historical_artifact_mutation_allowed",
        "docker_build_allowed",
        "docker_pull_or_load_allowed",
        "container_create_start_restart_allowed",
        "database_restore_allowed",
        "backend_query_allowed",
        "measurement_allowed",
        "historical_xmla_q1_q6_rerun_allowed",
        "sql_direct_rerun_allowed",
    ])

    print("parent_rupture_checkpoint_ancestor=PASS")
    print("historical_emondrian_source_identity=PASS")
    print("emondrian_explicit_tag_and_sha256_pin=PASS")
    print("tomcat_linux_amd64_digest_pin=PASS")
    print("mssql_jdbc_sha256_pin=PASS")
    print("web_inf_exact_manifest=PASS")
    print("historical_exact_runtime_reconstruction_claim_authorized=false")
    print("docker_build_authorized=false")
    print("materialization_authorized=false")
    print("measurement_authorized=false")
    print("R3_E3C_EMONDRIAN_PINNED_BUILD_INPUTS_STATIC_VERIFY=PASS")

if __name__ == "__main__":
    main()
