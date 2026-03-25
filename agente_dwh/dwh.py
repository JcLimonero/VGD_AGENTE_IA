"""Cliente de acceso al DWH."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
import time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .observability import record_query_event
from .sql_guard import validate_read_only_sql


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
        validate_read_only_sql(stripped)
        start = time.perf_counter()
        normalized_sql = self._normalize_sql_for_dialect(stripped)
        sql_with_limit = self._inject_limit_if_missing(normalized_sql)
        cached_rows = self._get_cached_rows(sql_with_limit)
        if cached_rows is not None:
            self._cache_hits += 1
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
                record_query_event(
                    source="dwh",
                    success=True,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    row_count=len(rows),
                    cached=False,
                )
                return rows
        except SQLAlchemyError as exc:
            record_query_event(
                source="dwh",
                success=False,
                duration_ms=(time.perf_counter() - start) * 1000.0,
                row_count=0,
                cached=False,
                message=str(exc),
            )
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
            normalized = self._rewrite_postgresql_extract_epoch_from_date_subtraction(normalized)
            normalized = self._rewrite_postgresql_round_two_arg(normalized)

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

