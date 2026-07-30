#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.harness.sensitivity_execution.validate_execution_spec import (
    SCHEMA_VERSION as EXECUTION_SCHEMA_VERSION,
    validate_execution_spec,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    SCHEMA_VERSION as WORKLOAD_SCHEMA_VERSION,
    validate_workload_spec,
)


ROOT = Path(__file__).resolve().parents[4]

CAMPAIGN_DIR = (
    ROOT
    / "reports/article_experiments/sensitivity"
    / "e2_2_controlled_families/campaigns"
    / "virtual_node_count"
)
INSTANCES_CSV = CAMPAIGN_DIR / "instances.csv"

E3_ROOT = (
    ROOT
    / "reports/article_experiments/sensitivity"
    / "e3_controlled_execution"
)
AUDIT_ROOT = E3_ROOT / "audits" / "virtual_node_count"
SOURCE_AUDIT_PATH = AUDIT_ROOT / "nv_intersection_audit.json"
OBSOLETE_AUDIT_PATH = AUDIT_ROOT / "strict_common_query_specs.json"
BY_REPLICATION_DIR = AUDIT_ROOT / "by_replication"
WORKLOAD_DIR = E3_ROOT / "workloads"
EXECUTION_SPEC_DIR = E3_ROOT / "execution_specs"
RUNS_DIR = E3_ROOT / "runs"

EXPECTED_AUDIT_ID = (
    "e3-virtual-node-count-nv-intersection-audit-v4"
)
EXPECTED_LEVELS = [6, 12, 24]
EXPECTED_REPLICATIONS = {0: 101, 1: 202}
EXPECTED_COMMON_QUERY_COUNT = 2
EXPECTED_CONSTRAINT_COUNT = 4


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(
            f"[ERROR] Required JSON file not found: {path}"
        )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise SystemExit(
            f"[ERROR] JSON root must be an object: {path}"
        )

    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def load_instances() -> list[dict[str, Any]]:
    if not INSTANCES_CSV.is_file():
        raise SystemExit(
            f"[ERROR] Missing instances.csv: {INSTANCES_CSV}"
        )

    with INSTANCES_CSV.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise SystemExit("[ERROR] instances.csv is empty.")

    required = {
        "objective_id",
        "relative_instance_dir",
        "factor_level",
        "replication_index",
        "seed",
        "realised_constraint_count",
        "realised_virtual_node_count",
    }

    missing = required - set(rows[0])

    if missing:
        raise SystemExit(
            "[ERROR] Missing instances.csv columns: "
            f"{sorted(missing)}"
        )

    instances: list[dict[str, Any]] = []

    for row in rows:
        relative_dir = str(row["relative_instance_dir"])
        instance_dir = CAMPAIGN_DIR / relative_dir

        for required_file in (
            instance_dir / "objectives.yaml",
            instance_dir / "manifest.json",
        ):
            if not required_file.is_file():
                raise SystemExit(
                    f"[ERROR] Missing instance artifact: {required_file}"
                )

        instances.append(
            {
                "objective_id": str(row["objective_id"]),
                "relative_instance_dir": relative_dir,
                "factor_level": int(row["factor_level"]),
                "replication_index": int(
                    row["replication_index"]
                ),
                "seed": int(row["seed"]),
                "realised_constraint_count": int(
                    row["realised_constraint_count"]
                ),
                "realised_virtual_node_count": int(
                    row["realised_virtual_node_count"]
                ),
            }
        )

    return instances


