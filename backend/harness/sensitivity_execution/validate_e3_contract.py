from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit(
        "[ERROR] PyYAML is required. Install it with: "
        "python -m pip install pyyaml"
    ) from exc


CONTRACT_PATH = Path(__file__).with_name("e3_contract.yaml")


SUPPORTED_FACTOR_GENERATOR_PROFILES = {
    "constraint_count": (
        "mcad-sensitivity-e2.2-v1",
        "mcad-sensitivity-e2.1-v1",
    ),
    "virtual_node_count": (
        "mcad-sensitivity-e2.2-v1",
        "mcad-sensitivity-e2.1-v1",
    ),
    "membership_density": (
        "mcad-sensitivity-e2.2-membership-density-v1",
        "mcad-sensitivity-e2.1-membership-density-v1",
    ),
    "objective_count": (
        "mcad-sensitivity-e2.2-objective-count-v1",
        "mcad-sensitivity-e2.1-objective-count-v1",
    ),
}


def fail(message: str) -> None:
    raise AssertionError(message)


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be a mapping")
    return value


def require_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        fail(f"{label} must be a list")
    return value


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def require_true(value: Any, label: str) -> None:
    if value is not True:
        fail(f"{label} must be true")


def require_items(
    actual: Sequence[Any],
    required: set[str],
    label: str,
) -> None:
    actual_set = {str(item) for item in actual}
    missing = sorted(required - actual_set)
    if missing:
        fail(f"{label} is missing: {missing}")


