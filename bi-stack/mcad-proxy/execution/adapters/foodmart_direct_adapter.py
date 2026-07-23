from __future__ import annotations

from typing import Any
import time

from .base import AdapterExecutionResult, BaseAdapter, digest_payload
from direct_executor import execute_direct_query


class FoodMartDirectAdapter(BaseAdapter):
    """Adapter preserving the current BI-direct FoodMart execution path."""

    def health(self) -> dict[str, Any]:
        h = super().health()
        h.update({
            "status": "available" if self.config.enabled else "disabled",
            "capabilities": ["execute_mdx_subset", "materialized_public_result", "nvac_probe", "sql_direct_fallback"],
            "real_execution": True,
            "adapter_family": "sql_direct",
            "logical_query_language": self.config.logical_input_language or "mdx",
            "physical_query_language": self.config.physical_query_language or "sql_direct",
            "fallback": self.config.fallback,
        })
        return h

    def metadata(self) -> dict[str, Any]:
        m = super().metadata()
        m.update({
            "ok": bool(self.config.enabled),
            "catalog": self.config.catalog or "FoodMart",
            "cube": self.config.cube or "Sales",
            "measures": ["Store Sales", "Profit", "Unit Sales", "Warehouse Sales", "Store Cost"],
            "dimensions": ["Time", "Store", "Product", "Measures"],
            "capabilities": ["mdx_subset", "direct_result_summary", "probe_subspace", "fallback_sql_direct"],
            "execution_contract": "MCAD_ALLOW_THEN_SQL_DIRECT",
        })
        return m

    def execute(self, query_text: str, query_type: str = "mdx", context: dict[str, Any] | None = None) -> AdapterExecutionResult:
        if not self.config.enabled:
            return AdapterExecutionResult.unavailable(self.config, "Data warehouse adapter is disabled.")
        started = time.time()
        res = execute_direct_query(query_text, query_type=query_type)
        elapsed_ms = int((time.time() - started) * 1000) if getattr(res, "elapsed_ms", None) is None else int(res.elapsed_ms)
        summary = res.raw_result_summary if isinstance(res.raw_result_summary, dict) else {"raw_result_summary": res.raw_result_summary}
        response_bytes = getattr(res, "response_bytes", None)
        response_digest = getattr(res, "response_digest", None)
        if response_bytes is None or not response_digest:
            response_bytes, response_digest = digest_payload(summary)
        summary.update({
            "ok": bool(int(getattr(res, "status_code", 200)) < 400),
            "physical_execution": True,
            "execution_mode": "real",
            "adapter_family": "sql_direct",
            "adapter_id": self.adapter_id,
            "dw_id": self.config.id,
            "dataset": self.config.dataset or "FoodMart",
            "logical_query_language": self.config.logical_input_language or "mdx",
            "physical_query_language": self.config.physical_query_language or "sql_direct",
            "catalog": self.config.catalog or "FoodMart",
            "cube": self.config.cube or "Sales",
            "status_code": int(getattr(res, "status_code", 200)),
            "elapsed_ms": elapsed_ms,
            "response_bytes": int(response_bytes),
            "response_digest": str(response_digest),
            "result_digest": str(response_digest),
            "execution_path": "sql_direct",
        })
        return AdapterExecutionResult(
            status_code=int(getattr(res, "status_code", 200)),
            elapsed_ms=elapsed_ms,
            response_bytes=int(response_bytes),
            response_digest=str(response_digest),
            raw_result_summary=summary,
            adapter_id=self.adapter_id,
            dw_id=self.config.id,
            query_language=query_type or self.config.query_language,
            backend_type=self.config.backend_type,
        )

    def probe_subspace(self, query_spec: dict[str, Any]) -> dict[str, Any]:
        # V9.4.0 keeps the dedicated /bi/nvac-probe endpoint behavior. This
        # method is exposed for the V9.4.x gateway contract and can be expanded
        # when probes are moved entirely into adapters.
        return {"ok": True, "dw_id": self.config.id, "adapter": self.adapter_id, "method": "delegated_to_bi_nvac_probe"}