def validate_source_audit(
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    if audit.get("audit_id") != EXPECTED_AUDIT_ID:
        raise SystemExit(
            "[ERROR] Unexpected source audit_id: "
            f"{audit.get('audit_id')!r}"
        )

    if audit.get("instance_count") != 6:
        raise SystemExit(
            "[ERROR] Expected source audit instance_count=6."
        )

    if audit.get("all_replications_usable") is not True:
        raise SystemExit(
            "[ERROR] Source audit does not mark all "
            "replications usable."
        )

    if audit.get("global_common_query_count") != 0:
        raise SystemExit(
            "[ERROR] Expected global_common_query_count=0; "
            "workloads must remain replication-specific."
        )

    replications = audit.get("by_replication")

    if not isinstance(replications, list):
        raise SystemExit(
            "[ERROR] Source audit by_replication must be a list."
        )

    if len(replications) != len(EXPECTED_REPLICATIONS):
        raise SystemExit(
            "[ERROR] Expected exactly two replications."
        )

    seen: set[int] = set()

    for item in replications:
        if not isinstance(item, dict):
            raise SystemExit(
                "[ERROR] Invalid replication entry."
            )

        rep = int(item.get("replication_index", -1))

        if rep not in EXPECTED_REPLICATIONS:
            raise SystemExit(
                f"[ERROR] Unexpected replication_index={rep}."
            )

        if rep in seen:
            raise SystemExit(
                f"[ERROR] Duplicate replication_index={rep}."
            )

        seen.add(rep)

        if int(item.get("seed", -1)) != EXPECTED_REPLICATIONS[rep]:
            raise SystemExit(
                f"[ERROR] Seed mismatch for replication {rep}."
            )

        levels = [
            int(value)
            for value in item.get("factor_levels", [])
        ]

        if levels != EXPECTED_LEVELS:
            raise SystemExit(
                f"[ERROR] Invalid levels for replication {rep}: "
                f"{levels}"
            )

        if item.get("usable") is not True:
            raise SystemExit(
                f"[ERROR] Replication {rep} is not usable."
            )

        if int(item.get("common_query_count", -1)) != (
            EXPECTED_COMMON_QUERY_COUNT
        ):
            raise SystemExit(
                f"[ERROR] Replication {rep} must expose exactly "
                f"{EXPECTED_COMMON_QUERY_COUNT} common queries."
            )

        query_specs = item.get("common_query_specs")

        if (
            not isinstance(query_specs, list)
            or len(query_specs)
            != EXPECTED_COMMON_QUERY_COUNT
        ):
            raise SystemExit(
                f"[ERROR] Invalid common_query_specs for rep {rep}."
            )

        if len(
            {canonical_json(query) for query in query_specs}
        ) != len(query_specs):
            raise SystemExit(
                f"[ERROR] Duplicate common queries for rep {rep}."
            )

    if seen != set(EXPECTED_REPLICATIONS):
        raise SystemExit(
            "[ERROR] Missing expected replication."
        )

    return sorted(
        replications,
        key=lambda item: int(item["replication_index"]),
    )


def normalise_query_spec(
    query_spec: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "cube",
        "measures",
        "group_by",
        "slicers",
        "aggregators",
        "units",
        "window_start",
        "window_end",
    }

    missing = required - set(query_spec)

    if missing:
        raise SystemExit(
            "[ERROR] Common query is missing fields: "
            f"{sorted(missing)}"
        )

    result = {
        "cube": str(query_spec["cube"]),
        "measures": list(query_spec["measures"]),
        "group_by": list(query_spec["group_by"]),
        "slicers": dict(query_spec["slicers"]),
        "aggregators": list(query_spec["aggregators"]),
        "units": list(query_spec["units"]),
        "window_start": str(query_spec["window_start"]),
        "window_end": str(query_spec["window_end"]),
    }

    year = result["slicers"].get("Time.Year")

    if year is not None:
        result["time_members"] = [str(year)]

    validate_workload_spec(
        {
            "contract_version": WORKLOAD_SCHEMA_VERSION,
            "workload_id": "e3-validation-probe",
            "objective_id": "O_E3_VALIDATION_PROBE",
            "session_id": "S_E3_VALIDATION_PROBE",
            "steps": [
                {
                    "step_index": 1,
                    "step_id": "step-0001-validation-probe",
                    "query_spec": result,
                }
            ],
        }
    )

    return result


def slug(value: Any) -> str:
    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        str(value).strip().lower(),
    )
    return text.strip("-") or "value"


