"""Non-executable Djedaini/IDEB provenance stub."""

from .base import AdapterIdentity, ControlledAdapter


class DjedainiAdapter(ControlledAdapter):
    identity = AdapterIdentity(
        method_id="djedaini_ideb",
        method_version="publication-2019",
        source_repository="https://doi.org/10.1016/j.is.2018.06.008",
        source_ref="doi:10.1016/j.is.2018.06.008",
        reproducibility_class="NATIVE_REPRODUCTION_BLOCKED_STRUCTURAL",
        native_role="post-execution contribution baseline",
        observation_stage="post_result",
        requires_current_query_result=True,
        requires_history=True,
        requires_auxiliary_query=False,
    )

    def status(self, input_digest: str) -> dict:
        return self._result(
            input_digest=input_digest,
            raw_outputs={},
            native_decision=None,
            status="unavailable_structural",
            error="Native reproduction is structurally blocked; no execution was attempted.",
            provenance={
                "execution": "not_available",
                "future_implementation_label": "paper-faithful reimplementation",
            },
        )
