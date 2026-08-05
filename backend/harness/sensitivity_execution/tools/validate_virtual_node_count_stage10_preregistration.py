from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_RELATIVE_PATH = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/planning/"
    "virtual_node_count_stage10_preregistration.json"
)

VALIDATION_JSON_RELATIVE_PATH = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/planning/"
    "virtual_node_count_stage10_"
    "preregistration_validation.json"
)

VALIDATION_MD_RELATIVE_PATH = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/planning/"
    "virtual_node_count_stage10_"
    "preregistration_validation.md"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(repo_root: Path) -> list[str]:
    errors: list[str] = []

    contract_path = repo_root / CONTRACT_RELATIVE_PATH

    if not contract_path.is_file():
        return [f"Missing contract: {contract_path}"]

    contract = load_json(contract_path)

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        contract.get("schema_version")
        == (
            "mcad-virtual-node-count-"
            "stage10-preregistration-v1"
        ),
        "Unexpected schema version.",
    )

    require(
        contract.get("status") == "preregistered",
        "Contract is not preregistered.",
    )

    campaign = contract.get("campaign_contract", {})

    require(
        campaign.get("factor") == "virtual_node_count",
        "Unexpected factor.",
    )
    require(
        campaign.get("levels") == [6, 12, 24],
        "Unexpected factor levels.",
    )
    require(
        campaign.get("fixed_constraint_count") == 4,
        "Constraint count is not fixed at four.",
    )
    require(
        campaign.get("stage10_replication_count") == 10,
        "Stage-10 replication count is not ten.",
    )

    seeds = campaign.get("stage10_seeds", [])

    require(len(seeds) == 10, "Expected ten Stage-10 seeds.")
    require(
        len(set(seeds)) == 10,
        "Stage-10 seeds are not unique.",
    )
    require(
        seeds[:2] == [101, 202],
        "Historical seed prefix changed.",
    )
    require(
        campaign.get("expected_stage10_instance_count") == 30,
        "Expected Stage-10 instance count is not 30.",
    )
    require(
        campaign.get("expected_stage10_functional_step_count")
        == 60,
        "Expected functional step count is not 60.",
    )

    prefix = contract.get(
        "historical_functional_prefix",
        {},
    )

    require(
        prefix.get("replications") == [0, 1],
        "Historical replication prefix changed.",
    )
    require(
        prefix.get("reuse_required") is True,
        "Historical prefix reuse is not required.",
    )
    require(
        prefix.get("rerun_required") is False,
        "Historical prefix is incorrectly marked for rerun.",
    )
    require(
        prefix.get("rerun_authorized") is False,
        "Historical prefix rerun is incorrectly authorized.",
    )

    functional = contract.get(
        "stage10_functional_plan",
        {},
    )

    require(
        functional.get("reused_replications") == [0, 1],
        "Unexpected reused replications.",
    )
    require(
        functional.get("new_replications")
        == list(range(2, 10)),
        "Unexpected new functional replications.",
    )
    require(
        functional.get("new_instance_count") == 24,
        "Expected 24 new instances.",
    )
    require(
        functional.get("new_functional_step_count") == 48,
        "Expected 48 new functional steps.",
    )
    require(
        functional.get("new_execution_authorized_by_preregistration")
        is False,
        "New execution must remain unauthorized.",
    )

    timing = contract.get("timing_protocol", {})

    require(
        timing.get("replications") == list(range(10)),
        "Unexpected timing replication set.",
    )
    require(
        timing.get("warmups_per_cell") == 10,
        "Unexpected warmup count.",
    )
    require(
        timing.get("measurements_per_cell") == 100,
        "Unexpected measurement count.",
    )
    require(
        timing.get("order_seed_base") == 20260728,
        "Unexpected order seed base.",
    )
    require(
        timing.get("reuse_successful") is True,
        "Successful-output reuse must be enabled.",
    )
    require(
        timing.get("expected_cell_count") == 60,
        "Expected 60 timing cells.",
    )
    require(
        timing.get("expected_warmup_observation_count") == 600,
        "Expected 600 warmup observations.",
    )
    require(
        timing.get("expected_measurement_observation_count") == 6000,
        "Expected 6000 measurement observations.",
    )
    require(
        timing.get("execution_authorized") is False,
        "Timing execution must remain unauthorized.",
    )

    precision = contract.get("precision_protocol", {})

    require(
        precision.get("stage_size") == 10,
        "Unexpected precision stage size.",
    )
    require(
        precision.get("measurements_per_cluster") == 100,
        "Unexpected cluster measurement count.",
    )
    require(
        precision.get("cluster_unit") == "structural_seed",
        "Bootstrap unit must be the structural seed.",
    )
    require(
        precision.get("bootstrap_repetitions") == 10000,
        "Unexpected bootstrap repetition count.",
    )
    require(
        precision.get("bootstrap_seed_base") == 20260728,
        "Unexpected bootstrap seed base.",
    )
    require(
        precision.get("confidence_level") == 0.95,
        "Unexpected confidence level.",
    )
    require(
        precision.get("median_relative_half_width_target")
        == 0.10,
        "Unexpected median target.",
    )
    require(
        precision.get("p95_relative_half_width_target")
        == 0.15,
        "Unexpected p95 target.",
    )
    require(
        precision.get("all_cells_must_pass") is True,
        "All precision cells must pass.",
    )

    extension = contract.get(
        "stage_extension_policy",
        {},
    )

    stage20_seeds = extension.get("stage20_seeds", [])

    require(
        len(stage20_seeds) == 20,
        "Expected 20 Stage-20 seeds.",
    )
    require(
        stage20_seeds[:10] == seeds,
        "Stage-20 does not preserve the Stage-10 prefix.",
    )
    require(
        extension.get("stage20_new_replications")
        == list(range(10, 20)),
        "Unexpected Stage-20 extension set.",
    )
    require(
        extension.get("stage20_generation_authorized") is False,
        "Stage-20 generation must remain unauthorized.",
    )
    require(
        extension.get("stage30_policy")
        == "not_authorized_requires_contract_amendment",
        "Stage-30 policy is not safely closed.",
    )

    gates = contract.get("authorization_gates", {})

    require(
        gates.get("preregistration_contract_complete") is True,
        "Contract-complete gate is false.",
    )
    require(
        gates.get("structural_stage10_generation_authorized")
        is True,
        "Stage-10 structural generation is not authorized.",
    )
    require(
        gates.get("historical_functional_rerun_authorized")
        is False,
        "Historical functional rerun is authorized.",
    )
    require(
        gates.get("new_functional_execution_authorized")
        is False,
        "New functional execution is authorized too early.",
    )
    require(
        gates.get("formal_timing_execution_authorized")
        is False,
        "Formal timing is authorized too early.",
    )
    require(
        gates.get("stage20_execution_authorized") is False,
        "Stage-20 execution is authorized too early.",
    )
    require(
        gates.get("latency_claim_authorized") is False,
        "Latency claim is authorized too early.",
    )

    source_evidence = contract.get("source_evidence", {})

    path_and_digest_fields = [
        (
            "preflight_path",
            "preflight_sha256",
        ),
        (
            "seed_schedule_path",
            "seed_schedule_sha256",
        ),
        (
            "historical_campaign_spec_path",
            "historical_campaign_spec_sha256",
        ),
        (
            "historical_campaign_manifest_path",
            "historical_campaign_manifest_sha256",
        ),
    ]

    for path_field, digest_field in path_and_digest_fields:
        relative = source_evidence.get(path_field)
        expected_digest = source_evidence.get(digest_field)

        if not relative:
            errors.append(f"Missing source path field: {path_field}")
            continue

        source_path = repo_root / relative

        if not source_path.is_file():
            errors.append(f"Missing source evidence: {source_path}")
            continue

        if sha256_file(source_path) != expected_digest:
            errors.append(
                f"Source digest mismatch: {source_path}"
            )

    for section_name, path_field, digest_field in (
        (
            "timing_protocol",
            "runner_path",
            "runner_sha256",
        ),
        (
            "precision_protocol",
            "analyzer_path",
            "analyzer_sha256",
        ),
    ):
        section = contract.get(section_name, {})
        relative = section.get(path_field)
        expected_digest = section.get(digest_field)

        if not relative:
            errors.append(
                f"Missing implementation path in {section_name}."
            )
            continue

        implementation_path = repo_root / relative

        if not implementation_path.is_file():
            errors.append(
                f"Missing implementation: {implementation_path}"
            )
            continue

        if sha256_file(implementation_path) != expected_digest:
            errors.append(
                f"Implementation digest mismatch: "
                f"{implementation_path}"
            )

    require(
        contract.get("next_stage")
        == (
            "generate_and_audit_virtual_node_count_"
            "stage10_structure"
        ),
        "Unexpected next stage.",
    )

    return errors