def make_step_id(
    query_spec: dict[str, Any],
    index: int,
) -> str:
    return (
        f"step-{index:04d}-"
        f"{slug(query_spec['measures'][0])}-"
        f"{slug(query_spec['aggregators'][0])}-"
        f"{slug(query_spec['slicers'].get('Geography.Region', 'region'))}-"
        f"{slug(query_spec['slicers'].get('Time.Year', 'year'))}"
    )


def select_instances(
    instances: list[dict[str, Any]],
    replication_index: int,
    expected_seed: int,
) -> list[dict[str, Any]]:
    selected = sorted(
        [
            item
            for item in instances
            if item["replication_index"] == replication_index
        ],
        key=lambda item: item["factor_level"],
    )

    if len(selected) != 3:
        raise SystemExit(
            f"[ERROR] Replication {replication_index} must "
            "contain exactly three instances."
        )

    levels = [item["factor_level"] for item in selected]

    if levels != EXPECTED_LEVELS:
        raise SystemExit(
            f"[ERROR] Instance levels mismatch for rep "
            f"{replication_index}: {levels}"
        )

    seeds = {item["seed"] for item in selected}

    if seeds != {expected_seed}:
        raise SystemExit(
            f"[ERROR] Seed contamination for rep "
            f"{replication_index}: {sorted(seeds)}"
        )

    constraint_counts = {
        item["realised_constraint_count"]
        for item in selected
    }

    if constraint_counts != {EXPECTED_CONSTRAINT_COUNT}:
        raise SystemExit(
            "[ERROR] realised_constraint_count is not "
            f"constant at {EXPECTED_CONSTRAINT_COUNT}: "
            f"{sorted(constraint_counts)}"
        )

    realised_nv = [
        item["realised_virtual_node_count"]
        for item in selected
    ]

    if realised_nv != EXPECTED_LEVELS:
        raise SystemExit(
            "[ERROR] realised_virtual_node_count mismatch: "
            f"{realised_nv}"
        )

    return selected


