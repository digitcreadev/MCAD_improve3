from __future__ import annotations

from typing import Any
import os
import re
import time

from .base import AdapterExecutionResult, BaseAdapter, digest_payload

try:  # python-tds avoids ODBC driver installation in the proxy image.
    import pytds  # type: ignore
except Exception:  # pragma: no cover
    pytds = None


class AdventureWorksDirectAdapter(BaseAdapter):
    """SQL Server Docker-backed AdventureWorksDW direct adapter.

    V9.5.0 supports a controlled first subset:
    - read-only SELECT T-SQL;
    - MDX-like demo queries mapped to AdventureWorksDW T-SQL.

    It never fabricates rows: if SQL Server/AdventureWorksDW is unavailable,
    it returns physical_execution=false with a structured error.
    """

    adapter_id = "adventureworks_direct"

    def _host(self) -> str:
        return os.getenv("ADVENTUREWORKS_SQLSERVER_HOST") or str(self.config.config.get("host") or "adventureworks-sqlserver")

    def _port(self) -> int:
        return int(os.getenv("ADVENTUREWORKS_SQLSERVER_PORT") or self.config.config.get("port") or 1433)

    def _database(self) -> str:
        return os.getenv("ADVENTUREWORKS_SQLSERVER_DATABASE") or str(self.config.config.get("database") or self.config.catalog or "AdventureWorksDW2022")

    def _user(self) -> str:
        return os.getenv("ADVENTUREWORKS_SQLSERVER_USER") or str(self.config.config.get("user") or "sa")

    def _password(self) -> str:
        return os.getenv("ADVENTUREWORKS_SQLSERVER_PASSWORD") or os.getenv("ADVENTUREWORKS_SA_PASSWORD") or str(self.config.config.get("password") or "MCAD_AwDWDemo!2026")

    def _connect(self):
        if pytds is None:
            raise RuntimeError("python-tds is not installed in mcad-proxy. Rebuild the image after applying V9.5.0.")
        return pytds.connect(
            server=self._host(), port=self._port(), database=self._database(),
            user=self._user(), password=self._password(), autocommit=True,
            timeout=10, login_timeout=10, as_dict=True,
        )

    def _execute_sql(self, sql: str, max_rows: int = 200) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchmany(max_rows)
                columns = [c[0] for c in (cur.description or [])]
        clean_rows = []
        for r in rows or []:
            if isinstance(r, dict):
                clean_rows.append({k: _jsonable(v) for k, v in r.items()})
            else:
                clean_rows.append({columns[i]: _jsonable(v) for i, v in enumerate(r)})
        return {"columns": columns, "rows": clean_rows, "row_count": len(clean_rows)}

    def _read_only_sql(self, sql: str) -> bool:
        s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        s = re.sub(r"--.*?$", " ", s, flags=re.M).strip().lower()
        forbidden = ("insert", "update", "delete", "drop", "alter", "create", "merge", "truncate", "restore", "backup", "exec", "execute")
        if not s.startswith("select") and not s.startswith("with"):
            return False
        return not any(re.search(rf"\b{kw}\b", s) for kw in forbidden)

    def _mdx_to_sql(self, mdx: str) -> tuple[str | None, str | None]:
        q = (mdx or "").lower()
        measure_expr = "SUM(f.SalesAmount)"
        measure_label = "SalesAmount"
        if "total product cost" in q or "totalproductcost" in q or "product cost" in q:
            measure_expr = "SUM(f.TotalProductCost)"; measure_label = "TotalProductCost"
        elif "order quantity" in q or "orderquantity" in q:
            measure_expr = "SUM(CAST(f.OrderQuantity AS BIGINT))"; measure_label = "OrderQuantity"
        elif "gross margin" in q or "profit" in q or "margin" in q:
            measure_expr = "SUM(f.SalesAmount - f.TotalProductCost)"; measure_label = "GrossMargin"

        select_dims: list[str] = []
        group_dims: list[str] = []
        order_dims: list[str] = []

        # V9.5.1: support composite AdventureWorks demo grains.  The first
        # V9.5.0 adapter used an if/elif branch, so a query mentioning both
        # Month and Territory was grouped only by Month.  The objective/scenario
        # pack needs the real Month x SalesTerritoryRegion grain.
        if "month" in q:
            select_dims += ["d.CalendarYear", "d.MonthNumberOfYear", "d.EnglishMonthName"]
            group_dims += ["d.CalendarYear", "d.MonthNumberOfYear", "d.EnglishMonthName"]
            order_dims += ["d.CalendarYear", "d.MonthNumberOfYear"]
        if "territory" in q or "region" in q:
            select_dims += ["t.SalesTerritoryGroup", "t.SalesTerritoryCountry", "t.SalesTerritoryRegion"]
            group_dims += ["t.SalesTerritoryGroup", "t.SalesTerritoryCountry", "t.SalesTerritoryRegion"]
            order_dims += ["t.SalesTerritoryGroup", "t.SalesTerritoryCountry", "t.SalesTerritoryRegion"]
        if not select_dims:
            select_dims.append("d.CalendarYear"); group_dims.append("d.CalendarYear"); order_dims.append("d.CalendarYear")

        filters = ["f.SalesAmount IS NOT NULL"]
        if "2014" in q: filters.append("d.CalendarYear = 2014")
        elif "2013" in q: filters.append("d.CalendarYear = 2013")
        elif "2012" in q: filters.append("d.CalendarYear = 2012")
        elif "2011" in q: filters.append("d.CalendarYear = 2011")
        if "united states" in q or "[united states]" in q: filters.append("t.SalesTerritoryCountry = 'United States'")
        if "canada" in q: filters.append("t.SalesTerritoryCountry = 'Canada'")
        if "europe" in q: filters.append("t.SalesTerritoryGroup = 'Europe'")
        if "north america" in q: filters.append("t.SalesTerritoryGroup = 'North America'")
        if "pacific" in q: filters.append("t.SalesTerritoryGroup = 'Pacific'")
        if "bikes" in q or "bike" in q: filters.append("pc.EnglishProductCategoryName = 'Bikes'")
        if "accessories" in q: filters.append("pc.EnglishProductCategoryName = 'Accessories'")
        if "clothing" in q: filters.append("pc.EnglishProductCategoryName = 'Clothing'")
        if "components" in q: filters.append("pc.EnglishProductCategoryName = 'Components'")

        sql = f"""
SELECT TOP (200)
       {', '.join(select_dims)},
       CAST({measure_expr} AS DECIMAL(18,2)) AS [{measure_label}]
FROM dbo.FactInternetSales AS f
JOIN dbo.DimDate AS d ON d.DateKey = f.OrderDateKey
LEFT JOIN dbo.DimSalesTerritory AS t ON t.SalesTerritoryKey = f.SalesTerritoryKey
LEFT JOIN dbo.DimProduct AS p ON p.ProductKey = f.ProductKey
LEFT JOIN dbo.DimProductSubcategory AS ps ON ps.ProductSubcategoryKey = p.ProductSubcategoryKey
LEFT JOIN dbo.DimProductCategory AS pc ON pc.ProductCategoryKey = ps.ProductCategoryKey
WHERE {' AND '.join(filters)}
GROUP BY {', '.join(group_dims)}
ORDER BY {', '.join(order_dims)};
""".strip()
        return sql, measure_label

    def health(self) -> dict[str, Any]:
        h = super().health()
        h.update({"adapter_family": "sqlserver_direct", "host": self._host(), "port": self._port(), "database": self._database(), "requires_restore": "AdventureWorksDW2022.bak", "setup_script": "bi-stack/scripts/setup_adventureworks_sqlserver.sh"})
        if not self.config.enabled:
            h.update({"ok": False, "status": "disabled", "real_execution": False}); return h
        try:
            fact = self._execute_sql("SELECT CAST(COUNT_BIG(*) AS BIGINT) AS FactInternetSalesRows FROM dbo.FactInternetSales;", max_rows=1)
            h.update({"ok": True, "status": "available", "database_ready": True, "real_execution": True, "fact_rows": fact.get("rows", [])})
        except Exception as exc:
            h.update({"ok": False, "status": "configured_but_not_ready", "database_ready": False, "real_execution": False, "error": str(exc)})
        return h

    def metadata(self) -> dict[str, Any]:
        m = super().metadata()
        m.update({"ok": bool(self.config.enabled), "dataset": "AdventureWorksDW", "database": self._database(), "adapter_id": self.adapter_id, "physical_query_language": "sqlserver_tsql", "supported_measures": ["SalesAmount", "TotalProductCost", "OrderQuantity", "GrossMargin"], "supported_grains": ["CalendarYear", "Month", "SalesTerritoryCountry", "SalesTerritoryRegion"], "supported_tables": ["FactInternetSales", "DimDate", "DimSalesTerritory", "DimProduct", "DimProductCategory"], "execution_contract": "MCAD_ALLOW_THEN_SQLSERVER_EXECUTE"})
        return m

    def execute(self, query_text: str, query_type: str = "mdx", context: dict[str, Any] | None = None) -> AdapterExecutionResult:
        if not self.config.enabled:
            return AdapterExecutionResult.unavailable(self.config, "AdventureWorksDW SQL Server adapter is disabled.")
        qtype = str(query_type or "mdx").lower()
        started = time.time(); generated_sql = None; logical_mapping = None
        try:
            if qtype in {"sql", "tsql", "sqlserver_tsql"}:
                if not self._read_only_sql(query_text):
                    return AdapterExecutionResult.unavailable(self.config, "Only read-only SELECT SQL is allowed for AdventureWorksDW SQL Direct.", status_code=400)
                generated_sql = query_text.strip(); logical_mapping = "direct_read_only_sql"
            elif qtype in {"mdx", "mdx_or_sql"}:
                generated_sql, logical_mapping = self._mdx_to_sql(query_text)
            else:
                return AdapterExecutionResult.unavailable(self.config, f"Unsupported query_type={query_type!r} for AdventureWorksDW SQL Direct.", status_code=400)
            result = self._execute_sql(generated_sql, max_rows=int((context or {}).get("max_rows") or 200))
            elapsed_ms = int((time.time() - started) * 1000)
            payload = {"ok": True, "physical_execution": True, "execution_mode": "real", "adapter_family": "sqlserver_direct", "adapter_id": self.adapter_id, "dw_id": self.config.id, "dataset": self.config.dataset, "database": self._database(), "logical_query_language": qtype, "physical_query_language": "sqlserver_tsql", "logical_mapping": logical_mapping, "generated_sql": generated_sql, "columns": result.get("columns", []), "rows": result.get("rows", []), "row_count": result.get("row_count", 0), "status_code": 200, "elapsed_ms": elapsed_ms}
            response_bytes, response_digest = digest_payload(payload)
            payload.update({"response_bytes": response_bytes, "response_digest": response_digest, "result_digest": response_digest})
            return AdapterExecutionResult(status_code=200, elapsed_ms=elapsed_ms, response_bytes=response_bytes, response_digest=response_digest, raw_result_summary=payload, adapter_id=self.adapter_id, dw_id=self.config.id, query_language=qtype, backend_type=self.config.backend_type)
        except Exception as exc:
            elapsed_ms = int((time.time() - started) * 1000)
            summary = {"ok": False, "physical_execution": False, "execution_mode": "real_attempt_failed", "adapter_family": "sqlserver_direct", "adapter_id": self.adapter_id, "dw_id": self.config.id, "dataset": self.config.dataset, "database": self._database(), "logical_query_language": qtype, "physical_query_language": "sqlserver_tsql", "generated_sql": generated_sql, "elapsed_ms": elapsed_ms, "error": str(exc)}
            response_bytes, response_digest = digest_payload(summary)
            return AdapterExecutionResult(status_code=502, elapsed_ms=elapsed_ms, response_bytes=response_bytes, response_digest=response_digest, raw_result_summary=summary, adapter_id=self.adapter_id, dw_id=self.config.id, query_language=qtype, backend_type=self.config.backend_type, error=str(exc))


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)): return v
    if hasattr(v, "isoformat"): return v.isoformat()
    try: return float(v)
    except Exception: return str(v)