def write_validation_report(
    repo_root: Path,
    errors: list[str],
) -> None:
    contract_path = repo_root / CONTRACT_RELATIVE_PATH

    payload = {
        "schema_version": (
            "mcad-virtual-node-count-"
            "stage10-preregistration-validation-v1"
        ),
        "status": "pass" if not errors else "fail",
        "contract_path": CONTRACT_RELATIVE_PATH.as_posix(),
        "contract_sha256": (
            sha256_file(contract_path)
            if contract_path.is_file()
            else None
        ),
        "error_count": len(errors),
        "errors": errors,
        "experimental_execution_performed": False,
        "historical_prefix_rerun_required": False,
        "next_stage": (
            "generate_and_audit_virtual_node_count_"
            "stage10_structure"
            if not errors
            else "repair_preregistration_contract"
        ),
    }

    json_path = repo_root / VALIDATION_JSON_RELATIVE_PATH
    md_path = repo_root / VALIDATION_MD_RELATIVE_PATH

    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Virtual-node-count Stage-10 "
        "preregistration validation",
        "",
        f"- Status: `{payload['status']}`",
        f"- Error count: `{len(errors)}`",
        "- Experimental execution performed: `false`",
        "- Historical prefix rerun required: `false`",
        f"- Next stage: `{payload['next_stage']}`",
        "",
    ]

    if errors:
        lines.extend(
            [
                "## Errors",
                "",
                *[f"- {error}" for error in errors],
                "",
            ]
        )

    md_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
    )

    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    errors = validate_contract(repo_root)

    if args.write_report:
        write_validation_report(repo_root, errors)

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")

        print("preregistration_validation=FAIL")
        return 1

    print("preregistration_validation=PASS")
    print("historical_prefix_rerun_required=false")
    print("experimental_execution_performed=false")
    print(
        "next_stage="
        "generate_and_audit_virtual_node_count_"
        "stage10_structure"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
