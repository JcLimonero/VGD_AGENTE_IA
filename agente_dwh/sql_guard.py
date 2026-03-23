"""Validaciones basicas para permitir solo SQL de lectura."""

from __future__ import annotations

import re

_FORBIDDEN = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXEC",
)


def clean_sql_output(raw_sql: str) -> str:
    """Limpia formato comun del LLM (```sql ...```) y retorna SQL plano."""
    cleaned = raw_sql.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def sanitize_generated_sql(raw_sql: str) -> str:
    """Alias de compatibilidad para limpieza de SQL."""
    return clean_sql_output(raw_sql)


def validate_read_only_sql(sql: str) -> None:
    """Lanza ValueError si la consulta no es de solo lectura."""
    if not sql or not sql.strip():
        raise ValueError("La consulta SQL esta vacia.")

    normalized = sql.strip().strip(";")
    # Bloquea multiples sentencias.
    if ";" in normalized:
        raise ValueError("Solo se permite una sentencia SQL por consulta.")

    upper = normalized.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError("Solo se permiten consultas que inicien con SELECT o WITH.")

    for word in _FORBIDDEN:
        if re.search(rf"\b{word}\b", upper):
            raise ValueError(f"La consulta contiene una operacion no permitida: {word}")
