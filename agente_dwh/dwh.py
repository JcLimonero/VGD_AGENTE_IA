"""Compatibilidad pública de DWH.

Este módulo mantiene la ruta histórica `agente_dwh.dwh.DwhClient`
y delega en la implementación modular.
"""

from __future__ import annotations

from .dwh_client import DwhClient

__all__ = ["DwhClient"]
"""Compatibilidad: reexporta DwhClient modularizado."""

from .dwh_client import DwhClient

__all__ = ["DwhClient"]
"""Cliente de acceso al DWH."""

# from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from . import sql_rewrites
from .cache import QueryCacheBackend, build_query_cache
from .db_engine import create_dwh_engine
from .dialects import normalize_sql_for_dialect, rewrite_postgresql_undefined_column_retry
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
    """Cliente para ejecutar consultas contra el DWH."""

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
            if self.dialect_name == "postgresql":
                retry_sql = self._rewrite_postgresql_undefined_column_retry(
                    sql_with_limit, str(exc)
                )
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
                        "reason": "undefined_column",
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

            self._last_execution_info = {
                "auto_retry_undefined_column": bool(retry_sql),
                "retry_applied": False,
                "cached": False,
                "failed": True,
            }
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(retry_exc or exc),
            )
            try:
                log_error_and_run_subagent(
                    source="dwh_execute_select",
                    message=str(retry_exc or exc),
                    context={"sql": sql_with_limit, "dialect": self.dialect_name},
                )
            except Exception:
                pass
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

    # Wrappers de compatibilidad para tests/extensiones existentes.
    def _quote_postgresql_mixed_case_identifiers(self, sql: str) -> str:
        return sql_rewrites.quote_postgresql_mixed_case_identifiers(sql)

    def _rewrite_postgresql_h_view_legacy_identifiers(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_h_view_legacy_identifiers(sql)

    def _rewrite_postgresql_undefined_column_retry(self, sql: str, err: str) -> str | None:
        return rewrite_postgresql_undefined_column_retry(sql, err)

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
"""Cliente de acceso al DWH."""

# from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .cache import QueryCacheBackend, build_query_cache
from .db_engine import create_dwh_engine
from .dialects import normalize_sql_for_dialect, rewrite_postgresql_undefined_column_retry
from .error_subagent import log_error_and_run_subagent
from .observability import record_query_event
from .query_executor import QueryExecutor, inject_limit_if_missing
from .sql_guard import (
    validate_read_only_sql,
    validate_vgd_dwh_sql,
    vgd_execution_guard_enabled,
)
from . import sql_rewrites


@dataclass
class DwhClient:
    """Cliente para ejecutar consultas contra el DWH."""

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
            if self.dialect_name == "postgresql":
                retry_sql = self._rewrite_postgresql_undefined_column_retry(
                    sql_with_limit, str(exc)
                )
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
                        "reason": "undefined_column",
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

            self._last_execution_info = {
                "auto_retry_undefined_column": bool(retry_sql),
                "retry_applied": False,
                "cached": False,
                "failed": True,
            }
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(retry_exc or exc),
            )
            try:
                log_error_and_run_subagent(
                    source="dwh_execute_select",
                    message=str(retry_exc or exc),
                    context={"sql": sql_with_limit, "dialect": self.dialect_name},
                )
            except Exception:
                pass
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

    # Wrappers de compatibilidad para tests y extensiones existentes.
    def _quote_postgresql_mixed_case_identifiers(self, sql: str) -> str:
        return sql_rewrites.quote_postgresql_mixed_case_identifiers(sql)

    def _rewrite_postgresql_h_view_legacy_identifiers(self, sql: str) -> str:
        return sql_rewrites.rewrite_postgresql_h_view_legacy_identifiers(sql)

    def _rewrite_postgresql_undefined_column_retry(self, sql: str, err: str) -> str | None:
        return rewrite_postgresql_undefined_column_retry(sql, err)

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
"""Cliente de acceso al DWH."""

# from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
import time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .error_subagent import log_error_and_run_subagent
from .observability import record_query_event
from .sql_guard import (
    validate_read_only_sql,
    validate_vgd_dwh_sql,
    vgd_execution_guard_enabled,
)

