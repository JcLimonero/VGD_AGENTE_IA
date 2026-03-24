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

        return re.sub(
            r"DATEADD\s*\(\s*(?P<unit>day|month|year)\s*,\s*(?P<amount>-?\d+)\s*,\s*(?P<date_expr>[^)]+?)\s*\)",
            _replace_dateadd,
            sql,
            flags=re.IGNORECASE,
        )
