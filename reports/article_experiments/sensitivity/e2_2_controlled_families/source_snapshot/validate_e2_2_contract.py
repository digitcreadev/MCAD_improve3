#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "e2_2_contract.yaml"

EXPECTED_SCHEMA = "mcad-sensitivity-e2.2-contract-v1"
EXPECTED_GENERATOR = "mcad-sensitivity-e2.1-v1"

EXPECTED_FACTORS = {
    "constraint_count": "n_constraints",
    "virtual_node_count": "n_virtual_nodes",
}

FORBIDDEN_CALLS = {
    "sat",
    "real",
    "ceval",
    "phi",
}


def load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open(
        "r",
        encoding="utf-8",
    ) as stream:
        payload = yaml.safe_load(stream)

    if not isinstance(payload, dict):
        raise ValueError(
            "E2.2 contract root must be a mapping."
        )

    return payload


def validate_contract(
    payload: dict[str, Any],
) -> None:
    if payload.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError(
            "Unexpected E2.2 schema version: "
            f"{payload.get('schema_version')!r}"
        )

    phase = payload.get("phase") or {}

    if phase.get("id") != "E2.2":
        raise ValueError("phase.id must equal E2.2.")

    if phase.get("mode") != "structural-generation-only":
        raise ValueError(
            "E2.2 must remain structural-generation-only."
        )

    dependency = payload.get("dependency") or {}

    if dependency.get("phase") != "E2.1":
        raise ValueError(
            "E2.2 must depend on E2.1."
        )

    if (
        dependency.get("generator_version")
        != EXPECTED_GENERATOR
    ):
        raise ValueError(
            "E2.2 must bind to the validated E2.1 "
            "generator version."
        )

    if (
        dependency.get("canonical_entrypoint")
        != "generate_structural_instance"
    ):
        raise ValueError(
            "Unexpected E2.1 entrypoint."
        )

    factors = payload.get("supported_factors") or {}

    if set(factors) != set(EXPECTED_FACTORS):
        raise ValueError(
            "Supported E2.2 factors differ from the "
            "validated first-version scope."
        )

    for factor_name, config_field in (
        EXPECTED_FACTORS.items()
    ):
        factor = factors.get(factor_name) or {}

        if factor.get("config_field") != config_field:
            raise ValueError(
                f"{factor_name} must bind to "
                f"{config_field}."
            )

        if factor.get("positive_integer") is not True:
            raise ValueError(
                f"{factor_name} must require "
                "positive integers."
            )

    design = payload.get("design") or {}

    if design.get("method") != "OFAT":
        raise ValueError(
            "E2.2 first version must use OFAT."
        )

    if design.get("replication_unit") != "seed":
        raise ValueError(
            "E2.2 replication unit must be seed."
        )

    if design.get("deterministic_naming") is not True:
        raise ValueError(
            "E2.2 naming must be deterministic."
        )

    if design.get("wall_clock_in_identifiers") is not False:
        raise ValueError(
            "Wall-clock values must not enter "
            "experimental identifiers."
        )

    forbidden = set(payload.get("forbidden_calls") or [])

    if forbidden != FORBIDDEN_CALLS:
        raise ValueError(
            "Forbidden call set must be exactly "
            f"{sorted(FORBIDDEN_CALLS)}."
        )

    outputs = set(payload.get("required_outputs") or [])

    expected_outputs = {
        "campaign_spec.json",
        "campaign_manifest.json",
        "instances.csv",
        "instances/*/manifest.json",
        "instances/*/objectives.yaml",
    }

    if outputs != expected_outputs:
        raise ValueError(
            "Unexpected E2.2 required-output set."
        )


def called_function_names(
    source_path: Path,
) -> set[str]:
    tree = ast.parse(
        source_path.read_text(encoding="utf-8"),
        filename=str(source_path),
    )

    names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func

        if isinstance(function, ast.Name):
            names.add(function.id)
        elif isinstance(function, ast.Attribute):
            names.add(function.attr)

    return names


def validate_python_sources() -> None:
    ignored_names = {
        Path(__file__).name,
    }

    for source_path in sorted(HERE.glob("*.py")):
        if source_path.name in ignored_names:
            continue

        called = called_function_names(source_path)
        violations = sorted(called & FORBIDDEN_CALLS)

        if violations:
            raise ValueError(
                f"Forbidden evaluation calls in "
                f"{source_path}: {violations}"
            )


def main() -> None:
    payload = load_contract()
    validate_contract(payload)
    validate_python_sources()

    print("[OK] E2.2 contract is valid.")
    print(
        "[OK] dependency="
        "mcad-sensitivity-e2.1-v1"
    )
    print(
        "[OK] supported_factors="
        "constraint_count,virtual_node_count"
    )
    print("[OK] design=OFAT")
    print("[OK] replication_unit=seed")
    print(
        "[OK] sat/real/ceval/phi calls are forbidden"
    )


if __name__ == "__main__":
    main()
