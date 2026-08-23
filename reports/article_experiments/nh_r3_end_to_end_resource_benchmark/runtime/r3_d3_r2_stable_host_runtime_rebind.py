#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

R3 = Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
PARENT = "af03ce42ec9e35293b438aa1924b7f8eb76c5449"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

RECOVERY_AUTH_BLOB = "14fce8bcc4601947ce82d9dbe686c51286689206"
INTERRUPTION_FREEZE_BLOB = "67e256df516bd8079971c1dc645df408804cebe5"
D3_CONTRACT_BLOB = "c4e45aa2a04bdb084a2c9a9047f074c31a5cf665"
COMPOSE_BLOB = "f807f35039d89ac5dae153fb3fa36d99f4a33e53"

PRESERVED = Path(
    "/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_INTERRUPTED_20260823T211928Z_"
    "PRESERVED_20260823T215439Z.tar.gz"
)
PRESERVED_SHA = "1c5bb0d802e1400a38c8bd57d629553f331821771d8bfbf83424caecd5d7fb37"
OLD_ATTEMPT = Path("/workspaces/MCAD_R3_D3_CONFIRMATORY_PRIMARY_ATTEMPT_20260823T211928Z")

PROTECTED = {
    "protected_sqlserver": {
        "id": "ca2434ae491845dec2d2a5dc4ef4b1056f6eb20282024c64a191c3ac5d1f264c",
        "started_at": "2026-08-23T10:02:34.457234573Z",
        "image": "sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89",
    },
    "protected_mcad_api": {
        "id": "5767c68c60ecfe5450a9af6ccde82221c3076f9046f82a5a8353865bd73292c1",
        "started_at": "2026-08-23T10:09:46.36179959Z",
        "image": "sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840",
    },
    "protected_mcad_proxy": {
        "id": "ebd1dca12df3cff15dc411c9a5902dc16547c6a78708fd42ff6623cddd9fd612",
        "started_at": "2026-08-23T10:08:25.609823871Z",
        "image": "sha256:2494827f7dda2769fcd80e1659bbb2520b0aafe52fdefdc79e6fff07db0fe6b4",
    },
}

CLONE = {
    "clone_sqlserver": {
        "id": "7eb03679a67d80f1f9d708a0ecc42ee1d89e4f60ec26ff0fea2925f1b041395c",
        "image": "sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89",
        "name": "/mcad-r3-rerun1-r3-sqlserver-1",
    },
    "clone_mcad_api": {
        "id": "ec03867deaf7fb31a909eef371895189603be78b8526b14528155cea645f7c8b",
        "image": "sha256:7648c28b5e974a9a1e972c7d42fbfb3d20a181f821a97197f460ed77662b7840",
        "name": "/mcad-r3-rerun1-r3-mcad-api-1",
    },
    "clone_mcad_proxy": {
        "id": "c12ba832d2f59b55037e6086d3021e66b8093c6fb3ef5cb26a37c0796ff20786",
        "image": "sha256:2494827f7dda2769fcd80e1659bbb2520b0aafe52fdefdc79e6fff07db0fe6b4",
        "name": "/mcad-r3-rerun1-r3-mcad-proxy-1",
    },
}

NETWORK = "mcad-r3-rerun1_r3_internal"
VOLUME = "mcad-r3-rerun1_r3_sql_data"
RUNTIME_ROOT = Path("/workspaces/MCAD_R3_ISOLATED_RUNTIME_d2f5e40171bd2daccec18e7d450644e0b510b5d8")


def sh(*args: str, check: bool = True) -> str:
    cp = subprocess.run(list(args), text=True, capture_output=True)
    if check and cp.returncode != 0:
        raise RuntimeError(
            f"command failed ({cp.returncode}): {' '.join(args)}\nstdout={cp.stdout}\nstderr={cp.stderr}"
        )
    return cp.stdout.strip()


def git(repo: Path, *args: str) -> str:
    return sh("git", "-C", str(repo), *args)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def docker_inspect(cid: str) -> dict[str, Any]:
    data = json.loads(sh("docker", "inspect", cid))
    if len(data) != 1:
        raise RuntimeError(f"docker inspect returned {len(data)} entries for {cid}")
    return data[0]


