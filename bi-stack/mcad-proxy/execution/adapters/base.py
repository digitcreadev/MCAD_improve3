from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
import hashlib
import json
import time


@dataclass(frozen=True)
class DataWarehouseConfig:
    """Registry entry for one selectable data warehouse/backend."""

    id: str
    label: str
    backend_type: str
    query_language: str = "mdx"
    enabled: bool = True
    experimental: bool = False
    default: bool = False
    catalog: str | None = None
    cube: str | None = None
    adapter: str | None = None
    notes: str = ""
    dataset: str | None = None
    logical_input_language: str | None = None
    physical_query_language: str | None = None
    execution_priority: int | None = None
    fallback_dw_id: str | None = None
    fallback: bool = False
    connection_profile: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DataWarehouseConfig":
        raw = dict(raw or {})
        config = dict(raw.get("config") or {})
        known = {
            "id", "label", "backend_type", "query_language", "enabled", "experimental",
            "default", "catalog", "cube", "adapter", "notes", "dataset",
            "logical_input_language", "physical_query_language", "execution_priority",
            "fallback_dw_id", "fallback", "connection_profile", "config",
        }
        for key, value in raw.items():
            if key not in known:
                config.setdefault(key, value)
        return cls(
            id=str(raw.get("id") or raw.get("dw_id") or "").strip(),
            label=str(raw.get("label") or raw.get("name") or raw.get("id") or "").strip(),
            backend_type=str(raw.get("backend_type") or raw.get("type") or "unknown").strip(),
            query_language=str(raw.get("query_language") or raw.get("language") or "mdx").strip(),
            enabled=bool(raw.get("enabled", True)),
            experimental=bool(raw.get("experimental", False)),
            default=bool(raw.get("default", False)),
            catalog=raw.get("catalog"),
            cube=raw.get("cube"),
            adapter=raw.get("adapter"),
            notes=str(raw.get("notes") or ""),
            dataset=raw.get("dataset"),
            logical_input_language=raw.get("logical_input_language"),
            physical_query_language=raw.get("physical_query_language"),
            execution_priority=int(raw.get("execution_priority")) if raw.get("execution_priority") is not None else None,
            fallback_dw_id=raw.get("fallback_dw_id"),
            fallback=bool(raw.get("fallback", False)),
            connection_profile=raw.get("connection_profile"),
            config=config,
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.backend_type,
            "backend_type": self.backend_type,
            "query_language": self.query_language,
            "enabled": self.enabled,
            "experimental": self.experimental,
            "default": self.default,
            "catalog": self.catalog,
            "cube": self.cube,
            "adapter": self.adapter,
            "dataset": self.dataset,
            "logical_input_language": self.logical_input_language,
            "physical_query_language": self.physical_query_language,
            "execution_priority": self.execution_priority,
            "fallback_dw_id": self.fallback_dw_id,
            "fallback": self.fallback,
            "connection_profile": self.connection_profile,
            "notes": self.notes,
        }


@dataclass
class AdapterExecutionResult:
    """Uniform execution result returned by every backend adapter."""

    status_code: int
    elapsed_ms: int
    response_bytes: int
    response_digest: str
    raw_result_summary: dict[str, Any]
    adapter_id: str
    dw_id: str
    query_language: str
    backend_type: str
    error: str | None = None

    @classmethod
    def unavailable(cls, dw: DataWarehouseConfig, error: str, status_code: int = 503) -> "AdapterExecutionResult":
        digest = hashlib.sha256(error.encode("utf-8")).hexdigest()[:16]
        return cls(
            status_code=status_code,
            elapsed_ms=0,
            response_bytes=len(error.encode("utf-8")),
            response_digest=digest,
            raw_result_summary={"ok": False, "error": error, "row_count": 0, "columns": [], "rows": []},
            adapter_id=str(dw.adapter or dw.backend_type),
            dw_id=dw.id,
            query_language=dw.query_language,
            backend_type=dw.backend_type,
            error=error,
        )


class DWAdapter(Protocol):
    """Stable adapter contract used by the execution gateway."""

    config: DataWarehouseConfig

    def health(self) -> dict[str, Any]: ...
    def metadata(self) -> dict[str, Any]: ...
    def normalize_query(self, query_text: str, query_type: str = "mdx") -> dict[str, Any]: ...
    def execute(self, query_text: str, query_type: str = "mdx", context: dict[str, Any] | None = None) -> AdapterExecutionResult: ...
    def probe_subspace(self, query_spec: dict[str, Any]) -> dict[str, Any]: ...


class BaseAdapter:
    """Base implementation shared by concrete adapters."""

    def __init__(self, config: DataWarehouseConfig):
        self.config = config

    @property
    def adapter_id(self) -> str:
        return str(self.config.adapter or self.config.backend_type)

    def health(self) -> dict[str, Any]:
        return {
            "ok": bool(self.config.enabled),
            "status": "available" if self.config.enabled else "disabled",
            "dw_id": self.config.id,
            "label": self.config.label,
            "backend_type": self.config.backend_type,
            "adapter": self.adapter_id,
            "experimental": self.config.experimental,
            "dataset": self.config.dataset,
            "logical_input_language": self.config.logical_input_language,
            "physical_query_language": self.config.physical_query_language,
            "fallback_dw_id": self.config.fallback_dw_id,
            "fallback": self.config.fallback,
            "notes": self.config.notes,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "ok": bool(self.config.enabled),
            "dw_id": self.config.id,
            "label": self.config.label,
            "backend_type": self.config.backend_type,
            "query_language": self.config.query_language,
            "catalog": self.config.catalog,
            "cube": self.config.cube,
            "experimental": self.config.experimental,
            "adapter": self.adapter_id,
            "dataset": self.config.dataset,
            "logical_input_language": self.config.logical_input_language,
            "physical_query_language": self.config.physical_query_language,
            "fallback_dw_id": self.config.fallback_dw_id,
            "fallback": self.config.fallback,
            "connection_profile": self.config.connection_profile,
            "capabilities": [],
        }

    def normalize_query(self, query_text: str, query_type: str = "mdx") -> dict[str, Any]:
        return {
            "query_text": query_text or "",
            "query_type": query_type or self.config.query_language,
            "dw_id": self.config.id,
            "adapter": self.adapter_id,
        }

    def execute(self, query_text: str, query_type: str = "mdx", context: dict[str, Any] | None = None) -> AdapterExecutionResult:
        return AdapterExecutionResult.unavailable(self.config, f"Adapter {self.adapter_id} does not implement execute().")

    def probe_subspace(self, query_spec: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "dw_id": self.config.id, "adapter": self.adapter_id, "non_empty": None, "error": "probe_subspace not implemented"}


def digest_payload(payload: Any) -> tuple[int, str]:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return len(raw), hashlib.sha256(raw).hexdigest()[:16]


def now_ms() -> int:
    return int(time.time() * 1000)
