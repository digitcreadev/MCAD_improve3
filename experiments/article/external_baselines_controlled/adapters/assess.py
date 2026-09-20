"""ASSESS 1.0.0 build-smoke provenance stub; not a runtime adapter."""

from .base import AdapterIdentity, ControlledAdapter


class AssessAdapter(ControlledAdapter):
    identity = AdapterIdentity(
        method_id="assess_iam",
        method_version="1.0.0",
        source_repository="https://github.com/big-unibo/assess",
        source_ref="f77bf3ae3727aa6e5605fc1fc57a454a0e6e6def",
        publication_reference="doi:10.5441/002/edbt.2021.12; release:1.0.0",
        reproducibility_class="RELEASE_1_0_0_TESTCLASSES_PASS_WITH_EXACT_SOURCE_DEPENDENCY_RECONSTRUCTION",
        native_role="post-execution functional/cost comparator",
        observation_stage="post_result",
        requires_current_query_result=True,
        requires_history=False,
        requires_auxiliary_query=False,
    )

    def status(self, input_digest: str) -> dict:
        return self._result(
            input_digest=input_digest,
            raw_outputs={},
            native_decision=None,
            status="build_smoke_only_not_runtime_integrated",
            error="Runtime integration was not tested and is not available in Phase 2B-3A.",
            provenance={
                "verified_scope": "release_1.0.0_testclasses_build_and_test_compilation",
                "runtime_integration": "not_tested",
                "mcad_safe_to_prune_oracle": False,
            },
        )
