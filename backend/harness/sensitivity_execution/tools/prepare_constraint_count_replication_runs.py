from __future__ import annotations

import csv
import hashlib
import json
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


ROOT = Path("/workspaces/MCAD_improve3")

CAMPAIGN_DIR = (
    ROOT
    / "reports/article_experiments/sensitivity/"
      "e2_2_controlled_families/campaigns/"
      "constraint_count"
)

INSTANCES_CSV = CAMPAIGN_DIR / "instances.csv"

E3_ROOT = (
    ROOT
    / "reports/article_experiments/sensitivity/"
      "e3_controlled_execution"
)

AUDIT_DIR = (
    E3_ROOT
    / "audits/constraint_count/by_replication"
)

WORKLOAD_DIR = E3_ROOT / "workloads"
EXECUTION_SPEC_DIR = E3_ROOT / "execution_specs"
RUNS_DIR = E3_ROOT / "runs"


SEMANTIC_FIELDS = (
    "fact",
    "grain",
    "measure",
    "aggregator",
    "unit",
    "slicers",
    "window_start",
    "window_end",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def semantic_digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def load_objective(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    objectives = (
        document.get("objectives", document)
        if isinstance(document, dict)
        else document
    )

    if isinstance(objectives, list):
        if not objectives:
            raise ValueError(
                f"No objective found in {path}"
            )
        objective = objectives[0]

    elif isinstance(objectives, dict):
        if "constraints" in objectives:
            objective = objectives
        elif objectives:
            objective = next(iter(objectives.values()))
        else:
            raise ValueError(
                f"No objective found in {path}"
            )
    else:
        raise ValueError(
            f"Unsupported objective structure: {path}"
        )

    if not isinstance(objective, dict):
        raise ValueError(
            f"Objective is not an object: {path}"
        )

    return objective


def semantic_projection(
    virtual_node: dict[str, Any],
) -> dict[str, Any]:
    missing = [
        field
        for field in SEMANTIC_FIELDS
        if field not in virtual_node
    ]

    if missing:
        raise ValueError(
            f"Virtual Node {virtual_node.get('id')} "
            f"is missing fields {missing}"
        )

    return {
        field: deepcopy(virtual_node[field])
        for field in SEMANTIC_FIELDS
    }


def query_spec_from_semantic(
    semantic_node: dict[str, Any],
) -> dict[str, Any]:
    query_spec = {
        "cube": semantic_node["fact"],
        "measures": [
            semantic_node["measure"]
        ],
        "group_by": list(
            semantic_node["grain"]
        ),
        "slicers": deepcopy(
            semantic_node["slicers"]
        ),
        "aggregators": [
            semantic_node["aggregator"]
        ],
        "units": [
            semantic_node["unit"]
        ],
        "window_start": (
            semantic_node["window_start"]
        ),
        "window_end": (
            semantic_node["window_end"]
        ),
    }

    year = (
        semantic_node
        .get("slicers", {})
        .get("Time.Year")
    )

    if year is not None:
        query_spec["time_members"] = [
            str(year)
        ]

    return query_spec


def step_slug(
    semantic_node: dict[str, Any],
    index: int,
) -> str:
    measure = str(
        semantic_node["measure"]
    ).lower()

    aggregator = str(
        semantic_node["aggregator"]
    ).lower()

    region = str(
        semantic_node["slicers"]
        .get("Geography.Region", "region")
    ).lower()

    year = str(
        semantic_node["slicers"]
        .get("Time.Year", "year")
    ).lower()

    return (
        f"step-{index:04d}-"
        f"{measure}-{aggregator}-"
        f"{region}-{year}"
    )


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
    raise SystemExit(
        "[ERROR] instances.csv is empty."
    )


required_columns = {
    "objective_id",
    "relative_instance_dir",
    "factor_level",
    "replication_index",
    "seed",
}

missing_columns = (
    required_columns
    - set(rows[0])
)

if missing_columns:
    raise SystemExit(
        "[ERROR] Missing instances.csv columns: "
        f"{sorted(missing_columns)}"
    )


instances: list[dict[str, Any]] = []

for row in rows:
    instance_dir = (
        CAMPAIGN_DIR
        / row["relative_instance_dir"]
    )

    objectives_path = (
        instance_dir
        / "objectives.yaml"
    )

    objective = load_objective(
        objectives_path
    )

    semantic_nodes: dict[
        str,
        dict[str, Any],
    ] = {}

    occurrences: dict[
        str,
        list[dict[str, str]],
    ] = {}

    for constraint in objective.get(
        "constraints",
        [],
    ):
        constraint_id = str(
            constraint.get("id", "")
        )

        for virtual_node in constraint.get(
            "virtual_nodes",
            [],
        ):
            semantic_node = semantic_projection(
                virtual_node
            )

            digest = semantic_digest(
                semantic_node
            )

            semantic_nodes.setdefault(
                digest,
                semantic_node,
            )

            occurrences.setdefault(
                digest,
                [],
            ).append(
                {
                    "constraint_id": (
                        constraint_id
                    ),
                    "virtual_node_id": str(
                        virtual_node.get("id", "")
                    ),
                }
            )

    instances.append(
        {
            "objective_id": (
                row["objective_id"]
            ),
            "relative_instance_dir": (
                row["relative_instance_dir"]
            ),
            "factor_level": int(
                row["factor_level"]
            ),
            "replication_index": int(
                row["replication_index"]
            ),
            "seed": int(
                row["seed"]
            ),
            "semantic_nodes": semantic_nodes,
            "occurrences": occurrences,
        }
    )


replication_indices = sorted(
    {
        instance["replication_index"]
        for instance in instances
    }
)


AUDIT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

WORKLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

EXECUTION_SPEC_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RUNS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


campaign_report: dict[str, Any] = {
    "contract_version": (
        "mcad-e3-constraint-count-"
        "replication-plan-v1"
    ),
    "campaign_dir": str(CAMPAIGN_DIR),
    "replications": [],
}


for replication_index in replication_indices:
    selected = sorted(
        [
            instance
            for instance in instances
            if instance["replication_index"]
            == replication_index
        ],
        key=lambda item: item["factor_level"],
    )

    levels = [
        instance["factor_level"]
        for instance in selected
    ]

    if levels != [2, 4, 8]:
        raise SystemExit(
            "[ERROR] Expected levels [2, 4, 8] "
            f"for replication {replication_index}, "
            f"found {levels}."
        )

    seeds = {
        instance["seed"]
        for instance in selected
    }

    if len(seeds) != 1:
        raise SystemExit(
            "[ERROR] Replication "
            f"{replication_index} has inconsistent "
            f"seeds: {sorted(seeds)}"
        )

    seed = next(iter(seeds))

    common_digests = set.intersection(
        *[
            set(instance["semantic_nodes"])
            for instance in selected
        ]
    )

    if not common_digests:
        raise SystemExit(
            "[ERROR] No strictly common query "
            f"for replication {replication_index}."
        )

    common_nodes = [
        selected[0]["semantic_nodes"][digest]
        for digest in sorted(common_digests)
    ]

    steps = []

    for index, semantic_node in enumerate(
        common_nodes,
        start=1,
    ):
        steps.append(
            {
                "step_index": index,
                "step_id": step_slug(
                    semantic_node,
                    index,
                ),
                "query_spec": (
                    query_spec_from_semantic(
                        semantic_node
                    )
                ),
            }
        )

    replication_token = (
        f"rep_{replication_index:03d}"
    )

    workload_path = (
        WORKLOAD_DIR
        / (
            "constraint_count_"
            f"{replication_token}_"
            "strict_common.json"
        )
    )

    execution_spec_path = (
        EXECUTION_SPEC_DIR
        / (
            "constraint_count_"
            f"{replication_token}_"
            "strict_common.json"
        )
    )

    output_dir = (
        RUNS_DIR
        / (
            "constraint_count_"
            f"{replication_token}_"
            "strict_common"
        )
    )

    workload = {
        "contract_version": (
            WORKLOAD_SCHEMA_VERSION
        ),
        "workload_id": (
            "e3-constraint-count-"
            f"{replication_token}-"
            "strict-common-v1"
        ),
        "objective_id": (
            "O_E3_CONSTRAINT_COUNT_"
            f"{replication_token.upper()}_"
            "RUNTIME_BOUND"
        ),
        "session_id": (
            "S_E3_CONSTRAINT_COUNT_"
            f"{replication_token.upper()}_"
            "STRICT_COMMON"
        ),
        "steps": steps,
    }

    execution_spec = {
        "contract_version": (
            EXECUTION_SCHEMA_VERSION
        ),
        "execution_id": (
            "e3-constraint-count-"
            f"{replication_token}-"
            "strict-common-v1"
        ),
        "campaign_dir": str(
            CAMPAIGN_DIR
        ),
        "workload_path": str(
            workload_path
        ),
        "output_dir": str(
            output_dir
        ),
        "instance_selection": {
            "instance_ids": [
                instance[
                    "relative_instance_dir"
                ]
                for instance in selected
            ]
        },
    }

    validate_workload_spec(workload)
    validate_execution_spec(
        execution_spec
    )

    workload_path.write_text(
        json.dumps(
            workload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    execution_spec_path.write_text(
        json.dumps(
            execution_spec,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    occurrence_report = []

    for digest in sorted(common_digests):
        by_instance = []

        for instance in selected:
            by_instance.append(
                {
                    "factor_level": (
                        instance["factor_level"]
                    ),
                    "objective_id": (
                        instance["objective_id"]
                    ),
                    "relative_instance_dir": (
                        instance[
                            "relative_instance_dir"
                        ]
                    ),
                    "occurrences": (
                        instance["occurrences"]
                        .get(digest, [])
                    ),
                }
            )

        occurrence_report.append(
            {
                "semantic_digest": digest,
                "semantic_virtual_node": (
                    selected[0][
                        "semantic_nodes"
                    ][digest]
                ),
                "instances": by_instance,
            }
        )

    replication_report = {
        "replication_index": (
            replication_index
        ),
        "seed": seed,
        "factor_levels": levels,
        "instance_count": len(selected),
        "strict_common_query_spec_count": (
            len(common_nodes)
        ),
        "workload_path": str(
            workload_path
        ),
        "execution_spec_path": str(
            execution_spec_path
        ),
        "output_dir": str(
            output_dir
        ),
        "instances": [
            {
                "factor_level": (
                    instance["factor_level"]
                ),
                "objective_id": (
                    instance["objective_id"]
                ),
                "relative_instance_dir": (
                    instance[
                        "relative_instance_dir"
                    ]
                ),
            }
            for instance in selected
        ],
        "common_query_specs": (
            occurrence_report
        ),
    }

    report_path = (
        AUDIT_DIR
        / (
            "constraint_count_"
            f"{replication_token}.json"
        )
    )

    report_path.write_text(
        json.dumps(
            replication_report,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    campaign_report[
        "replications"
    ].append(
        replication_report
    )

    print()
    print(
        f"[OK] replication="
        f"{replication_index} "
        f"seed={seed} "
        f"levels={levels} "
        f"common_steps={len(steps)}"
    )
    print(
        f"[OK] workload={workload_path}"
    )
    print(
        "[OK] execution_spec="
        f"{execution_spec_path}"
    )
    print(
        f"[OK] output_dir={output_dir}"
    )

    for step in steps:
        query = step["query_spec"]

        print(
            "  "
            f"step={step['step_index']} "
            f"id={step['step_id']} "
            f"measure={query['measures'][0]} "
            f"aggregator="
            f"{query['aggregators'][0]} "
            f"unit={query['units'][0]} "
            f"slicers={query['slicers']}"
        )


campaign_report_path = (
    AUDIT_DIR
    / "replication_execution_plan.json"
)

campaign_report_path.write_text(
    json.dumps(
        campaign_report,
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)

print()
print(
    "[OK] Replication execution plan "
    "completed."
)
print(
    f"[OK] report={campaign_report_path}"
)
