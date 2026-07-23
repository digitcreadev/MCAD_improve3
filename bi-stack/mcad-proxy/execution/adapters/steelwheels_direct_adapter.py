from __future__ import annotations

from typing import Any
from decimal import Decimal
import os
import re
import time

from .base import AdapterExecutionResult, BaseAdapter, digest_payload

try:
    import pytds  # type: ignore
except Exception:  # pragma: no cover
    pytds = None


class SteelWheelsDirectAdapter(BaseAdapter):
    """SQL Server-backed SteelWheels direct adapter.

    Supports a controlled read-only subset:
    - direct SELECT SQL;
    - MDX-like demo queries mapped to SteelWheels T-SQL.
    """

    adapter_id = "steelwheels_direct"

    def _host(self) -> str:
        return os.getenv("STEELWHEELS_SQLSERVER_HOST") or "adventureworks-sqlserver"

    def _port(self) -> int:
        return int(os.getenv("STEELWHEELS_SQLSERVER_PORT") or 1433)

    def _database(self) -> str:
        return os.getenv("STEELWHEELS_SQLSERVER_DATABASE") or "SteelWheels"

    def _user(self) -> str:
        return os.getenv("STEELWHEELS_SQLSERVER_USER") or "sa"

    def _password(self) -> str:
        return (
            os.getenv("STEELWHEELS_SQLSERVER_PASSWORD")
            or os.getenv("ADVENTUREWORKS_SA_PASSWORD")
            or "MCAD_AwDWDemo!2026"
        )

    def _connect(self):
        if pytds is None:
            raise RuntimeError("python-tds is not installed in mcad-proxy.")
        return pytds.connect(
            server=self._host(),
            port=self._port(),
            database=self._database(),
            user=self._user(),
            password=self._password(),
            autocommit=True,
            timeout=10,
            login_timeout=10,
            as_dict=True,
        )

    def _execute_sql(self, sql: str, max_rows: int = 200) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchmany(max_rows)
                columns = [c[0] for c in (cur.description or [])]

        clean_rows = []
        for row in rows or []:
            if isinstance(row, dict):
                clean_rows.append({k: _jsonable(v) for k, v in row.items()})
            else:
                clean_rows.append({columns[i]: _jsonable(v) for i, v in enumerate(row)})

        return {"columns": columns, "rows": clean_rows, "row_count": len(clean_rows)}

    def _read_only_sql(self, sql: str) -> bool:
        s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        s = re.sub(r"--.*?$", " ", s, flags=re.M).strip().lower()
        forbidden = (
            "insert", "update", "delete", "drop", "alter", "create",
            "merge", "truncate", "restore", "backup", "exec", "execute"
        )
        if not s.startswith("select") and not s.startswith("with"):
            return False
        return not any(re.search(rf"\b{kw}\b", s) for kw in forbidden)

    def _mdx_to_sql(self, mdx: str) -> tuple[str, str]:
        q = (mdx or "").lower()

        measure_col = "TOTALPRICE"
        measure_label = "Sales"
        if "quantity" in q or "quantityordered" in q:
            measure_col = "QUANTITYORDERED"
            measure_label = "Quantity"

        select_dims: list[str] = []
        group_dims: list[str] = []
        order_dims: list[str] = []

        if "month" in q:
            select_dims += ["t.YEAR_ID", "t.QTR_NAME", "t.MONTH_ID", "t.MONTH_NAME"]
            group_dims += ["t.YEAR_ID", "t.QTR_NAME", "t.MONTH_ID", "t.MONTH_NAME"]
            order_dims += ["t.YEAR_ID", "t.MONTH_ID"]
        elif "quarter" in q or "qtr" in q:
            select_dims += ["t.YEAR_ID", "t.QTR_ID", "t.QTR_NAME"]
            group_dims += ["t.YEAR_ID", "t.QTR_ID", "t.QTR_NAME"]
            order_dims += ["t.YEAR_ID", "t.QTR_ID"]
        else:
            select_dims += ["t.YEAR_ID"]
            group_dims += ["t.YEAR_ID"]
            order_dims += ["t.YEAR_ID"]

        if "territory" in q:
            select_dims.append("c.TERRITORY")
            group_dims.append("c.TERRITORY")
            order_dims.append("c.TERRITORY")
        if "country" in q:
            select_dims.append("c.COUNTRY")
            group_dims.append("c.COUNTRY")
            order_dims.append("c.COUNTRY")
        if "city" in q:
            select_dims.append("c.CITY")
            group_dims.append("c.CITY")
            order_dims.append("c.CITY")
        if "line" in q or "productline" in q:
            select_dims.append("p.PRODUCTLINE")
            group_dims.append("p.PRODUCTLINE")
            order_dims.append("p.PRODUCTLINE")
        if "vendor" in q:
            select_dims.append("p.PRODUCTVENDOR")
            group_dims.append("p.PRODUCTVENDOR")
            order_dims.append("p.PRODUCTVENDOR")
        if "status" in q:
            select_dims.append("o.STATUS")
            group_dims.append("o.STATUS")
            order_dims.append("o.STATUS")

        filters = ["1 = 1"]

        for year in ("2003", "2004", "2005"):
            if year in q:
                filters.append(f"t.YEAR_ID = {year}")
                break

        for territory in ("emea", "north america", "apac", "latam"):
            if territory in q:
                filters.append(f"LOWER(c.TERRITORY) = '{territory}'")
                break

        product_lines = [
            "classic cars",
            "motorcycles",
            "vintage cars",
            "planes",
            "trucks and buses",
        ]
        for line in product_lines:
            if line in q:
                filters.append(f"LOWER(p.PRODUCTLINE) = '{line}'")
                break

        for status in ("shipped", "resolved", "on hold", "cancelled"):
            if status in q:
                filters.append(f"LOWER(o.STATUS) = '{status}'")
                break

        sql = f"""
SELECT TOP (200)
       {', '.join(select_dims)},
       CAST(SUM(o.{measure_col}) AS DECIMAL(18,2)) AS [{measure_label}]
FROM dbo.orderfact AS o
JOIN dbo.time AS t ON t.TIME_ID = o.TIME_ID
JOIN dbo.customer_w_ter AS c ON c.CUSTOMERNUMBER = o.CUSTOMERNUMBER
JOIN dbo.products AS p ON p.PRODUCTCODE = o.PRODUCTCODE
WHERE {' AND '.join(filters)}
GROUP BY {', '.join(group_dims)}
ORDER BY {', '.join(order_dims)};
""".strip()

        return sql, measure_label

    def health(self) -> dict[str, Any]:
        h = super().health()
        h.update({
            "adapter_family": "sqlserver_direct",
            "host": self._host(),
            "port": self._port(),
            "database": self._database(),
            "physical_query_language": "sqlserver_tsql",
        })

        if not self.config.enabled:
            h.update({"ok": False, "status": "disabled", "real_execution": False})
            return h

        try:
            fact = self._execute_sql(
                "SELECT CAST(COUNT_BIG(*) AS BIGINT) AS OrderFactRows FROM dbo.orderfact;",
                max_rows=1,
            )
            h.update({
                "ok": True,
                "status": "available",
                "database_ready": True,
                "real_execution": True,
                "fact_rows": fact.get("rows", []),
            })
        except Exception as exc:
            h.update({
                "ok": False,
                "status": "configured_but_not_ready",
                "database_ready": False,
                "real_execution": False,
                "error": str(exc),
            })

        return h

    def metadata(self) -> dict[str, Any]:
        m = super().metadata()
        m.update({
            "ok": bool(self.config.enabled),
            "dataset": "SteelWheels",
            "database": self._database(),
            "adapter_id": self.adapter_id,
            "catalog": self.config.catalog or "SteelWheels",
            "cube": self.config.cube or "SteelWheelsSales",
            "physical_query_language": "sqlserver_tsql",
            "supported_measures": ["Sales", "Quantity"],
            "supported_grains": ["Years", "Quarters", "Months", "Territory", "Country", "Product Line", "Status"],
            "supported_tables": ["orderfact", "customer_w_ter", "products", "time"],
            "execution_contract": "MCAD_ALLOW_THEN_SQLSERVER_EXECUTE",
        })
        return m

    def execute(self, query_text: str, query_type: str = "mdx", context: dict[str, Any] | None = None) -> AdapterExecutionResult:
        if not self.config.enabled:
            return AdapterExecutionResult.unavailable(self.config, "SteelWheels SQL Server adapter is disabled.")

        qtype = str(query_type or "mdx").lower()
        started = time.time()
        generated_sql = None
        logical_mapping = None

        try:
            if qtype in {"sql", "tsql", "sqlserver_tsql"}:
                if not self._read_only_sql(query_text):
                    return AdapterExecutionResult.unavailable(
                        self.config,
                        "Only read-only SELECT SQL is allowed for SteelWheels SQL Direct.",
                        status_code=400,
                    )
                generated_sql = query_text.strip()
                logical_mapping = "direct_read_only_sql"
            elif qtype in {"mdx", "mdx_or_sql"}:
                generated_sql, logical_mapping = self._mdx_to_sql(query_text)
            else:
                return AdapterExecutionResult.unavailable(
                    self.config,
                    f"Unsupported query_type={query_type!r} for SteelWheels SQL Direct.",
                    status_code=400,
                )

            result = self._execute_sql(generated_sql, max_rows=int((context or {}).get("max_rows") or 200))
            elapsed_ms = int((time.time() - started) * 1000)

            payload = {
                "ok": True,
                "physical_execution": True,
                "execution_mode": "real",
                "adapter_family": "sqlserver_direct",
                "adapter_id": self.adapter_id,
                "dw_id": self.config.id,
                "dataset": self.config.dataset or "SteelWheels",
                "database": self._database(),
                "logical_query_language": qtype,
                "physical_query_language": "sqlserver_tsql",
                "logical_mapping": logical_mapping,
                "generated_sql": generated_sql,
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "row_count": result.get("row_count", 0),
                "status_code": 200,
                "elapsed_ms": elapsed_ms,
                "execution_path": "sqlserver_direct",
            }

            response_bytes, response_digest = digest_payload(payload)
            payload.update({
                "response_bytes": response_bytes,
                "response_digest": response_digest,
                "result_digest": response_digest,
            })

            return AdapterExecutionResult(
                status_code=200,
                elapsed_ms=elapsed_ms,
                response_bytes=response_bytes,
                response_digest=response_digest,
                raw_result_summary=payload,
                adapter_id=self.adapter_id,
                dw_id=self.config.id,
                query_language=qtype,
                backend_type=self.config.backend_type,
            )

        except Exception as exc:
            elapsed_ms = int((time.time() - started) * 1000)
            summary = {
                "ok": False,
                "physical_execution": False,
                "execution_mode": "real_attempt_failed",
                "adapter_family": "sqlserver_direct",
                "adapter_id": self.adapter_id,
                "dw_id": self.config.id,
                "dataset": self.config.dataset or "SteelWheels",
                "database": self._database(),
                "logical_query_language": qtype,
                "physical_query_language": "sqlserver_tsql",
                "generated_sql": generated_sql,
                "elapsed_ms": elapsed_ms,
                "error": str(exc),
            }
            response_bytes, response_digest = digest_payload(summary)
            return AdapterExecutionResult(
                status_code=502,
                elapsed_ms=elapsed_ms,
                response_bytes=response_bytes,
                response_digest=response_digest,
                raw_result_summary=summary,
                adapter_id=self.adapter_id,
                dw_id=self.config.id,
                query_language=qtype,
                backend_type=self.config.backend_type,
                error=str(exc),
            )


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v
