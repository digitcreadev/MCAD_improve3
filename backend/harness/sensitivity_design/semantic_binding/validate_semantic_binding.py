#!/usr/bin/env python3
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any

import yaml

from backend.ckg.ckg_updater import CKGGraph


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "semantic_binding.yaml"
DOCUMENT_PATH = ROOT / "SEMANTIC_BINDING_E1_1.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)

    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")

    return value


def validate(config: dict[str, Any]) -> None:
    require(
        config.get("binding_version")
        == "mcad-sensitivity-semantic-binding-e1.1",
        "invalid semantic-binding version",
    )

    canonical = config.get("canonical_store") or {}

    require(
        canonical.get("objectives") == "CKGGraph.objectives",
        "objectives must bind to CKGGraph.objectives",
    )

    require(
        canonical.get("graph") == "CKGGraph.G",
        "graph must bind to CKGGraph.G",
    )

    semantics = config.get("requirement_set_semantics") or {}

    require(
        semantics.get("within_set") == "conjunction",
        "within-set semantics must be conjunction",
    )

    require(
        semantics.get("across_sets") == "disjunction",
        "across-set semantics must be disjunction",
    )

    density = config.get("density") or {}

    require(
        density.get("name") == "membership_density",
        "density must be membership_density",
    )

    tolerance = density.get("tolerance")

    require(
        isinstance(tolerance, (int, float))
        and 0.0 < float(tolerance) < 0.1,
        "invalid density tolerance",
    )

    forbidden = set(config.get("e2_1_forbidden_calls") or [])

    require(
        forbidden == {"sat", "real", "ceval", "phi"},
        "E2.1 forbidden-call set is incomplete",
    )

    for name in forbidden:
        require(
            callable(getattr(CKGGraph, name, None)),
            f"production method missing: {name}",
        )

    source = inspect.getsource(CKGGraph.bootstrap_objectives)

    require(
        'obj.get("constraints"' in source,
        "bootstrap does not expose nested constraints as expected",
    )
    require(
        'c.get("requirement_sets"' in source,
        "bootstrap does not preserve requirement sets",
    )
    require(
        'rel="HAS_CONSTRAINT"' in source,
        "HAS_CONSTRAINT projection not found",
    )
    require(
        'rel="REQUIRES_NV"' in source,
        "REQUIRES_NV projection not found",
    )

    ceval_source = inspect.getsource(CKGGraph.ceval)

    require(
        "if any(" in ceval_source,
        "Ceval alternative-set disjunction not found",
    )
    require(
        "_supports_requirement_set" in ceval_source,
        "Ceval requirement-set support call not found",
    )

    phi_fields = config.get("future_phi_fields") or []

    require(
        phi_fields == [
            "phi_unweighted",
            "phi_weighted",
        ],
        "future phi fields must be explicit",
    )


def main() -> int:
    if not DOCUMENT_PATH.is_file():
        print(
            f"[ERROR] Missing document: {DOCUMENT_PATH}",
            file=sys.stderr,
        )
        return 1

    try:
        validate(load_yaml(CONFIG_PATH))
    except (ValueError, KeyError, TypeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("[OK] Semantic binding E1.1 is valid.")
    print("[OK] canonical_objectives=CKGGraph.objectives")
    print("[OK] canonical_graph=CKGGraph.G")
    print("[OK] requirement_sets=nested metadata")
    print("[OK] density=membership_density")
    print("[OK] E2.1 evaluation calls are forbidden")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
