"""Validaciones para permitir solo SQL de lectura y reducir riesgo de inyección."""

from __future__ import annotations

import re
import os
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
    """Limpia formato del LLM y retorna SQL plano.

    Maneja tres casos:
    1. Bloque ```sql ... ``` en cualquier parte del texto (el LLM añade explicación).
    2. Texto que empieza directamente con ``` sin lenguaje.
    3. Texto plano que ya es SQL (empieza con SELECT/WITH).
    """
    cleaned = raw_sql.strip()

    # Caso 1: extraer el primer bloque ```...``` que aparezca en cualquier posición
    block = re.search(r"```[a-zA-Z]*\s*\n?(.*?)```", cleaned, re.DOTALL)
    if block:
        return block.group(1).strip()

    # Caso 2: el texto empieza con ``` sin bloque de cierre bien formado
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    # Caso 3: buscar desde el primer SELECT o WITH si hay texto previo
    match = re.search(r"(?i)\b(SELECT|WITH)\b", cleaned)
    if match and match.start() > 0:
        return cleaned[match.start():].strip()

    return cleaned


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


def _truncate_to_first_statement(sql_no_comments: str) -> str:
    """
    Deja solo la primera sentencia: recorta texto tras el primer ';' fuera de literales.

    - Varios ';' fuera de literales -> error (varias sentencias).
    - Un ';' y texto detrás (p. ej. prosa del LLM) -> se descarta lo que sigue al primer ';'.
    """
    s = sql_no_comments.strip()
    positions = _semicolon_positions_outside_quotes(s)
    if len(positions) > 1:
        raise ValueError(
            "Solo se permite una sentencia SQL: se encontraron varios punto y coma fuera de literales."
        )
    if len(positions) == 1:
        after = s[positions[0] + 1 :]
        if after.strip():
            return s[: positions[0] + 1].strip()
    return s


def _validate_single_statement(sql_no_comments: str) -> None:
    """Comprueba que no quede texto tras un único ';' final (tras truncar prosa)."""
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


def validate_read_only_sql(sql: str) -> str:
    """
    Valida SQL de solo lectura y devuelve el texto normalizado listo para ejecutar
    (sin comentarios, una sola sentencia, sin punto y coma final).

    Lanza ValueError si la consulta no es de solo lectura o muestra patrones de riesgo.

    - Una sola sentencia (punto y coma solo al final, permitido en cadena dentro de literales).
    - Texto tras el primer ';' (p. ej. explicación del modelo) se descarta.
    - Sin bytes nulos.
    - Comentarios eliminados para analisis; palabras prohibidas buscadas fuera de literales.
    """
    if not sql or not sql.strip():
        raise ValueError("La consulta SQL esta vacia.")
    if "\x00" in sql:
        raise ValueError("La consulta contiene caracteres no permitidos.")

    without_comments = _truncate_to_first_statement(_strip_sql_comments(sql))
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

    return trimmed


# Patrón: COUNT() sin expresión dentro del paréntesis (inválido en PostgreSQL).
_COUNT_EMPTY_RE = re.compile(r"(?is)\bCOUNT\s*\(\s*\)")

def _forbidden_tables_from_env() -> tuple[str, ...]:
    """
    Lista opcional de tablas prohibidas para prevalidación (separadas por coma).
    Ejemplo:
      AGENTE_DWH_FORBIDDEN_TABLES=sales,vehicles

    Por defecto no bloquea ninguna tabla por nombre para evitar acoplarse a un esquema legacy.
    """
    raw = os.getenv("AGENTE_DWH_FORBIDDEN_TABLES", "").strip()
    if not raw:
        return ()
    return tuple(x.strip().upper() for x in raw.split(",") if x.strip())


def _sql_references_table(upper_masked: str, table_upper: str) -> bool:
    schema_tbl = rf"(?:[A-Za-z0-9_]+\.)?{table_upper}"
    return bool(
        re.search(rf"(?is)\bFROM\s+{schema_tbl}\b", upper_masked)
        or re.search(rf"(?is)\bJOIN\s+{schema_tbl}\b", upper_masked)
        or re.search(rf"(?is),\s*{table_upper}\b", upper_masked)
    )


_TABLE_REF_RE = re.compile(
    r'(?is)\b(?:FROM|JOIN)\s+((?:"?[A-Za-z_][A-Za-z0-9_]*"?)(?:\.(?:"?[A-Za-z_][A-Za-z0-9_]*"?))?)'
)
_CTE_NAME_RE = re.compile(r'(?is)\b("?[A-Za-z_][A-Za-z0-9_]*"?)\s+AS\s*\(')
_NON_TABLE_TOKENS = {
    "lateral",
    "select",
    "unnest",
    "generate_series",
    "values",
    # Tipos / palabras reservadas que a veces el LLM coloca tras JOIN/FROM por error.
    "timestamp",
    "timestamptz",
    "date",
    "time",
    "interval",
    "boolean",
    "bool",
    "varchar",
    "char",
    "character",
    "text",
    "int",
    "integer",
    "bigint",
    "smallint",
    "numeric",
    "decimal",
    "float",
    "real",
    "double",
    "precision",
    "serial",
    "bigserial",
    "uuid",
    "json",
    "jsonb",
    "xml",
    "cast",
}


