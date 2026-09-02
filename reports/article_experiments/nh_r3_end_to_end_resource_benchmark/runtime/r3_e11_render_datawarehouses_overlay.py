#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

TARGET_ID = "adventureworks_xmla"
TARGET_URL = "http://r3e-emondrian-adventureworks:8080/emondrian/xmla"


def render(source: Path, output: Path) -> None:
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("datawarehouses"), list):
        raise RuntimeError("unexpected datawarehouses.yaml structure")

    hits = 0
    for item in data["datawarehouses"]:
        if isinstance(item, dict) and item.get("id") == TARGET_ID:
            if item.get("adapter") != "xmla_mondrian":
                raise RuntimeError("AdventureWorks XMLA adapter changed")
            if item.get("fallback") is not False or item.get("fallback_dw_id") is not None:
                raise RuntimeError("AdventureWorks XMLA fallback contract changed")
            item["xmla_url"] = TARGET_URL
            hits += 1

    if hits != 1:
        raise RuntimeError(f"expected one {TARGET_ID} entry, got {hits}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    render(Path(args.source), Path(args.output))
    print("R3_E11_DATAWAREHOUSE_OVERLAY_RENDER=PASS")


if __name__ == "__main__":
    main()
