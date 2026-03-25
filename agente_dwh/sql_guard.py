"""Validaciones para permitir solo SQL de lectura y reducir riesgo de inyección."""

from __future__ import annotations

import re
from typing import Pattern

# Operaciones de escritura / DDL / privilegios / ejecución remota.
_FORBIDDEN_KEYWORDS: tuple[str, ...] = (
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
    "EXECUTE",
    "REPLACE",  # REPLACE INTO (MySQL)
    "PREPARE",
    "DEALLOCATE",
    "LISTEN",
    "NOTIFY",
    "UNLISTEN",
    "VACUUM",
    "REINDEX",
    "CLUSTER",
    "DISCARD",
    "RESET",
    "COMMENT",  # COMMENT ON ...
    "LOCK",
    "UNLOCK",
    "LOAD",
    "IMPORT",
    "ATTACH",
    "DETACH",
    "PRAGMA",
)

# Patrones adicionales (aplicados sobre SQL en mayúsculas, sin literales enmascarados).
_DANGEROUS_PATTERNS: tuple[tuple[Pattern[str], str], ...] = (
    (re.compile(r"(?is)\bCOPY\b.*\bTO\s+PROGRAM\b"), "COPY ... TO PROGRAM"),
    (re.compile(r"\bREFRESH\b\s+MATERIALIZED\b"), "REFRESH MATERIALIZED VIEW"),
    (re.compile(r"\bINTO\s+OUTFILE\b"), "INTO OUTFILE"),
    (re.compile(r"\bINTO\s+DUMPFILE\b"), "INTO DUMPFILE"),
    (re.compile(r"\bPG_READ_FILE\s*\("), "pg_read_file"),
    (re.compile(r"\bPG_WRITE_FILE\s*\("), "pg_write_file"),
    (re.compile(r"\bLO_IMPORT\s*\("), "lo_import"),
    (re.compile(r"\bLO_EXPORT\s*\("), "lo_export"),
    (re.compile(r"\bDBLINK\s*\("), "dblink"),
    (re.compile(r"\bPG_SLEEP\s*\("), "pg_sleep"),
    (re.compile(r"\bSET\s+ROLE\b"), "SET ROLE"),
    (re.compile(r"\bSET\s+SESSION\b"), "SET SESSION"),
    (re.compile(r"\bSET\s+CONSTRAINTS\b"), "SET CONSTRAINTS"),
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


def _strip_sql_comments(sql: str) -> str:
    """Elimina comentarios SQL (-- y /* */) respetando literales ' y " (identificadores PG)."""
    out: list[str] = []
    i = 0
    n = len(sql)
    state = "normal"
    while i < n:
        c = sql[i]
        if state == "normal":
            if c == "-" and i + 1 < n and sql[i + 1] == "-":
                while i < n and sql[i] != "\n":
                    i += 1
                out.append(" ")
                continue
            if c == "/" and i + 1 < n and sql[i + 1] == "*":
                i += 2
                while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                    i += 1
                i = min(i + 2, n)
                out.append(" ")
                continue
            if c == "'":
                state = "sq"
                out.append(c)
                i += 1
                continue
            if c == '"':
                state = "dq"
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        if state == "sq":
            out.append(c)
            if c == "'" and i + 1 < n and sql[i + 1] == "'":
                out.append(sql[i + 1])
                i += 2
                continue
            if c == "'":
                state = "normal"
            i += 1
            continue
        if state == "dq":
            out.append(c)
            if c == '"' and i + 1 < n and sql[i + 1] == '"':
                out.append(sql[i + 1])
                i += 2
                continue
            if c == '"':
                state = "normal"
            i += 1
            continue
    return "".join(out)


def _mask_quoted_for_scan(sql: str) -> str:
    """Sustituye por espacios el contenido de literales '...' y "..." para buscar tokens sin falsos positivos."""
    chars = list(sql)
    i = 0
    n = len(sql)
    state = "normal"
    while i < n:
        c = sql[i]
        if state == "normal":
            if c == "'":
                state = "sq"
                i += 1
                continue
            if c == '"':
                state = "dq"
                i += 1
                continue
            i += 1
            continue
        if state == "sq":
            if c == "'" and i + 1 < n and sql[i + 1] == "'":
                chars[i] = chars[i + 1] = " "
                i += 2
                continue
            if c == "'":
                state = "normal"
                i += 1
                continue
            chars[i] = " "
            i += 1
            continue
        if state == "dq":
            if c == '"' and i + 1 < n and sql[i + 1] == '"':
                chars[i] = chars[i + 1] = " "
                i += 2
                continue
            if c == '"':
                state = "normal"
                i += 1
                continue
            chars[i] = " "
            i += 1
            continue
    return "".join(chars)


def _semicolon_positions_outside_quotes(sql: str) -> list[int]:
    pos: list[int] = []
    i = 0
    n = len(sql)
    state = "normal"
    while i < n:
        c = sql[i]
        if state == "normal":
            if c == "'":
                state = "sq"
            elif c == '"':
                state = "dq"
            elif c == ";":
                pos.append(i)
            i += 1
            continue
        if state == "sq":
            if c == "'" and i + 1 < n and sql[i + 1] == "'":
                i += 2
            elif c == "'":
                state = "normal"
                i += 1
            else:
                i += 1
            continue
        if state == "dq":
            if c == '"' and i + 1 < n and sql[i + 1] == '"':
                i += 2
            elif c == '"':
                state = "normal"
                i += 1
            else:
                i += 1
            continue
    return pos


def _validate_single_statement(sql_no_comments: str) -> None:
    positions = _semicolon_positions_outside_quotes(sql_no_comments)
    if len(positions) > 1:
        raise ValueError(
            "Solo se permite una sentencia SQL: se encontraron varios punto y coma fuera de literales."
        )
    if len(positions) == 1:
        after = sql_no_comments[positions[0] + 1 :]
        if after.strip():
            raise ValueError(
                "Solo se permite un punto y coma final opcional: hay texto despues del primer ';'."
            )


def _starts_with_select_or_with(stripped: str) -> bool:
    s = stripped.lstrip()
    return bool(re.match(r"(?is)\A(WITH|SELECT)\b", s))


def validate_read_only_sql(sql: str) -> None:
    """
    Lanza ValueError si la consulta no es de solo lectura o muestra patrones de riesgo.

    - Una sola sentencia (punto y coma solo al final, permitido en cadena dentro de literales).
    - Sin bytes nulos.
    - Comentarios eliminados para analisis; palabras prohibidas buscadas fuera de literales.
    """
    if not sql or not sql.strip():
        raise ValueError("La consulta SQL esta vacia.")
    if "\x00" in sql:
        raise ValueError("La consulta contiene caracteres no permitidos.")

    without_comments = _strip_sql_comments(sql)
    _validate_single_statement(without_comments)

    trimmed = without_comments.strip().rstrip(";").strip()
    if not trimmed:
        raise ValueError("La consulta SQL esta vacia tras quitar comentarios.")

    if not _starts_with_select_or_with(trimmed):
        raise ValueError("Solo se permiten consultas que inicien con SELECT o WITH.")

    masked = _mask_quoted_for_scan(without_comments)
    upper_masked = masked.upper()

    for word in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", upper_masked):
            raise ValueError(f"La consulta contiene una operacion no permitida: {word}")

    for pattern, label in _DANGEROUS_PATTERNS:
        if pattern.search(upper_masked):
            raise ValueError(f"La consulta contiene un patron no permitido: {label}")
