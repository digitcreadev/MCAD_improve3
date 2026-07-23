from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:9000")
    p.add_argument("--scenario-id", required=True)
    p.add_argument("--objective-id", default="")
    p.add_argument("--dw-id", default="")
    p.add_argument("--new-session", action="store_true")
    p.add_argument("--out", default="bi-stack/reports/direct_scenario_check.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    payload = {
        "create_new_session": args.new_session,
    }
    if args.objective_id:
        payload["objective_id"] = args.objective_id
    if args.dw_id:
        payload["dw_id"] = args.dw_id

    r = requests.post(
        f"{args.base}/bi/scenarios/{args.scenario_id}/run",
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = data.get("summary", [])
    for row in summary:
        print(
            f"{row.get('step')}. {row.get('query_id')}: "
            f"{row.get('decision')} "
            f"expected={row.get('expected_decision')} "
            f"ok={row.get('ok_vs_expected')}"
        )

    mismatches = [x for x in summary if x.get("ok_vs_expected") is False]
    if mismatches:
        print(f"FAILED: {len(mismatches)} mismatch(es). See {out}")
        return 1

    print(f"OK: scenario {args.scenario_id} executed. See {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
