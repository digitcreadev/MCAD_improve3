from pathlib import Path

from backend.harness.sensitivity_execution.tools.validate_virtual_node_count_stage10_preregistration import (
    validate_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def test_virtual_node_count_stage10_preregistration_is_valid():
    assert validate_contract(REPO_ROOT) == []


def test_virtual_node_count_historical_prefix_is_not_rerun():
    import json

    contract_path = (
        REPO_ROOT
        / "reports/article_experiments/sensitivity"
        / "e3_controlled_execution/planning"
        / "virtual_node_count_stage10_preregistration.json"
    )

    contract = json.loads(
        contract_path.read_text(encoding="utf-8")
    )

    prefix = contract["historical_functional_prefix"]
    gates = contract["authorization_gates"]

    assert prefix["rerun_required"] is False
    assert prefix["rerun_authorized"] is False
    assert (
        gates["historical_functional_rerun_authorized"]
        is False
    )


def test_execution_remains_blocked_after_preregistration():
    import json

    contract_path = (
        REPO_ROOT
        / "reports/article_experiments/sensitivity"
        / "e3_controlled_execution/planning"
        / "virtual_node_count_stage10_preregistration.json"
    )

    contract = json.loads(
        contract_path.read_text(encoding="utf-8")
    )

    gates = contract["authorization_gates"]

    assert gates["structural_stage10_generation_authorized"] is True
    assert gates["new_functional_execution_authorized"] is False
    assert gates["formal_timing_execution_authorized"] is False
    assert gates["stage20_execution_authorized"] is False
    assert gates["latency_claim_authorized"] is False
