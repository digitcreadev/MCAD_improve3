from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from backend.harness.sensitivity_generator.families.controlled_families import (
    ControlledFamilySpec,
    generate_controlled_family,
)


CONTRACT_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/planning/"
    "virtual_node_count_stage10_preregistration.json"
)

HISTORICAL_CAMPAIGN_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e2_2_controlled_families/campaigns/"
    "virtual_node_count"
)

STAGE10_CAMPAIGN_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/formal_campaigns/"
    "virtual_node_count_stage10_c4"
)

AUDIT_DIR_REL = Path(
    "reports/article_experiments/sensitivity/"
    "e3_controlled_execution/audits/"
    "virtual_node_count_stage10"
)

AUDIT_JSON_NAME = "structural_generation_and_prefix_audit.json"
AUDIT_MD_NAME = "structural_generation_and_prefix_audit.md"

PREFIX_REPLICATIONS = (0, 1)

ROW_SEMANTIC_FIELDS = (
    "factor",
    "factor_level",
    "replication_index",
    "seed",
    "relative_instance_dir",
    "requested_constraint_count",
    "realised_constraint_count",
    "requested_virtual_node_count",
    "realised_virtual_node_count",
    "requirement_set_count",
    "requirement_membership_link_count",
    "membership_density",
    "graph_node_count",
    "graph_edge_count",
    "generator_version",
)

MANIFEST_SEMANTIC_FIELDS = (
    "generator_version",
    "seed",
    "requested_constraint_count",
    "realised_constraint_count",
    "requested_virtual_node_count",
    "realised_virtual_node_count",
    "requirement_set_count",
    "requirement_membership_link_count",
    "membership_density",
    "graph_node_count",
    "graph_edge_count",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()



def normalize_csv_line_endings(path: Path) -> bool:
    """Store generated CSV evidence with repository-standard LF endings."""
    payload = path.read_bytes()

    normalized = (
        payload
        .replace(b"\r\n", b"\n")
        .replace(b"\r", b"\n")
    )

    if normalized == payload:
        return False

    path.write_bytes(normalized)
    return True

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        newline="",
        encoding="utf-8",
    ) as stream:
        return list(csv.DictReader(stream))


def row_key(row: dict[str, str]) -> tuple[int, int]:
    return (
        int(row["replication_index"]),
        int(row["factor_level"]),
    )


def projection(
    value: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        field: value.get(field)
        for field in fields
    }


def normalised_objectives_payload(
    path: Path,
    objective_id: str,
) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8")
    occurrence_count = text.count(objective_id)

    normalised = text.replace(
        objective_id,
        "__OBJECTIVE_ID__",
    )

    return normalised, occurrence_count


