from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from backend.harness.sensitivity_execution.validate_e3_contract import (
    CONTRACT_PATH,
    validate_contract,
)


def load_contract() -> Mapping[str, Any]:
    raw = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def test_contract_file_exists() -> None:
    expected_path = Path(
        "backend/harness/sensitivity_execution/e3_contract.yaml"
    ).resolve()

    assert CONTRACT_PATH.resolve() == expected_path
    assert CONTRACT_PATH.is_file()


def test_canonical_contract_is_valid() -> None:
    validate_contract(load_contract())


def test_contract_preserves_e2_generator_versions() -> None:
    contract = load_contract()
    dependencies = contract["dependencies"]

    assert (
        dependencies["structural_generation"]["generator_version"]
        == "mcad-sensitivity-e2.1-v1"
    )
    assert (
        dependencies["controlled_families"]["generator_version"]
        == "mcad-sensitivity-e2.2-v1"
    )


def test_contract_requires_canonical_ckg_evaluator() -> None:
    contract = load_contract()

    assert (
        contract["dependencies"]["evaluator"]["canonical_entrypoint"]
        == "backend.ckg.ckg_updater.CKGGraph.evaluate_step"
    )
    assert (
        contract["dependencies"]["evaluator"]["invocation_mode"]
        == "local-python"
    )
    assert (
        contract["dependencies"]["evaluator"][
            "backend_api_is_source_of_truth"
        ]
        is False
    )


def test_contract_requires_explicit_workload() -> None:
    contract = load_contract()
    required_inputs = set(
        contract["input_contract"]["required_e3_inputs"]
    )

    assert required_inputs == {
        "execution_spec.json",
        "workload_spec.json",
    }


def test_contract_requires_fresh_instance_isolation() -> None:
    contract = load_contract()
    isolation = contract["execution_semantics"]["isolation"]

    assert isolation["fresh_runtime_state_per_instance"] is True
    assert isolation["fresh_session_per_instance"] is True
    assert isolation["cross_instance_state_reuse"] is False


def test_contract_protects_e2_inputs() -> None:
    contract = load_contract()
    immutability = contract["immutability"]

    assert immutability["e2_inputs_are_read_only"] is True
    assert immutability["source_objectives_are_read_only"] is True
    assert immutability["source_manifests_are_read_only"] is True
    assert immutability["outputs_written_outside_e2_tree"] is True


@pytest.mark.parametrize(
    "behavior",
    [
        "mutate_e2_campaign",
        "mutate_e2_instance",
        "regenerate_e2_instance",
        "bypass_ckg_evaluator",
        "reimplement_sat",
        "reimplement_real",
        "reimplement_ceval",
        "reimplement_phi",
        "use_backend_http_api_as_source_of_truth",
        "reuse_runtime_state_across_instances",
        "use_wall_clock_identifiers",
    ],
)
def test_contract_forbids_unsafe_behavior(
    behavior: str,
) -> None:
    contract = load_contract()

    assert behavior in contract["forbidden_behaviors"]


@pytest.mark.parametrize(
    "field",
    [
        "step_index",
        "step_id",
        "session_id",
        "objective_id",
        "sat",
        "real_node_ids",
        "calculable_constraints",
        "phi",
        "phi_weighted",
        "phi_leq_t",
        "delta_phi_t",
        "evaluator_latency_ms",
        "status",
    ],
)
def test_contract_requires_step_field(field: str) -> None:
    contract = load_contract()

    assert field in contract["required_step_fields"]


@pytest.mark.parametrize(
    "output_name",
    [
        "execution_manifest.json",
        "timeline.json",
        "metrics.json",
        "audit.json",
    ],
)
def test_contract_requires_instance_output(
    output_name: str,
) -> None:
    contract = load_contract()

    assert output_name in contract["required_instance_outputs"]


@pytest.mark.parametrize(
    "output_name",
    [
        "execution_spec.json",
        "execution_manifest.json",
        "instance_results.csv",
        "campaign_metrics.json",
    ],
)
def test_contract_requires_campaign_output(
    output_name: str,
) -> None:
    contract = load_contract()

    assert output_name in contract["required_campaign_outputs"]


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        (
            lambda contract: contract["phase"].update(
                {"mode": "http-evaluation"}
            ),
            "phase.mode",
        ),
        (
            lambda contract: contract["dependencies"][
                "evaluator"
            ].update(
                {"canonical_entrypoint": "custom.evaluate"}
            ),
            "evaluator canonical entrypoint",
        ),
        (
            lambda contract: contract["input_contract"].update(
                {"required_e3_inputs": ["execution_spec.json"]}
            ),
            "required E3 inputs",
        ),
        (
            lambda contract: contract["execution_semantics"][
                "isolation"
            ].update(
                {"fresh_session_per_instance": False}
            ),
            "fresh session per instance",
        ),
        (
            lambda contract: contract["immutability"].update(
                {"e2_inputs_are_read_only": False}
            ),
            "immutability.e2_inputs_are_read_only",
        ),
        (
            lambda contract: contract.update(
                {"forbidden_behaviors": []}
            ),
            "forbidden behaviors",
        ),
    ],
)
def test_validator_rejects_contract_regressions(
    mutation: Any,
    expected_message: str,
) -> None:
    contract = deepcopy(load_contract())
    mutation(contract)

    with pytest.raises(
        AssertionError,
        match=expected_message,
    ):
        validate_contract(contract)
