#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from backend.harness.sensitivity_execution.validate_execution_spec import (
    SCHEMA_VERSION as EXECUTION_SCHEMA_VERSION,
    validate_execution_spec,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    SCHEMA_VERSION as WORKLOAD_SCHEMA_VERSION,
    validate_workload_spec,
)


ROOT = Path(__file__).resolve().parents[4]
CANONICAL_ROOT = Path("/workspaces/MCAD_improve3")

CAMPAIGN_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/formal_campaigns/"
    "virtual_node_count_stage10_c4"
)

PREREGISTRATION_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/planning/"
    "virtual_node_count_stage10_preregistration.json"
)

HISTORICAL_AUDIT_REL = Path(
    "reports/article_experiments/sensitivity/e3_controlled_execution/audits/virtual_node_count_stage10/common_workloads/source_inputs/historical_nv_intersection_audit.json"
)

E3_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution"
)

AUDIT_REL = (
    E3_REL
    / "audits"
    / "virtual_node_count_stage10"
    / "common_workloads"
)

BY_REPLICATION_REL = AUDIT_REL / "by_replication"
WORKLOAD_REL = E3_REL / "workloads"
EXECUTION_SPEC_REL = E3_REL / "execution_specs"
RUNS_REL = E3_REL / "runs"

GLOBAL_AUDIT_REL = (
    AUDIT_REL
    / "stage10_common_workload_audit.json"
)

GLOBAL_SUMMARY_REL = (
    AUDIT_REL
    / "stage10_common_workload_audit.md"
)

PLAN_REL = (
    AUDIT_REL
    / "stage10_replication_execution_plan.json"
)

EXPECTED_LEVELS = [6, 12, 24]
EXPECTED_REPLICATION_COUNT = 10
EXPECTED_COMMON_QUERY_COUNT = 2
EXPECTED_CONSTRAINT_COUNT = 4


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


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
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def validate_contract(
    contract: dict[str, Any],
) -> tuple[list[int], list[int]]:
    campaign = contract.get("campaign_contract", {})
    common = contract.get("common_workload_contract", {})
    prefix = contract.get("historical_functional_prefix", {})
    gates = contract.get("authorization_gates", {})

    errors: list[str] = []

    def require(
        condition: bool,
        message: str,
    ) -> None:
        if not condition:
            errors.append(message)

    levels = campaign.get("levels")
    seeds = campaign.get("stage10_seeds")

    require(
        campaign.get("campaign_id")
        == "virtual_node_count_stage10_c4",
        "Unexpected campaign identifier.",
    )
    require(
        campaign.get("factor")
        == "virtual_node_count",
        "Unexpected sensitivity factor.",
    )
    require(
        levels == EXPECTED_LEVELS,
        "Unexpected factor levels.",
    )
    require(
        isinstance(seeds, list)
        and len(seeds) == EXPECTED_REPLICATION_COUNT,
        "Expected exactly ten Stage-10 seeds.",
    )
    require(
        campaign.get("fixed_constraint_count")
        == EXPECTED_CONSTRAINT_COUNT,
        "Constraint count must remain fixed at four.",
    )
    require(
        campaign.get("steps_per_instance")
        == EXPECTED_COMMON_QUERY_COUNT,
        "Expected exactly two steps per instance.",
    )

    require(
        common.get("comparison_scope")
        == "within_replication_across_levels",
        "Invalid workload comparison scope.",
    )
    require(
        common.get("cross_replication_workload_reuse")
        is False,
        "Cross-replication workload reuse must remain false.",
    )
    require(
        common.get(
            "expected_common_query_count_per_replication"
        )
        == EXPECTED_COMMON_QUERY_COUNT,
        "Expected two common queries per replication.",
    )
    require(
        common.get("fully_nested_intersection_required")
        is True,
        "Strict three-level intersection is required.",
    )
    require(
        common.get("semantic_digest_equality_required")
        is True,
        "Semantic digest equality is required.",
    )

    require(
        prefix.get("replications") == [0, 1],
        "Unexpected historical prefix.",
    )
    require(
        prefix.get("reuse_required") is True,
        "Historical prefix reuse must remain required.",
    )
    require(
        prefix.get("rerun_required") is False,
        "Historical prefix must not be rerun.",
    )
    require(
        prefix.get("rerun_authorized") is False,
        "Historical prefix rerun must remain unauthorized.",
    )

    require(
        gates.get("new_functional_execution_authorized")
        is False,
        "Functional execution is authorized too early.",
    )
    require(
        gates.get("formal_timing_execution_authorized")
        is False,
        "Timing execution is authorized too early.",
    )
    require(
        gates.get("stage20_execution_authorized")
        is False,
        "Stage-20 execution is authorized too early.",
    )

    if errors:
        raise SystemExit(
            "[ERROR] Invalid preregistration contract: "
            + "; ".join(errors)
        )

    return (
        [int(value) for value in levels],
        [int(value) for value in seeds],
    )


