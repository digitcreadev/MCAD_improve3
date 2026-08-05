from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.sensitivity_execution.tools.objective_count_noise_operators_v2 import (
    semantic_projection,
    sha256_payload,
    support_query_from_virtual_node,
)

AUDITOR_VERSION = "mcad-sa5-objective-count-structure-auditor-v2"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def audit_objective_count_structure_v2(campaign_dir: Path) -> dict[str, Any]:
    campaign_dir = campaign_dir.resolve()
    manifest = _read_json(campaign_dir / "campaign_manifest.json")
    with (campaign_dir / "instances.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]

    failures: list[str] = []
    instance_reports: list[dict[str, Any]] = []
    for row in rows:
        instance_dir = campaign_dir / row["relative_instance_dir"]
        instance_manifest = _read_json(instance_dir / "manifest.json")
        document = yaml.safe_load(
            (instance_dir / "objectives.yaml").read_text(encoding="utf-8")
        ) or {}
        selected_id = row["objective_id"]
        selected = next(
            item for item in document["objectives"] if item["id"] == selected_id
        )
        if selected.get("session_support_policy") != "union_requirement_sets":
            failures.append(f"{selected_id}: support policy")
        constraints = list(selected.get("constraints") or [])
        if len(constraints) != 8:
            failures.append(f"{selected_id}: constraint count")

        ckg = CKGGraph(output_dir=str(instance_dir / "audit_runtime"))
        ckg.G.clear()
        ckg.objectives.clear()
        ckg.history.clear()
        ckg.session_coverage.clear()
        ckg.session_weighted_coverage.clear()
        ckg.session_resource_coverage.clear()
        ckg.bootstrap_objectives(str(instance_dir / "objectives.yaml"))

        signatures: list[str] = []
        real_node_counts: list[int] = []
        support_count = 0
        for constraint_index, constraint in enumerate(constraints):
            virtual_nodes = list(constraint.get("virtual_nodes") or [])
            requirement_sets = list(constraint.get("requirement_sets") or [])
            if len(virtual_nodes) != 4:
                failures.append(f"{selected_id}: C{constraint_index} NV count")
            expected_sets = [
                [virtual_nodes[0]["id"], virtual_nodes[1]["id"]],
                [virtual_nodes[1]["id"], virtual_nodes[2]["id"]],
            ]
            if requirement_sets != expected_sets:
                failures.append(f"{selected_id}: C{constraint_index} requirement sets")
            support = ckg._constraint_support(selected_id, constraint["id"])
            if support != sorted(
                {virtual_nodes[0]["id"], virtual_nodes[1]["id"], virtual_nodes[2]["id"]}
            ):
                failures.append(f"{selected_id}: C{constraint_index} support union")
            support_count += len(support)
            for local_index in range(3):
                ordinal = constraint_index * 3 + local_index
                query = support_query_from_virtual_node(
                    virtual_nodes[local_index],
                    support_ordinal=ordinal,
                    constraint_index=constraint_index,
                    local_virtual_node_index=local_index,
                )
                signatures.append(sha256_payload(semantic_projection(query)))
                real_ids = ckg.real(
                    selected_id,
                    ckg.add_qp_node(
                        f"audit-{ordinal}",
                        ordinal,
                        {"objective_id": selected_id, "query_spec": query},
                    ),
                )
                real_node_counts.append(len(real_ids))
                if real_ids != {virtual_nodes[local_index]["id"]}:
                    failures.append(f"{selected_id}: support query {ordinal}")

        if len(set(signatures)) != 24:
            failures.append(f"{selected_id}: duplicate support signatures")
        if support_count != 24:
            failures.append(f"{selected_id}: support count")

        expected_level = int(row["factor_level"])
        expected_counts = {
            "total_constraint_count": 8 * expected_level,
            "useful_virtual_node_count": 24 * expected_level,
            "irrelevant_virtual_node_count": 8 * expected_level,
            "total_virtual_node_count": 32 * expected_level,
            "requirement_set_count": 16 * expected_level,
            "requirement_membership_link_count": 32 * expected_level,
            "maximum_membership_link_count": 64 * expected_level,
        }
        for key, expected in expected_counts.items():
            if int(instance_manifest.get(key, -1)) != expected:
                failures.append(f"{selected_id}: manifest {key}")
        if float(instance_manifest.get("realised_density", -1)) != 0.5:
            failures.append(f"{selected_id}: density")

        instance_reports.append(
            {
                "objective_id": selected_id,
                "factor_level": expected_level,
                "support_resource_count": support_count,
                "support_query_signature_count": len(set(signatures)),
                "support_query_real_node_counts": real_node_counts,
            }
        )

    return {
        "schema_version": "mcad-sa5-objective-count-structure-audit-v2",
        "auditor_version": AUDITOR_VERSION,
        "campaign_id": manifest.get("campaign_id"),
        "instance_count": len(rows),
        "instance_reports": instance_reports,
        "failure_count": len(failures),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit_objective_count_structure_v2(args.campaign_dir)
    if args.report:
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
