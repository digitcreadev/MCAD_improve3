import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
A9_SHA256 = "40c4ede02a919765f8baf15d71978df183001c882a46019ee7204456aabac9df"


def _registry():
    return json.loads((ROOT / "registry.yaml").read_text(encoding="utf-8"))


def test_a9_freeze_digest_is_exact():
    freeze = json.loads((ROOT / "provenance/a9_freeze_reference.json").read_text(encoding="utf-8"))
    assert freeze == {
        "evidence_bundle": "final_a9_evidence_bundle",
        "sha256": A9_SHA256,
        "phase": "2B-2",
        "state": "closed",
        "use": "scientific authority for Phase 2B-3A adapter classifications",
    }


def test_frozen_refs_and_reproducibility_classes_are_exact():
    entries = {item["method_id"]: item for item in _registry()["methods"]}
    expected = {
        "delian_pre": ("doi:10.1016/j.is.2024.102381", "NATIVE_CODE_SMOKE_PASS_UNDER_RECONSTRUCTED_PUBLICATION_ENV"),
        "delian_post": ("doi:10.1016/j.is.2024.102381", "NATIVE_CODE_SMOKE_PASS_UNDER_RECONSTRUCTED_PUBLICATION_ENV"),
        "djedaini_ideb": ("doi:10.1016/j.is.2018.06.008", "NATIVE_REPRODUCTION_BLOCKED_STRUCTURAL"),
        "assess_iam": ("release:1.0.0", "RELEASE_1_0_0_TESTCLASSES_PASS_WITH_EXACT_SOURCE_DEPENDENCY_RECONSTRUCTION"),
    }
    assert {key: (value["source_ref"], value["reproducibility_class"]) for key, value in entries.items()} == expected


def test_blocked_stubs_cannot_claim_runtime_pass():
    from adapters import AssessAdapter, DjedainiAdapter

    djedaini = DjedainiAdapter().status("sha256:d")
    assess = AssessAdapter().status("sha256:a")
    assert djedaini["status"] == "unavailable_structural"
    assert djedaini["provenance"]["execution"] == "not_available"
    assert assess["status"] == "build_smoke_only_not_runtime_integrated"
    assert assess["provenance"]["runtime_integration"] == "not_tested"
    assert assess["provenance"]["mcad_safe_to_prune_oracle"] is False
