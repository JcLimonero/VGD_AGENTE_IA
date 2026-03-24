from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dwh import DwhClient
from .kpi_templates import DeterministicQuery, match_kpi_template
from .llm_local import OllamaClient
from .observability import StopWatch, record_query_event
from .sql_guard import clean_sql_output, validate_read_only_sql


SYSTEM_PROMPT = """Eres un asistente experto en SQL para analytics.
Tu tarea es responder EXCLUSIVAMENTE con una consulta SQL de solo lectura.

Reglas obligatorias:
1) Solo una consulta SQL.
2) No uses markdown, comentarios ni texto adicional.
3) Usa sentencias SELECT para analítica.
4) No uses UPDATE, INSERT, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, GRANT, REVOKE, CALL o EXEC.
5) Limita resultados a un máximo de 1000 filas cuando aplique.
6) Si la pregunta no se puede resolver con SQL, devuelve: SELECT 'No se puede resolver con SQL' AS mensaje;
7) Respeta SIEMPRE el dialecto SQL del motor indicado en el prompt del usuario.
"""

SQL_FIX_PROMPT = """Eres un asistente experto en corrección de SQL.
Debes corregir una consulta SQL que falló al ejecutarse.

Reglas obligatorias:
1) Responde SOLO con SQL (sin markdown ni texto adicional).
2) Mantén la intención original de la pregunta de negocio.
3) Usa únicamente SQL de lectura (SELECT/CTE), sin operaciones de escritura.
4) Corrige alias, columnas o joins inválidos según el error reportado.
5) Respeta SIEMPRE el dialecto SQL del motor indicado en el prompt del usuario.
"""


@dataclass
class QueryResult:
    question: str
    generated_sql: str
    rows: list[dict[str, Any]]
    deterministic_kpi: str = ""
    deterministic_explanation: str = ""


class DwhAgent:
    def __init__(
        self,
        dwh_client: DwhClient,
        llm_client: OllamaClient,
        schema_hint: str = "",
    ) -> None:
        self._dwh = dwh_client
        self._llm = llm_client
        self._schema_hint = schema_hint.strip()

    def _try_deterministic_kpi(self, question: str) -> QueryResult | None:
        matched: DeterministicQuery | None = match_kpi_template(question)
        if not matched:
            return None
        rows = self._dwh.execute_select(matched.sql)
        return QueryResult(
            question=question,
            generated_sql=matched.sql,
            rows=rows,
            deterministic_kpi=matched.name,
            deterministic_explanation=matched.explanation,
        )

    def _dialect_guidance(self) -> str:
        dialect = self._dwh.dialect_name
        if dialect == "sqlite":
            return (
                "Motor SQL objetivo: SQLite.\n"
                "Reglas de dialecto SQLite:\n"
                "- NO uses DATEADD, DATEDIFF ni funciones exclusivas de SQL Server.\n"
                "- Para fechas usa date()/datetime()/strftime() de SQLite.\n"
                "- Usa CURRENT_DATE, CURRENT_TIMESTAMP o date('now') según convenga.\n"
                "- Operadores válidos: <=, >=, != (evita símbolos unicode como ≤, ≥, ≠).\n"
            )
        if dialect == "postgresql":
            return (
                "Motor SQL objetivo: PostgreSQL.\n"
                "Reglas de dialecto PostgreSQL:\n"
                "- Para fechas usa intervalos (por ejemplo: fecha + INTERVAL '1 month').\n"
                "- Evita funciones exclusivas de SQL Server como DATEADD.\n"
            )
        if dialect:
            return f"Motor SQL objetivo: {dialect}.\nRespeta estrictamente este dialecto.\n"
        return "Motor SQL objetivo no identificado. Usa SQL ANSI estándar cuando sea posible.\n"

    def _build_user_prompt(self, question: str) -> str:
        schema_context = self._schema_hint or "No se proporcionó esquema."
        return (
            f"{self._dialect_guidance()}\n"
            f"Esquema de referencia:\n{schema_context}\n\n"
            f"Pregunta de negocio:\n{question}\n\n"
            "Devuelve solamente SQL válido para el motor del DWH."
        )

    def _build_fix_prompt(self, question: str, previous_sql: str, execution_error: str) -> str:
        schema_context = self._schema_hint or "No se proporcionó esquema."
        return (
            f"{self._dialect_guidance()}\n"
            f"Esquema de referencia:\n{schema_context}\n\n"
            f"Pregunta original:\n{question}\n\n"
            f"SQL que falló:\n{previous_sql}\n\n"
            f"Error de ejecución:\n{execution_error}\n\n"
            "Devuelve SOLO una versión corregida del SQL."
        )

    def get_cache_stats(self) -> dict[str, Any]:
        return self._dwh.get_cache_stats()

    def answer(self, question: str) -> QueryResult:
        stopwatch = StopWatch()
        try:
            deterministic_result = self._try_deterministic_kpi(question)
            if deterministic_result is not None:
                record_query_event(
                    source="agent",
                    success=True,
                    duration_ms=stopwatch.elapsed_ms(),
                    row_count=len(deterministic_result.rows),
                    cached=False,
                    message=f"kpi_deterministico:{deterministic_result.deterministic_kpi}",
                )
                return deterministic_result

            prompt = self._build_user_prompt(question)
            raw_output = self._llm.generar_sql(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            generated_sql = clean_sql_output(raw_output)
            validate_read_only_sql(generated_sql)
            try:
                rows = self._dwh.execute_select(generated_sql)
                result = QueryResult(question=question, generated_sql=generated_sql, rows=rows)
                record_query_event(
                    source="agent",
                    success=True,
                    duration_ms=stopwatch.elapsed_ms(),
                    row_count=len(rows),
                    cached=False,
                    message="llm_sql",
                )
                return result
            except RuntimeError as first_exc:
                # Reintento único: pedir al LLM una corrección basada en el error SQL.
                fix_prompt = self._build_fix_prompt(
                    question=question,
                    previous_sql=generated_sql,
                    execution_error=str(first_exc),
                )
                fixed_raw = self._llm.generar_sql(prompt=fix_prompt, system_prompt=SQL_FIX_PROMPT)
                fixed_sql = clean_sql_output(fixed_raw)
                validate_read_only_sql(fixed_sql)
                rows = self._dwh.execute_select(fixed_sql)
                result = QueryResult(question=question, generated_sql=fixed_sql, rows=rows)
                record_query_event(
                    source="agent",
                    success=True,
                    duration_ms=stopwatch.elapsed_ms(),
                    row_count=len(rows),
                    cached=False,
                    message="llm_sql_fix",
                )
                return result
        except Exception as exc:
            record_query_event(
                source="agent",
                success=False,
                duration_ms=stopwatch.elapsed_ms(),
                row_count=0,
                cached=False,
                message=str(exc),
            )
            raise