def load_instances(
    campaign_dir: Path,
) -> list[dict[str, Any]]:
    instances_path = campaign_dir / "instances.csv"

    if not instances_path.is_file():
        raise SystemExit(
            f"[ERROR] Missing instances.csv: {instances_path}"
        )

    with instances_path.open(
        newline="",
        encoding="utf-8",
    ) as stream:
        rows = list(csv.DictReader(stream))

    instances: list[dict[str, Any]] = []

    for row in rows:
        relative_dir = str(
            row["relative_instance_dir"]
        )
        instance_dir = campaign_dir / relative_dir

        for artifact in (
            instance_dir / "manifest.json",
            instance_dir / "objectives.yaml",
        ):
            if not artifact.is_file():
                raise SystemExit(
                    f"[ERROR] Missing instance artifact: {artifact}"
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
                "instance_digest": str(
                    row["instance_digest"]
                ),
            }
        )

    if len(instances) != 30:
        raise SystemExit(
            "[ERROR] Expected exactly 30 Stage-10 instances."
        )

    return instances


def load_objective(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(document, dict):
        raise SystemExit(
            f"[ERROR] Invalid objective document: {path}"
        )

    objectives = document.get("objectives")

    if (
        not isinstance(objectives, list)
        or len(objectives) != 1
        or not isinstance(objectives[0], dict)
    ):
        raise SystemExit(
            f"[ERROR] Expected one objective in {path}"
        )

    return objectives[0]


def semantic_query_spec(
    semantic_node: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "fact",
        "measure",
        "grain",
        "slicers",
        "aggregator",
        "unit",
        "window_start",
        "window_end",
    }

    missing = required - set(semantic_node)

    if missing:
        raise SystemExit(
            "[ERROR] Semantic node missing fields: "
            f"{sorted(missing)}"
        )

    return {
        "cube": str(semantic_node["fact"]),
        "measures": [
            str(semantic_node["measure"])
        ],
        # group_by order is normalized for semantic equality.
        "group_by": sorted(
            str(value)
            for value in semantic_node["grain"]
        ),
        "slicers": {
            str(key): str(value)
            for key, value
            in semantic_node["slicers"].items()
        },
        "aggregators": [
            str(semantic_node["aggregator"])
        ],
        "units": [
            str(semantic_node["unit"])
        ],
        "window_start": str(
            semantic_node["window_start"]
        ),
        "window_end": str(
            semantic_node["window_end"]
        ),
    }


def workload_query_spec(
    semantic_spec: dict[str, Any],
) -> dict[str, Any]:
    result = deepcopy(semantic_spec)

    year = (
        result
        .get("slicers", {})
        .get("Time.Year")
    )

    if year is not None:
        result["time_members"] = [str(year)]

    return result


def objective_query_map(
    objective_path: Path,
) -> dict[str, dict[str, Any]]:
    objective = load_objective(objective_path)
    constraints = objective.get("constraints")

    if not isinstance(constraints, list):
        raise SystemExit(
            f"[ERROR] Missing constraints in {objective_path}"
        )

    result: dict[str, dict[str, Any]] = {}

    for constraint in constraints:
        if not isinstance(constraint, dict):
            raise SystemExit(
                f"[ERROR] Invalid constraint in {objective_path}"
            )

        virtual_nodes = constraint.get("virtual_nodes")

        if not isinstance(virtual_nodes, list):
            raise SystemExit(
                f"[ERROR] Missing virtual_nodes in {objective_path}"
            )

        for node in virtual_nodes:
            if not isinstance(node, dict):
                raise SystemExit(
                    f"[ERROR] Invalid virtual node in {objective_path}"
                )

            query = semantic_query_spec(node)
            result[canonical_json(query)] = query

    if not result:
        raise SystemExit(
            f"[ERROR] No semantic queries in {objective_path}"
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


def selected_instances(
    instances: list[dict[str, Any]],
    replication_index: int,
    expected_seed: int,
) -> list[dict[str, Any]]:
    selected = sorted(
        [
            item
            for item in instances
            if item["replication_index"]
            == replication_index
        ],
        key=lambda item: item["factor_level"],
    )

    levels = [
        item["factor_level"]
        for item in selected
    ]

    if levels != EXPECTED_LEVELS:
        raise SystemExit(
            f"[ERROR] Invalid levels for replication "
            f"{replication_index}: {levels}"
        )

    if {
        item["seed"]
        for item in selected
    } != {expected_seed}:
        raise SystemExit(
            f"[ERROR] Seed contamination for replication "
            f"{replication_index}."
        )

    if {
        item["realised_constraint_count"]
        for item in selected
    } != {EXPECTED_CONSTRAINT_COUNT}:
        raise SystemExit(
            f"[ERROR] Constraint count changed for replication "
            f"{replication_index}."
        )

    if [
        item["realised_virtual_node_count"]
        for item in selected
    ] != EXPECTED_LEVELS:
        raise SystemExit(
            f"[ERROR] Realised virtual-node levels differ for "
            f"replication {replication_index}."
        )

    return selected


def historical_prefix(
    root: Path,
) -> tuple[
    dict[int, dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    audit = load_json(root / HISTORICAL_AUDIT_REL)

    audit_by_replication = {
        int(item["replication_index"]): item
        for item in audit["by_replication"]
    }

    workloads: dict[int, dict[str, Any]] = {}

    for rep in (0, 1):
        path = (
            root
            / AUDIT_REL
            / "source_inputs"
            / (
                "historical_virtual_node_count_"
                f"rep_{rep:03d}_strict_common.json"
            )
        )
        workloads[rep] = load_json(path)

    return audit_by_replication, workloads


def prepare(
    root: Path,
    canonical_root: Path,
) -> dict[str, Any]:
    contract_path = root / PREREGISTRATION_REL
    campaign_dir = root / CAMPAIGN_REL

    contract = load_json(contract_path)
    levels, seeds = validate_contract(contract)
    instances = load_instances(campaign_dir)

    historical_audit, historical_workloads = (
        historical_prefix(root)
    )

    audit_root = root / AUDIT_REL
    by_replication_dir = root / BY_REPLICATION_REL
    workload_dir = root / WORKLOAD_REL
    execution_dir = root / EXECUTION_SPEC_REL

    audit_root.mkdir(parents=True, exist_ok=True)
    by_replication_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    workload_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.mkdir(parents=True, exist_ok=True)

    replication_reports: list[
        dict[str, Any]
    ] = []

    plan: dict[str, Any] = {
        "contract_version": (
            "mcad-e3-virtual-node-count-stage10-"
            "replication-plan-v1"
        ),
        "campaign_id": (
            "virtual_node_count_stage10_c4"
        ),
        "campaign_dir": str(
            canonical_root / CAMPAIGN_REL
        ),
        "replications": [],
        "functional_execution_performed": False,
        "timing_execution_performed": False,
    }

    for replication_index, seed in enumerate(seeds):
        selected = selected_instances(
            instances,
            replication_index,
            seed,
        )

        maps_by_level: dict[
            int,
            dict[str, dict[str, Any]],
        ] = {}

        for instance in selected:
            level = instance["factor_level"]
            objective_path = (
                campaign_dir
                / instance["relative_instance_dir"]
                / "objectives.yaml"
            )

            maps_by_level[level] = (
                objective_query_map(objective_path)
            )

        common_keys = set.intersection(
            *[
                set(maps_by_level[level])
                for level in levels
            ]
        )

        if len(common_keys) != EXPECTED_COMMON_QUERY_COUNT:
            raise SystemExit(
                f"[ERROR] Replication {replication_index} "
                f"exposes {len(common_keys)} common queries; "
                f"expected {EXPECTED_COMMON_QUERY_COUNT}."
            )

        semantic_specs = [
            maps_by_level[levels[0]][key]
            for key in sorted(common_keys)
        ]

        query_specs = sorted(
            [
                workload_query_spec(spec)
                for spec in semantic_specs
            ],
            key=canonical_json,
        )

        steps = [
            {
                "step_index": index,
                "step_id": make_step_id(
                    query_spec,
                    index,
                ),
                "query_spec": query_spec,
            }
            for index, query_spec in enumerate(
                query_specs,
                start=1,
            )
        ]

        token = f"rep_{replication_index:03d}"
        stem = (
            "virtual_node_count_stage10_"
            f"{token}_strict_common"
        )

        workload_rel = (
            WORKLOAD_REL / f"{stem}.json"
        )
        execution_rel = (
            EXECUTION_SPEC_REL / f"{stem}.json"
        )
        output_rel = RUNS_REL / stem

        workload = {
            "contract_version": (
                WORKLOAD_SCHEMA_VERSION
            ),
            "workload_id": (
                "e3-virtual-node-count-stage10-"
                f"{token}-strict-common-v1"
            ),
            "objective_id": (
                "O_E3_VIRTUAL_NODE_COUNT_STAGE10_"
                f"{token.upper()}_RUNTIME_BOUND"
            ),
            "session_id": (
                "S_E3_VIRTUAL_NODE_COUNT_STAGE10_"
                f"{token.upper()}_STRICT_COMMON"
            ),
            "steps": steps,
        }

        execution_spec = {
            "contract_version": (
                EXECUTION_SCHEMA_VERSION
            ),
            "execution_id": (
                "e3-virtual-node-count-stage10-"
                f"{token}-strict-common-v1"
            ),
            "campaign_dir": str(
                canonical_root / CAMPAIGN_REL
            ),
            "workload_path": str(
                canonical_root / workload_rel
            ),
            "output_dir": str(
                canonical_root / output_rel
            ),
            "instance_selection": {
                "instance_ids": [
                    item["relative_instance_dir"]
                    for item in selected
                ]
            },
        }

        validate_workload_spec(workload)
        validate_execution_spec(execution_spec)

        prefix_audit_match: bool | None = None
        prefix_workload_match: bool | None = None

        if replication_index in (0, 1):
            expected_semantic_keys = {
                canonical_json(
                    {
                        **spec,
                        "group_by": sorted(
                            spec["group_by"]
                        ),
                    }
                )
                for spec in historical_audit[
                    replication_index
                ]["common_query_specs"]
            }

            prefix_audit_match = (
                common_keys == expected_semantic_keys
            )

            prefix_workload_match = (
                steps
                == historical_workloads[
                    replication_index
                ]["steps"]
            )

            if (
                not prefix_audit_match
                or not prefix_workload_match
            ):
                raise SystemExit(
                    "[ERROR] Historical prefix workload "
                    f"mismatch for replication "
                    f"{replication_index}."
                )

        write_json(
            root / workload_rel,
            workload,
        )
        write_json(
            root / execution_rel,
            execution_spec,
        )

        pairwise_nesting: list[
            dict[str, Any]
        ] = []

        for lower, upper in zip(
            levels,
            levels[1:],
        ):
            lower_keys = set(
                maps_by_level[lower]
            )
            upper_keys = set(
                maps_by_level[upper]
            )
            missing = sorted(
                lower_keys - upper_keys
            )

            pairwise_nesting.append(
                {
                    "lower_level": lower,
                    "upper_level": upper,
                    "nested": not missing,
                    "missing_from_upper_count": (
                        len(missing)
                    ),
                }
            )

        replication_report = {
            "schema_version": (
                "mcad-virtual-node-count-stage10-"
                "common-workload-replication-audit-v1"
            ),
            "status": "pass",
            "replication_index": replication_index,
            "seed": seed,
            "factor_levels": levels,
            "instance_count": len(selected),
            "common_query_count": len(query_specs),
            "selected_common_queries_present_in_all_levels": (
                True
            ),
            "full_objective_set_nesting_required": False,
            "pairwise_objective_set_nesting": (
                pairwise_nesting
            ),
            "semantic_digest_equality": True,
            "semantic_query_digests": [
                sha256_digest(spec)
                for spec in semantic_specs
            ],
            "workload_query_digests": [
                sha256_digest(spec)
                for spec in query_specs
            ],
            "historical_prefix_audit_match": (
                prefix_audit_match
            ),
            "historical_prefix_workload_match": (
                prefix_workload_match
            ),
            "workload_path": workload_rel.as_posix(),
            "execution_spec_path": (
                execution_rel.as_posix()
            ),
            "planned_output_path": (
                output_rel.as_posix()
            ),
            "instances": selected,
            "common_query_specs": query_specs,
            "functional_execution_performed": False,
            "timing_execution_performed": False,
        }

        replication_report_rel = (
            BY_REPLICATION_REL
            / (
                "virtual_node_count_stage10_"
                f"{token}.json"
            )
        )

        write_json(
            root / replication_report_rel,
            replication_report,
        )

        plan["replications"].append(
            {
                "replication_index": (
                    replication_index
                ),
                "seed": seed,
                "workload_path": str(
                    canonical_root / workload_rel
                ),
                "execution_spec_path": str(
                    canonical_root / execution_rel
                ),
                "output_dir": str(
                    canonical_root / output_rel
                ),
                "execution_authorized": False,
            }
        )

        replication_reports.append(
            replication_report
        )

        print(
            "[OK] "
            f"replication={replication_index} "
            f"seed={seed} "
            "levels=6,12,24 "
            "common_queries=2"
        )

    write_json(root / PLAN_REL, plan)

    prefix_audit_matches = all(
        item["historical_prefix_audit_match"]
        is True
        for item in replication_reports
        if item["replication_index"] in (0, 1)
    )

    prefix_workload_matches = all(
        item["historical_prefix_workload_match"]
        is True
        for item in replication_reports
        if item["replication_index"] in (0, 1)
    )

    report = {
        "schema_version": (
            "mcad-virtual-node-count-stage10-"
            "common-workload-audit-v1"
        ),
        "status": "pass",
        "campaign_id": (
            "virtual_node_count_stage10_c4"
        ),
        "campaign_path": CAMPAIGN_REL.as_posix(),
        "campaign_manifest_sha256": sha256_file(
            campaign_dir / "campaign_manifest.json"
        ),
        "preregistration_path": (
            PREREGISTRATION_REL.as_posix()
        ),
        "preregistration_sha256": sha256_file(
            contract_path
        ),
        "comparison_scope": (
            "within_replication_across_levels"
        ),
        "fully_nested_intersection_interpretation": (
            "The two selected workload queries must be "
            "present at levels 6, 12 and 24. Full nesting "
            "of every objective query set is not required."
        ),
        "group_by_equivalence_policy": (
            "group_by members are sorted for semantic "
            "comparison and workload serialization"
        ),
        "replication_count": len(
            replication_reports
        ),
        "expected_replication_count": (
            EXPECTED_REPLICATION_COUNT
        ),
        "workload_count": len(
            replication_reports
        ),
        "execution_spec_count": len(
            replication_reports
        ),
        "common_query_count_per_replication": (
            EXPECTED_COMMON_QUERY_COUNT
        ),
        "all_replications_usable": True,
        "historical_prefix_audit_matches": (
            prefix_audit_matches
        ),
        "historical_prefix_workload_matches": (
            prefix_workload_matches
        ),
        "historical_prefix_rerun_required": False,
        "functional_execution_performed": False,
        "timing_execution_performed": False,
        "new_functional_execution_authorized": False,
        "formal_timing_execution_authorized": False,
        "replications": replication_reports,
        "next_stage": (
            "merge_stage10_common_workload_preparation"
        ),
    }

    if (
        len(replication_reports)
        != EXPECTED_REPLICATION_COUNT
        or not prefix_audit_matches
        or not prefix_workload_matches
    ):
        raise SystemExit(
            "[ERROR] Stage-10 common-workload audit failed."
        )

    write_json(root / GLOBAL_AUDIT_REL, report)

    lines = [
        "# Virtual-node-count Stage-10 common workloads",
        "",
        "- Status: `PASS`",
        "- Replications: `10`",
        "- Levels per replication: `6`, `12`, `24`",
        "- Common queries per replication: `2`",
        "- Workloads: `10`",
        "- Execution specifications: `10`",
        "- Historical prefix audit matches: `true`",
        "- Historical prefix workload matches: `true`",
        "- Historical functional rerun required: `false`",
        "- Functional execution performed: `false`",
        "- Timing execution performed: `false`",
        "",
        "## Contract interpretation",
        "",
        (
            "The two selected queries must occur at all three "
            "virtual-node levels. Complete nesting of the full "
            "objective query sets is not required."
        ),
        "",
        "## Next stage",
        "",
        "`merge_stage10_common_workload_preparation`",
        "",
    ]

    (root / GLOBAL_SUMMARY_REL).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
    )
    parser.add_argument(
        "--canonical-root",
        type=Path,
        default=CANONICAL_ROOT,
    )

    args = parser.parse_args()

    report = prepare(
        args.repo_root.resolve(),
        args.canonical_root.resolve(),
    )

    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=args.repo_root,
            text=True,
        ).strip()
    except Exception:
        source_commit = "unknown"

    print()
    print(
        "stage10_common_workload_preparation=PASS"
    )
    print(f"source_commit={source_commit}")
    print(
        "replication_count="
        f"{report['replication_count']}"
    )
    print(
        "workload_count="
        f"{report['workload_count']}"
    )
    print(
        "execution_spec_count="
        f"{report['execution_spec_count']}"
    )
    print(
        "historical_prefix_audit_matches=true"
    )
    print(
        "historical_prefix_workload_matches=true"
    )
    print(
        "historical_prefix_rerun_required=false"
    )
    print("functional_execution_performed=false")
    print("timing_execution_performed=false")
    print(
        "next_stage="
        "merge_stage10_common_workload_preparation"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