def validate_authorities(repo: Path) -> None:
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git(repo, "rev-parse", "HEAD") != PARENT:
        raise RuntimeError("unexpected head")
    checks = (
        (repo / R3 / "config/r3_d3_mechanical_rerun_authorization.json", RECOVERY_AUTH_BLOB, "recovery auth"),
        (repo / R3 / "results/d3_interrupted_attempt_20260823T211928Z/interruption_freeze.json", INTERRUPTION_FREEZE_BLOB, "interruption freeze"),
        (repo / R3 / "config/r3_d3_primary_confirmatory_execution_contract.json", D3_CONTRACT_BLOB, "D3 execution contract"),
        (repo / R3 / "runtime/r3_isolated_runtime.compose.yml", COMPOSE_BLOB, "isolated compose"),
    )
    for path, expected, label in checks:
        actual = git_blob(path)
        if actual != expected:
            raise RuntimeError(f"{label} blob changed: {actual}")
    auth = json.loads(
        (repo / R3 / "config/r3_d3_mechanical_rerun_authorization.json").read_text(encoding="utf-8")
    )
    policy = auth.get("rerun_policy") or {}
    if policy.get("mechanical_full_rerun_scientifically_authorized") is not True:
        raise RuntimeError("mechanical full rerun not scientifically authorized")
    if policy.get("execution_authorized_now") is not False:
        raise RuntimeError("rerun execution unexpectedly authorized before R2")
    if policy.get("rerun_scope") != "FULL_PRIMARY_300_FROM_BLOCK_1":
        raise RuntimeError("rerun scope changed")
    if policy.get("reuse_partial_receipts") is not False:
        raise RuntimeError("partial receipts unexpectedly reusable")
    if policy.get("resume_partial_attempt") is not False:
        raise RuntimeError("partial resume unexpectedly authorized")
    if policy.get("activate_fallback_120") is not False:
        raise RuntimeError("fallback unexpectedly activated")


def inspect_protected_exact_exited() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, expected in PROTECTED.items():
        d = docker_inspect(expected["id"])
        state = d["State"]["Status"]
        started = d["State"]["StartedAt"]
        restarts = int(d.get("RestartCount") or 0)
        image = d["Image"]
        if state != "exited":
            raise RuntimeError(f"{label} must remain exited, got {state}")
        if started != expected["started_at"]:
            raise RuntimeError(f"{label} StartedAt changed")
        if restarts != 0:
            raise RuntimeError(f"{label} RestartCount changed: {restarts}")
        if image != expected["image"]:
            raise RuntimeError(f"{label} image changed")
        out[label] = {
            "id": expected["id"], "state": state, "started_at": started,
            "restart_count": restarts, "image": image,
        }
    return out


