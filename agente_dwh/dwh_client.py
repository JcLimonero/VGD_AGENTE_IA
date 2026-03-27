"""Implementación principal del cliente DWH."""

from dataclasses import dataclass
import time
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from . import sql_rewrites
from .cache import QueryCacheBackend, build_query_cache
from .db_engine import create_dwh_engine
from .dialects import (
    normalize_sql_for_dialect,
    rewrite_postgresql_undefined_column_retry,
    rewrite_postgresql_undefined_table_retry,
)
from .error_subagent import log_error_and_run_subagent
from .observability import record_query_event
from .query_executor import QueryExecutor, inject_limit_if_missing
from .sql_guard import (
    validate_read_only_sql,
    validate_vgd_dwh_sql,
    vgd_execution_guard_enabled,
)


@dataclass
class DwhClient:
    engine: Engine
    default_limit: int = 200
    cache_ttl_seconds: int = 120
    cache_max_entries: int = 500
    cache_backend: str = "local"
    cache_redis_url: str = ""
    cache_redis_namespace: str = "agente_dwh:sql"

    def __post_init__(self) -> None:
        self._cache: QueryCacheBackend = build_query_cache(
            backend=self.cache_backend,
            ttl_seconds=self.cache_ttl_seconds,
            max_entries=self.cache_max_entries,
            redis_url=self.cache_redis_url,
            redis_namespace=self.cache_redis_namespace,
        )
        self._executor = QueryExecutor(self.engine)
        self._last_execution_info: dict[str, Any] = {}

    @classmethod
    def from_url(
        cls,
        database_url: str,
        default_limit: int = 200,
        cache_ttl_seconds: int = 120,
        cache_max_entries: int = 500,
        *,
        cache_backend: str = "local",
        cache_redis_url: str = "",
        cache_redis_namespace: str = "agente_dwh:sql",
    ) -> "DwhClient":
        engine = create_dwh_engine(database_url)
        return cls(
            engine=engine,
            default_limit=default_limit,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_max_entries=cache_max_entries,
            cache_backend=cache_backend,
            cache_redis_url=cache_redis_url,
            cache_redis_namespace=cache_redis_namespace,
        )

    @property
    def dialect_name(self) -> str:
        return (self.engine.dialect.name or "").lower()

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        stripped = sql.strip()
        validated = validate_read_only_sql(stripped)
        start = time.perf_counter()
        self._last_execution_info = {
            "auto_retry_undefined_column": False,
            "retry_applied": False,
        }
        normalized_sql = self._normalize_sql_for_dialect(validated)
        if self.dialect_name == "postgresql" and vgd_execution_guard_enabled(
            database_url=str(self.engine.url)
        ):
            validate_vgd_dwh_sql(normalized_sql)

        sql_with_limit = self._inject_limit_if_missing(normalized_sql)
        cached_rows = self._get_cached_rows(sql_with_limit)
        if cached_rows is not None:
            self._last_execution_info = {
                "auto_retry_undefined_column": False,
                "retry_applied": False,
                "cached": True,
            }
            record_query_event(
                source="dwh",
                success=True,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=len(cached_rows),
                cached=True,
            )
            return cached_rows

        try:
            rows = self._executor.run_select(sql_with_limit)
            self._set_cache_rows(sql_with_limit, rows)
            self._last_execution_info = {
                "auto_retry_undefined_column": False,
                "retry_applied": False,
                "cached": False,
            }
            record_query_event(
                source="dwh",
                success=True,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=len(rows),
                cached=False,
            )
            return rows
        except SQLAlchemyError as exc:
            retry_sql = None
            retry_exc: SQLAlchemyError | None = None
            subagent_retry_exc: Exception | None = None
            if self.dialect_name == "postgresql":
                retry_sql = self._rewrite_postgresql_undefined_column_retry(
                    sql_with_limit, str(exc)
                )
                if not retry_sql:
                    retry_sql = self._rewrite_postgresql_undefined_table_retry(
                        sql_with_limit, str(exc)
                    )
                if not retry_sql and "operator does not exist" in str(exc).lower():
                    from . import sql_rewrites as _sr
                    candidate = _sr.rewrite_h_agencies_surrogate_id_in_joins(sql_with_limit)
                    if candidate != sql_with_limit:
                        retry_sql = candidate
            if retry_sql and retry_sql != sql_with_limit:
                try:
                    if self.dialect_name == "postgresql" and vgd_execution_guard_enabled(
                        database_url=str(self.engine.url)
                    ):
                        validate_vgd_dwh_sql(retry_sql)
                    rows = self._executor.run_select(retry_sql)
                    self._set_cache_rows(sql_with_limit, rows)
                    self._set_cache_rows(retry_sql, rows)
                    self._last_execution_info = {
                        "auto_retry_undefined_column": True,
                        "retry_applied": True,
                        "cached": False,
                        "reason": (
                            "undefined_column"
                            if "column" in str(exc).lower()
                            else "undefined_table"
                        ),
                    }
                    record_query_event(
                        source="dwh",
                        success=True,
                        duration_ms=(time.perf_counter() - start) * 1000.0,
                        row_count=len(rows),
                        cached=False,
                        message="auto_retry_undefined_column",
                    )
                    return rows
                except SQLAlchemyError as rex:
                    retry_exc = rex

            # Segundo intento opcional: corrección heurística del subagente.
            subagent_sql = retry_sql if (retry_sql and retry_sql != sql_with_limit) else sql_with_limit
            try:
                fix_results = log_error_and_run_subagent(
                    source="dwh_execute_select",
                    message=str(retry_exc or exc),
                    context={"sql": subagent_sql, "dialect": self.dialect_name},
                )
                fixed_sql = next(
                    (
                        r.fixed_sql
                        for r in fix_results
                        if getattr(r, "fixed_sql", None)
                        and str(r.fixed_sql).strip()
                        and str(r.fixed_sql).strip() != sql_with_limit.strip()
                    ),
                    None,
                )
                if fixed_sql:
                    candidate_sql = self._inject_limit_if_missing(
                        self._normalize_sql_for_dialect(validate_read_only_sql(fixed_sql.strip()))
                    )
                    if self.dialect_name == "postgresql" and vgd_execution_guard_enabled(
                        database_url=str(self.engine.url)
                    ):
                        validate_vgd_dwh_sql(candidate_sql)
                    rows = self._executor.run_select(candidate_sql)
                    self._set_cache_rows(sql_with_limit, rows)
                    self._set_cache_rows(candidate_sql, rows)
                    self._last_execution_info = {
                        "auto_retry_undefined_column": bool(retry_sql),
                        "retry_applied": True,
                        "cached": False,
                        "reason": "subagent_fix",
                    }
                    record_query_event(
                        source="dwh",
                        success=True,
                        duration_ms=(time.perf_counter() - start) * 1000.0,
                        row_count=len(rows),
                        cached=False,
                        message="auto_retry_subagent_fix",
                    )
                    return rows
            except Exception as sub_exc:  # noqa: BLE001
                subagent_retry_exc = sub_exc

            self._last_execution_info = {
                "auto_retry_undefined_column": bool(retry_sql),
                "retry_applied": False,
                "cached": False,
                "failed": True,
                "subagent_retry_error": str(subagent_retry_exc) if subagent_retry_exc else "",
            }
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(retry_exc or exc),
            )
            if retry_exc is not None:
                raise RuntimeError(f"Error ejecutando consulta en DWH: {retry_exc}") from retry_exc
            raise RuntimeError(f"Error ejecutando consulta en DWH: {exc}") from exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        return self.execute_select(sql)

    def get_cache_stats(self) -> dict[str, Any]:
        base = self._cache.stats()
        base.update(
            {
                "ttl_seconds": self.cache_ttl_seconds,
                "max_entries": self.cache_max_entries,
                "backend": self._cache.backend_name,
            }
        )
        return base

    def get_last_execution_info(self) -> dict[str, Any]:
        return dict(self._last_execution_info)

    def _get_cached_rows(self, sql: str) -> list[dict[str, Any]] | None:
        return self._cache.get(sql)

    def _set_cache_rows(self, sql: str, rows: list[dict[str, Any]]) -> None:
        self._cache.set(sql, rows)

    def _inject_limit_if_missing(self, sql: str) -> str:
        return inject_limit_if_missing(sql, self.default_limit)

    def _normalize_sql_for_dialect(self, sql: str) -> str:
        return normalize_sql_for_dialect(sql, self.dialect_name)

    def _quote_postgresql_mixed_case_identifiers(self, sql: str) -> str:
        return sql_rewrites.quote_postgresql_mixed_case_identifiers(sql)

    def _rewrite_postgresql_h_view_legacy_identifiers(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_h_view_legacy_identifiers(sql)

    def _rewrite_postgresql_undefined_column_retry(self, sql: str, err: str) -> str | None:
        return rewrite_postgresql_undefined_column_retry(sql, err)

    def _rewrite_postgresql_undefined_table_retry(self, sql: str, err: str) -> str | None:
        return rewrite_postgresql_undefined_table_retry(sql, err)

    def _rewrite_postgresql_idagency_equality_cast(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_idagency_equality_cast(sql)

    def _rewrite_postgresql_group_by_year_alias(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_group_by_year_alias(sql)

    def _normalize_sqlite_sql(self, sql: str) -> str:
        return sql_rewrites.normalize_sqlite_sql(sql)

    def _rewrite_interval_arithmetic(self, sql: str) -> str:
        return sql_rewrites.rewrite_interval_arithmetic(sql)

    def _rewrite_window_avg_misuse(self, sql: str) -> str:
        return sql_rewrites.rewrite_window_avg_misuse(sql)

    def _rewrite_sales_status_aliases(self, sql: str) -> str:
        return sql_rewrites.rewrite_sales_status_aliases(sql)

    def _rewrite_service_appointments_aliases(self, sql: str) -> str:
        return sql_rewrites.rewrite_service_appointments_aliases(sql)

    def _rewrite_insurance_policies_policy_status(self, sql: str) -> str:
        return sql_rewrites.rewrite_insurance_policies_policy_status(sql)

    @staticmethod
    def _parse_round_call_args(sql: str, open_paren_idx: int) -> tuple[str, str | None, int] | None:
        return sql_rewrites.parse_round_call_args(sql, open_paren_idx)

    def _rewrite_postgresql_round_two_arg(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_round_two_arg(sql)

    def _rewrite_postgresql_extract_epoch_from_date_subtraction(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_extract_epoch_from_date_subtraction(sql)

    def _rewrite_postgresql_count_empty_parentheses(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_count_empty_parentheses(sql)

    def _rewrite_postgresql_mysql_style_date_parts(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_mysql_style_date_parts(sql)

    def _rewrite_postgresql_invalid_interval_literal_cast(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_invalid_interval_literal_cast(sql)
