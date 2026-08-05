from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.sensitivity_execution.tools.objective_count_noise_operators_v2 import (
    support_query_from_virtual_node,
)
from backend.harness.sensitivity_generator.objective_count_generator_v2 import (
    GENERATOR_VERSION,
    SESSION_SUPPORT_POLICY,
    ObjectiveCountV2Config,
    generate_objective_count_instance_v2,
)


def _config(output_dir: Path, *, objective_count: int = 2, seed: int = 101):
    return ObjectiveCountV2Config(
        instance_id="objective_count_v2_test",
        objective_count=objective_count,
        selected_objective_index=0,
        constraints_per_objective=8,
        virtual_nodes_per_objective=32,
        seed=seed,
        output_dir=str(output_dir),
    )


def test_generator_realises_exact_micro_design(tmp_path: Path) -> None:
    manifest = generate_objective_count_instance_v2(_config(tmp_path / "instance"))
    assert manifest.generator_version == GENERATOR_VERSION
    assert manifest.objective_count == 2
    assert manifest.total_constraint_count == 16
    assert manifest.useful_virtual_node_count == 48
    assert manifest.irrelevant_virtual_node_count == 16
    assert manifest.total_virtual_node_count == 64
    assert manifest.requirement_set_count == 32
    assert manifest.requirement_membership_link_count == 64
    assert manifest.maximum_membership_link_count == 128
    assert manifest.realised_density == 0.5
    assert manifest.session_support_policy == SESSION_SUPPORT_POLICY

    stored = json.loads((tmp_path / "instance" / "manifest.json").read_text())
    expected = asdict(manifest)
    expected["objective_ids"] = list(expected["objective_ids"])
    assert stored == expected

    document = yaml.safe_load((tmp_path / "instance" / "objectives.yaml").read_text())
    assert len(document["objectives"]) == 2
    for objective in document["objectives"]:
        assert objective["session_support_policy"] == SESSION_SUPPORT_POLICY
        assert len(objective["constraints"]) == 8
        for constraint in objective["constraints"]:
            assert len(constraint["virtual_nodes"]) == 4
            nvs = constraint["virtual_nodes"]
            assert constraint["requirement_sets"] == [
                [nvs[0]["id"], nvs[1]["id"]],
                [nvs[1]["id"], nvs[2]["id"]],
            ]
            assert len({tuple(sorted(nv["slicers"].items())) for nv in nvs}) == 4


def test_support_queries_resolve_exactly_one_nv(tmp_path: Path) -> None:
    output = tmp_path / "single"
    manifest = generate_objective_count_instance_v2(
        _config(output, objective_count=1)
    )
    document = yaml.safe_load((output / "objectives.yaml").read_text())
    objective = document["objectives"][0]
    ckg = CKGGraph(output_dir=str(tmp_path / "runtime"))
    ckg.G.clear(); ckg.objectives.clear(); ckg.history.clear()
    ckg.session_coverage.clear(); ckg.session_weighted_coverage.clear()
    ckg.session_resource_coverage.clear()
    ckg.bootstrap_objectives(str(output / "objectives.yaml"))

    signatures = set()
    for constraint_index, constraint in enumerate(objective["constraints"]):
        assert len(ckg._constraint_support(manifest.objective_id, constraint["id"])) == 3
        for local_index in range(3):
            ordinal = constraint_index * 3 + local_index
            query = support_query_from_virtual_node(
                constraint["virtual_nodes"][local_index],
                support_ordinal=ordinal,
                constraint_index=constraint_index,
                local_virtual_node_index=local_index,
            )
            qp_node = ckg.add_qp_node(
                f"probe-{ordinal}", ordinal,
                {"objective_id": manifest.objective_id, "query_spec": query},
            )
            assert ckg.real(manifest.objective_id, qp_node) == {
                constraint["virtual_nodes"][local_index]["id"]
            }
            signatures.add(json.dumps(query, sort_keys=True))
    assert len(signatures) == 24


def test_selected_shape_is_level_invariant(tmp_path: Path) -> None:
    one = generate_objective_count_instance_v2(_config(tmp_path / "one", objective_count=1, seed=202))
    five = generate_objective_count_instance_v2(_config(tmp_path / "five", objective_count=5, seed=202))
    assert one.selected_objective_shape_digest == five.selected_objective_shape_digest
