from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dwh import DwhClient
from .llm_local import OllamaClient
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
"""


@dataclass
class QueryResult:
    question: str
    generated_sql: str
    rows: list[dict[str, Any]]


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

    def _build_user_prompt(self, question: str) -> str:
        schema_context = self._schema_hint or "No se proporcionó esquema."
        return (
            f"Esquema de referencia:\n{schema_context}\n\n"
            f"Pregunta de negocio:\n{question}\n\n"
            "Devuelve solamente SQL válido para el motor del DWH."
        )

    def answer(self, question: str) -> QueryResult:
        prompt = self._build_user_prompt(question)
        raw_output = self._llm.generar_sql(prompt=prompt, system_prompt=SYSTEM_PROMPT)
        generated_sql = clean_sql_output(raw_output)
        validate_read_only_sql(generated_sql)
        rows = self._dwh.execute_select(generated_sql)
        return QueryResult(question=question, generated_sql=generated_sql, rows=rows)
