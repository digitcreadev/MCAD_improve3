from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


ROOT = Path("/workspaces/MCAD_improve3")

CAMPAIGN_DIR = (
    ROOT
    / "reports/article_experiments/sensitivity/"
      "e2_2_controlled_families/campaigns/"
      "constraint_count"
)

INSTANCES_CSV = CAMPAIGN_DIR / "instances.csv"

OUTPUT_DIR = (
    ROOT
    / "reports/article_experiments/sensitivity/"
      "e3_controlled_execution/audits/"
      "constraint_count"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "strict_common_query_specs.json"
)

SUMMARY_PATH = (
    OUTPUT_DIR
    / "strict_common_query_specs_summary.txt"
)


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
        default=str,
    )


def digest(value: Any) -> str:
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
            objective = next(
                iter(objectives.values())
            )
        else:
            raise ValueError(
                f"No objective found in {path}"
            )
    else:
        raise ValueError(
            f"Unsupported objective structure in {path}"
        )

    if not isinstance(objective, dict):
        raise ValueError(
            f"Objective is not an object in {path}"
        )

    return objective


def semantic_virtual_node(
    virtual_node: dict[str, Any],
) -> dict[str, Any]:
    projection = {
        field: deepcopy(virtual_node[field])
        for field in SEMANTIC_FIELDS
        if field in virtual_node
    }

    missing = [
        field
        for field in SEMANTIC_FIELDS
        if field not in projection
    ]

    if missing:
        raise ValueError(
            "Virtual Node is missing required semantic "
            f"fields: {missing}; "
            f"id={virtual_node.get('id')}"
        )

    return projection


def workload_query_spec(
    semantic_node: dict[str, Any],
) -> dict[str, Any]:
    year = (
        semantic_node
        .get("slicers", {})
        .get("Time.Year")
    )

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

    if year is not None:
        query_spec["time_members"] = [
            str(year)
        ]

    return query_spec


if not INSTANCES_CSV.is_file():
    raise SystemExit(
        f"[ERROR] Missing instances.csv: "
        f"{INSTANCES_CSV}"
    )


with INSTANCES_CSV.open(
    "r",
    encoding="utf-8",
    newline="",
) as handle:
    instance_rows = list(
        csv.DictReader(handle)
    )


if not instance_rows:
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
    - set(instance_rows[0])
)

if missing_columns:
    raise SystemExit(
        "[ERROR] Missing instances.csv columns: "
        f"{sorted(missing_columns)}"
    )


instances: list[dict[str, Any]] = []

for row in instance_rows:
    relative_dir = Path(
        row["relative_instance_dir"]
    )

    instance_dir = (
        CAMPAIGN_DIR
        / relative_dir
    )

    objectives_path = (
        instance_dir
        / "objectives.yaml"
    )

    if not objectives_path.is_file():
        raise SystemExit(
            "[ERROR] Missing objectives.yaml: "
            f"{objectives_path}"
        )

    objective = load_objective(
        objectives_path
    )

    nodes_by_digest: dict[
        str,
        dict[str, Any],
    ] = {}

    occurrences_by_digest: dict[
        str,
        list[dict[str, str]],
    ] = {}

    constraints = objective.get(
        "constraints",
        [],
    )

    if not isinstance(constraints, list):
        raise SystemExit(
            "[ERROR] constraints must be a list: "
            f"{objectives_path}"
        )

    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue

        constraint_id = str(
            constraint.get("id", "")
        )

        virtual_nodes = constraint.get(
            "virtual_nodes",
            [],
        )

        if not isinstance(
            virtual_nodes,
            list,
        ):
            continue

        for virtual_node in virtual_nodes:
            if not isinstance(
                virtual_node,
                dict,
            ):
                continue

            semantic_node = (
                semantic_virtual_node(
                    virtual_node
                )
            )

            node_digest = digest(
                semantic_node
            )

            nodes_by_digest.setdefault(
                node_digest,
                semantic_node,
            )

            occurrences_by_digest.setdefault(
                node_digest,
                [],
            ).append(
                {
                    "constraint_id": (
                        constraint_id
                    ),
                    "virtual_node_id": str(
                        virtual_node.get(
                            "id",
                            "",
                        )
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
            "constraint_count": len(
                constraints
            ),
            "semantic_nodes": (
                nodes_by_digest
            ),
            "occurrences": (
                occurrences_by_digest
            ),
        }
    )


instances.sort(
    key=lambda item: (
        item["factor_level"],
        item["replication_index"],
        item["seed"],
    )
)


digest_sets = [
    set(
        instance["semantic_nodes"]
    )
    for instance in instances
]


strict_common_digests = (
    set.intersection(*digest_sets)
    if digest_sets
    else set()
)


presence_counter: Counter[str] = Counter()

for digest_set in digest_sets:
    presence_counter.update(
        digest_set
    )


all_semantic_nodes: dict[
    str,
    dict[str, Any],
] = {}

for instance in instances:
    all_semantic_nodes.update(
        instance["semantic_nodes"]
    )


strict_common_nodes = []

for node_digest in sorted(
    strict_common_digests
):
    semantic_node = all_semantic_nodes[
        node_digest
    ]

    occurrences = []

    for instance in instances:
        for occurrence in (
            instance["occurrences"]
            .get(node_digest, [])
        ):
            occurrences.append(
                {
                    "relative_instance_dir": (
                        instance[
                            "relative_instance_dir"
                        ]
                    ),
                    "objective_id": (
                        instance[
                            "objective_id"
                        ]
                    ),
                    **occurrence,
                }
            )

    strict_common_nodes.append(
        {
            "semantic_digest": (
                node_digest
            ),
            "semantic_virtual_node": (
                semantic_node
            ),
            "query_spec": (
                workload_query_spec(
                    semantic_node
                )
            ),
            "occurrences": occurrences,
        }
    )


near_common_nodes = []

instance_count = len(instances)

for node_digest, count in sorted(
    presence_counter.items(),
    key=lambda item: (
        -item[1],
        item[0],
    ),
):
    if count == instance_count:
        continue

    near_common_nodes.append(
        {
            "semantic_digest": (
                node_digest
            ),
            "instance_presence_count": (
                count
            ),
            "instance_count": (
                instance_count
            ),
            "presence_ratio": round(
                count / instance_count,
                6,
            ),
            "semantic_virtual_node": (
                all_semantic_nodes[
                    node_digest
                ]
            ),
        }
    )


report = {
    "audit_contract_version": (
        "mcad-e3-constraint-count-"
        "common-workload-audit-v1"
    ),
    "campaign_dir": str(
        CAMPAIGN_DIR
    ),
    "instance_count": (
        instance_count
    ),
    "factor_levels": sorted(
        {
            instance["factor_level"]
            for instance in instances
        }
    ),
    "replication_indices": sorted(
        {
            instance[
                "replication_index"
            ]
            for instance in instances
        }
    ),
    "instances": [
        {
            "objective_id": (
                instance["objective_id"]
            ),
            "relative_instance_dir": (
                instance[
                    "relative_instance_dir"
                ]
            ),
            "factor_level": (
                instance["factor_level"]
            ),
            "replication_index": (
                instance[
                    "replication_index"
                ]
            ),
            "seed": instance["seed"],
            "constraint_count": (
                instance[
                    "constraint_count"
                ]
            ),
            "unique_semantic_node_count": (
                len(
                    instance[
                        "semantic_nodes"
                    ]
                )
            ),
        }
        for instance in instances
    ],
    "strict_common_query_spec_count": (
        len(strict_common_nodes)
    ),
    "strict_common_query_specs": (
        strict_common_nodes
    ),
    "near_common_query_specs": (
        near_common_nodes
    ),
}


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT_PATH.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)


