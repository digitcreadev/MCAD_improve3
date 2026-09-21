def test_execution_and_exclusions(plan):
    assert plan["execution_authorized"] is False
    assert "FamilyBasedRelevance" in plan["excluded"]["measures"]
    assert plan["excluded"]["executions"] == ["Djedaini", "ASSESS"]
    forbidden = {"thresholds", "AUROC", "AUPRC", "ALLOW", "BLOCK", "SAFE_TO_PRUNE", "MCAD decision conversion"}
    assert forbidden <= set(plan["excluded"]["claims_or_analyses"])


def test_timing_and_pre_result_caveat(plan):
    timing = plan["timing_semantics"]
    assert timing == {"classification": "SMOKE_DIAGNOSTIC_ONLY", "comparative_tables_allowed": False, "pre_post_latency_comparison_allowed": False, "backend_avoidance_claim_allowed": False}
    caveat = plan["scientific_caveat"]
    assert "SessionQueryProcessorEngine.answerCubeQueryWithInterestMeasures" in caveat
    assert "executes database queries" in caveat
    assert "never pre-backend timing or performance" in caveat


def test_isolation_and_fail_closed(plan):
    assert plan["isolation"] == {"fresh_exact_source_export_per_track": True, "history_mutation_cross_track_allowed": False, "exact_dump_overlay_required": True}
    assert len(plan["failure_policy"]["fail_closed_on"]) == 8
