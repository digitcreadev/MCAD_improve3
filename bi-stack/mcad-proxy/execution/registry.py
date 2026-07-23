from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal local checks
    yaml = None

from .adapters.base import DataWarehouseConfig


_DEFAULT_REGISTRY = {
    "datawarehouses": [
        {
            "id": "foodmart",
            "label": "FoodMart — XMLA/eMondrian",
            "dataset": "FoodMart",
            "backend_type": "xmla_mondrian",
            "adapter": "xmla_mondrian",
            "query_language": "mdx",
            "logical_input_language": "mdx",
            "physical_query_language": "xmla_mdx",
            "catalog": "FoodMart",
            "cube": "Sales",
            "enabled": True,
            "default": True,
            "experimental": False,
            "execution_priority": 1,
            "fallback_dw_id": "foodmart_sql_direct",
            "xmla_url": "http://emondrian:8080/emondrian/xmla",
            "notes": "Priority MDX/OLAP path for demonstrations; falls back to FoodMart SQL Direct if XMLA execution fails.",
        },
        {
            "id": "foodmart_sql_direct",
            "label": "FoodMart — SQL Direct fallback",
            "dataset": "FoodMart",
            "backend_type": "foodmart_direct",
            "adapter": "foodmart_direct",
            "query_language": "mdx",
            "logical_input_language": "mdx",
            "physical_query_language": "sql_direct",
            "catalog": "FoodMart",
            "cube": "Sales",
            "enabled": True,
            "default": False,
            "fallback": True,
            "experimental": False,
            "execution_priority": 2,
            "notes": "Stable BI-direct FoodMart execution path preserved as fallback/secondary adapter.",
        },
        {
            "id": "adventureworks_xmla",
            "label": "AdventureWorksDW — XMLA/eMondrian experimental",
            "dataset": "AdventureWorksDW",
            "backend_type": "xmla_mondrian",
            "adapter": "xmla_mondrian",
            "query_language": "mdx",
            "logical_input_language": "mdx",
            "physical_query_language": "xmla_mdx",
            "catalog": "AdventureWorksDW",
            "cube": "Adventure Works DW",
            "enabled": True,
            "default": False,
            "experimental": True,
            "execution_priority": 1,
            "fallback": False,
            "fallback_dw_id": None,
            "xmla_url": "http://emondrian:8080/emondrian/xmla",
            "datasource_info": "AdventureWorksDW",
            "real_execution": "conditional_on_emondrian_catalog",
            "notes": "Enabled after direct proof of MDX -> XMLA -> eMondrian -> SQL Server AdventureWorksDW2022 execution.",
        },
        {
            "id": "adventureworks_sql_direct",
            "label": "AdventureWorksDW — SQL Direct",
            "dataset": "AdventureWorksDW",
            "backend_type": "sqlserver_direct",
            "adapter": "adventureworks_direct",
            "query_language": "sql",
            "logical_input_language": "mdx_or_sql",
            "physical_query_language": "sql",
            "catalog": "AdventureWorksDW",
            "cube": "Adventure Works DW",
            "enabled": False,
            "default": False,
            "experimental": True,
            "execution_priority": 2,
            "connection_profile": "sqlserver_adventureworks_dw",
            "notes": "Registered SQL Direct fallback/secondary path. Real SQL Server connection and semantic mapping are planned for the AdventureWorksDW integration step.",
        },
        {
            "id": "steelwheels_xmla",
            "label": "SteelWheels — XMLA/eMondrian",
            "dataset": "SteelWheels / Pentaho SampleData",
            "backend_type": "xmla_mondrian",
            "adapter": "xmla_mondrian",
            "query_language": "mdx",
            "logical_input_language": "mdx",
            "physical_query_language": "xmla_mdx",
            "catalog": "SteelWheels",
            "cube": "SteelWheelsSales",
            "enabled": False,
            "default": False,
            "experimental": True,
            "execution_priority": 1,
            "fallback_dw_id": "steelwheels_sql_direct",
            "xmla_url": "http://emondrian:8080/emondrian/xmla",
            "notes": "Third reputed Mondrian/Pentaho-compatible dataset candidate. Enable after adding the SteelWheels schema/catalog to eMondrian.",
        },
        {
            "id": "steelwheels_sql_direct",
            "label": "SteelWheels — SQL Direct fallback",
            "dataset": "SteelWheels / Pentaho SampleData",
            "backend_type": "sql_direct",
            "adapter": "steelwheels_direct",
            "query_language": "sql",
            "logical_input_language": "mdx_or_sql",
            "physical_query_language": "sql",
            "catalog": "SteelWheels",
            "cube": "SteelWheelsSales",
            "enabled": False,
            "default": False,
            "experimental": True,
            "fallback": True,
            "execution_priority": 2,
            "connection_profile": "steelwheels_sampledata",
            "notes": "Registered fallback/secondary adapter for SteelWheels. Physical connection and mapping are deferred to the SteelWheels integration step.",
        },
    ]
}


class DWRegistry:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path or os.getenv("MCAD_DW_REGISTRY", "/app/datawarehouses.yaml"))
        self._entries: dict[str, DataWarehouseConfig] = {}
        self.reload()

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return dict(_DEFAULT_REGISTRY)
        raw = self.path.read_text(encoding="utf-8")
        if self.path.suffix.lower() in {".json"}:
            return json.loads(raw)
        if yaml is not None:
            data = yaml.safe_load(raw) or {}
            return data if isinstance(data, dict) else {"datawarehouses": []}
        # Fallback: allow JSON content in .yaml when PyYAML is unavailable.
        return json.loads(raw)

    def reload(self) -> None:
        payload = self._read_payload()
        items = payload.get("datawarehouses") or payload.get("items") or []
        entries: dict[str, DataWarehouseConfig] = {}
        for raw in items:
            if not isinstance(raw, dict):
                continue
            cfg = DataWarehouseConfig.from_dict(raw)
            if cfg.id:
                entries[cfg.id] = cfg
        # Preserve a complete hybrid registry even if a partial YAML is supplied.
        for raw in _DEFAULT_REGISTRY["datawarehouses"]:
            cfg = DataWarehouseConfig.from_dict(raw)
            entries.setdefault(cfg.id, cfg)
        self._entries = entries

    def all(self) -> list[DataWarehouseConfig]:
        return sorted(
            self._entries.values(),
            key=lambda cfg: (cfg.dataset or cfg.label or cfg.id, cfg.execution_priority or 99, cfg.id),
        )

    def get(self, dw_id: str | None) -> DataWarehouseConfig:
        key = str(dw_id or "").strip()
        if key and key in self._entries:
            return self._entries[key]
        for cfg in self._entries.values():
            if cfg.default:
                return cfg
        if "foodmart" in self._entries:
            return self._entries["foodmart"]
        raise KeyError(f"No data warehouse registered for id={dw_id!r}")

    def public_items(self) -> list[dict[str, Any]]:
        return [cfg.public_dict() for cfg in self.all()]


_REGISTRY: DWRegistry | None = None


def get_registry() -> DWRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = DWRegistry()
    return _REGISTRY


def list_datawarehouses() -> list[dict[str, Any]]:
    return get_registry().public_items()


def get_datawarehouse(dw_id: str | None) -> DataWarehouseConfig:
    return get_registry().get(dw_id)
