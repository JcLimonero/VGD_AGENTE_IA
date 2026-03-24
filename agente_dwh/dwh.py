"""Cliente de acceso al DWH."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
import time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .observability import record_query_event


@dataclass
class DwhClient:
    """Cliente para ejecutar consultas contra el DWH."""

    engine: Engine
    default_limit: int = 200
    cache_ttl_seconds: int = 120
    cache_max_entries: int = 500

    def __post_init__(self) -> None:
        self._cache: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

    @classmethod
    def from_url(
        cls,
        database_url: str,
        default_limit: int = 200,
        cache_ttl_seconds: int = 120,
        cache_max_entries: int = 500,
    ) -> "DwhClient":
        engine = create_engine(database_url)
        return cls(
            engine=engine,
            default_limit=default_limit,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_max_entries=cache_max_entries,
        )

    @property
    def dialect_name(self) -> str:
        """Nombre normalizado del dialecto SQL en uso."""
        return (self.engine.dialect.name or "").lower()

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        """Ejecuta una consulta de solo lectura y devuelve filas en formato dict."""
        start = time.perf_counter()
        normalized_sql = self._normalize_sql_for_dialect(sql.strip())
        sql_with_limit = self._inject_limit_if_missing(normalized_sql)
        cached_rows = self._get_cached_rows(sql_with_limit)
        if cached_rows is not None:
            self._cache_hits += 1
            record_query_event(
                source="dwh",
                success=True,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=len(cached_rows),
                cached=True,
            )
            return cached_rows

        self._cache_misses += 1
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(sql_with_limit))
                rows = [dict(row._mapping) for row in result.fetchall()]
                self._set_cache_rows(sql_with_limit, rows)
                record_query_event(
                    source="dwh",
                    success=True,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    row_count=len(rows),
                    cached=False,
                )
                return rows
        except SQLAlchemyError as exc:
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(exc),
            )
            raise RuntimeError(f"Error ejecutando consulta en DWH: {exc}") from exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        """Alias para compatibilidad con versiones previas."""
        return self.execute_select(sql)

    def get_cache_stats(self) -> dict[str, Any]:
        total = self._cache_hits + self._cache_misses
        hit_ratio = (self._cache_hits / total) if total else 0.0
        return {
            "entries": len(self._cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_ratio": round(hit_ratio, 4),
            "ttl_seconds": self.cache_ttl_seconds,
            "max_entries": self.cache_max_entries,
        }

    def _get_cached_rows(self, sql: str) -> list[dict[str, Any]] | None:
        if self.cache_ttl_seconds <= 0:
            return None
        now = time.time()
        cached = self._cache.get(sql)
        if cached is None:
            return None
        created_at, rows = cached
        if now - created_at > self.cache_ttl_seconds:
            self._cache.pop(sql, None)
            return None
        self._cache.move_to_end(sql)
        return [dict(row) for row in rows]

    def _set_cache_rows(self, sql: str, rows: list[dict[str, Any]]) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        self._cache[sql] = (time.time(), [dict(row) for row in rows])
        self._cache.move_to_end(sql)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)

    def _inject_limit_if_missing(self, sql: str) -> str:
        lowered = sql.lower()
        # Evita duplicar LIMIT cuando ya viene en la consulta.
        if re.search(r"\blimit\b", lowered):
            return sql
        return f"{sql.rstrip(';')} LIMIT {self.default_limit};"

    def _normalize_sql_for_dialect(self, sql: str) -> str:
        """Normaliza diferencias comunes de sintaxis entre motores."""
        normalized = (
            sql.replace("≤", "<=")
            .replace("≥", ">=")
            .replace("≠", "!=")
        )

        if self.dialect_name == "sqlite":
            normalized = self._normalize_sqlite_sql(normalized)

        return normalized

    def _normalize_sqlite_sql(self, sql: str) -> str:
        """Traduce funciones frecuentes de otros motores a SQLite."""

        def _replace_dateadd(match: re.Match[str]) -> str:
            unit = match.group("unit").lower()
            amount = int(match.group("amount"))
            date_expr = match.group("date_expr").strip()
            unit_map = {"day": "days", "month": "months", "year": "years"}
            modifier_unit = unit_map.get(unit, f"{unit}s")
            sign = "+" if amount >= 0 else ""
            return f"date({date_expr}, '{sign}{amount} {modifier_unit}')"

        normalized = re.sub(
            r"DATEADD\s*\(\s*(?P<unit>day|month|year)\s*,\s*(?P<amount>-?\d+)\s*,\s*(?P<date_expr>[^)]+?)\s*\)",
            _replace_dateadd,
            sql,
            flags=re.IGNORECASE,
        )
        normalized = self._rewrite_interval_arithmetic(normalized)
        normalized = self._rewrite_window_avg_misuse(normalized)
        normalized = self._rewrite_service_appointments_status_aliases(normalized)
        return self._rewrite_sales_status_aliases(normalized)

    def _rewrite_interval_arithmetic(self, sql: str) -> str:
        """Convierte aritmética de intervalos estilo PostgreSQL a SQLite."""

        def _replace_with_sign(match: re.Match[str]) -> str:
            func = match.group("func")
            sign = match.group("sign")
            amount = int(match.group("amount"))
            unit = match.group("unit").lower()
            unit_map = {"day": "days", "month": "months", "year": "years"}
            modifier_unit = unit_map.get(unit, f"{unit}s")
            signed_amount = amount if sign == "+" else -amount
            sign_prefix = "+" if signed_amount >= 0 else ""
            return f"{func}('now', '{sign_prefix}{signed_amount} {modifier_unit}')"

        # Ejemplos:
        # date('now') - interval '1 month' -> date('now', '-1 months')
        # datetime('now') + interval '7 day' -> datetime('now', '+7 days')
        return re.sub(
            r"(?P<func>date|datetime)\s*\(\s*'now'\s*\)\s*(?P<sign>[+-])\s*interval\s*'(?P<amount>\d+)\s+(?P<unit>day|month|year)s?'",
            _replace_with_sign,
            sql,
            flags=re.IGNORECASE,
        )

    def _rewrite_window_avg_misuse(self, sql: str) -> str:
        """Corrige patrón común inválido en SQLite: AVG(...LAG(...) OVER (...))."""
        normalized = " ".join(sql.strip().split())
        pattern = (
            r"^SELECT\s+customer_id\s*,\s*"
            r"AVG\(\s*julianday\(\s*sale_date\s*\)\s*-\s*LAG\(\s*julianday\(\s*sale_date\s*\)\s*\)\s*"
            r"OVER\s*\(\s*PARTITION\s+BY\s+customer_id\s+ORDER\s+BY\s+sale_date\s*\)\s*\)\s*"
            r"AS\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+"
            r"FROM\s+sales\s+GROUP\s+BY\s+customer_id(?P<tail>.*)$"
        )
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            return sql

        alias = match.group("alias")
        tail = (match.group("tail") or "").strip().rstrip(";")
        order_clause = ""
        limit_clause = ""

        order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?=\s+LIMIT\b|$)", tail, flags=re.IGNORECASE)
        if order_match:
            order_clause = f"ORDER BY {order_match.group(1).strip()}"

        limit_match = re.search(r"\bLIMIT\s+(?P<n>\d+)\b", tail, flags=re.IGNORECASE)
        if limit_match:
            limit_clause = f"LIMIT {limit_match.group('n')}"

        rewritten = (
            "WITH sale_gaps AS ("
            " SELECT customer_id, "
            " julianday(sale_date) - julianday(LAG(sale_date) OVER (PARTITION BY customer_id ORDER BY sale_date)) AS gap_days "
            " FROM sales"
            ") "
            f"SELECT customer_id, ROUND(AVG(gap_days), 2) AS {alias} "
            "FROM sale_gaps "
            "WHERE gap_days IS NOT NULL "
            "GROUP BY customer_id "
        )
        if order_clause:
            rewritten += f"{order_clause} "
        if limit_clause:
            rewritten += limit_clause
        return rewritten.strip()

    def _rewrite_sales_status_aliases(self, sql: str) -> str:
        """Mapea alias de estados comunes al catálogo real de la demo SQLite."""
        # En la demo usamos estados: cerrada, facturada, entregada.
        # El LLM a veces usa 'completed'; aquí lo ampliamos a todos los estados
        # equivalentes para no perder filas en consultas de recompra.
        return re.sub(
            r"(?i)(?P<prefix>\b(?:[A-Za-z_][A-Za-z0-9_]*\.)?status)\s*=\s*'completed'",
            r"\g<prefix> IN ('completed', 'entregada', 'facturada', 'cerrada')",
            sql,
        )

    def _rewrite_service_appointments_status_aliases(self, sql: str) -> str:
        """
        Corrige SQL generado para agenda de servicio cuando usa columna status.

        En service_appointments la columna real es appointment_status.
        El LLM puede generar `status` por consistencia con otras tablas.
        """
        lowered = sql.lower()
        if "service_appointments" not in lowered:
            return sql

        normalized = re.sub(
            r"(?i)(\bservice_appointments\s*\.\s*)status\b",
            r"\1appointment_status",
            sql,
        )
        normalized = re.sub(
            r"(?i)(\b(?:from|join)\s+service_appointments(?:\s+as)?\s+)([A-Za-z_][A-Za-z0-9_]*)",
            r"\1\2",
            normalized,
        )
        alias_matches = re.findall(
            r"(?i)\b(?:from|join)\s+service_appointments(?:\s+as)?\s+([A-Za-z_][A-Za-z0-9_]*)",
            normalized,
        )
        for alias in alias_matches:
            normalized = re.sub(
                rf"(?i)(\b{re.escape(alias)}\s*\.\s*)status\b",
                rf"\1appointment_status",
                normalized,
            )

        if re.search(r"(?i)\bappointment_status\b", normalized):
            normalized = re.sub(r"(?i)\bstatus\b", "appointment_status", normalized)
            return normalized

        # Si la consulta usa service_appointments sin alias explícito y no mezcla
        # otras tablas con columna status, reemplazamos status sin prefijo.
        has_other_status_tables = re.search(
            r"(?i)\b(?:from|join)\s+(sales|services)\b",
            normalized,
        )
        if not has_other_status_tables:
            normalized = re.sub(r"(?i)\bstatus\b", "appointment_status", normalized)
        return normalized
