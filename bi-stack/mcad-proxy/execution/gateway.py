from __future__ import annotations

from typing import Any

from .adapters.base import AdapterExecutionResult, DataWarehouseConfig
from .adapters.foodmart_direct_adapter import FoodMartDirectAdapter
from .adapters.adventureworks_direct_adapter import AdventureWorksDirectAdapter
from .adapters.steelwheels_direct_adapter import SteelWheelsDirectAdapter
from .adapters.xmla_mondrian_adapter import XmlaMondrianAdapter
from .registry import get_registry


class ExecutionGateway:
    """Selects a DW adapter from dw_id and executes through the stable contract.

    V9.4.2 supports a hybrid registry:
    - XMLA/eMondrian is the priority path for MDX demonstrations.
    - SQL Direct is the fallback/secondary path.
    - Fallback is attempted only after MCAD has already returned ALLOW, only
      when allow_fallback=true is explicitly supplied, and only when the selected
      registry entry declares fallback_dw_id. V9.4.2b avoids silent fallback so
      the UI choice remains auditable.
    """

    def __init__(self):
        self.registry = get_registry()
        self._adapter_cache: dict[str, Any] = {}

    def _adapter_for(self, cfg: DataWarehouseConfig):
        if cfg.id in self._adapter_cache:
            return self._adapter_cache[cfg.id]
        key = str(cfg.adapter or cfg.backend_type or "").lower()
        backend = str(cfg.backend_type or "").lower()
        if key in {"xmla_mondrian", "mondrian_xmla"} or backend == "xmla_mondrian":
            adapter = XmlaMondrianAdapter(cfg)
        elif key in {"foodmart_direct", "bi_direct"} or (cfg.id == "foodmart_sql_direct"):
            adapter = FoodMartDirectAdapter(cfg)
        elif key in {"adventureworks_direct", "sqlserver_direct"} or backend == "sqlserver_direct" or cfg.id == "adventureworks_sql_direct":
            adapter = AdventureWorksDirectAdapter(cfg)
        elif key in {"steelwheels_direct"} or "steelwheels_sql" in cfg.id:
            adapter = SteelWheelsDirectAdapter(cfg)
        else:
            adapter = XmlaMondrianAdapter(cfg) if cfg.query_language == "mdx" else AdventureWorksDirectAdapter(cfg)
        self._adapter_cache[cfg.id] = adapter
        return adapter

    def list_datawarehouses(self) -> list[dict[str, Any]]:
        return self.registry.public_items()

    def get_config(self, dw_id: str | None) -> DataWarehouseConfig:
        return self.registry.get(dw_id)

    def health(self) -> dict[str, Any]:
        items = []
        for cfg in self.registry.all():
            try:
                items.append(self._adapter_for(cfg).health())
            except Exception as exc:
                items.append({"ok": False, "dw_id": cfg.id, "label": cfg.label, "error": str(exc)})
        enabled = [x for x in items if x.get("ok")]
        return {
            "ok": True,
            "gateway": "mcad.execution_gateway.v2.hybrid",
            "strategy": "xmla_priority_sql_direct_fallback",
            "enabled_count": len(enabled),
            "items": items,
        }

    def health_one(self, dw_id: str) -> dict[str, Any]:
        cfg = self.registry.get(dw_id)
        return self._adapter_for(cfg).health()

    def metadata(self, dw_id: str) -> dict[str, Any]:
        cfg = self.registry.get(dw_id)
        return self._adapter_for(cfg).metadata()

    def _execute_without_fallback(
        self,
        cfg: DataWarehouseConfig,
        query_text: str,
        query_type: str,
        context: dict[str, Any],
    ) -> AdapterExecutionResult:
        adapter = self._adapter_for(cfg)
        if not cfg.enabled:
            return AdapterExecutionResult.unavailable(cfg, f"Data warehouse '{cfg.id}' is registered but disabled.")
        return adapter.execute(query_text, query_type=query_type, context=context or {})

    def execute(
        self,
        query_text: str,
        query_type: str = "mdx",
        *,
        dw_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AdapterExecutionResult:
        cfg = self.registry.get(dw_id)
        ctx = dict(context or {})
        ctx.setdefault("requested_dw_id", dw_id or cfg.id)
        ctx.setdefault("selected_dw_id", cfg.id)
        result = self._execute_without_fallback(cfg, query_text, query_type, ctx)

        # Try fallback only for real execution failures, never before MCAD ALLOW.
        allow_fallback = bool(ctx.get("allow_fallback", False))
        fallback_id = str(cfg.fallback_dw_id or "").strip()
        if result.error and allow_fallback and fallback_id and fallback_id != cfg.id:
            try:
                fallback_cfg = self.registry.get(fallback_id)
                fallback_ctx = dict(ctx)
                fallback_ctx.update({
                    "fallback_from_dw_id": cfg.id,
                    "fallback_from_adapter": result.adapter_id,
                    "fallback_original_error": result.error,
                })
                fallback_result = self._execute_without_fallback(fallback_cfg, query_text, query_type, fallback_ctx)
                if isinstance(fallback_result.raw_result_summary, dict):
                    fallback_result.raw_result_summary.setdefault("fallback_used", True)
                    fallback_result.raw_result_summary.setdefault("fallback_from_dw_id", cfg.id)
                    fallback_result.raw_result_summary.setdefault("fallback_from_adapter", result.adapter_id)
                    fallback_result.raw_result_summary.setdefault("fallback_original_error", result.error)
                    fallback_result.raw_result_summary.setdefault("requested_dw_id", dw_id or cfg.id)
                return fallback_result
            except Exception as exc:
                if isinstance(result.raw_result_summary, dict):
                    result.raw_result_summary.setdefault("fallback_attempted", True)
                    result.raw_result_summary.setdefault("fallback_dw_id", fallback_id)
                    result.raw_result_summary.setdefault("fallback_error", str(exc))
        return result


_GATEWAY: ExecutionGateway | None = None


def get_gateway() -> ExecutionGateway:
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = ExecutionGateway()
    return _GATEWAY