def validate_generation_contract(
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    campaign = contract.get("campaign_contract", {})
    gates = contract.get("authorization_gates", {})
    prefix = contract.get(
        "historical_functional_prefix",
        {},
    )

    require(
        contract.get("status") == "preregistered",
        "Preregistration status is not preregistered.",
    )
    require(
        campaign.get("campaign_id")
        == "virtual_node_count_stage10_c4",
        "Unexpected campaign identifier.",
    )
    require(
        campaign.get("factor") == "virtual_node_count",
        "Unexpected factor.",
    )
    require(
        campaign.get("levels") == [6, 12, 24],
        "Unexpected virtual-node levels.",
    )
    require(
        campaign.get("fixed_constraint_count") == 4,
        "Constraint count is not fixed at four.",
    )
    require(
        campaign.get("stage10_replication_count") == 10,
        "Stage-10 replication count is not ten.",
    )
    require(
        len(campaign.get("stage10_seeds", [])) == 10,
        "Expected exactly ten Stage-10 seeds.",
    )
    require(
        campaign.get("stage10_seeds", [])[:2] == [101, 202],
        "Historical seed prefix changed.",
    )
    require(
        gates.get(
            "structural_stage10_generation_authorized"
        )
        is True,
        "Structural Stage-10 generation is not authorized.",
    )
    require(
        gates.get(
            "historical_functional_rerun_authorized"
        )
        is False,
        "Historical functional rerun is authorized.",
    )
    require(
        gates.get("new_functional_execution_authorized")
        is False,
        "Functional execution is authorized too early.",
    )
    require(
        gates.get("formal_timing_execution_authorized")
        is False,
        "Timing execution is authorized too early.",
    )
    require(
        prefix.get("replications") == [0, 1],
        "Unexpected historical prefix.",
    )
    require(
        prefix.get("rerun_required") is False,
        "Historical prefix is incorrectly marked for rerun.",
    )

    return errors


def validate_stage10_structure(
    repo_root: Path,
) -> dict[str, Any]:
    contract_path = repo_root / CONTRACT_REL
    historical_dir = repo_root / HISTORICAL_CAMPAIGN_REL
    stage10_dir = repo_root / STAGE10_CAMPAIGN_REL

    errors: list[str] = []

    for path in (
        contract_path,
        historical_dir / "campaign_spec.json",
        historical_dir / "campaign_manifest.json",
        historical_dir / "instances.csv",
        stage10_dir / "campaign_spec.json",
        stage10_dir / "campaign_manifest.json",
        stage10_dir / "instances.csv",
    ):
        if not path.is_file():
            errors.append(f"Missing required file: {path}")

    if errors:
        return {
            "status": "fail",
            "errors": errors,
        }

    contract = load_json(contract_path)
    contract_errors = validate_generation_contract(
        contract
    )
    errors.extend(contract_errors)

    campaign_contract = contract["campaign_contract"]
    levels = campaign_contract["levels"]
    seeds = campaign_contract["stage10_seeds"]

    stage10_spec = load_json(
        stage10_dir / "campaign_spec.json"
    )
    stage10_manifest = load_json(
        stage10_dir / "campaign_manifest.json"
    )

    expected_matrix = {
        (replication_index, level, seed)
        for replication_index, seed in enumerate(seeds)
        for level in levels
    }

    stage10_rows = read_csv(
        stage10_dir / "instances.csv"
    )

    realised_matrix = {
        (
            int(row["replication_index"]),
            int(row["factor_level"]),
            int(row["seed"]),
        )
        for row in stage10_rows
    }

    if len(stage10_rows) != 30:
        errors.append(
            "Stage-10 instance count is not 30."
        )

    if realised_matrix != expected_matrix:
        errors.append(
            "Stage-10 condition matrix is incomplete "
            "or duplicated."
        )

    if stage10_spec.get("campaign_id") != (
        "virtual_node_count_stage10_c4"
    ):
        errors.append(
            "Generated campaign identifier is incorrect."
        )

    if stage10_spec.get("factor") != (
        "virtual_node_count"
    ):
        errors.append(
            "Generated campaign factor is incorrect."
        )

    if stage10_spec.get("levels") != levels:
        errors.append(
            "Generated campaign levels differ from "
            "the preregistration."
        )

    if stage10_spec.get("seeds") != seeds:
        errors.append(
            "Generated campaign seeds differ from "
            "the preregistration."
        )

    if stage10_spec.get(
        "baseline_constraint_count"
    ) != 4:
        errors.append(
            "Generated campaign changed the fixed "
            "constraint count."
        )

    if stage10_spec.get(
        "baseline_virtual_node_count"
    ) != 12:
        errors.append(
            "Generated campaign changed the declared "
            "virtual-node baseline."
        )

    if stage10_manifest.get(
        "expected_instance_count"
    ) != 30:
        errors.append(
            "Manifest expected-instance count is not 30."
        )

    if stage10_manifest.get(
        "realised_instance_count"
    ) != 30:
        errors.append(
            "Manifest realised-instance count is not 30."
        )

    if stage10_manifest.get(
        "replication_count"
    ) != 10:
        errors.append(
            "Manifest replication count is not 10."
        )

    for row in stage10_rows:
        level = int(row["factor_level"])

        if int(row["requested_constraint_count"]) != 4:
            errors.append(
                f"Constraint count changed for {row_key(row)}."
            )

        if int(row["realised_constraint_count"]) != 4:
            errors.append(
                f"Realised constraint count changed "
                f"for {row_key(row)}."
            )

        if int(
            row["requested_virtual_node_count"]
        ) != level:
            errors.append(
                f"Requested virtual-node level mismatch "
                f"for {row_key(row)}."
            )

        if int(
            row["realised_virtual_node_count"]
        ) != level:
            errors.append(
                f"Realised virtual-node level mismatch "
                f"for {row_key(row)}."
            )

        if float(row["membership_density"]) != 1.0:
            errors.append(
                f"Membership density changed for "
                f"{row_key(row)}."
            )

        instance_dir = (
            stage10_dir
            / row["relative_instance_dir"]
        )

        actual_files = {
            path.name
            for path in instance_dir.iterdir()
            if path.is_file()
        } if instance_dir.is_dir() else set()

        if actual_files != {
            "manifest.json",
            "objectives.yaml",
        }:
            errors.append(
                f"Unexpected instance file set for "
                f"{row_key(row)}: {sorted(actual_files)}"
            )

    historical_rows = read_csv(
        historical_dir / "instances.csv"
    )

    historical_prefix = {
        row_key(row): row
        for row in historical_rows
        if int(row["replication_index"])
        in PREFIX_REPLICATIONS
    }

    stage10_prefix = {
        row_key(row): row
        for row in stage10_rows
        if int(row["replication_index"])
        in PREFIX_REPLICATIONS
    }

    expected_prefix_keys = {
        (replication_index, level)
        for replication_index
        in PREFIX_REPLICATIONS
        for level in levels
    }

    if set(historical_prefix) != expected_prefix_keys:
        errors.append(
            "Historical prefix matrix is incomplete."
        )

    if set(stage10_prefix) != expected_prefix_keys:
        errors.append(
            "Stage-10 prefix matrix is incomplete."
        )

    prefix_results: list[dict[str, Any]] = []

    for key in sorted(expected_prefix_keys):
        old_row = historical_prefix.get(key)
        new_row = stage10_prefix.get(key)

        if old_row is None or new_row is None:
            continue

        row_projection_old = projection(
            old_row,
            ROW_SEMANTIC_FIELDS,
        )
        row_projection_new = projection(
            new_row,
            ROW_SEMANTIC_FIELDS,
        )

        row_semantic_match = (
            row_projection_old
            == row_projection_new
        )

        old_instance_dir = (
            historical_dir
            / old_row["relative_instance_dir"]
        )
        new_instance_dir = (
            stage10_dir
            / new_row["relative_instance_dir"]
        )

        old_manifest = load_json(
            old_instance_dir / "manifest.json"
        )
        new_manifest = load_json(
            new_instance_dir / "manifest.json"
        )

        manifest_projection_old = projection(
            old_manifest,
            MANIFEST_SEMANTIC_FIELDS,
        )
        manifest_projection_new = projection(
            new_manifest,
            MANIFEST_SEMANTIC_FIELDS,
        )

        manifest_semantic_match = (
            manifest_projection_old
            == manifest_projection_new
        )

        old_objectives, old_occurrences = (
            normalised_objectives_payload(
                old_instance_dir / "objectives.yaml",
                old_row["objective_id"],
            )
        )

        new_objectives, new_occurrences = (
            normalised_objectives_payload(
                new_instance_dir / "objectives.yaml",
                new_row["objective_id"],
            )
        )

        objectives_semantic_match = (
            old_objectives == new_objectives
            and old_occurrences > 0
            and new_occurrences > 0
        )

        prefix_match = (
            row_semantic_match
            and manifest_semantic_match
            and objectives_semantic_match
        )

        if not prefix_match:
            errors.append(
                "Historical prefix mismatch for "
                f"replication={key[0]}, level={key[1]}."
            )

        prefix_results.append(
            {
                "replication_index": key[0],
                "factor_level": key[1],
                "seed": int(old_row["seed"]),
                "historical_objective_id": (
                    old_row["objective_id"]
                ),
                "stage10_objective_id": (
                    new_row["objective_id"]
                ),
                "row_semantic_match": (
                    row_semantic_match
                ),
                "manifest_semantic_match": (
                    manifest_semantic_match
                ),
                "objectives_semantic_match": (
                    objectives_semantic_match
                ),
                "historical_objective_occurrences": (
                    old_occurrences
                ),
                "stage10_objective_occurrences": (
                    new_occurrences
                ),
                "historical_normalised_objectives_sha256": (
                    sha256_bytes(
                        old_objectives.encode("utf-8")
                    )
                ),
                "stage10_normalised_objectives_sha256": (
                    sha256_bytes(
                        new_objectives.encode("utf-8")
                    )
                ),
                "historical_configuration_digest": (
                    old_row["configuration_digest"]
                ),
                "stage10_configuration_digest": (
                    new_row["configuration_digest"]
                ),
                "historical_instance_digest": (
                    old_row["instance_digest"]
                ),
                "stage10_instance_digest": (
                    new_row["instance_digest"]
                ),
                "campaign_bound_digests_used_as_compatibility_gate": (
                    False
                ),
                "prefix_match": prefix_match,
            }
        )

    status = "pass" if not errors else "fail"

    return {
        "schema_version": (
            "mcad-virtual-node-count-stage10-"
            "structural-generation-audit-v1"
        ),
        "status": status,
        "errors": errors,
        "contract_path": CONTRACT_REL.as_posix(),
        "contract_sha256": sha256_file(
            contract_path
        ),
        "historical_campaign_path": (
            HISTORICAL_CAMPAIGN_REL.as_posix()
        ),
        "stage10_campaign_path": (
            STAGE10_CAMPAIGN_REL.as_posix()
        ),
        "stage10_campaign_spec_sha256": (
            sha256_file(
                stage10_dir / "campaign_spec.json"
            )
        ),
        "stage10_campaign_manifest_sha256": (
            sha256_file(
                stage10_dir / "campaign_manifest.json"
            )
        ),
        "stage10_instances_csv_sha256": (
            sha256_file(
                stage10_dir / "instances.csv"
            )
        ),
        "stage10_replication_count": 10,
        "stage10_level_count": 3,
        "stage10_instance_count": len(stage10_rows),
        "expected_stage10_instance_count": 30,
        "fixed_constraint_count": 4,
        "prefix_expected_instance_count": 6,
        "prefix_compared_instance_count": len(
            prefix_results
        ),
        "prefix_matching_instance_count": sum(
            int(item["prefix_match"])
            for item in prefix_results
        ),
        "prefix_results": prefix_results,
        "historical_functional_prefix_reused": True,
        "historical_functional_prefix_rerun_required": False,
        "functional_execution_performed": False,
        "timing_execution_performed": False,
        "new_functional_execution_authorized": False,
        "formal_timing_execution_authorized": False,
        "next_stage": (
            "prepare_and_audit_virtual_node_count_"
            "stage10_common_workloads"
            if status == "pass"
            else "repair_stage10_structure_or_prefix"
        ),
    }


def write_audit_reports(
    repo_root: Path,
    report: dict[str, Any],
) -> None:
    audit_dir = repo_root / AUDIT_DIR_REL
    audit_dir.mkdir(parents=True, exist_ok=True)

    json_path = audit_dir / AUDIT_JSON_NAME
    md_path = audit_dir / AUDIT_MD_NAME

    write_json(json_path, report)

    lines = [
        "# Virtual-node-count Stage-10 structural audit",
        "",
        f"- Status: `{report['status']}`",
        "- Structural replications: `10`",
        "- Virtual-node levels: `6`, `12`, `24`",
        "- Expected instances: `30`",
        f"- Realised instances: `{report.get('stage10_instance_count')}`",
        "- Fixed constraint count: `4`",
        "- Historical prefix instances: `6`",
        "- Historical functional rerun required: `false`",
        "- Functional execution performed: `false`",
        "- Timing execution performed: `false`",
        "",
        "## Prefix compatibility",
        "",
    ]

    for item in report.get("prefix_results", []):
        lines.append(
            "- "
            f"`rep_{item['replication_index']:03d}`, "
            f"level `{item['factor_level']}`: "
            f"`{'PASS' if item['prefix_match'] else 'FAIL'}`"
        )

    if report.get("errors"):
        lines.extend(
            [
                "",
                "## Errors",
                "",
                *[
                    f"- {error}"
                    for error in report["errors"]
                ],
            ]
        )

    lines.extend(
        [
            "",
            "## Next stage",
            "",
            f"`{report['next_stage']}`",
            "",
        ]
    )

    md_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_structure(
    repo_root: Path,
    reuse_existing: bool,
) -> dict[str, Any]:
    contract_path = repo_root / CONTRACT_REL
    output_dir = repo_root / STAGE10_CAMPAIGN_REL

    if not contract_path.is_file():
        raise SystemExit(
            f"Missing preregistration contract: {contract_path}"
        )

    contract = load_json(contract_path)
    errors = validate_generation_contract(contract)

    if errors:
        raise SystemExit(
            "Invalid generation contract: "
            + "; ".join(errors)
        )

    campaign = contract["campaign_contract"]

    if output_dir.exists() and any(output_dir.iterdir()):
        if not reuse_existing:
            raise SystemExit(
                "Stage-10 output directory already exists "
                "and is non-empty. Use --reuse-existing "
                "only for validation recovery."
            )

        print("structural_generation_reused_existing=true")

    else:
        spec = ControlledFamilySpec(
            campaign_id=campaign["campaign_id"],
            factor=campaign["factor"],
            levels=tuple(campaign["levels"]),
            seeds=tuple(campaign["stage10_seeds"]),
            baseline_constraint_count=(
                campaign["fixed_constraint_count"]
            ),
            baseline_virtual_node_count=(
                campaign["baseline_virtual_node_count"]
            ),
            output_dir=str(output_dir),
        )

        manifest = generate_controlled_family(spec)

        print("structural_generation_performed=true")
        print(
            "generated_instance_count="
            f"{manifest.realised_instance_count}"
        )

    csv_normalized = normalize_csv_line_endings(
        output_dir / "instances.csv"
    )

    print(
        "instances_csv_lf_normalized="
        f"{str(csv_normalized).lower()}"
    )

    report = validate_stage10_structure(repo_root)
    write_audit_reports(repo_root, report)

    if report["status"] != "pass":
        for error in report["errors"]:
            print(f"[ERROR] {error}")

        raise SystemExit(1)

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
    )

    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    report = generate_structure(
        repo_root,
        reuse_existing=args.reuse_existing,
    )

    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
        ).strip()
    except Exception:
        source_commit = "unknown"

    print("structural_generation_and_prefix_audit=PASS")
    print(f"source_commit={source_commit}")
    print(
        "stage10_instance_count="
        f"{report['stage10_instance_count']}"
    )
    print(
        "prefix_compared_instance_count="
        f"{report['prefix_compared_instance_count']}"
    )
    print(
        "prefix_matching_instance_count="
        f"{report['prefix_matching_instance_count']}"
    )
    print("historical_prefix_rerun_required=false")
    print("functional_execution_performed=false")
    print("timing_execution_performed=false")
    print(
        "next_stage="
        "prepare_and_audit_virtual_node_count_"
        "stage10_common_workloads"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