def main() -> int:
    source_audit = load_json(SOURCE_AUDIT_PATH)
    replications = validate_source_audit(source_audit)
    instances = load_instances()

    BY_REPLICATION_DIR.mkdir(parents=True, exist_ok=True)
    WORKLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXECUTION_SPEC_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    campaign_report: dict[str, Any] = {
        "contract_version": (
            "mcad-e3-virtual-node-count-"
            "replication-plan-v1"
        ),
        "source_audit_id": EXPECTED_AUDIT_ID,
        "source_audit_path": str(SOURCE_AUDIT_PATH),
        "source_audit_sha256": hashlib.sha256(
            SOURCE_AUDIT_PATH.read_bytes()
        ).hexdigest(),
        "campaign_dir": str(CAMPAIGN_DIR),
        "replications": [],
    }

    for source_replication in replications:
        rep = int(source_replication["replication_index"])
        seed = int(source_replication["seed"])

        selected = select_instances(
            instances,
            rep,
            seed,
        )

        query_specs = sorted(
            [
                normalise_query_spec(dict(query))
                for query in source_replication[
                    "common_query_specs"
                ]
            ],
            key=canonical_json,
        )

        steps = [
            {
                "step_index": index,
                "step_id": make_step_id(query_spec, index),
                "query_spec": query_spec,
            }
            for index, query_spec in enumerate(
                query_specs,
                start=1,
            )
        ]

        token = f"rep_{rep:03d}"
        stem = (
            "virtual_node_count_"
            f"{token}_strict_common"
        )

        workload_path = WORKLOAD_DIR / f"{stem}.json"
        execution_spec_path = (
            EXECUTION_SPEC_DIR / f"{stem}.json"
        )
        output_dir = RUNS_DIR / stem

        workload = {
            "contract_version": WORKLOAD_SCHEMA_VERSION,
            "workload_id": (
                "e3-virtual-node-count-"
                f"{token}-strict-common-v1"
            ),
            "objective_id": (
                "O_E3_VIRTUAL_NODE_COUNT_"
                f"{token.upper()}_RUNTIME_BOUND"
            ),
            "session_id": (
                "S_E3_VIRTUAL_NODE_COUNT_"
                f"{token.upper()}_STRICT_COMMON"
            ),
            "steps": steps,
        }

        execution_spec = {
            "contract_version": EXECUTION_SCHEMA_VERSION,
            "execution_id": (
                "e3-virtual-node-count-"
                f"{token}-strict-common-v1"
            ),
            "campaign_dir": str(CAMPAIGN_DIR),
            "workload_path": str(workload_path),
            "output_dir": str(output_dir),
            "instance_selection": {
                "instance_ids": [
                    item["relative_instance_dir"]
                    for item in selected
                ]
            },
        }

        validate_workload_spec(workload)
        validate_execution_spec(execution_spec)

        write_json(workload_path, workload)
        write_json(execution_spec_path, execution_spec)

        replication_report = {
            "replication_index": rep,
            "seed": seed,
            "factor_levels": EXPECTED_LEVELS,
            "instance_count": len(selected),
            "strict_common_query_spec_count": len(steps),
            "fully_nested": bool(
                source_replication.get("fully_nested", False)
            ),
            "source_audit_id": EXPECTED_AUDIT_ID,
            "source_query_specs_sha256": sha256_digest(
                source_replication["common_query_specs"]
            ),
            "workload_path": str(workload_path),
            "execution_spec_path": str(execution_spec_path),
            "output_dir": str(output_dir),
            "instances": selected,
            "common_query_specs": [
                {
                    "step_index": step["step_index"],
                    "step_id": step["step_id"],
                    "query_spec_sha256": sha256_digest(
                        step["query_spec"]
                    ),
                    "query_spec": step["query_spec"],
                }
                for step in steps
            ],
        }

        report_path = (
            BY_REPLICATION_DIR
            / f"virtual_node_count_{token}.json"
        )

        write_json(report_path, replication_report)

        campaign_report["replications"].append(
            replication_report
        )

        print()
        print(
            f"[OK] replication={rep} "
            f"seed={seed} "
            f"levels={EXPECTED_LEVELS} "
            f"common_steps={len(steps)}"
        )
        print(f"[OK] workload={workload_path}")
        print(
            f"[OK] execution_spec={execution_spec_path}"
        )
        print(f"[OK] output_dir={output_dir}")

        for step in steps:
            query = step["query_spec"]
            print(
                "  "
                f"step={step['step_index']} "
                f"id={step['step_id']} "
                f"measure={query['measures'][0]} "
                f"aggregator={query['aggregators'][0]} "
                f"unit={query['units'][0]} "
                f"slicers={query['slicers']}"
            )

    plan_path = (
        BY_REPLICATION_DIR
        / "replication_execution_plan.json"
    )
    write_json(plan_path, campaign_report)

    write_json(
        AUDIT_ROOT / "superseded_audit_notice.json",
        {
            "status": "superseded",
            "superseded_artifact": str(
                OBSOLETE_AUDIT_PATH
            ),
            "reason": (
                "The superseded audit projected semantic "
                "properties at the wrong structural level and "
                "produced an invalid empty query specification."
            ),
            "authoritative_artifact": str(
                SOURCE_AUDIT_PATH
            ),
            "authoritative_audit_id": EXPECTED_AUDIT_ID,
            "must_not_be_used_for_execution": True,
        },
    )

    print()
    print(
        "[OK] Virtual-node-count preparation completed."
    )
    print(f"[OK] report={plan_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
