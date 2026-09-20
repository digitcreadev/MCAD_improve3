"""Common immutable result construction with Phase 2B-3A guardrails."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AdapterIdentity:
    method_id: str
    method_version: str
    source_repository: str
    source_ref: str
    reproducibility_class: str
    native_role: str
    observation_stage: str
    requires_current_query_result: bool
    requires_history: bool
    requires_auxiliary_query: bool


class ControlledAdapter:
    """Build envelopes only; this base class has no external execution path."""

    identity: AdapterIdentity

    def _result(
        self,
        *,
        input_digest: str,
        raw_outputs: Mapping[str, Any],
        native_decision: str | int | float | bool | None,
        status: str,
        error: str | None,
        provenance: Mapping[str, Any],
        adapter_compute_ms: float = 0.0,
        backend_execution_ms: float = 0.0,
        auxiliary_execution_ms: float = 0.0,
        physical_query_count: int = 0,
        auxiliary_query_count: int = 0,
    ) -> dict[str, Any]:
        timings = (adapter_compute_ms, backend_execution_ms, auxiliary_execution_ms)
        counts = (physical_query_count, auxiliary_query_count)
        if not input_digest:
            raise ValueError("input_digest must identify the adapter input")
        if any(value < 0 for value in timings + counts):
            raise ValueError("timings and query counts cannot be negative")
        if auxiliary_query_count and not self.identity.requires_auxiliary_query:
            raise ValueError("auxiliary queries were not declared by this adapter")

        return {
            **asdict(self.identity),
            "input_digest": input_digest,
            "raw_outputs": dict(raw_outputs),
            "native_decision": native_decision,
            # Deliberately hard-coded: external values are not MCAD decisions.
            "normalized_binary_decision": None,
            "adapter_compute_ms": adapter_compute_ms,
            "backend_execution_ms": backend_execution_ms,
            "auxiliary_execution_ms": auxiliary_execution_ms,
            "physical_query_count": physical_query_count,
            "auxiliary_query_count": auxiliary_query_count,
            "status": status,
            "error": error,
            "provenance": dict(provenance),
        }
