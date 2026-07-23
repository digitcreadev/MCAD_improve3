#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--artifact-dir", required=True)
    args = p.parse_args()

    run = Path(args.run_dir)
    art = Path(args.artifact_dir)
    summary = load(run / "article_summary.json")
    data = load(art / "article_artifact_data.json")
    manifest = load(art / "artifact_manifest.json")

    print("=== Article benchmark run ===")
    print("run_dir:", run)
    print("total_sessions_or_validations:", summary.get("total_sessions"))
    print("total_query_decisions:", summary.get("total_queries"))
    print("parameters:", summary.get("parameters"))

    print("\n=== Locked / current evidence ===")
    a = data["campaign_a"]
    b = data["campaign_b"]["manifest"]
    c = data["campaign_c"]["manifest"]
    print("Campaign A: sessions=", a.get("executed_session_count"), "queries=", a.get("executed_query_count"), "allow=", a.get("allow_count"), "block=", a.get("block_count"), "ckg_events=", a.get("ckg_events"))
    print("Campaign B: ok=", b.get("ok"), "scenarios=", b.get("scenario_count"), "queries=", b.get("query_count"), "allow=", b.get("allow_count"), "block=", b.get("block_count"), "ckg_events=", data["campaign_b"].get("ckg_events"))
    print("Campaign C: ok=", c.get("ok"), "totals=", c.get("totals"), "checks=", c.get("portability_checks"))

    print("\n=== Generated artifacts ===")
    print("figures:", manifest.get("figure_count"))
    print("tables:", manifest.get("table_count"))
    print("manifest:", art / "artifact_manifest.json")
    print("checksums:", art / "SHA256SUMS.txt")


if __name__ == "__main__":
    main()
