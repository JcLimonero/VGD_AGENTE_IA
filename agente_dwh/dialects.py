"""Normalización SQL por dialecto."""

from __future__ import annotations

from . import sql_rewrites


def normalize_sql_for_dialect(sql: str, dialect_name: str) -> str:
    """Normaliza diferencias comunes de sintaxis entre motores."""
    normalized = (
        sql.replace("≤", "<=")
        .replace("≥", ">=")
        .replace("≠", "!=")
    )
    normalized = sql_rewrites.rewrite_service_appointments_aliases(normalized)
    normalized = sql_rewrites.rewrite_sales_status_aliases(normalized)
    normalized = sql_rewrites.rewrite_insurance_policies_policy_status(normalized)
    normalized = sql_rewrites.rewrite_service_type_equality_to_ilike(normalized)

    if dialect_name == "sqlite":
        normalized = sql_rewrites.normalize_sqlite_sql(normalized)
    elif dialect_name == "postgresql":
        normalized = sql_rewrites.quote_postgresql_mixed_case_identifiers(normalized)
        normalized = sql_rewrites.rewrite_postgresql_h_view_legacy_identifiers(normalized)
        normalized = sql_rewrites.rewrite_h_agencies_surrogate_id_in_joins(normalized)
        normalized = sql_rewrites.rewrite_postgresql_idagency_equality_cast(normalized)
        normalized = sql_rewrites.rewrite_postgresql_nd_client_dms_cast(normalized)
        normalized = sql_rewrites.rewrite_postgresql_group_by_year_alias(normalized)
        normalized = sql_rewrites.rewrite_postgresql_count_empty_parentheses(normalized)
        normalized = sql_rewrites.rewrite_postgresql_mysql_style_date_parts(normalized)
        normalized = sql_rewrites.rewrite_postgresql_invalid_interval_literal_cast(normalized)
        normalized = sql_rewrites.rewrite_postgresql_extract_epoch_from_date_subtraction(normalized)
        normalized = sql_rewrites.rewrite_postgresql_round_two_arg(normalized)

    return normalized


def rewrite_postgresql_undefined_column_retry(sql: str, err: str) -> str | None:
    return sql_rewrites.rewrite_postgresql_undefined_column_retry(sql, err)


def rewrite_postgresql_undefined_table_retry(sql: str, err: str) -> str | None:
    return sql_rewrites.rewrite_postgresql_undefined_table_retry(sql, err)