def validate_contract(contract: Mapping[str, Any]) -> None:
    require_equal(
        contract.get("schema_version"),
        "mcad-sensitivity-e3-contract-v1",
        "schema_version",
    )

    phase = require_mapping(contract.get("phase"), "phase")
    require_equal(phase.get("id"), "E3", "phase.id")
    require_equal(
        phase.get("name"),
        "controlled-execution",
        "phase.name",
    )
    require_equal(
        phase.get("mode"),
        "controlled-local-evaluation",
        "phase.mode",
    )

    dependencies = require_mapping(
        contract.get("dependencies"),
        "dependencies",
    )

    e2_1 = require_mapping(
        dependencies.get("structural_generation"),
        "dependencies.structural_generation",
    )
    require_equal(
        e2_1.get("generator_version"),
        "mcad-sensitivity-e2.1-v1",
        "E2.1 generator version",
    )

    e2_2 = require_mapping(
        dependencies.get("controlled_families"),
        "dependencies.controlled_families",
    )
    require_equal(
        e2_2.get("generator_version"),
        "mcad-sensitivity-e2.2-v1",
        "E2.2 generator version",
    )

    profiles = require_mapping(
        contract.get(
            "factor_generator_profiles"
        ),
        "factor_generator_profiles",
    )

    require_equal(
        set(profiles),
        set(
            SUPPORTED_FACTOR_GENERATOR_PROFILES
        ),
        "factor_generator_profiles keys",
    )

    for factor, expected_versions in (
        SUPPORTED_FACTOR_GENERATOR_PROFILES.items()
    ):
        profile = require_mapping(
            profiles.get(factor),
            (
                "factor_generator_profiles."
                f"{factor}"
            ),
        )

        require_equal(
            profile.get(
                "campaign_generator_version"
            ),
            expected_versions[0],
            (
                f"{factor} campaign "
                "generator version"
            ),
        )

        require_equal(
            profile.get(
                "structural_generator_version"
            ),
            expected_versions[1],
            (
                f"{factor} structural "
                "generator version"
            ),
        )

    evaluator = require_mapping(
        dependencies.get("evaluator"),
        "dependencies.evaluator",
    )
    require_equal(
        evaluator.get("canonical_entrypoint"),
        "backend.ckg.ckg_updater.CKGGraph.evaluate_step",
        "evaluator canonical entrypoint",
    )
    require_equal(
        evaluator.get("invocation_mode"),
        "local-python",
        "evaluator invocation mode",
    )
    require_equal(
        evaluator.get("backend_api_is_source_of_truth"),
        False,
        "backend API source-of-truth flag",
    )

    input_contract = require_mapping(
        contract.get("input_contract"),
        "input_contract",
    )
    e3_inputs = require_sequence(
        input_contract.get("required_e3_inputs"),
        "input_contract.required_e3_inputs",
    )
    require_items(
        e3_inputs,
        {"execution_spec.json", "workload_spec.json"},
        "required E3 inputs",
    )

    semantics = require_mapping(
        contract.get("execution_semantics"),
        "execution_semantics",
    )
    isolation = require_mapping(
        semantics.get("isolation"),
        "execution_semantics.isolation",
    )
    require_true(
        isolation.get("fresh_runtime_state_per_instance"),
        "fresh runtime state per instance",
    )
    require_true(
        isolation.get("fresh_session_per_instance"),
        "fresh session per instance",
    )
    require_equal(
        isolation.get("cross_instance_state_reuse"),
        False,
        "cross-instance state reuse",
    )

    evaluation = require_mapping(
        semantics.get("evaluation"),
        "execution_semantics.evaluation",
    )
    require_true(
        evaluation.get("production_evaluator_semantics_preserved"),
        "production evaluator semantics preservation",
    )
    require_true(
        evaluation.get("evaluator_reimplementation_forbidden"),
        "evaluator reimplementation prohibition",
    )

    step_fields = require_sequence(
        contract.get("required_step_fields"),
        "required_step_fields",
    )
    require_items(
        step_fields,
        {
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
        },
        "required step fields",
    )

    instance_outputs = require_sequence(
        contract.get("required_instance_outputs"),
        "required_instance_outputs",
    )
    require_items(
        instance_outputs,
        {
            "execution_manifest.json",
            "timeline.json",
            "metrics.json",
            "audit.json",
        },
        "required instance outputs",
    )

    campaign_outputs = require_sequence(
        contract.get("required_campaign_outputs"),
        "required_campaign_outputs",
    )
    require_items(
        campaign_outputs,
        {
            "execution_spec.json",
            "execution_manifest.json",
            "instance_results.csv",
            "campaign_metrics.json",
        },
        "required campaign outputs",
    )

    determinism = require_mapping(
        contract.get("determinism"),
        "determinism",
    )
    require_true(
        determinism.get("deterministic_execution_identifiers"),
        "deterministic execution identifiers",
    )
    require_true(
        determinism.get("deterministic_manifest_digest"),
        "deterministic manifest digest",
    )
    require_equal(
        determinism.get("wall_clock_in_identifiers"),
        False,
        "wall-clock identifier flag",
    )

    immutability = require_mapping(
        contract.get("immutability"),
        "immutability",
    )
    for key in (
        "e2_inputs_are_read_only",
        "source_objectives_are_read_only",
        "source_manifests_are_read_only",
        "outputs_written_outside_e2_tree",
    ):
        require_true(immutability.get(key), f"immutability.{key}")

    forbidden = require_sequence(
        contract.get("forbidden_behaviors"),
        "forbidden_behaviors",
    )
    require_items(
        forbidden,
        {
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
        },
        "forbidden behaviors",
    )

    validations = require_sequence(
        contract.get("required_validations"),
        "required_validations",
    )
    require_items(
        validations,
        {
            "required_inputs_exist",
            "workload_objective_binding_valid",
            "workload_step_identifiers_unique",
            "one_execution_per_instance",
            "fresh_session_per_instance",
            "required_step_fields_present",
            "e2_inputs_unchanged",
            "deterministic_execution_digest",
            "cumulative_phi_in_range",
            "cumulative_phi_monotone",
            "evaluator_entrypoint_preserved",
            "forbidden_behaviors_absent",
        },
        "required validations",
    )


def main() -> int:
    if not CONTRACT_PATH.is_file():
        print(f"[ERROR] Missing contract: {CONTRACT_PATH}")
        return 1

    try:
        raw = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
        contract = require_mapping(raw, "contract")
        validate_contract(contract)
    except (AssertionError, yaml.YAMLError) as exc:
        print(f"[ERROR] E3 contract is invalid: {exc}")
        return 1

    print("[OK] E3 contract is valid.")
    print("[OK] dependency=mcad-sensitivity-e2.1-v1")
    print("[OK] dependency=mcad-sensitivity-e2.2-v1")
    print(
        "[OK] evaluator="
        "backend.ckg.ckg_updater.CKGGraph.evaluate_step"
    )
    print("[OK] workload_spec.json is required.")
    print("[OK] E2 inputs are immutable.")
    print("[OK] evaluator reimplementation is forbidden.")
    print("[OK] deterministic controlled execution is required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
