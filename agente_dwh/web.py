from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st

try:
    from .agent import DwhAgent
    from .dwh import DwhClient
    from .llm_local import LocalOllamaClient
except ImportError:
    # Cuando Streamlit ejecuta el archivo como script, no hay paquete padre.
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agente_dwh.agent import DwhAgent
    from agente_dwh.dwh import DwhClient
    from agente_dwh.llm_local import LocalOllamaClient


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _read_schema_hint(path: str) -> str:
    if not path.strip():
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _build_agent(
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    row_limit: int,
    llm_timeout_seconds: int,
    schema_hint: str,
) -> DwhAgent:
    dwh = DwhClient.from_url(dwh_url, default_limit=row_limit)
    llm = LocalOllamaClient(
        base_url=llm_endpoint,
        model_name=llm_model,
        timeout_seconds=llm_timeout_seconds,
    )
    return DwhAgent(dwh_client=dwh, llm_client=llm, schema_hint=schema_hint)


def _render_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("La consulta no regresó filas.")
        return
    st.success(f"Filas obtenidas: {len(rows)}")
    st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Agente IA DWH", page_icon="🧠", layout="wide")
    st.title("Agente IA para DWH (LLM local)")
    st.caption("Convierte una pregunta de negocio en SQL y ejecuta la consulta en tu DWH.")
    st.info(
        "En movil, abre el menu lateral (>>) para editar la configuracion. "
        "Tambien puedes usar el formulario rapido de conexion que aparece abajo."
    )

    with st.sidebar:
        st.header("Configuración")
        dwh_url = st.text_input(
            "DWH_URL",
            value=os.getenv("DWH_URL", ""),
            help="Ejemplo: postgresql+psycopg://usuario:password@host:5432/base",
            type="password",
        )
        llm_endpoint = st.text_input(
            "LLM_ENDPOINT",
            value=os.getenv("LLM_ENDPOINT", "http://127.0.0.1:11434"),
        )
        llm_model = st.text_input("LLM_MODEL", value=os.getenv("LLM_MODEL", "llama3.1"))
        max_rows = st.number_input(
            "MAX_ROWS",
            min_value=1,
            max_value=10000,
            value=_env_int("MAX_ROWS", 200),
            step=10,
        )
        llm_timeout = st.number_input(
            "LLM_TIMEOUT_SECONDS",
            min_value=1,
            max_value=600,
            value=_env_int("LLM_TIMEOUT_SECONDS", 60),
            step=5,
        )
        schema_hint_file = st.text_input(
            "SCHEMA_HINT_FILE (opcional)",
            value=os.getenv("SCHEMA_HINT_FILE", "schema_hint_customers.txt"),
            help="Ruta a un archivo con descripción de tablas/columnas para mejorar el SQL.",
        )

    with st.expander("Configuracion rapida de conexion (recomendada en movil)", expanded=True):
        dwh_url_main = st.text_input(
            "DWH_URL (principal)",
            value=dwh_url,
            help="Ejemplo: postgresql+psycopg://usuario:password@host:5432/base",
            type="password",
            key="dwh_url_main",
        )
        llm_endpoint_main = st.text_input(
            "LLM_ENDPOINT (principal)",
            value=llm_endpoint,
            key="llm_endpoint_main",
        )
        llm_model_main = st.text_input(
            "LLM_MODEL (principal)",
            value=llm_model,
            key="llm_model_main",
        )
        max_rows_main = st.number_input(
            "MAX_ROWS (principal)",
            min_value=1,
            max_value=10000,
            value=int(max_rows),
            step=10,
            key="max_rows_main",
        )
        llm_timeout_main = st.number_input(
            "LLM_TIMEOUT_SECONDS (principal)",
            min_value=1,
            max_value=600,
            value=int(llm_timeout),
            step=5,
            key="llm_timeout_main",
        )
        schema_hint_file_main = st.text_input(
            "SCHEMA_HINT_FILE (principal, opcional)",
            value=schema_hint_file,
            key="schema_hint_file_main",
        )

    # Prioriza valores del formulario principal para mejorar uso en desktop/movil.
    dwh_url = dwh_url_main
    llm_endpoint = llm_endpoint_main
    llm_model = llm_model_main
    max_rows = max_rows_main
    llm_timeout = llm_timeout_main
    schema_hint_file = schema_hint_file_main

    col1, col2 = st.columns([2, 1])
    with col1:
        question = st.text_area(
            "Pregunta de negocio",
            value="Cuántos clientes hay por estado?",
            height=110,
            placeholder="Ejemplo: Top 20 agencias por número de clientes consolidados.",
        )
    with col2:
        st.markdown("### Ejecutar")
        run = st.button("Consultar", type="primary", use_container_width=True)

    if not run:
        st.info("Completa la configuración y presiona 'Consultar'.")
        return

    if not dwh_url.strip():
        st.error("Debes indicar DWH_URL.")
        return
    if not question.strip():
        st.error("Debes escribir una pregunta.")
        return

    schema_hint = _read_schema_hint(schema_hint_file)

    with st.spinner("Generando SQL y consultando DWH..."):
        try:
            agent = _build_agent(
                dwh_url=dwh_url.strip(),
                llm_endpoint=llm_endpoint.strip(),
                llm_model=llm_model.strip(),
                row_limit=int(max_rows),
                llm_timeout_seconds=int(llm_timeout),
                schema_hint=schema_hint,
            )
            result = agent.answer(question.strip())
        except Exception as exc:  # noqa: BLE001
            st.error(f"Error ejecutando consulta: {exc}")
            return

    st.subheader("SQL generado")
    st.code(result.generated_sql, language="sql")

    st.subheader("Resultados")
    _render_rows(result.rows)

    st.subheader("Salida JSON")
    st.json(
        {
            "pregunta": result.question,
            "sql": result.generated_sql,
            "rows": result.rows,
        }
    )


if __name__ == "__main__":
    main()
