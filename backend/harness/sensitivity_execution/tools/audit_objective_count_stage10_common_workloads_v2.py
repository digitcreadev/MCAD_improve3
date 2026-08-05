from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.sensitivity_execution.tools.objective_count_noise_operators_v2 import (
    CONTRIBUTIVE_STEP_COUNT,
    NOISE_CLASS_ORDER,
    NOISE_STEP_COUNT,
    OPERATOR_REGISTRY_VERSION,
    WORKLOAD_LENGTH,
    build_noise_schedule,
    semantic_projection,
    sha256_payload,
)
from backend.harness.sensitivity_execution.validate_workload_spec import (
    validate_workload_spec,
)

AUDITOR_VERSION = "mcad-sa5-objective-count-stage10-workload-auditor-v2"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def audit_common_workloads(
    campaign_dir: Path,
    workload_dir: Path,
) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    workload_dir = workload_dir.resolve()
    common_manifest = _read_json(workload_dir / "common_workloads_manifest.json")

    with (campaign_dir / "instances.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    row_by_rep = {
        int(row["replication_index"]): row
        for row in sorted(rows, key=lambda item: int(item["factor_level"]))
    }

    failures: list[str] = []
    workload_reports: list[dict[str, Any]] = []
    stage_counts: Counter[str] = Counter()

    for entry in common_manifest["entries"]:
        replication_index = int(entry["replication_index"])
        seed = int(entry["seed"])
        workload = _read_json(workload_dir / entry["workload_path"])
        validate_workload_spec(workload)
        schedule = build_noise_schedule(seed)
        if len(workload["steps"]) != WORKLOAD_LENGTH:
            failures.append(f"rep {replication_index}: workload length")

        row = row_by_rep[replication_index]
        instance_dir = campaign_dir / row["relative_instance_dir"]
        ckg = CKGGraph(output_dir=str(workload_dir / f"audit_runtime_{replication_index}"))
        ckg.G.clear()
        ckg.objectives.clear()
        ckg.history.clear()
        ckg.session_coverage.clear()
        ckg.session_weighted_coverage.clear()
        ckg.session_resource_coverage.clear()
        ckg.bootstrap_objectives(str(instance_dir / "objectives.yaml"))
        objective_id = row["objective_id"]
        session_id = f"audit-rep-{replication_index:03d}"

        observed_contributive = 0
        observed_noncontributive = 0
        support_ordinals: list[int] = []
        noise_counts: Counter[str] = Counter()
        operator_mismatch_count = 0

        step_results: dict[int, dict[str, Any]] = {}
        for step in workload["steps"]:
            step_index = int(step["step_index"])
            query_spec = step["query_spec"]
            result = ckg.evaluate_step(
                session_id=session_id,
                objective_id=objective_id,
                step_idx=step_index,
                qp={"objective_id": objective_id, "query_spec": query_spec},
            )
            step_results[step_index] = result
            metadata = query_spec.get("mcad_controlled_noise")
            if metadata is None:
                coordinate = query_spec.get("mcad_support_coordinate") or {}
                support_ordinals.append(int(coordinate["support_ordinal"]))
                if result["is_session_contributive"] is not True:
                    operator_mismatch_count += 1
                if len(result["gained_resource_ids"]) != 1:
                    operator_mismatch_count += 1
                observed_contributive += int(result["is_session_contributive"])
            else:
                noise_class = metadata["noise_class"]
                noise_counts[noise_class] += 1
                stage_counts[noise_class] += 1
                if metadata["operator_registry_version"] != OPERATOR_REGISTRY_VERSION:
                    operator_mismatch_count += 1
                if metadata["source_semantic_digest"] != sha256_payload(
                    semantic_projection(
                        workload["steps"][
                            metadata["source_step_index"] - 1
                        ]["query_spec"]
                        if noise_class == "redundant_contribution"
                        else query_spec
                    )
                ) and noise_class == "redundant_contribution":
                    operator_mismatch_count += 1
                expected_sat = noise_class == "redundant_contribution"
                if result["sat"] is not expected_sat:
                    operator_mismatch_count += 1
                if bool(result.get("is_session_contributive", False)):
                    operator_mismatch_count += 1
                if result.get("gained_resource_ids") or []:
                    operator_mismatch_count += 1
                if noise_class == "redundant_contribution":
                    source_index = int(metadata["source_step_index"])
                    if source_index >= step_index:
                        operator_mismatch_count += 1
                    if step_results[source_index]["is_session_contributive"] is not True:
                        operator_mismatch_count += 1
                observed_noncontributive += int(
                    not bool(result.get("is_session_contributive", False))
                )

        if sorted(support_ordinals) != list(range(CONTRIBUTIVE_STEP_COUNT)):
            failures.append(f"rep {replication_index}: support-coordinate bijection")
        if noise_counts != Counter({item: 1 for item in NOISE_CLASS_ORDER}):
            failures.append(f"rep {replication_index}: noise classes")
        if observed_contributive != CONTRIBUTIVE_STEP_COUNT:
            failures.append(f"rep {replication_index}: contribution count")
        if observed_noncontributive != NOISE_STEP_COUNT:
            failures.append(f"rep {replication_index}: noise count")
        if operator_mismatch_count:
            failures.append(f"rep {replication_index}: operator oracle")
        if tuple(schedule.noise_positions) != tuple(
            step["step_index"]
            for step in workload["steps"]
            if "mcad_controlled_noise" in step["query_spec"]
        ):
            failures.append(f"rep {replication_index}: deterministic positions")

        workload_reports.append(
            {
                "replication_index": replication_index,
                "seed": seed,
                "workload_length": len(workload["steps"]),
                "oracle_contributive_query_count": observed_contributive,
                "non_contributive_query_count": observed_noncontributive,
                "realised_noise_ratio": observed_noncontributive / WORKLOAD_LENGTH,
                "realised_noise_class_counts": dict(sorted(noise_counts.items())),
                "operator_oracle_mismatch_count": operator_mismatch_count,
                "semantic_workload_digest": sha256_payload(
                    [semantic_projection(step["query_spec"]) for step in workload["steps"]]
                ),
                "objective_normalized_workload_digest": sha256_payload(
                    {
                        "steps": [
                            {
                                "step_index": step["step_index"],
                                "query_spec": step["query_spec"],
                            }
                            for step in workload["steps"]
                        ]
                    }
                ),
            }
        )

    if stage_counts != Counter({item: len(workload_reports) for item in NOISE_CLASS_ORDER}):
        failures.append("stage noise-class totals")

    return {
        "schema_version": "mcad-sa5-objective-count-stage10-workload-audit-v2",
        "auditor_version": AUDITOR_VERSION,
        "workload_count": len(workload_reports),
        "workload_reports": workload_reports,
        "stage10_noise_class_counts": dict(sorted(stage_counts.items())),
        "failure_count": len(failures),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("workload_dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit_common_workloads(args.campaign_dir, args.workload_dir)
    if args.report:
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
