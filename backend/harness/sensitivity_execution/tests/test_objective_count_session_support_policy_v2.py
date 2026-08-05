from __future__ import annotations

from pathlib import Path

import yaml

from backend.ckg.ckg_updater import CKGGraph
from backend.mcad.models import Objective
import backend.mcad.objectives as objective_registry


def _document(policy_marker=True):
    objective = {
        "id": "O_POLICY",
        "name": "Policy",
        "description": "Policy",
        "kpis": ["K1"],
        "constraints": [
            {
                "id": "C1",
                "kpi_id": "K1",
                "description": "C1",
                "weight": 1.0,
                "virtual_nodes": [
                    {"id": f"NV{i}", "fact": "F", "grain": ["G"], "measure": "M", "aggregator": "SUM", "unit": "U"}
                    for i in range(1, 5)
                ],
                "requirement_sets": [["NV1", "NV2"], ["NV2", "NV3"]],
            }
        ],
    }
    if policy_marker is True:
        objective["session_support_policy"] = "union_requirement_sets"
    elif isinstance(policy_marker, str):
        objective["session_support_policy"] = policy_marker
    return {"objectives": [objective]}


def _ckg(tmp_path: Path, marker=True):
    path = tmp_path / f"obj-{marker}.yaml"
    path.write_text(yaml.safe_dump(_document(marker), sort_keys=False))
    ckg = CKGGraph(output_dir=str(tmp_path / f"runtime-{marker}"))
    ckg.G.clear(); ckg.objectives.clear(); ckg.history.clear()
    ckg.session_coverage.clear(); ckg.session_weighted_coverage.clear(); ckg.session_resource_coverage.clear()
    ckg.bootstrap_objectives(str(path))
    return ckg


def test_union_policy_and_historical_fallback(tmp_path: Path) -> None:
    union = _ckg(tmp_path, True)
    assert union.objectives["O_POLICY"]["session_support_policy"] == "union_requirement_sets"
    assert union._constraint_support("O_POLICY", "C1") == ["NV1", "NV2", "NV3"]

    missing = _ckg(tmp_path, False)
    assert missing._constraint_support("O_POLICY", "C1") == ["NV1", "NV2"]

    unknown = _ckg(tmp_path, "unknown_policy")
    assert unknown._constraint_support("O_POLICY", "C1") == ["NV1", "NV2"]


def test_ckg_clone_preserves_policy(tmp_path: Path) -> None:
    ckg = _ckg(tmp_path, True)
    ckg.clone_objective("O_POLICY", "O_POLICY_CLONE", suffix="CLONE")
    assert ckg.objectives["O_POLICY_CLONE"]["session_support_policy"] == "union_requirement_sets"


def test_model_and_registry_clone_preserve_policy(monkeypatch) -> None:
    base = Objective(
        id="O_POLICY",
        name="Policy",
        description="Policy",
        session_support_policy="union_requirement_sets",
        kpis=[],
        constraints=[],
    )
    dumped = base.model_dump() if hasattr(base, "model_dump") else base.dict()
    assert dumped["session_support_policy"] == "union_requirement_sets"

    monkeypatch.setattr(objective_registry, "_OBJECTIVES", {base.id: base})
    monkeypatch.setattr(objective_registry, "_OBJECTIVES_YAML_PATH", "memory")
    cloned = objective_registry.clone_objective(base.id)
    assert cloned.session_support_policy == "union_requirement_sets"
