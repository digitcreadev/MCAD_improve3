from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from backend.harness.sensitivity_execution.tools.objective_count_noise_operators_v2 import (
    CONTRIBUTIVE_STEP_COUNT,
    NOISE_CLASS_ORDER,
    NOISE_STEP_COUNT,
    OPERATOR_REGISTRY_VERSION,
    WORKLOAD_LENGTH,
    apply_noise_operator,
    build_noise_schedule,
    semantic_projection,
    sha256_payload,
    support_query_from_virtual_node,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    SCHEMA_VERSION,
    validate_workload_spec,
)

CAMPAIGN_GENERATOR_VERSION = "mcad-sensitivity-e2.2-objective-count-v2"
STRUCTURAL_GENERATOR_VERSION = "mcad-sensitivity-e2.1-objective-count-v2"
MATERIALIZER_VERSION = "mcad-sa5-objective-count-stage10-workload-materializer-v2"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _selected_objective(
    objectives_path: Path,
    selected_objective_id: str,
) -> dict[str, Any]:
    document = yaml.safe_load(objectives_path.read_text(encoding="utf-8")) or {}
    objectives = document.get("objectives") or []
    matches = [
        item
        for item in objectives
        if isinstance(item, dict) and item.get("id") == selected_objective_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one selected objective {selected_objective_id!r} in "
            f"{objectives_path}."
        )
    return matches[0]


def support_queries_for_objective(
    objective: Mapping[str, Any],
) -> list[dict[str, Any]]:
    constraints = list(objective.get("constraints") or [])
    if len(constraints) != 8:
        raise ValueError("Objective-count v2 workload requires 8 constraints.")

    queries: list[dict[str, Any]] = []
    for constraint_index, constraint in enumerate(constraints):
        virtual_nodes = list(constraint.get("virtual_nodes") or [])
        if len(virtual_nodes) != 4:
            raise ValueError("Each objective-count v2 constraint requires 4 NVs.")
        for local_index in range(3):
            support_ordinal = constraint_index * 3 + local_index
            queries.append(
                support_query_from_virtual_node(
                    virtual_nodes[local_index],
                    support_ordinal=support_ordinal,
                    constraint_index=constraint_index,
                    local_virtual_node_index=local_index,
                )
            )
    if len(queries) != CONTRIBUTIVE_STEP_COUNT:
        raise ValueError("Expected exactly 24 support queries.")
    signatures = [sha256_payload(semantic_projection(query)) for query in queries]
    if len(set(signatures)) != len(signatures):
        raise ValueError("Support-query semantic signatures are not unique.")
    return queries


def build_common_workload(
    *,
    seed: int,
    replication_index: int,
    representative_objective: Mapping[str, Any],
) -> dict[str, Any]:
    objective_id = str(representative_objective["id"])
    schedule = build_noise_schedule(seed)
    support_queries = support_queries_for_objective(representative_objective)

    steps: list[dict[str, Any]] = []
    steps_by_index: dict[int, dict[str, Any]] = {}

    for step_index in range(1, WORKLOAD_LENGTH + 1):
        if step_index in schedule.contributive_positions:
            support_ordinal = schedule.contributive_positions.index(step_index)
            query_spec = dict(support_queries[support_ordinal])
            step_id = f"step-{step_index:04d}-support-{support_ordinal:02d}"
        else:
            noise_class = schedule.class_by_position[step_index]
            if noise_class == "redundant_contribution":
                source_step_index = schedule.redundant_source_step_index
                source_query = steps_by_index[source_step_index]["query_spec"]
                query_spec = apply_noise_operator(
                    noise_class,
                    source_query,
                    target_support_ordinal=(
                        schedule.redundant_source_support_ordinal
                    ),
                    source_step_index=source_step_index,
                )
            else:
                support_ordinal = (
                    schedule.target_support_ordinal_by_class[noise_class]
                )
                query_spec = apply_noise_operator(
                    noise_class,
                    support_queries[support_ordinal],
                    target_support_ordinal=support_ordinal,
                )
            step_id = f"step-{step_index:04d}-noise-{noise_class}"

        step = {
            "step_index": step_index,
            "step_id": step_id,
            "query_spec": query_spec,
        }
        steps.append(step)
        steps_by_index[step_index] = step

    workload = {
        "contract_version": SCHEMA_VERSION,
        "workload_id": (
            "sa5-objective-count-stage10-"
            f"rep-{replication_index:03d}-seed-{seed}"
        ),
        "objective_id": objective_id,
        "session_id": (
            "sa5-objective-count-stage10-session-"
            f"rep-{replication_index:03d}-seed-{seed}"
        ),
        "steps": steps,
    }
    validate_workload_spec(workload)
    return workload


