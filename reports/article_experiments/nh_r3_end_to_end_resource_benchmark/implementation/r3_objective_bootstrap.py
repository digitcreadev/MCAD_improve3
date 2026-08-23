#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests

OBJECTIVE_ID = "O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN"
DW_ID = "adventureworks_sql_direct"


def http_json(method: str, url: str, *, payload: Any | None = None, timeout_s: float = 30.0) -> dict[str, Any]:
    response = requests.request(method, url, json=payload, timeout=timeout_s)
    text = response.text
    if not response.ok:
        raise RuntimeError(f"{method} {url} -> HTTP {response.status_code}: {text[:1500]}")
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"{method} {url} returned invalid JSON: {text[:1500]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{method} {url} returned non-object JSON")
    return data


def load_objective(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("objective payload must be one JSON object")
    if str(data.get("id") or "") != OBJECTIVE_ID:
        raise RuntimeError(f"unexpected objective id in payload: {data.get('id')!r}")
    return data


def verify_detail(base: str) -> dict[str, Any]:
    detail = http_json("GET", f"{base}/objectives/{OBJECTIVE_ID}")
    if str(detail.get("id") or "") != OBJECTIVE_ID:
        raise RuntimeError(f"objective detail mismatch: {detail}")
    return detail


def command_import(args: argparse.Namespace) -> None:
    base = args.mcad_base.rstrip("/")
    payload = load_objective(Path(args.objective_file))
    result = http_json("POST", f"{base}/objectives/import", payload=payload)
    if result.get("ok") is not True:
        raise RuntimeError(f"objective import failed: {result}")
    ids = [str(x) for x in (result.get("objective_ids") or [])]
    if OBJECTIVE_ID not in ids:
        raise RuntimeError(f"objective import response missing frozen id: {result}")
    verify_detail(base)
    print("objective_import=PASS")
    print(f"objective_id={OBJECTIVE_ID}")
    print("backend_query_executed=false")
    print("measurement_executed=false")


def command_verify_persistence(args: argparse.Namespace) -> None:
    base = args.mcad_base.rstrip("/")
    verify_detail(base)
    session = http_json(
        "POST",
        f"{base}/sessions/create",
        payload={"objective_id": OBJECTIVE_ID, "dw_id": DW_ID},
    )
    item = session.get("session")
    if not isinstance(item, dict) or not item.get("session_id"):
        raise RuntimeError(f"invalid create-session response: {session}")
    print("objective_persistence_after_restart=PASS")
    print(f"objective_id={OBJECTIVE_ID}")
    print(f"verification_session_id={item['session_id']}")
    print("backend_query_executed=false")
    print("measurement_executed=false")


def main() -> None:
    parser = argparse.ArgumentParser(description="NH-R3 B2g objective bootstrap")
    parser.add_argument("--mcad-base", default="http://127.0.0.1:8000")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser("import")
    p_import.add_argument("--objective-file", required=True)
    p_import.set_defaults(func=command_import)

    p_verify = sub.add_parser("verify-persistence")
    p_verify.set_defaults(func=command_verify_persistence)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