# Identificadores mixtos (camelCase/PascalCase) que en PostgreSQL requieren comillas dobles.
_PG_MIXED_CASE_IDENTIFIERS: tuple[str, ...] = (
    "idAgency",
    "ndClientDMS",
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


def _to_snake_case(identifier: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", identifier)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s or identifier.lower()


_HOMOLOGATED_LEGACY_IDENTIFIER_MAP: dict[str, str] = {
    **{name: _to_snake_case(name) for name in _PG_MIXED_CASE_IDENTIFIERS},
    "Id": "id",
}

_H_VIEW_TABLE_COLUMN_FALLBACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "h_agencies": {
        "agency_name": ("name",),
        "nombre_agencia": ("name",),
        "agencia_nombre": ("name",),
        "branch_name": ("name",),
        "dealer_name": ("name",),
    },
    "h_customers": {
        "created_at": ("timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
    },
    "h_orders": {
        "created_at": ("delivery_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
    },
    "h_invoices": {
        "created_at": ("billing_date", "delivery_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
    },
    "h_services": {
        "created_at": ("service_date", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
    },
    "h_inventory": {
        "created_at": ("timestamp_created", "timestamp_dms", "timestamp"),
        "updated_at": ("timestamp_updated", "timestamp", "timestamp_dms"),
    },
    "h_customer_vehicle": {
        "created_at": ("timestamp_dms", "timestamp"),
        "updated_at": ("timestamp", "timestamp_dms"),
    },
}


@dataclass
class DwhClient:
    """Cliente para ejecutar consultas contra el DWH."""

    engine: Engine
    default_limit: int = 200
    cache_ttl_seconds: int = 120
    cache_max_entries: int = 500

    def __post_init__(self) -> None:
        self._cache: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_execution_info: dict[str, Any] = {}

    @classmethod
    def from_url(
        cls,
        database_url: str,
        default_limit: int = 200,
        cache_ttl_seconds: int = 120,
        cache_max_entries: int = 500,
    ) -> "DwhClient":
        engine = create_engine(database_url)
        return cls(
            engine=engine,
            default_limit=default_limit,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_max_entries=cache_max_entries,
        )

    @property
    def dialect_name(self) -> str:
        """Nombre normalizado del dialecto SQL en uso."""
        return (self.engine.dialect.name or "").lower()

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        """Ejecuta una consulta de solo lectura y devuelve filas en formato dict."""
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
            self._cache_hits += 1
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

        self._cache_misses += 1
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(sql_with_limit))
                rows = [dict(row._mapping) for row in result.fetchall()]
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
            if self.dialect_name == "postgresql":
                retry_sql = self._rewrite_postgresql_undefined_column_retry(sql_with_limit, str(exc))
            if retry_sql and retry_sql != sql_with_limit:
                try:
                    if self.dialect_name == "postgresql" and vgd_execution_guard_enabled(
                        database_url=str(self.engine.url)
                    ):
                        validate_vgd_dwh_sql(retry_sql)
                    with self.engine.connect() as connection:
                        result = connection.execute(text(retry_sql))
                        rows = [dict(row._mapping) for row in result.fetchall()]
                        # Cachea con ambas llaves para evitar repetir el fallo original.
                        self._set_cache_rows(sql_with_limit, rows)
                        self._set_cache_rows(retry_sql, rows)
                        self._last_execution_info = {
                            "auto_retry_undefined_column": True,
                            "retry_applied": True,
                            "cached": False,
                            "reason": "undefined_column",
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

            self._last_execution_info = {
                "auto_retry_undefined_column": bool(retry_sql),
                "retry_applied": False,
                "cached": False,
                "failed": True,
            }
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(retry_exc or exc),
            )
            try:
                log_error_and_run_subagent(
                    source="dwh_execute_select",
                    message=str(retry_exc or exc),
                    context={
                        "sql": sql_with_limit,
                        "dialect": self.dialect_name,
                    },
                )
            except Exception:
                # El registro/corrección nunca debe ocultar el error original del DWH.
                pass
            if retry_exc is not None:
                raise RuntimeError(f"Error ejecutando consulta en DWH: {retry_exc}") from retry_exc
            raise RuntimeError(f"Error ejecutando consulta en DWH: {exc}") from exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        """Alias para compatibilidad con versiones previas."""
        return self.execute_select(sql)

    def get_cache_stats(self) -> dict[str, Any]:
        total = self._cache_hits + self._cache_misses
        hit_ratio = (self._cache_hits / total) if total else 0.0
        return {
            "entries": len(self._cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_ratio": round(hit_ratio, 4),
            "ttl_seconds": self.cache_ttl_seconds,
            "max_entries": self.cache_max_entries,
        }

    def get_last_execution_info(self) -> dict[str, Any]:
        return dict(self._last_execution_info)

    def _get_cached_rows(self, sql: str) -> list[dict[str, Any]] | None:
        if self.cache_ttl_seconds <= 0:
            return None
        now = time.time()
        cached = self._cache.get(sql)
        if cached is None:
            return None
        created_at, rows = cached
        if now - created_at > self.cache_ttl_seconds:
            self._cache.pop(sql, None)
            return None
        self._cache.move_to_end(sql)
        return [dict(row) for row in rows]

    def _set_cache_rows(self, sql: str, rows: list[dict[str, Any]]) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        self._cache[sql] = (time.time(), [dict(row) for row in rows])
        self._cache.move_to_end(sql)
        while len(self._cache) > self.cache_max_entries:
            self._cache.popitem(last=False)

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
        normalized = self._rewrite_service_appointments_aliases(normalized)
        normalized = self._rewrite_sales_status_aliases(normalized)
        normalized = self._rewrite_insurance_policies_policy_status(normalized)

        if self.dialect_name == "sqlite":
            normalized = self._normalize_sqlite_sql(normalized)
        elif self.dialect_name == "postgresql":
            normalized = self._quote_postgresql_mixed_case_identifiers(normalized)
            normalized = self._rewrite_postgresql_h_view_legacy_identifiers(normalized)
            normalized = self._rewrite_postgresql_idagency_equality_cast(normalized)
            normalized = self._rewrite_postgresql_group_by_year_alias(normalized)
            normalized = self._rewrite_postgresql_count_empty_parentheses(normalized)
            normalized = self._rewrite_postgresql_mysql_style_date_parts(normalized)
            normalized = self._rewrite_postgresql_invalid_interval_literal_cast(normalized)
            normalized = self._rewrite_postgresql_extract_epoch_from_date_subtraction(normalized)
            normalized = self._rewrite_postgresql_round_two_arg(normalized)

        return normalized

    def _quote_postgresql_mixed_case_identifiers(self, sql: str) -> str:
        """
        PostgreSQL pliega identificadores sin comillas a minúsculas.
        Si el LLM emite `idAgency` sin comillas, termina buscando `idagency`.
        Este normalizador lo corrige a `"idAgency"` fuera de literales/comillas.
        """
        idset = set(_PG_MIXED_CASE_IDENTIFIERS)
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

    def _rewrite_postgresql_h_view_legacy_identifiers(self, sql: str) -> str:
        """
        Si la consulta usa vistas homologadas h_*, traduce identificadores legacy
        camelCase/PascalCase a snake_case para evitar errores de columnas inexistentes.
        """
        if not re.search(
            r'(?is)\b(?:FROM|JOIN)\s+(?:"?[A-Za-z_][A-Za-z0-9_]*"?\.)?"?h_[A-Za-z_][A-Za-z0-9_]*"?\b',
            sql,
        ):
            return sql

        out = sql
        # 1) Traducciones explícitas conocidas.
        for legacy, homologated in _HOMOLOGATED_LEGACY_IDENTIFIER_MAP.items():
            out = out.replace(f'"{legacy}"', f'"{homologated}"')

        # 2) Cualquier identificador quoted CamelCase/PascalCase -> snake_case.
        #    Esto captura casos no contemplados en el mapa estático.
        out = re.sub(
            r'"(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"',
            lambda m: (
                f'"{_to_snake_case(m.group("ident"))}"'
                if re.search(r"[a-z]", m.group("ident"))
                and re.search(r"[A-Z]", m.group("ident"))
                else m.group(0)
            ),
            out,
        )

        # 3) Referencias alias.columna en camelCase sin comillas -> alias.snake_case.
        out = re.sub(
            r'(?P<prefix>\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)(?P<ident>[A-Za-z_][A-Za-z0-9_]*)\b',
            lambda m: (
                f'{m.group("prefix")}{_to_snake_case(m.group("ident"))}'
                if re.search(r"[a-z]", m.group("ident"))
                and re.search(r"[A-Z]", m.group("ident"))
                else m.group(0)
            ),
            out,
        )
        return out

    def _rewrite_postgresql_undefined_column_retry(self, sql: str, err: str) -> str | None:
        """
        Reescribe un SQL fallido por UndefinedColumn para un único reintento automático.
        Se aplica solo cuando el query usa vistas homologadas h_*.
        """
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
        snake_ident = _to_snake_case(legacy_ident)

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
                for cand in _H_VIEW_TABLE_COLUMN_FALLBACKS.get(table or "", {}).get(
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
                for cand in _H_VIEW_TABLE_COLUMN_FALLBACKS.get(only_table, {}).get(
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

        out = self._rewrite_postgresql_h_view_legacy_identifiers(out)
        return out if out != sql else None

    def _rewrite_postgresql_idagency_equality_cast(self, sql: str) -> str:
        """
        En algunos snapshots del DWH, idAgency no tiene el mismo tipo entre tablas
        (p. ej. invoices/services bigint vs agencies/customers text). Para evitar
        errores de operador en joins/filtros, castea comparaciones de idAgency a text.
        """
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

    def _rewrite_postgresql_group_by_year_alias(self, sql: str) -> str:
        """
        Corrige consultas donde se selecciona `... AS year` (EXTRACT) pero el GROUP BY
        omite ese alias, lo que rompe en PostgreSQL.
        """
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
        return normalized

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
        """Mapea alias de estados comunes al catálogo real de la demo."""
        # En la demo usamos estados: cerrada, facturada, entregada.
        # El LLM a veces usa 'completed'; aquí lo ampliamos a todos los estados
        # equivalentes para no perder filas en consultas de recompra.
        return re.sub(
            r"(?i)(?P<prefix>\b(?:[A-Za-z_][A-Za-z0-9_]*\.)?status)\s*=\s*'completed'",
            r"\g<prefix> IN ('completed', 'entregada', 'facturada', 'cerrada')",
            sql,
        )

    def _rewrite_service_appointments_aliases(self, sql: str) -> str:
        """
        Corrige SQL generado para agenda de servicio con aliases comunes.

        En service_appointments las columnas reales son appointment_status y
        appointment_date.         El LLM puede generar `status`, `scheduled_date`, `service_date` o
        `appointment_time` por consistencia con otros esquemas (p. ej. la tabla
        `services` sí tiene service_date; en citas la columna es appointment_date).
        También mapea `advisor` a `workshop` en este dataset demo.
        """
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

    def _rewrite_insurance_policies_policy_status(self, sql: str) -> str:
        """
        El LLM suele usar estados en inglés o inventados; en la demo son activa, vencida, cancelada.
        Solo aplica cuando la consulta menciona insurance_policies.
        """
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

    @staticmethod
    def _parse_round_call_args(sql: str, open_paren_idx: int) -> tuple[str, str | None, int] | None:
        """
        A partir del '(' de ROUND(, devuelve (primer_arg, segundo_arg_o_None, indice_despues_del_cierre).
        Respeta paréntesis anidados y literales entre comillas simples.
        """
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

    def _rewrite_postgresql_round_two_arg(self, sql: str) -> str:
        """
        PostgreSQL no implementa ROUND(double precision, int); usar ROUND((x)::numeric, n).
        """
        round_re = re.compile(r"\bROUND\s*\(", re.IGNORECASE)
        out: list[str] = []
        pos = 0
        for m in round_re.finditer(sql):
            open_idx = m.end() - 1
            parsed = self._parse_round_call_args(sql, open_idx)
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

    def _rewrite_postgresql_extract_epoch_from_date_subtraction(self, sql: str) -> str:
        """
        EXTRACT(EPOCH FROM (a - b)) falla si a y b son DATE: en PostgreSQL DATE - DATE = INTEGER (días),
        no INTERVAL, y EXTRACT(EPOCH FROM integer) no existe. Castea a timestamp para obtener intervalo.
        """

        def repl(match: re.Match[str]) -> str:
            inner = match.group("inner").strip()
            binop = re.fullmatch(
                r"([A-Za-z_][A-Za-z0-9_.]*)\s*-\s*([A-Za-z_][A-Za-z0-9_.]*)",
                inner,
            )
            if not binop:
                return match.group(0)
            left, right = binop.group(1), binop.group(2)
            return (
                f"EXTRACT(EPOCH FROM ({left}::timestamp - {right}::timestamp))"
            )

        return re.sub(
            r"EXTRACT\s*\(\s*EPOCH\s+FROM\s*\(\s*(?P<inner>[^()]+?)\s*\)\s*\)",
            repl,
            sql,
            flags=re.IGNORECASE,
        )

    def _rewrite_postgresql_count_empty_parentheses(self, sql: str) -> str:
        """PostgreSQL no admite COUNT(); el LLM a veces lo emite como en otros dialectos."""
        return re.sub(r"\bCOUNT\s*\(\s*\)", "COUNT(*)", sql, flags=re.IGNORECASE)

    def _rewrite_postgresql_mysql_style_date_parts(self, sql: str) -> str:
        """
        MySQL usa YEAR(col), MONTH(col), DAY(col). En PostgreSQL no existen; usar EXTRACT.
        Recorre de izquierda a derecha respetando paréntesis anidados en el argumento.
        Repite por si hay anidación YEAR(MONTH(...)).
        """
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

    def _rewrite_postgresql_invalid_interval_literal_cast(self, sql: str) -> str:
        """
        El LLM a veces escribe (fecha2 - fecha1) :: interval 'day', que no es sintaxis válida en PostgreSQL.
        DATE - DATE ya devuelve INTEGER (días); se elimina el cast erróneo.
        """
        out = sql
        for lit in ("day", "days", "month", "months", "year", "years"):
            out = re.sub(
                rf"\)\s*::\s*interval\s+'{lit}'",
                ")",
                out,
                flags=re.IGNORECASE,
            )
        return out


# Reexport final para asegurar la implementación modular.
from .dwh_client import DwhClient as DwhClient

