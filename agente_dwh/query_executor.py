"""Ejecución de SQL de solo lectura y utilidades de consulta."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def inject_limit_if_missing(sql: str, default_limit: int) -> str:
    lowered = sql.lower()
    if re.search(r"\blimit\b", lowered):
        return sql
    return f"{sql.rstrip(';')} LIMIT {default_limit};"


class QueryExecutor:
    """Wrapper de ejecución para desacoplar cliente DWH de SQLAlchemy."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def run_select(self, sql: str) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            result = connection.execute(text(sql))
            return [dict(row._mapping) for row in result.fetchall()]
