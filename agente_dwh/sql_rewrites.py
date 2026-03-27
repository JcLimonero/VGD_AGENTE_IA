"""Reescrituras SQL reutilizables por dialecto."""

from __future__ import annotations

import re

# Identificadores mixtos (camelCase/PascalCase) que en PostgreSQL requieren comillas dobles.
PG_MIXED_CASE_IDENTIFIERS: tuple[str, ...] = (
    "idAgency",
    "ndClientDMS",
    "isActive",
    "IsMatriz",
    "tokenAppoinments",
    "customerName",
    "statusDescription",
    "typeDescription",
    "sendedSalesForce",
    "idSalesForce",
    "resultSF",
    "sf_jsonRequest",
    "IdStatus",
    "idServiceType",
    "serviceType",
    "serviceTypeDescription",
    "serviceTypeDetail",
    "startDateTime",
    "endDateTime",
    "ndConsultant",
    "consultantName",
    "consultantMail",
    "seller_Name",
    "seller_Email",
    "Est_Civil",
)


def to_snake_case(identifier: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", identifier)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s or identifier.lower()


HOMOLOGATED_LEGACY_IDENTIFIER_MAP: dict[str, str] = {
    **{name: to_snake_case(name) for name in PG_MIXED_CASE_IDENTIFIERS},
    "Id": "id",
}


H_VIEW_TABLE_COLUMN_FALLBACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "h_agencies": {
        "agency_name": ("name",),
        "nombre_agencia": ("name",),
        "agencia_nombre": ("name",),
        "branch_name": ("name",),
        "dealer_name": ("name",),
        "agency_id": ("id_agency",),
    },
    "h_customers": {
        "created_at": ("timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "id_client": ("nd_client_dms",),
        "client_id": ("nd_client_dms",),
        "customer_id": ("nd_client_dms",),
        "nd_client": ("nd_client_dms",),
        "customer_name": ("name",),
        "client_name": ("name",),
        "full_name": ("name",),
        "nombre": ("name",),
        "email": ("mail",),
    },
    "h_orders": {
        "created_at": ("delivery_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "id_client": ("nd_client_dms",),
        "client_id": ("nd_client_dms",),
        "customer_id": ("nd_client_dms",),
        "nd_client": ("nd_client_dms",),
        "order_date": ("delivery_date",),
        "order_timestamp": ("delivery_date", "timestamp_dms", "timestamp"),
        "date": ("delivery_date",),
        "order_id": ("order_dms",),
        "status": ("status_description",),
        "order_status": ("status_description",),
    },
    "h_invoices": {
        "created_at": ("billing_date", "delivery_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "invoice_date": ("billing_date",),
        "date": ("billing_date",),
        "invoice_id": ("invoice_reference",),
    },
    "h_services": {
        "created_at": ("service_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "date": ("service_date",),
        "service_name": ("service_to_perform",),
        "cost": ("amount",),
        "price": ("amount",),
    },
    "h_inventory": {
        "created_at": ("timestamp_created", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp_updated", "timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "price": ("amount",),
        "cost": ("amount",),
    },
    "h_customer_vehicle": {
        "created_at": ("timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
        "agency_id": ("id_agency",),
        "id_client": ("nd_client_dms",),
        "nd_client": ("nd_client_dms",),
        "client_id": ("nd_client_dms",),
        "customer_id": ("nd_client_dms",),
    },
}


def quote_postgresql_mixed_case_identifiers(sql: str) -> str:
    idset = set(PG_MIXED_CASE_IDENTIFIERS)
    out: list[str] = []
    i = 0
    n = len(sql)
    state = "normal"  # normal | sq | dq

    while i < n:
        c = sql[i]
        if state == "normal":
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
            if c.isalpha() or c == "_":
                j = i + 1
                while j < n and (sql[j].isalnum() or sql[j] == "_"):
                    j += 1
                token = sql[i:j]
                if token in idset:
                    out.append(f'"{token}"')
                else:
                    out.append(token)
                i = j
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


def rewrite_postgresql_h_view_legacy_identifiers(sql: str) -> str:
    if not re.search(
        r'(?is)\b(?:FROM|JOIN)\s+(?:"?[A-Za-z_][A-Za-z0-9_]*"?\.)?"?h_[A-Za-z_][A-Za-z0-9_]*"?\b',
        sql,
    ):
        return sql

    out = sql
    for legacy, homologated in HOMOLOGATED_LEGACY_IDENTIFIER_MAP.items():
        out = out.replace(f'"{legacy}"', f'"{homologated}"')

    out = re.sub(
        r'"(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"',
        lambda m: (
            f'"{to_snake_case(m.group("ident"))}"'
            if re.search(r"[a-z]", m.group("ident"))
            and re.search(r"[A-Z]", m.group("ident"))
            else m.group(0)
        ),
        out,
    )

    out = re.sub(
        r'(?P<prefix>\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)(?P<ident>[A-Za-z_][A-Za-z0-9_]*)\b',
        lambda m: (
            f'{m.group("prefix")}{to_snake_case(m.group("ident"))}'
            if re.search(r"[a-z]", m.group("ident"))
            and re.search(r"[A-Z]", m.group("ident"))
            else m.group(0)
        ),
        out,
    )
    return out


def rewrite_postgresql_undefined_column_retry(sql: str, err: str) -> str | None:
    if not re.search(
        r'(?is)\b(?:FROM|JOIN)\s+(?:"?[A-Za-z_][A-Za-z0-9_]*"?\.)?"?h_[A-Za-z_][A-Za-z0-9_]*"?\b',
        sql,
    ):
        return None
    m = re.search(
        r'(?is)\bcolumn\s+(?P<col>(?:"?[\w]+"?)(?:\.(?:"?[\w]+"?))?)\s+does not exist\b',
        err,
    )
    if not m:
        return None

    col_ref = m.group("col").strip()
    alias_to_table: dict[str, str] = {}
    for mt in re.finditer(
        r'(?is)\b(?:FROM|JOIN)\s+(?:"?(?P<table>h_[A-Za-z_][A-Za-z0-9_]*)"?)(?:\s+(?:AS\s+)?(?!(?:ON|USING|WHERE|GROUP|ORDER|LIMIT|JOIN|LEFT|RIGHT|FULL|INNER|CROSS)\b)(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?',
        sql,
    ):
        table = (mt.group("table") or "").lower()
        alias_raw = (mt.group("alias") or "").strip('"').lower()
        alias = table if not alias_raw else alias_raw
        if table:
            alias_to_table[alias] = table

    parts = [p.strip() for p in col_ref.split(".")]
    if not parts:
        return None
    legacy_ident = parts[-1].strip('"')
    snake_ident = to_snake_case(legacy_ident)

    out = sql
    replaced = False
    if len(parts) == 2:
        alias = parts[0].strip('"')
        if legacy_ident != snake_ident:
            next_out = re.sub(
                rf'(?i)\b{re.escape(alias)}\s*\.\s*"{re.escape(legacy_ident)}"\b',
                f'{alias}."{snake_ident}"',
                out,
            )
            next_out = re.sub(
                rf'(?i)\b{re.escape(alias)}\s*\.\s*{re.escape(legacy_ident)}\b',
                f'{alias}."{snake_ident}"',
                next_out,
            )
            replaced = replaced or (next_out != out)
            out = next_out
        if not replaced:
            table = alias_to_table.get(alias.lower())
            for cand in H_VIEW_TABLE_COLUMN_FALLBACKS.get(table or "", {}).get(
                legacy_ident.lower(), ()
            ):
                next_out = re.sub(
                    rf'(?i)\b{re.escape(alias)}\s*\.\s*"{re.escape(legacy_ident)}"\b',
                    f'{alias}."{cand}"',
                    out,
                )
                next_out = re.sub(
                    rf'(?i)\b{re.escape(alias)}\s*\.\s*{re.escape(legacy_ident)}\b',
                    f'{alias}."{cand}"',
                    next_out,
                )
                if next_out != out:
                    out = next_out
                    replaced = True
                    break
    else:
        if legacy_ident != snake_ident:
            next_out = re.sub(
                rf'(?i)"{re.escape(legacy_ident)}"',
                f'"{snake_ident}"',
                out,
            )
            next_out = re.sub(
                rf'(?i)\b{re.escape(legacy_ident)}\b',
                f'"{snake_ident}"',
                next_out,
            )
            replaced = replaced or (next_out != out)
            out = next_out
        if not replaced and len(alias_to_table) == 1:
            only_table = next(iter(alias_to_table.values()))
            for cand in H_VIEW_TABLE_COLUMN_FALLBACKS.get(only_table, {}).get(
                legacy_ident.lower(), ()
            ):
                next_out = re.sub(
                    rf'(?i)"{re.escape(legacy_ident)}"',
                    f'"{cand}"',
                    out,
                )
                next_out = re.sub(
                    rf'(?i)\b{re.escape(legacy_ident)}\b',
                    f'"{cand}"',
                    next_out,
                )
                if next_out != out:
                    out = next_out
                    replaced = True
                    break

    out = _fix_h_agencies_id_in_joins(out, alias_to_table)
    out = rewrite_postgresql_h_view_legacy_identifiers(out)
    return out if out != sql else None


def _fix_h_agencies_id_in_joins(sql: str, alias_to_table: dict[str, str]) -> str:
    """Corrige alias.id → alias.id_agency cuando el alias apunta a h_agencies."""
    out = sql
    for alias, table in alias_to_table.items():
        if table != "h_agencies":
            continue
        out = _apply_h_agencies_alias_id_fix(out, alias)
    return out


def _apply_h_agencies_alias_id_fix(sql: str, alias: str) -> str:
    """Reemplaza alias.id por alias.id_agency en comparaciones con id_agency."""
    out = sql
    out = re.sub(
        rf'(?i)\b{re.escape(alias)}\s*\.\s*id\s*=\s*(\S+\.\s*"?id_agency"?)\b',
        rf"{alias}.id_agency = \1",
        out,
    )
    out = re.sub(
        rf'(?i)(\S+\.\s*"?id_agency"?)\s*=\s*{re.escape(alias)}\s*\.\s*id\b(?!_)',
        rf"\1 = {alias}.id_agency",
        out,
    )
    return out


def rewrite_h_agencies_surrogate_id_in_joins(sql: str) -> str:
    """
    Normalización proactiva: en consultas con h_*, reemplaza h_agencies alias.id
    por alias.id_agency en condiciones de JOIN para evitar text = bigint.
    """
    if not re.search(
        r'(?is)\b(?:FROM|JOIN)\s+h_agencies\b', sql,
    ):
        return sql

    aliases: list[str] = []
    for m in re.finditer(
        r'(?is)\b(?:FROM|JOIN)\s+h_agencies'
        r'(?:\s+(?:AS\s+)?(?!(?:ON|USING|WHERE|GROUP|ORDER|LIMIT|JOIN|LEFT|RIGHT|FULL|INNER|CROSS)\b)'
        r'(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?',
        sql,
    ):
        alias = (m.group("alias") or "h_agencies").strip()
        if alias:
            aliases.append(alias)

    out = sql
    for alias in aliases:
        out = _apply_h_agencies_alias_id_fix(out, alias)
    return out


def rewrite_postgresql_undefined_table_retry(sql: str, err: str) -> str | None:
    """
    Reescritura para errores de tabla inexistente en vistas homologadas `h_*`.

    Casos comunes:
    - h_client / h_clients -> h_customers
    - id_client -> nd_client_dms (en h_customers)
    - joins por agencia con `a.id` -> `a.id_agency`
    """
    if "does not exist" not in err.lower() or "relation" not in err.lower():
        return None

    out = sql
    changed = False

    _TABLE_SINGULAR_TO_PLURAL: dict[str, str] = {
        "h_clients": "h_customers",
        "h_client": "h_customers",
        "h_customer": "h_customers",
        "h_order": "h_orders",
        "h_invoice": "h_invoices",
        "h_service": "h_services",
        "h_agency": "h_agencies",
    }
    for wrong, correct in _TABLE_SINGULAR_TO_PLURAL.items():
        next_out = re.sub(rf"(?i)\b{re.escape(wrong)}\b", correct, out)
        changed = changed or (next_out != out)
        out = next_out

    # Columnas legacy frecuentes en h_customers.
    next_out = re.sub(r'(?i)(\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)id_client\b', r'\1nd_client_dms', out)
    next_out = re.sub(r'(?i)(?<!\.)\bid_client\b', "nd_client_dms", next_out)
    changed = changed or (next_out != out)
    out = next_out

    # Join por agencia: en h_agencies la columna correcta es id_agency.
    next_out = re.sub(
        r'(?i)(\bh_agencies\s+[A-Za-z_][A-Za-z0-9_]*\s+JOIN\s+[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\s+ON\s+)([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*id\s*=',
        r"\1\2.id_agency =",
        out,
    )
    changed = changed or (next_out != out)
    out = next_out

    out = rewrite_postgresql_h_view_legacy_identifiers(out)
    return out if changed and out != sql else None


def rewrite_postgresql_idagency_equality_cast(sql: str) -> str:
    pattern = re.compile(
        r'(?P<l>[A-Za-z_][A-Za-z0-9_]*\s*\.\s*"idAgency")\s*=\s*(?P<r>[A-Za-z_][A-Za-z0-9_]*\s*\.\s*"idAgency")',
        flags=re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        left = re.sub(r"\s+", "", match.group("l"))
        right = re.sub(r"\s+", "", match.group("r"))
        if "::text" in left.lower() and "::text" in right.lower():
            return match.group(0)
        return f"{left}::text = {right}::text"

    return pattern.sub(repl, sql)


def rewrite_service_type_equality_to_ilike(sql: str) -> str:
    """
    Convierte comparaciones exactas de service_type a ILIKE con wildcards usando
    solo la primera palabra significativa del literal (evita que el LLM expanda
    el valor con texto inventado como 'MANTENIMIENTO Y SERVICIO MECANICA').
    service_type = 'VALOR'  →  service_type ILIKE '%primera_palabra%'
    service_type != 'VALOR' →  service_type NOT ILIKE '%primera_palabra%'
    """
    _STOP_WORDS = {"y", "e", "de", "del", "la", "el", "los", "las", "a", "en", "por", "and", "or"}

    def _keyword(literal: str) -> str:
        """Devuelve la palabra más significativa del literal."""
        words = [w for w in re.split(r'[\s/]+', literal) if w.lower() not in _STOP_WORDS and len(w) > 2]
        return words[0] if words else literal

    def to_ilike(m: re.Match[str]) -> str:
        prefix = m.group(1)
        neg = m.group(2)
        literal = m.group(3)
        op = "NOT ILIKE" if neg in ("!=", "<>") else "ILIKE"
        keyword = _keyword(literal)
        return f"{prefix} {op} '%{keyword}%'"

    out = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*(?:\s*\.\s*)?(?:"?service_type"?))\s*(!?=|<>)\s*\'([^\']+)\'',
        to_ilike,
        sql,
        flags=re.IGNORECASE,
    )
    return out


def rewrite_postgresql_nd_client_dms_cast(sql: str) -> str:
    """
    h_orders/h_invoices/h_services.nd_client_dms es TEXT pero h_customers.id es BIGINT.
    Reescribe comparaciones nd_client_dms = <alias>.id (y la inversa) añadiendo
    CAST(<alias>.id AS TEXT) para evitar 'operator does not exist: text = bigint'.
    """
    # Patrón: <alias>."nd_client_dms" = <alias>.id  o  <alias>.nd_client_dms = <alias>.id
    # también el caso invertido: <alias>.id = <alias>.nd_client_dms
    nd_expr = r'(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*(?:"nd_client_dms"|nd_client_dms))'
    id_expr = r'([A-Za-z_][A-Za-z0-9_]*\s*\.\s*id)\b'

    # nd_client_dms = alias.id  →  nd_client_dms = CAST(alias.id AS TEXT)
    out = re.sub(
        rf'({nd_expr})\s*=\s*{id_expr}(?!\s*::text)',
        lambda m: f'{m.group(1)} = CAST({m.group(2)} AS TEXT)',
        sql,
        flags=re.IGNORECASE,
    )
    # alias.id = nd_client_dms  →  CAST(alias.id AS TEXT) = nd_client_dms
    out = re.sub(
        rf'{id_expr}(?!\s*::text)\s*=\s*({nd_expr})',
        lambda m: f'CAST({m.group(1)} AS TEXT) = {m.group(2)}',
        out,
        flags=re.IGNORECASE,
    )
    return out


def rewrite_postgresql_group_by_year_alias(sql: str) -> str:
    lower = sql.lower()
    if " as year" not in lower or "group by" not in lower or "extract(year from" not in lower:
        return sql

    m = re.search(
        r"(?is)\bgroup\s+by\b(?P<group>.*?)(?=\border\s+by\b|\blimit\b|$)",
        sql,
    )
    if not m:
        return sql

    group_part = m.group("group")
    group_lower = group_part.lower()
    if " year" in group_lower or re.search(r"(?i)\b1\b", group_part):
        return sql

    new_group = group_part.rstrip() + ", year "
    return sql[: m.start("group")] + new_group + sql[m.end("group") :]


def rewrite_interval_arithmetic(sql: str) -> str:
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

    return re.sub(
        r"(?P<func>date|datetime)\s*\(\s*'now'\s*\)\s*(?P<sign>[+-])\s*interval\s*'(?P<amount>\d+)\s+(?P<unit>day|month|year)s?'",
        _replace_with_sign,
        sql,
        flags=re.IGNORECASE,
    )


def rewrite_window_avg_misuse(sql: str) -> str:
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


def normalize_sqlite_sql(sql: str) -> str:
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
    normalized = rewrite_interval_arithmetic(normalized)
    normalized = rewrite_window_avg_misuse(normalized)
    return normalized


def rewrite_sales_status_aliases(sql: str) -> str:
    return re.sub(
        r"(?i)(?P<prefix>\b(?:[A-Za-z_][A-Za-z0-9_]*\.)?status)\s*=\s*'completed'",
        r"\g<prefix> IN ('completed', 'entregada', 'facturada', 'cerrada')",
        sql,
    )


def rewrite_service_appointments_aliases(sql: str) -> str:
    lowered = sql.lower()
    if "service_appointments" not in lowered:
        return sql

    def _replace_prefixed(column: str, real_column: str, source_sql: str) -> str:
        updated = re.sub(
            rf"(?i)(\bservice_appointments\s*\.\s*){column}\b",
            rf"\1{real_column}",
            source_sql,
        )
        alias_matches = re.findall(
            r"(?i)\b(?:from|join)\s+service_appointments(?:\s+as)?\s+([A-Za-z_][A-Za-z0-9_]*)",
            updated,
        )
        for alias in alias_matches:
            updated = re.sub(
                rf"(?i)(\b{re.escape(alias)}\s*\.\s*){column}\b",
                rf"\1{real_column}",
                updated,
            )
        return updated

    normalized = _replace_prefixed("status", "appointment_status", sql)
    normalized = _replace_prefixed("scheduled_date", "appointment_date", normalized)
    normalized = _replace_prefixed("service_date", "appointment_date", normalized)
    normalized = _replace_prefixed("appointment_time", "appointment_date", normalized)
    normalized = _replace_prefixed("advisor", "workshop", normalized)

    has_other_status_tables = re.search(
        r"(?i)\b(?:from|join)\s+(sales|services)\b",
        normalized,
    )
    if not has_other_status_tables:
        normalized = re.sub(r"(?i)(?<!\.)\bstatus\b", "appointment_status", normalized)
        normalized = re.sub(r"(?i)(?<!\.)\bscheduled_date\b", "appointment_date", normalized)
        normalized = re.sub(r"(?i)(?<!\.)\bservice_date\b", "appointment_date", normalized)
        normalized = re.sub(r"(?i)(?<!\.)\bappointment_time\b", "appointment_date", normalized)
        normalized = re.sub(r"(?i)(?<!\.)\badvisor\b", "workshop", normalized)

    return normalized


def rewrite_insurance_policies_policy_status(sql: str) -> str:
    if "insurance_policies" not in sql.lower():
        return sql
    out = sql
    out = re.sub(
        r"(?i)(\bpolicy_status\s+IN\s*\(\s*)'active'\s*,\s*'vence_pronto'\s*(\))",
        r"\1'activa'\2",
        out,
    )
    out = re.sub(
        r"(?i)(\bpolicy_status\s+IN\s*\(\s*)'vence_pronto'\s*,\s*'active'\s*(\))",
        r"\1'activa'\2",
        out,
    )
    out = re.sub(r"(?i)(\bpolicy_status\s*=\s*)'active'", r"\1'activa'", out)
    out = re.sub(r"(?i)(\bpolicy_status\s*=\s*)'vence_pronto'", r"\1'activa'", out)
    out = re.sub(
        r"(?i)(\binsurance_policies\s*\.\s*policy_status\s*=\s*)'active'",
        r"\1'activa'",
        out,
    )
    out = re.sub(
        r"(?i)(\binsurance_policies\s*\.\s*policy_status\s*=\s*)'vence_pronto'",
        r"\1'activa'",
        out,
    )
    alias_matches = re.findall(
        r"(?i)\b(?:from|join)\s+insurance_policies(?:\s+as)?\s+([A-Za-z_][A-Za-z0-9_]*)",
        out,
    )
    for alias in alias_matches:
        out = re.sub(
            rf"(?i)(\b{re.escape(alias)}\s*\.\s*policy_status\s*=\s*)'active'",
            r"\1'activa'",
            out,
        )
        out = re.sub(
            rf"(?i)(\b{re.escape(alias)}\s*\.\s*policy_status\s*=\s*)'vence_pronto'",
            r"\1'activa'",
            out,
        )
    return out


def parse_round_call_args(sql: str, open_paren_idx: int) -> tuple[str, str | None, int] | None:
    if open_paren_idx >= len(sql) or sql[open_paren_idx] != "(":
        return None

    depth = 1
    i = open_paren_idx + 1
    first_start = i
    in_string = False

    while i < len(sql) and depth >= 1:
        c = sql[i]
        if in_string:
            if c == "\\" and i + 1 < len(sql):
                i += 2
                continue
            if c == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if c == "'":
            in_string = True
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return (sql[first_start:i].strip(), None, i + 1)
        elif c == "," and depth == 1:
            first = sql[first_start:i].strip()
            i += 1
            sec_start = i
            depth = 1
            in_string = False
            while i < len(sql):
                c = sql[i]
                if in_string:
                    if c == "\\" and i + 1 < len(sql):
                        i += 2
                        continue
                    if c == "'":
                        if i + 1 < len(sql) and sql[i + 1] == "'":
                            i += 2
                            continue
                        in_string = False
                    i += 1
                    continue
                if c == "'":
                    in_string = True
                    i += 1
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        second = sql[sec_start:i].strip()
                        return (first, second, i + 1)
                i += 1
            return None
        i += 1
    return None


def rewrite_postgresql_round_two_arg(sql: str) -> str:
    round_re = re.compile(r"\bROUND\s*\(", re.IGNORECASE)
    out: list[str] = []
    pos = 0
    for m in round_re.finditer(sql):
        open_idx = m.end() - 1
        parsed = parse_round_call_args(sql, open_idx)
        if parsed is None:
            continue
        first, second, end = parsed
        if second is None:
            continue
        second_clean = second.strip()
        if not re.fullmatch(r"-?\d+", second_clean):
            continue
        fl = first.lower()
        if "::numeric" in fl or "::decimal" in fl:
            out.append(sql[pos : m.start()])
            out.append(sql[m.start() : end])
            pos = end
            continue
        out.append(sql[pos : m.start()])
        out.append(sql[m.start() : open_idx + 1])
        out.append(f"({first})::numeric, {second_clean})")
        pos = end
    out.append(sql[pos:])
    return "".join(out)


def rewrite_postgresql_extract_epoch_from_date_subtraction(sql: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group("inner").strip()
        binop = re.fullmatch(
            r"([A-Za-z_][A-Za-z0-9_.]*)\s*-\s*([A-Za-z_][A-Za-z0-9_.]*)",
            inner,
        )
        if not binop:
            return match.group(0)
        left, right = binop.group(1), binop.group(2)
        return f"EXTRACT(EPOCH FROM ({left}::timestamp - {right}::timestamp))"

    return re.sub(
        r"EXTRACT\s*\(\s*EPOCH\s+FROM\s*\(\s*(?P<inner>[^()]+?)\s*\)\s*\)",
        repl,
        sql,
        flags=re.IGNORECASE,
    )


def rewrite_postgresql_count_empty_parentheses(sql: str) -> str:
    return re.sub(r"\bCOUNT\s*\(\s*\)", "COUNT(*)", sql, flags=re.IGNORECASE)


def rewrite_postgresql_mysql_style_date_parts(sql: str) -> str:
    for _ in range(10):
        pattern = re.compile(r"\b(YEAR|MONTH|DAY)\s*\(", re.IGNORECASE)
        out: list[str] = []
        i = 0
        changed = False
        while True:
            m = pattern.search(sql, i)
            if not m:
                out.append(sql[i:])
                break
            out.append(sql[i : m.start()])
            unit = m.group(1).upper()
            open_paren = m.end() - 1
            depth = 0
            j = open_paren
            while j < len(sql):
                ch = sql[j]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        inner = sql[open_paren + 1 : j].strip()
                        out.append(f"EXTRACT({unit} FROM {inner})")
                        i = j + 1
                        changed = True
                        break
                j += 1
            else:
                out.append(sql[m.start() :])
                break
        sql = "".join(out)
        if not changed:
            break
    return sql


def rewrite_postgresql_invalid_interval_literal_cast(sql: str) -> str:
    out = sql
    for lit in ("day", "days", "month", "months", "year", "years"):
        out = re.sub(
            rf"\)\s*::\s*interval\s+'{lit}'",
            ")",
            out,
            flags=re.IGNORECASE,
        )
    return out