def inspect_clone_expected_state(require_exited: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, expected in CLONE.items():
        d = docker_inspect(expected["id"])
        state = d["State"]["Status"]
        if require_exited and state != "exited":
            raise RuntimeError(f"{label} must be exited before rebind, got {state}")
        if d["Name"] != expected["name"]:
            raise RuntimeError(f"{label} container name changed: {d['Name']}")
        if d["Image"] != expected["image"]:
            raise RuntimeError(f"{label} image changed")
        out[label] = {
            "id": expected["id"],
            "state": state,
            "started_at": d["State"]["StartedAt"],
            "restart_count": int(d.get("RestartCount") or 0),
            "image": d["Image"],
            "name": d["Name"],
        }

    sql = docker_inspect(CLONE["clone_sqlserver"]["id"])
    sql_mounts = {m["Destination"]: m for m in sql.get("Mounts") or []}
    sql_data = sql_mounts.get("/var/opt/mssql")
    if not sql_data or sql_data.get("Name") != VOLUME:
        raise RuntimeError("isolated SQL volume changed")

    api = docker_inspect(CLONE["clone_mcad_api"]["id"])
    api_mounts = {m["Destination"]: m for m in api.get("Mounts") or []}
    backend = api_mounts.get("/app/backend")
    data = api_mounts.get("/app/data")
    if not backend or backend.get("Source") != str(Path("/workspaces/MCAD_improve3/backend")):
        raise RuntimeError("isolated API backend source changed")
    if backend.get("RW") is not False:
        raise RuntimeError("isolated API backend mount is not read-only")
    if not data or Path(data.get("Source", "")).parent != RUNTIME_ROOT:
        raise RuntimeError("isolated API data root changed")

    proxy = docker_inspect(CLONE["clone_mcad_proxy"]["id"])
    proxy_mounts = {m["Destination"]: m for m in proxy.get("Mounts") or []}
    pdata = proxy_mounts.get("/app/data")
    pdemo = proxy_mounts.get("/app/demo-evidence")
    if not pdata or pdata.get("Source") != str(RUNTIME_ROOT / "proxy-data"):
        raise RuntimeError("isolated proxy data root changed")
    if not pdemo or pdemo.get("Source") != str(RUNTIME_ROOT / "demo-evidence"):
        raise RuntimeError("isolated proxy demo-evidence root changed")

    sh("docker", "network", "inspect", NETWORK)
    sh("docker", "volume", "inspect", VOLUME)

    expected_ports = {
        CLONE["clone_sqlserver"]["id"]: ("1433/tcp", "127.0.0.1", "24333"),
        CLONE["clone_mcad_api"]["id"]: ("8000/tcp", "127.0.0.1", "18000"),
        CLONE["clone_mcad_proxy"]["id"]: ("9000/tcp", "127.0.0.1", "19000"),
    }
    for cid, (container_port, host_ip, host_port) in expected_ports.items():
        d = docker_inspect(cid)
        bindings = (d.get("HostConfig") or {}).get("PortBindings") or {}
        rows = bindings.get(container_port) or []
        if len(rows) != 1 or rows[0].get("HostIp") != host_ip or rows[0].get("HostPort") != host_port:
            raise RuntimeError(f"port binding changed for {cid}: {rows}")
    return out


def codespace_host_gate() -> dict[str, Any]:
    name = os.environ.get("CODESPACE_NAME")
    if not name:
        raise RuntimeError("CODESPACE_NAME is not set")
    raw = sh("gh", "codespace", "view", "-c", name, "--json", "name,state,idleTimeoutMinutes")
    data = json.loads(raw)
    timeout = int(data.get("idleTimeoutMinutes") or 0)
    state = str(data.get("state") or "")
    if timeout < 240:
        raise RuntimeError(f"codespace idleTimeoutMinutes must be >=240 for this rerun, got {timeout}")
    if state != "Available":
        raise RuntimeError(f"codespace state must be Available, got {state}")
    return {"name": data.get("name"), "state": state, "idle_timeout_minutes": timeout}


def wait_tcp(host: str, port: int, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                return
        except OSError as exc:
            last = str(exc)
            time.sleep(2.0)
    raise RuntimeError(f"TCP {host}:{port} not ready after {timeout_s}s; last={last}")


def http_get_json(url: str, timeout_s: float = 10.0) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=timeout_s) as r:
        status = int(r.status)
        body = r.read()
    return status, json.loads(body.decode("utf-8"))


def ensure_no_new_d3_attempts() -> None:
    attempts = sorted(Path("/workspaces").glob("MCAD_R3_D3_CONFIRMATORY_PRIMARY_ATTEMPT_*"))
    allowed = {OLD_ATTEMPT.resolve()}
    unexpected = [p for p in attempts if p.resolve() not in allowed]
    if unexpected:
        raise RuntimeError("unexpected new D3 attempt(s): " + ", ".join(str(p) for p in unexpected))
    if not OLD_ATTEMPT.is_dir():
        raise RuntimeError("frozen interrupted attempt directory missing")
    if not PRESERVED.is_file():
        raise RuntimeError("preserved interruption archive missing")
    if sha256(PRESERVED) != PRESERVED_SHA:
        raise RuntimeError("preserved interruption archive SHA changed")


def rebind(repo: Path, receipt: Path) -> dict[str, Any]:
    validate_authorities(repo)
    ensure_no_new_d3_attempts()
    host = codespace_host_gate()
    protected_before = inspect_protected_exact_exited()
    clone_before = inspect_clone_expected_state(require_exited=True)

    # Exact isolated clone only. No compose up/recreate/build/pull.
    for label in ("clone_sqlserver", "clone_mcad_proxy", "clone_mcad_api"):
        sh("docker", "start", CLONE[label]["id"])

    wait_tcp("127.0.0.1", 24333, 120.0)
    wait_tcp("127.0.0.1", 19000, 90.0)
    wait_tcp("127.0.0.1", 18000, 90.0)

    # Give uvicorn endpoints a short grace period after TCP opens.
    deadline = time.time() + 90.0
    api_health = api_openapi = proxy_openapi = None
    last_error = None
    while time.time() < deadline:
        try:
            api_health = http_get_json("http://127.0.0.1:18000/health")
            api_openapi = http_get_json("http://127.0.0.1:18000/openapi.json")
            proxy_openapi = http_get_json("http://127.0.0.1:19000/openapi.json")
            break
        except Exception as exc:
            last_error = repr(exc)
            time.sleep(2.0)
    if api_health is None or api_openapi is None or proxy_openapi is None:
        raise RuntimeError(f"HTTP endpoints not ready; last_error={last_error}")

    if api_health[0] != 200 or api_openapi[0] != 200 or proxy_openapi[0] != 200:
        raise RuntimeError("one or more isolated HTTP endpoints are not 200")

    api_paths = set((api_openapi[1].get("paths") or {}).keys())
    proxy_paths = set((proxy_openapi[1].get("paths") or {}).keys())
    if "/sessions/create" not in api_paths:
        raise RuntimeError("isolated API required /sessions/create route missing")
    for route in ("/bi/r3/measurement/gate-only", "/bi/r3/measurement/full-execute"):
        if route not in proxy_paths:
            raise RuntimeError(f"isolated proxy required route missing: {route}")

    protected_after = inspect_protected_exact_exited()
    clone_after = inspect_clone_expected_state(require_exited=False)
    for label, row in clone_after.items():
        if row["state"] != "running":
            raise RuntimeError(f"{label} did not reach running state: {row['state']}")
        if row["restart_count"] != 0:
            raise RuntimeError(f"{label} RestartCount unexpectedly changed: {row['restart_count']}")

    payload = {
        "contract_version": "mcad.nh_r3.d3.r2.runtime_rebind_receipt.v1",
        "station": "MCAD-NH-R3",
        "stage": "R3-D_CONFIRMATORY_SQL_DIRECT",
        "parent_recovery_head": PARENT,
        "host": host,
        "interrupted_attempt_archive_sha256": PRESERVED_SHA,
        "partial_attempt_reused": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "protected_historical_runtime_before": protected_before,
        "protected_historical_runtime_after": protected_after,
        "isolated_clone_before": clone_before,
        "isolated_clone_after": clone_after,
        "isolated_project": "mcad-r3-rerun1",
        "isolated_runtime_root": str(RUNTIME_ROOT),
        "sql_tcp_ready": True,
        "isolated_api_health_http": api_health[0],
        "isolated_api_openapi_http": api_openapi[0],
        "isolated_proxy_openapi_http": proxy_openapi[0],
        "api_required_routes": True,
        "proxy_required_measurement_routes": True,
        "clone_rebind_mutation_performed": True,
        "protected_historical_runtime_mutated": False,
        "backend_query_executed": False,
        "measurement_executed": False,
        "effect_analysis_performed": False,
        "effect_size_tuning_performed": False,
        "full_rerun_execution_authorized_now": False,
        "next": "R3-D3-R3_REPLACEMENT_PRIMARY_300_EXECUTION_AUTHORIZATION_AND_PREMEASUREMENT_GATE",
        "status": "PASS_READY_FOR_R3_D3_R3",
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def static_check(repo: Path) -> dict[str, Any]:
    validate_authorities(repo)
    return {
        "parent_recovery_head": PARENT,
        "mechanical_full_rerun_scientifically_authorized": True,
        "full_rerun_execution_authorized_now": False,
        "rerun_scope": "FULL_PRIMARY_300_FROM_BLOCK_1",
        "reuse_partial_receipts": False,
        "resume_from_arm_298": False,
        "fallback_120_activated": False,
        "measurement_executed": False,
        "backend_query_executed": False,
        "docker_command_executed": False,
        "effect_analysis_performed": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("static-check")
    p = sub.add_parser("rebind-preflight")
    p.add_argument("--receipt", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.cmd == "static-check":
        print(json.dumps(static_check(repo), indent=2, sort_keys=True))
        print("R3_D3_R2_STATIC_CHECK=PASS_NO_MEASUREMENT")
        return
    if args.cmd == "rebind-preflight":
        data = rebind(repo, Path(args.receipt).resolve())
        print("codespace_name=" + str(data["host"]["name"]))
        print("codespace_state=" + str(data["host"]["state"]))
        print("codespace_idle_timeout_minutes=" + str(data["host"]["idle_timeout_minutes"]))
        print("protected_historical_runtime_mutated=false")
        print("isolated_clone_rebound_running=true")
        print("sql_tcp_ready=true")
        print("isolated_api_health_http=200")
        print("isolated_api_openapi_http=200")
        print("isolated_proxy_openapi_http=200")
        print("backend_query_executed=false")
        print("measurement_executed=false")
        print("effect_analysis_performed=false")
        print("full_rerun_execution_authorized_now=false")
        print("R3_D3_R2_STABLE_HOST_RUNTIME_REBIND_PREFLIGHT=PASS_READY_FOR_R3_D3_R3")
        return


if __name__ == "__main__":
    main()