def _blank_special_calls_with_inner_from(sql: str) -> str:
    """Sustituye por espacios EXTRACT/SUBSTRING/TRIM/OVERLAY(...) para no confundir su FROM con FROM de relación."""
    chars = list(sql)
    n = len(sql)
    i = 0
    state = "normal"

    def find_matching_close(open_idx: int) -> int:
        depth = 0
        j = open_idx
        st = "normal"
        while j < n:
            c = sql[j]
            if st == "normal":
                if c == "'":
                    st = "sq"
                elif c == '"':
                    st = "dq"
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        return j
                j += 1
                continue
            if st == "sq":
                if c == "'" and j + 1 < n and sql[j + 1] == "'":
                    j += 2
                elif c == "'":
                    st = "normal"
                    j += 1
                else:
                    j += 1
                continue
            if st == "dq":
                if c == '"' and j + 1 < n and sql[j + 1] == '"':
                    j += 2
                elif c == '"':
                    st = "normal"
                    j += 1
                else:
                    j += 1
                continue
        return n - 1

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
            m = re.match(
                r"(?is)\b(?:EXTRACT|SUBSTRING|TRIM|OVERLAY)\s*\(",
                sql[i:],
            )
            if m:
                start = i
                open_paren = i + m.end() - 1
                close_paren = find_matching_close(open_paren)
                for k in range(start, close_paren + 1):
                    ch = chars[k]
                    if ch not in "'\"":
                        chars[k] = " "
                i = close_paren + 1
                continue
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
    return "".join(chars)


def _normalize_ident(token: str) -> str:
    t = token.strip()
    if t.startswith('"') and t.endswith('"') and len(t) >= 2:
        t = t[1:-1].replace('""', '"')
    return t


def _enforce_only_h_tables(sql_no_comments: str) -> None:
    """
    Restringe FROM/JOIN a objetos homologados `h_*` para el agente SQL.

    Activación por entorno:
      AGENTE_DWH_ONLY_H_TABLES=1
    """
    enabled = os.getenv("AGENTE_DWH_ONLY_H_TABLES", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not enabled:
        return

    scan_sql = _blank_special_calls_with_inner_from(sql_no_comments)
    ctes = {
        _normalize_ident(m.group(1)).lower()
        for m in _CTE_NAME_RE.finditer(sql_no_comments)
    }
    offenders: set[str] = set()
    for m in _TABLE_REF_RE.finditer(scan_sql):
        raw_ref = m.group(1)
        ref = _normalize_ident(raw_ref)
        parts = [_normalize_ident(p) for p in ref.split(".")]
        obj = parts[-1].lower() if parts else ""
        if not obj or obj in _NON_TABLE_TOKENS or obj in ctes:
            continue
        if not obj.startswith("h_"):
            offenders.add(obj)

    if offenders:
        refs = ", ".join(sorted(offenders))
        raise RuntimeError(
            "Prevalidación SQL: en este entorno solo se permiten objetos homologados `h_*` en FROM/JOIN. "
            f"Detectado: {refs}. Usa únicamente vistas h_* del esquema de referencia."
        )


def vgd_execution_guard_enabled(*, database_url: str = "") -> bool:
    """
    Activa validación ligera antes de ejecutar en PostgreSQL (p. ej. COUNT() vacío).
    Siempre activa en este producto: el DWH objetivo es vgd_dwh_prod_migracion.
    """
    import os

    if os.getenv("AGENTE_DWH_DISABLE_SQL_GUARD", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    return True


def validate_vgd_dwh_sql(sql: str) -> None:
    """
    Validación extra para SQL contra el DWH PostgreSQL: COUNT() vacío y tablas demo inexistentes (sales/vehicles).

    Usa el mismo enmascarado de literales que validate_read_only_sql para reducir falsos positivos.
    Lanza RuntimeError con mensaje en español (el agente puede reenviarlo al LLM como corrección).
    """
    if not sql or not sql.strip():
        return
    without_comments = _strip_sql_comments(sql)
    masked = _mask_quoted_for_scan(without_comments)
    upper = masked.upper()

    for tbl in _forbidden_tables_from_env():
        if _sql_references_table(upper, tbl):
            raise RuntimeError(
                f"Prevalidación SQL: la tabla «{tbl.lower()}» está marcada como no permitida para este entorno "
                "(AGENTE_DWH_FORBIDDEN_TABLES). Usa únicamente tablas del esquema de referencia."
            )

    _enforce_only_h_tables(without_comments)

    if _COUNT_EMPTY_RE.search(masked):
        raise RuntimeError(
            "Prevalidación SQL: COUNT() sin argumento no es válido en PostgreSQL; usa COUNT(*) o COUNT(nombre_columna)."
        )