summary_lines = [
    "MCAD E3 constraint_count common workload audit",
    "",
    f"campaign_dir={CAMPAIGN_DIR}",
    f"instance_count={instance_count}",
    (
        "factor_levels="
        + ",".join(
            str(level)
            for level in report[
                "factor_levels"
            ]
        )
    ),
    (
        "replication_indices="
        + ",".join(
            str(index)
            for index in report[
                "replication_indices"
            ]
        )
    ),
    (
        "strict_common_query_spec_count="
        f"{len(strict_common_nodes)}"
    ),
    "",
    "INSTANCE SUMMARY",
]


for instance in instances:
    summary_lines.append(
        "  "
        f"level={instance['factor_level']} "
        f"rep={instance['replication_index']} "
        f"seed={instance['seed']} "
        f"constraints="
        f"{instance['constraint_count']} "
        f"semantic_nodes="
        f"{len(instance['semantic_nodes'])} "
        f"path="
        f"{instance['relative_instance_dir']}"
    )


summary_lines.extend(
    [
        "",
        "STRICT COMMON QUERY SPECS",
    ]
)


if strict_common_nodes:
    for index, node in enumerate(
        strict_common_nodes,
        start=1,
    ):
        query_spec = node[
            "query_spec"
        ]

        summary_lines.append(
            "  "
            f"step={index} "
            f"digest="
            f"{node['semantic_digest']} "
            f"measure="
            f"{query_spec['measures'][0]} "
            f"aggregator="
            f"{query_spec['aggregators'][0]} "
            f"unit="
            f"{query_spec['units'][0]} "
            f"slicers="
            f"{query_spec['slicers']}"
        )
else:
    summary_lines.append(
        "  NONE"
    )


SUMMARY_PATH.write_text(
    "\n".join(summary_lines)
    + "\n",
    encoding="utf-8",
)


print("[OK] Constraint-count audit completed.")
print(
    f"[OK] instance_count="
    f"{instance_count}"
)
print(
    "[OK] factor_levels="
    + ",".join(
        str(level)
        for level in report[
            "factor_levels"
        ]
    )
)
print(
    "[OK] replication_indices="
    + ",".join(
        str(index)
        for index in report[
            "replication_indices"
        ]
    )
)
print(
    "[OK] strict_common_query_spec_count="
    f"{len(strict_common_nodes)}"
)
print(f"[OK] report={REPORT_PATH}")
print(f"[OK] summary={SUMMARY_PATH}")

print()
print("=== STRICT COMMON QUERY SPECS ===")

if not strict_common_nodes:
    print("NONE")
else:
    for index, node in enumerate(
        strict_common_nodes,
        start=1,
    ):
        query_spec = node[
            "query_spec"
        ]

        print()
        print(
            f"[STEP {index:02d}] "
            f"digest="
            f"{node['semantic_digest']}"
        )
        print(
            json.dumps(
                query_spec,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
