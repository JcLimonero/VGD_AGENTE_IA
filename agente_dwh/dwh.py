"""Cliente de acceso al DWH."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


@dataclass
class DwhClient:
    """Cliente para ejecutar consultas contra el DWH."""

    engine: Engine
    default_limit: int = 200

    @classmethod
    def from_url(cls, database_url: str, default_limit: int = 200) -> "DwhClient":
        engine = create_engine(database_url)
        return cls(engine=engine, default_limit=default_limit)

    @property
    def dialect_name(self) -> str:
        """Nombre normalizado del dialecto SQL en uso."""
        return (self.engine.dialect.name or "").lower()

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        """Ejecuta una consulta de solo lectura y devuelve filas en formato dict."""
        normalized_sql = self._normalize_sql_for_dialect(sql.strip())
        sql_with_limit = self._inject_limit_if_missing(normalized_sql)
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(sql_with_limit))
                rows = [dict(row._mapping) for row in result.fetchall()]
                return rows
        except SQLAlchemyError as exc:
            raise RuntimeError(f"Error ejecutando consulta en DWH: {exc}") from exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        """Alias para compatibilidad con versiones previas."""
        return self.execute_select(sql)

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
