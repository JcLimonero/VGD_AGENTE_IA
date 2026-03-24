from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

import streamlit as st

try:
    from .agent import DwhAgent
    from .demo_data import ensure_demo_db
    from .dwh import DwhClient
    from .llm_local import LocalOllamaClient
except ImportError:
    # Cuando Streamlit ejecuta el archivo como script, no hay paquete padre.
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agente_dwh.agent import DwhAgent
    from agente_dwh.demo_data import ensure_demo_db
    from agente_dwh.dwh import DwhClient
    from agente_dwh.llm_local import LocalOllamaClient

DEMO_DB_PATH = "/tmp/agente_dwh_demo.db"
DEFAULT_DWH_URL = f"sqlite+pysqlite:///{DEMO_DB_PATH}"
DEFAULT_LLM_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "qwen2.5:0.5b"
DEFAULT_SCHEMA_HINT = """Tablas demo disponibles:
- customers(id, customer_code, full_name, email, phone, city, state, segment, created_at)
- vehicles(id, customer_id, vin, plate, brand, model, year, fuel_type, mileage, created_at)
- sales(id, customer_id, vehicle_id, sale_date, amount, channel, seller, status)
- services(id, customer_id, vehicle_id, service_date, service_type, cost, status, workshop, notes)

Relaciones:
- customers.id = vehicles.customer_id
- customers.id = sales.customer_id
- customers.id = services.customer_id
- vehicles.id = sales.vehicle_id
- vehicles.id = services.vehicle_id
"""
RECOMMENDED_QUESTIONS = [
    "¿Cuántos clientes hay por estado?",
    "Top 10 clientes con más monto de ventas en 2025.",
    "¿Cuántos vehículos tiene cada cliente?",
    "¿Cuál es el total de servicios y monto por tipo de servicio?",
    "Clientes sin ventas pero con al menos un vehículo registrado.",
    "Ingresos por mes considerando ventas y servicios.",
]


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


def _extract_pg_hba_ip(error_message: str) -> str:
    """Extrae IP origen reportada por PostgreSQL en errores pg_hba."""
    match = re.search(r'host "(\d{1,3}(?:\.\d{1,3}){3})"', error_message)
    return match.group(1) if match else ""


def main() -> None:
    st.set_page_config(page_title="Agente IA DWH", page_icon="🧠", layout="wide")
    st.title("Agente IA para DWH (LLM local)")
    st.caption(
        "Convierte una pregunta de negocio en SQL y ejecuta la consulta en una base demo "
        "de clientes, vehículos, ventas y servicios."
    )
    st.info("Modo demo: solo escribe tu pregunta y presiona Consultar.")

    demo_info = ensure_demo_db(DEMO_DB_PATH)
    st.success(
        "Base demo lista: "
        f"{demo_info['customers']} clientes, "
        f"{demo_info['vehicles']} vehiculos, "
        f"{demo_info['sales']} ventas, "
        f"{demo_info['services']} servicios."
    )

    # Configuracion fija por defecto (puede sobreescribirse por variables de entorno).
    dwh_url = os.getenv("DWH_URL", DEFAULT_DWH_URL)
    llm_endpoint = os.getenv("LLM_ENDPOINT", DEFAULT_LLM_ENDPOINT)
    llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    max_rows = _env_int("MAX_ROWS", 200)
    llm_timeout = _env_int("LLM_TIMEOUT_SECONDS", 60)
    schema_hint_file = os.getenv("SCHEMA_HINT_FILE", "")

    with st.expander("Opciones avanzadas (LLM y limites)", expanded=False):
        llm_endpoint = st.text_input(
            "LLM_ENDPOINT",
            value=llm_endpoint,
            help="Si esta app corre en la nube, 127.0.0.1 apunta al servidor cloud, no a tu PC.",
        )
        llm_model = st.text_input("LLM_MODEL", value=llm_model)
        max_rows = st.number_input(
            "MAX_ROWS",
            min_value=1,
            max_value=10000,
            value=int(max_rows),
            step=10,
        )
        llm_timeout = st.number_input(
            "LLM_TIMEOUT_SECONDS",
            min_value=1,
            max_value=600,
            value=int(llm_timeout),
            step=5,
        )

    st.markdown("### Preguntas recomendadas")
    selected_question = ""
    rec_cols = st.columns(2)
    for idx, recommended in enumerate(RECOMMENDED_QUESTIONS):
        if rec_cols[idx % 2].button(recommended, key=f"q_rec_{idx}", use_container_width=True):
            selected_question = recommended

    col1, col2 = st.columns([2, 1])
    with col1:
        question = st.text_area(
            "Pregunta de negocio",
            value=selected_question or "¿Cuántos clientes hay por estado?",
            height=110,
            placeholder="Ejemplo: Top 20 agencias por número de clientes consolidados.",
        )
    with col2:
        st.markdown("### Ejecutar")
        run = st.button("Consultar", type="primary", use_container_width=True)

    if not run:
        st.info("Escribe tu pregunta y presiona 'Consultar'.")
        return

    if not dwh_url.strip():
        st.error("Debes indicar DWH_URL.")
        return
    if not question.strip():
        st.error("Debes escribir una pregunta.")
        return

    schema_hint = _read_schema_hint(schema_hint_file) or DEFAULT_SCHEMA_HINT

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
            message = str(exc)
            st.error(f"Error ejecutando consulta: {message}")
            if "No se pudo contactar Ollama" in message or "Connection refused" in message:
                st.warning(
                    "No se puede alcanzar Ollama desde este servidor. "
                    "Si tu Ollama corre en tu laptop, debes exponerlo por una URL publica "
                    "(por ejemplo, tunel) y usarla en LLM_ENDPOINT."
                )
            if "no pg_hba.conf entry" in message:
                client_ip = _extract_pg_hba_ip(message)
                st.warning(
                    "PostgreSQL bloqueo esta conexion por reglas de red (pg_hba.conf). "
                    "Debes autorizar la IP origen del servidor cloud."
                )
                if client_ip:
                    st.code(
                        "host    vgd_dwh_migration    postgres    "
                        f"{client_ip}/32    scram-sha-256"
                    )
                st.info(
                    "Despues de ajustar pg_hba.conf, recarga configuracion en PostgreSQL "
                    "(por ejemplo: SELECT pg_reload_conf();) y valida firewall en puerto 5432."
                )
            if "no encryption" in message:
                st.info(
                    "El servidor reporta conexion sin cifrado. Si tu instancia exige SSL, "
                    "usa una URL DWH con sslmode=require y habilita SSL en PostgreSQL."
                )
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
