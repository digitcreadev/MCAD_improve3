from __future__ import annotations

from pathlib import Path

from backend.harness.sensitivity_execution.tools.audit_objective_count_structure_v2 import (
    audit_objective_count_structure_v2,
)
from backend.harness.sensitivity_generator.families.objective_count_family_v2 import (
    ObjectiveCountV2FamilySpec,
    generate_objective_count_family_v2,
)


def test_structure_auditor_accepts_v2_family(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    generate_objective_count_family_v2(
        ObjectiveCountV2FamilySpec(
            campaign_id="structure-audit",
            levels=(1, 2),
            seeds=(101,),
            baseline_constraints_per_objective=8,
            baseline_virtual_nodes_per_objective=32,
            selected_objective_index=0,
            output_dir=str(campaign),
        )
    )
    report = audit_objective_count_structure_v2(campaign)
    assert report["status"] == "PASS"
    assert report["failure_count"] == 0
    assert report["instance_count"] == 2
    assert all(item["support_resource_count"] == 24 for item in report["instance_reports"])
    assert all(item["support_query_signature_count"] == 24 for item in report["instance_reports"])
