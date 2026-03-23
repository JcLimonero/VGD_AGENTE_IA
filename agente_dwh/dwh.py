"""Cliente de acceso al DWH."""

from __future__ import annotations

from dataclasses import dataclass
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

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        """Ejecuta una consulta de solo lectura y devuelve filas en formato dict."""
        sql_with_limit = self._inject_limit_if_missing(sql.strip())
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
        if " limit " in lowered or lowered.endswith(" limit"):
            return sql
        return f"{sql.rstrip(';')} LIMIT {self.default_limit};"