def _workload_semantic_digest(workload: Mapping[str, Any]) -> str:
    return sha256_payload(
        [
            {
                "step_index": int(step["step_index"]),
                "semantic_query": semantic_projection(step["query_spec"]),
                "noise_class": (
                    (step["query_spec"].get("mcad_controlled_noise") or {}).get(
                        "noise_class"
                    )
                ),
            }
            for step in workload["steps"]
        ]
    )


def prepare_common_workloads(
    campaign_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory must be absent or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    campaign_manifest = _read_json(campaign_dir / "campaign_manifest.json")
    if campaign_manifest.get("campaign_generator_version") != CAMPAIGN_GENERATOR_VERSION:
        raise ValueError("Campaign is not objective-count v2.")
    if campaign_manifest.get("structural_generator_version") != STRUCTURAL_GENERATOR_VERSION:
        raise ValueError("Campaign structural version is not objective-count v2.")

    rows = _read_rows(campaign_dir / "instances.csv")
    by_replication: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        by_replication.setdefault(int(row["replication_index"]), []).append(row)

    entries: list[dict[str, Any]] = []
    for replication_index in sorted(by_replication):
        group = sorted(
            by_replication[replication_index],
            key=lambda row: int(row["factor_level"]),
        )
        seeds = {int(row["seed"]) for row in group}
        shapes = {row["selected_objective_shape_digest"] for row in group}
        if len(seeds) != 1 or len(shapes) != 1:
            raise ValueError("Replication is not structurally shared across levels.")
        seed = next(iter(seeds))
        representative = group[0]
        objective = _selected_objective(
            campaign_dir
            / representative["relative_instance_dir"]
            / "objectives.yaml",
            representative["objective_id"],
        )
        workload = build_common_workload(
            seed=seed,
            replication_index=replication_index,
            representative_objective=objective,
        )
        filename = f"replication_{replication_index:03d}_seed_{seed}.json"
        path = output_dir / filename
        path.write_text(
            json.dumps(workload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        noise_classes = [
            (step["query_spec"].get("mcad_controlled_noise") or {}).get(
                "noise_class"
            )
            for step in workload["steps"]
            if "mcad_controlled_noise" in step["query_spec"]
        ]
        entries.append(
            {
                "replication_index": replication_index,
                "seed": seed,
                "workload_path": filename,
                "representative_factor_level": int(representative["factor_level"]),
                "representative_objective_id": representative["objective_id"],
                "shared_factor_levels": [int(row["factor_level"]) for row in group],
                "workload_length": len(workload["steps"]),
                "contributive_query_count": CONTRIBUTIVE_STEP_COUNT,
                "non_contributive_query_count": NOISE_STEP_COUNT,
                "noise_classes": noise_classes,
                "semantic_workload_digest": _workload_semantic_digest(workload),
                "file_sha256": sha256_payload(workload),
            }
        )

    manifest = {
        "schema_version": "mcad-sa5-objective-count-stage10-common-workloads-v2",
        "materializer_version": MATERIALIZER_VERSION,
        "campaign_generator_version": CAMPAIGN_GENERATOR_VERSION,
        "structural_generator_version": STRUCTURAL_GENERATOR_VERSION,
        "operator_registry_version": OPERATOR_REGISTRY_VERSION,
        "campaign_id": campaign_manifest["campaign_id"],
        "factor": "objective_count",
        "workload_count": len(entries),
        "workload_length": WORKLOAD_LENGTH,
        "contributive_query_count_per_workload": CONTRIBUTIVE_STEP_COUNT,
        "non_contributive_query_count_per_workload": NOISE_STEP_COUNT,
        "noise_class_order": list(NOISE_CLASS_ORDER),
        "entries": entries,
    }
    (output_dir / "common_workloads_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    manifest = prepare_common_workloads(args.campaign_dir, args.output_dir)
    print("[OK] objective-count v2 common workloads prepared")
    print(f"[OK] workload_count={manifest['workload_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
