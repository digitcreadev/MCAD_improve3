"""Delian post-result native-output packaging skeleton."""

from typing import Any, Mapping

from .base import AdapterIdentity, ControlledAdapter


class DelianPostAdapter(ControlledAdapter):
    identity = AdapterIdentity(
        method_id="delian_post",
        method_version="publication-2024",
        source_repository="https://doi.org/10.1016/j.is.2024.102381",
        source_ref="doi:10.1016/j.is.2024.102381",
        reproducibility_class="NATIVE_CODE_SMOKE_PASS_UNDER_RECONSTRUCTED_PUBLICATION_ENV",
        native_role="post-result extensional interestingness",
        observation_stage="post_result",
        requires_current_query_result=True,
        requires_history=True,
        requires_auxiliary_query=False,
    )

    def record_native_outputs(self, input_digest: str, raw_outputs: Mapping[str, Any]) -> dict[str, Any]:
        """Record extensional values without executing Delian or a backend."""
        return self._result(
            input_digest=input_digest,
            raw_outputs=raw_outputs,
            native_decision=None,
            status="native_outputs_recorded",
            error=None,
            provenance={"capture_mode": "caller_supplied_native_outputs"},
        )
