from __future__ import annotations

from pathlib import Path

from backend.harness.sensitivity_execution.tools.audit_objective_count_stage10_common_workloads_v2 import (
    audit_common_workloads,
)
from backend.harness.sensitivity_execution.tools.prepare_objective_count_stage10_common_workloads_v2 import (
    prepare_common_workloads,
)
from backend.harness.sensitivity_generator.families.objective_count_family_v2 import (
    ObjectiveCountV2FamilySpec,
    generate_objective_count_family_v2,
)


def test_common_workload_materializer_and_auditor(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    workloads = tmp_path / "workloads"
    generate_objective_count_family_v2(
        ObjectiveCountV2FamilySpec(
            campaign_id="workload-audit",
            levels=(1, 2),
            seeds=(101,),
            baseline_constraints_per_objective=8,
            baseline_virtual_nodes_per_objective=32,
            selected_objective_index=0,
            output_dir=str(campaign),
        )
    )
    manifest = prepare_common_workloads(campaign, workloads)
    assert manifest["workload_count"] == 1
    assert manifest["workload_length"] == 32
    assert manifest["contributive_query_count_per_workload"] == 24
    assert manifest["non_contributive_query_count_per_workload"] == 8
    assert manifest["entries"][0]["shared_factor_levels"] == [1, 2]

    report = audit_common_workloads(campaign, workloads)
    assert report["status"] == "PASS", report
    assert report["failure_count"] == 0
    row = report["workload_reports"][0]
    assert row["oracle_contributive_query_count"] == 24
    assert row["non_contributive_query_count"] == 8
    assert row["realised_noise_ratio"] == 0.25
    assert row["operator_oracle_mismatch_count"] == 0
    assert set(row["realised_noise_class_counts"].values()) == {1}
