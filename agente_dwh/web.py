from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

import streamlit as st
import pandas as pd

try:
    from .agent import DwhAgent
    from .demo_data import ensure_demo_db
    from .dwh import DwhClient
    from .forecast import (
        FORECAST_DIMENSIONS,
        FORECAST_METHODS,
        compute_sales_forecast,
        extract_dimension_from_question,
        extract_horizon_from_question,
        extract_method_from_question,
        is_forecast_intent,
    )
    from .llm_local import LocalOllamaClient
    from .observability import get_metrics_snapshot, get_recent_alerts, get_recent_events
except ImportError:
    # Cuando Streamlit ejecuta el archivo como script, no hay paquete padre.
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agente_dwh.agent import DwhAgent
    from agente_dwh.demo_data import ensure_demo_db
    from agente_dwh.dwh import DwhClient
    from agente_dwh.forecast import (
        FORECAST_DIMENSIONS,
        FORECAST_METHODS,
        compute_sales_forecast,
        extract_dimension_from_question,
        extract_horizon_from_question,
        extract_method_from_question,
        is_forecast_intent,
    )
    from agente_dwh.llm_local import LocalOllamaClient
    from agente_dwh.observability import get_metrics_snapshot, get_recent_alerts, get_recent_events

DEMO_DB_PATH = "/tmp/agente_dwh_demo.db"
DEFAULT_DWH_URL = f"sqlite+pysqlite:///{DEMO_DB_PATH}"
DEFAULT_LLM_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "qwen2.5:7b"
FALLBACK_LLM_MODEL = "qwen2.5:7b"
DEFAULT_SCHEMA_HINT = """Tablas demo disponibles:
- customers(id, customer_code, full_name, gender, age, birth_date, email, phone, city, state, segment, monthly_income, risk_profile, created_at)
- vehicles(id, customer_id, vin, plate, brand, model, unit_type, year, fuel_type, mileage, created_at)
- sales(id, customer_id, vehicle_id, sale_date, amount, channel, seller, payment_method, status)
- services(id, customer_id, vehicle_id, service_date, service_type, cost, status, workshop, notes)
- service_appointments(id, customer_id, vehicle_id, appointment_date, scheduled_start, scheduled_end, service_type, status, advisor, workshop, estimated_cost, created_at, notes)
- insurance_policies(id, customer_id, vehicle_id, policy_start_date, policy_end_date, insurer, coverage_type, annual_premium, policy_status, claim_count, last_claim_date)

Relaciones:
- customers.id = vehicles.customer_id
- customers.id = sales.customer_id
- customers.id = services.customer_id
- customers.id = service_appointments.customer_id
- customers.id = insurance_policies.customer_id
- vehicles.id = sales.vehicle_id
- vehicles.id = services.vehicle_id
- vehicles.id = service_appointments.vehicle_id
- vehicles.id = insurance_policies.vehicle_id
"""
RECOMMENDED_QUESTIONS = [
    "¿Cuántos clientes hay por estado?",
    "Top 10 clientes con más monto de ventas en 2025.",
    "¿Cuántos vehículos tiene cada cliente?",
    "¿Cuál es el total de servicios y monto por tipo de servicio?",
    "Clientes sin ventas pero con al menos un vehículo registrado.",
    "¿Cuál es el tiempo promedio de recompra de mis clientes?",
    "¿A qué clientes les puedo ofrecer un seguro hoy?",
    "¿Cuál es la edad promedio de los clientes que compran?",
    "¿Qué tipo de unidad compra más cada rango de edad y género?",
    "¿Cuántas citas de servicio hay por estatus este mes?",
    "¿Cuál es el porcentaje de no show en citas de servicio por taller?",
    "Top 10 asesores con más no show en citas de servicio.",
    "¿Cuál es la tasa de no show semanal de los últimos 3 meses?",
    "¿Cuáles son los motivos de cancelación más frecuentes en citas de servicio?",
    "¿Cuál es la conversión de citas programadas a completadas por taller?",
    "Ingresos por mes considerando ventas y servicios.",
    "Pronóstico de ventas para los próximos 3 meses.",
    "Pronóstico de ventas por estado para los próximos 6 meses con tendencia lineal.",
]
DEMO_COMMERCIAL_QUESTIONS = [
    "¿Cuál es el tiempo promedio de recompra de mis clientes?",
    "¿A qué clientes les puedo ofrecer un seguro hoy?",
    "¿Cuál es la edad promedio de los clientes que compran?",
    "¿Qué tipo de unidad es más conveniente ofrecer por rango de edad y género?",
    "¿Qué porcentaje de clientes tiene póliza activa, vencida o sin póliza?",
    "¿Qué clientes tienen póliza por vencer en los próximos 60 días?",
    "¿Qué asesores tienen más citas canceladas o no show?",
    "Top 10 asesores con más no show en citas de servicio.",
    "¿Cuál es la tasa de no show semanal de los últimos 3 meses?",
    "¿Cuáles son los motivos de cancelación más frecuentes en citas de servicio?",
    "¿Cuál es la conversión de citas programadas a completadas por taller?",
]

GENERAL_REFERENCE_QUESTIONS = [
    "¿Cuántos clientes hay por estado?",
    "Top 10 clientes con más monto de ventas en 2025.",
    "¿Cuántos vehículos tiene cada cliente?",
    "¿Cuál es el total de servicios y monto por tipo de servicio?",
    "Clientes sin ventas pero con al menos un vehículo registrado.",
    "Ingresos por mes considerando ventas y servicios.",
    "Pronóstico de ventas para los próximos 3 meses.",
    "Pronóstico de ventas por estado para los próximos 6 meses con tendencia lineal.",
]
SPANISH_COLUMN_LABELS: dict[str, str] = {
    "id": "Id",
    "customer_id": "Id Cliente",
    "vehicle_id": "Id Unidad",
    "customer_code": "Código Cliente",
    "full_name": "Nombre Completo",
    "gender": "Género",
    "age": "Edad",
    "birth_date": "Fecha Nacimiento",
    "email": "Correo",
    "phone": "Teléfono",
    "city": "Ciudad",
    "state": "Estado",
    "segment": "Segmento",
    "monthly_income": "Ingreso Mensual",
    "risk_profile": "Perfil Riesgo",
    "created_at": "Fecha Alta",
    "vin": "VIN",
    "plate": "Placa",
    "brand": "Marca",
    "model": "Modelo",
    "unit_type": "Tipo Unidad",
    "year": "Año",
    "fuel_type": "Tipo Combustible",
    "mileage": "Kilometraje",
    "sale_date": "Fecha Venta",
    "amount": "Monto",
    "channel": "Canal",
    "seller": "Vendedor",
    "payment_method": "Método Pago",
    "status": "Estatus",
    "service_date": "Fecha Servicio",
    "service_type": "Tipo Servicio",
    "cost": "Costo",
    "workshop": "Taller",
    "notes": "Notas",
    "appointment_date": "Fecha Cita",
    "scheduled_start": "Inicio Programado",
    "scheduled_end": "Fin Programado",
    "advisor": "Asesor",
    "estimated_cost": "Costo Estimado",
    "policy_start_date": "Inicio Póliza",
    "policy_end_date": "Fin Póliza",
    "insurer": "Aseguradora",
    "coverage_type": "Cobertura",
    "annual_premium": "Prima Anual",
    "policy_status": "Estatus Póliza",
    "claim_count": "Número Siniestros",
    "last_claim_date": "Fecha Último Siniestro",
    "avg_repurchase_days": "Días Promedio Recompra",
    "avg_time_between_purchases": "Días Promedio Entre Compras",
    "avg_days_between_purchases": "Días Promedio Entre Compras",
    "avg_rebuy_time": "Días Promedio Recompra",
}
SPANISH_VALUE_LABELS: dict[str, str] = {
    # Estatus de venta/servicio/póliza
    "completed": "Completado",
    "cerrada": "Cerrada",
    "facturada": "Facturada",
    "entregada": "Entregada",
    "completado": "Completado",
    "activa": "Activa",
    "vencida": "Vencida",
    "cancelada": "Cancelada",
    "sin_poliza": "Sin Póliza",
    # Riesgo
    "alto": "Alto",
    "medio": "Medio",
    "bajo": "Bajo",
    # Método de pago
    "contado": "Contado",
    "financiamiento": "Financiamiento",
    "leasing": "Arrendamiento",
    # Canal
    "digital": "Digital",
    "showroom": "Sala de ventas",
    "referido": "Referido",
    "flotillas": "Flotillas",
    # Tipo de unidad
    "suv": "SUV",
    "sedan": "Sedán",
    "hatchback": "Hatchback",
    "deportivo": "Deportivo",
    "van": "Van",
    "pickup": "Pickup",
    # Género
    "mujer": "Mujer",
    "hombre": "Hombre",
}
MXN_COLUMNS = {"monthly_income", "amount", "cost", "annual_premium"}
TIME_IN_DAYS_COLUMNS = {
    "avg_repurchase_days",
    "avg_time_between_purchases",
    "avg_days_between_purchases",
    "avg_rebuy_time",
    "gap_days",
}
FIELD_GUIDE_DETAILS: dict[str, list[dict[str, str]]] = {
    "customers": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_code", "type": "TEXT", "example": "C00001"},
        {"field": "full_name", "type": "TEXT", "example": "Mariana Ramirez Martinez"},
        {"field": "gender", "type": "TEXT", "example": "Mujer"},
        {"field": "age", "type": "INTEGER", "example": "42"},
        {"field": "birth_date", "type": "DATE/TEXT", "example": "1983-05-17"},
        {"field": "email", "type": "TEXT", "example": "cliente001@demo.local"},
        {"field": "phone", "type": "TEXT", "example": "5540643274"},
        {"field": "city", "type": "TEXT", "example": "Leon"},
        {"field": "state", "type": "TEXT", "example": "Guanajuato"},
        {"field": "segment", "type": "TEXT", "example": "Retail"},
        {"field": "monthly_income", "type": "REAL", "example": "38500.00"},
        {"field": "risk_profile", "type": "TEXT", "example": "medio"},
        {"field": "created_at", "type": "DATE/TEXT", "example": "2024-07-30"},
    ],
    "vehicles": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_id", "type": "INTEGER", "example": "1"},
        {"field": "vin", "type": "TEXT", "example": "VIN00000000000001"},
        {"field": "plate", "type": "TEXT", "example": "D1858NE"},
        {"field": "brand", "type": "TEXT", "example": "Nissan"},
        {"field": "model", "type": "TEXT", "example": "Versa"},
        {"field": "unit_type", "type": "TEXT", "example": "SUV"},
        {"field": "year", "type": "INTEGER", "example": "2026"},
        {"field": "fuel_type", "type": "TEXT", "example": "Gasolina"},
        {"field": "mileage", "type": "INTEGER", "example": "138494"},
        {"field": "created_at", "type": "DATE/TEXT", "example": "2023-06-12"},
    ],
    "sales": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_id", "type": "INTEGER", "example": "1"},
        {"field": "vehicle_id", "type": "INTEGER", "example": "1"},
        {"field": "sale_date", "type": "DATE/TEXT", "example": "2025-07-31"},
        {"field": "amount", "type": "REAL", "example": "347758.40"},
        {"field": "channel", "type": "TEXT", "example": "Digital"},
        {"field": "seller", "type": "TEXT", "example": "Alberto Ruiz"},
        {"field": "payment_method", "type": "TEXT", "example": "Financiamiento"},
        {"field": "status", "type": "TEXT", "example": "facturada"},
    ],
    "services": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_id", "type": "INTEGER", "example": "1"},
        {"field": "vehicle_id", "type": "INTEGER", "example": "1"},
        {"field": "service_date", "type": "DATE/TEXT", "example": "2025-09-02"},
        {"field": "service_type", "type": "TEXT", "example": "Mantenimiento preventivo"},
        {"field": "cost", "type": "REAL", "example": "10289.01"},
        {"field": "status", "type": "TEXT", "example": "entregado"},
        {"field": "workshop", "type": "TEXT", "example": "Taller Sur"},
        {"field": "notes", "type": "TEXT", "example": "Generado para demo"},
    ],
    "service_appointments": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_id", "type": "INTEGER", "example": "1"},
        {"field": "vehicle_id", "type": "INTEGER", "example": "1"},
        {"field": "appointment_date", "type": "DATE/TEXT", "example": "2026-03-18"},
        {"field": "scheduled_start", "type": "DATETIME/TEXT", "example": "2026-03-18 09:00:00"},
        {"field": "scheduled_end", "type": "DATETIME/TEXT", "example": "2026-03-18 10:30:00"},
        {"field": "service_type", "type": "TEXT", "example": "Mantenimiento preventivo"},
        {"field": "status", "type": "TEXT", "example": "no_show"},
        {"field": "advisor", "type": "TEXT", "example": "Diana Perez"},
        {"field": "workshop", "type": "TEXT", "example": "Taller Norte"},
        {"field": "estimated_cost", "type": "REAL", "example": "3600.00"},
        {"field": "created_at", "type": "DATE/TEXT", "example": "2026-03-15 14:12:00"},
        {"field": "notes", "type": "TEXT", "example": "Cliente pidió reagendar."},
    ],
    "insurance_policies": [
        {"field": "id", "type": "INTEGER", "example": "1"},
        {"field": "customer_id", "type": "INTEGER", "example": "1"},
        {"field": "vehicle_id", "type": "INTEGER", "example": "1"},
        {"field": "policy_start_date", "type": "DATE/TEXT", "example": "2025-01-01"},
        {"field": "policy_end_date", "type": "DATE/TEXT", "example": "2026-01-01"},
        {"field": "insurer", "type": "TEXT", "example": "AXA"},
        {"field": "coverage_type", "type": "TEXT", "example": "Amplia"},
        {"field": "annual_premium", "type": "REAL", "example": "17350.20"},
        {"field": "policy_status", "type": "TEXT", "example": "activa"},
        {"field": "claim_count", "type": "INTEGER", "example": "0"},
        {"field": "last_claim_date", "type": "DATE/TEXT", "example": "2025-09-18"},
    ],
}


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
    cache_ttl_seconds: int,
    cache_max_entries: int,
) -> DwhAgent:
    dwh = DwhClient.from_url(
        dwh_url,
        default_limit=row_limit,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
    )
    llm = LocalOllamaClient(
        base_url=llm_endpoint,
        model_name=llm_model,
        timeout_seconds=llm_timeout_seconds,
    )
    return DwhAgent(dwh_client=dwh, llm_client=llm, schema_hint=schema_hint)


def _friendly_column_name(name: Any) -> str:
    raw = str(name).strip()
    key = raw.lower()
    if key in SPANISH_COLUMN_LABELS:
        return SPANISH_COLUMN_LABELS[key]
    text = raw.replace("_", " ")
    return " ".join(part.capitalize() for part in text.split())


def _prettify_dataframe_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    rename_map: dict[str, str] = {}
    used_labels: set[str] = set()
    for column in df.columns:
        raw_name = str(column)
        base_label = _friendly_column_name(raw_name) or raw_name
        label = base_label
        suffix = 2
        while label in used_labels:
            label = f"{base_label} ({suffix})"
            suffix += 1
        rename_map[raw_name] = label
        used_labels.add(label)
    return df.rename(columns=rename_map), rename_map


def _translate_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    key = value.strip().lower()
    return SPANISH_VALUE_LABELS.get(key, value)


def _translate_dataframe_values(df: pd.DataFrame) -> pd.DataFrame:
    translated = df.copy()
    for column in translated.columns:
        if pd.api.types.is_object_dtype(translated[column]) or pd.api.types.is_string_dtype(
            translated[column]
        ):
            translated[column] = translated[column].map(_translate_value)
    return translated


def _format_mxn_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"MXN ${number:,.2f}"


def _format_time_value(days_value: Any) -> str:
    try:
        days = float(days_value)
    except (TypeError, ValueError):
        return str(days_value)

    abs_days = abs(days)
    if abs_days > 365:
        years = days / 365.0
        return f"{years:,.1f} años"
    if abs_days > 30:
        months = days / 30.0
        return f"{months:,.1f} meses"
    return f"{days:,.1f} días"


def _format_mxn_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for column in formatted.columns:
        if str(column).lower() in MXN_COLUMNS:
            numeric_series = pd.to_numeric(formatted[column], errors="coerce")
            formatted[column] = [
                _format_mxn_value(val) if pd.notna(num) else val
                for val, num in zip(formatted[column], numeric_series)
            ]
        elif str(column).lower() in TIME_IN_DAYS_COLUMNS:
            numeric_series = pd.to_numeric(formatted[column], errors="coerce")
            formatted[column] = [
                _format_time_value(val) if pd.notna(num) else val
                for val, num in zip(formatted[column], numeric_series)
            ]
    return formatted


def _render_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("La consulta no regresó filas.")
        return
    st.success(f"Filas obtenidas: {len(rows)}")
    df = _translate_dataframe_values(pd.DataFrame(rows))
    df = _format_mxn_columns(df)
    pretty_df, _ = _prettify_dataframe_columns(df)
    st.dataframe(pretty_df, use_container_width=True)


def _render_chart_options(rows: list[dict[str, Any]]) -> None:
    """Permite graficar resultados tabulares cuando hay columnas útiles."""
    if not rows:
        return

    df = _translate_dataframe_values(pd.DataFrame(rows))
    if df.empty:
        return

    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if not numeric_cols:
        st.info("No hay columnas numéricas para graficar en este resultado.")
        return

    # Cuando la consulta devuelve un único valor numérico (por ejemplo, un promedio),
    # mostramos un KPI en vez de forzar una gráfica con ejes X/Y.
    if len(df.columns) == 1 and len(numeric_cols) == 1:
        value_col = numeric_cols[0]
        numeric_series = pd.to_numeric(df[value_col], errors="coerce").dropna()
        st.markdown("### Resultado numérico")
        value_col_lower = str(value_col).lower()
        if numeric_series.empty:
            st.info("La consulta devolvió un valor nulo (NULL).")
        elif len(numeric_series) == 1:
            if value_col_lower in MXN_COLUMNS:
                metric_value = _format_mxn_value(numeric_series.iloc[0])
            elif value_col_lower in TIME_IN_DAYS_COLUMNS:
                metric_value = _format_time_value(numeric_series.iloc[0])
            else:
                metric_value = f"{float(numeric_series.iloc[0]):,.2f}"
            st.metric(_friendly_column_name(value_col), metric_value)
        else:
            kpi_df = numeric_series.reset_index(drop=True).to_frame(
                name=_friendly_column_name(value_col)
            )
            st.line_chart(kpi_df, use_container_width=True)
        return

    st.markdown("### Graficar resultados")
    chart_type = st.selectbox("Tipo de gráfica", ["Barras", "Línea", "Área"], index=0)

    x_candidates = list(df.columns)
    label_map = {col: _friendly_column_name(col) for col in x_candidates}

    # Evita errores cuando cambian las columnas entre consultas y el estado previo queda inválido.
    if "chart_x_col" not in st.session_state or st.session_state["chart_x_col"] not in x_candidates:
        st.session_state["chart_x_col"] = x_candidates[0]
    if "chart_y_col" not in st.session_state or st.session_state["chart_y_col"] not in numeric_cols:
        st.session_state["chart_y_col"] = numeric_cols[0]

    x_col = st.selectbox(
        "Columna eje X",
        x_candidates,
        key="chart_x_col",
        format_func=lambda value: label_map.get(value, str(value)),
    )
    y_candidates = [col for col in numeric_cols if col != x_col]
    if not y_candidates:
        st.info("No hay una segunda columna numérica disponible para eje Y.")
        return
    if "chart_y_col" not in st.session_state or st.session_state["chart_y_col"] not in y_candidates:
        st.session_state["chart_y_col"] = y_candidates[0]
    y_col = st.selectbox(
        "Columna eje Y (numérica)",
        y_candidates,
        key="chart_y_col",
        format_func=lambda value: label_map.get(value, str(value)),
    )

    chart_df = df[[x_col, y_col]].copy()
    chart_df = chart_df.dropna()
    if chart_df.empty:
        st.info("No hay datos válidos para construir la gráfica.")
        return

    # index de texto para categorías y fechas convertibles
    chart_df[x_col] = chart_df[x_col].astype(str)
    chart_df = chart_df.set_index(x_col)

    # Pasamos solo la serie Y para evitar errores por columnas faltantes al rerender.
    if chart_type == "Barras":
        st.bar_chart(chart_df[[y_col]], use_container_width=True)
    elif chart_type == "Línea":
        st.line_chart(chart_df[[y_col]], use_container_width=True)
    else:
        st.area_chart(chart_df[[y_col]], use_container_width=True)


def _extract_pg_hba_ip(error_message: str) -> str:
    """Extrae IP origen reportada por PostgreSQL en errores pg_hba."""
    match = re.search(r'host "(\d{1,3}(?:\.\d{1,3}){3})"', error_message)
    return match.group(1) if match else ""


def _nearest_horizon_option(value: int) -> int:
    options = [1, 3, 6, 12]
    return min(options, key=lambda opt: abs(opt - value))


def _prepare_new_result_view() -> None:
    """Resetea estado visual de resultados para una búsqueda nueva."""
    st.session_state.pop("chart_x_col", None)
    st.session_state.pop("chart_y_col", None)


def _render_query_result(
    result: Any,
    model_used: str | None = None,
    cache_stats: dict[str, Any] | None = None,
) -> None:
    """Renderiza resultado SQL en paneles colapsables con gráfica primero."""
    with st.expander("Gráfica", expanded=True):
        _render_chart_options(result.rows)

    with st.expander("SQL generado", expanded=False):
        st.code(result.generated_sql, language="sql")
        if model_used:
            st.caption(f"Modelo usado: {model_used}")

    with st.expander("Resultados", expanded=False):
        _render_rows(result.rows)

    with st.expander("Salida JSON", expanded=False):
        payload: dict[str, Any] = {
            "pregunta": result.question,
            "sql": result.generated_sql,
            "rows": result.rows,
        }
        if getattr(result, "deterministic_kpi", ""):
            payload["kpi_deterministico"] = result.deterministic_kpi
            payload["explicacion_kpi"] = getattr(result, "deterministic_explanation", "")
        if cache_stats:
            payload["cache"] = cache_stats
        if model_used:
            payload["modelo_usado"] = model_used
        st.json(payload)


def _render_forecast_result(result: Any, cache_stats: dict[str, Any] | None = None) -> None:
    st.subheader("Pronóstico de ventas")
    st.caption(
        f"Método: {result.method_label} | Horizonte: {result.horizon_months} meses | "
        f"Nivel: {FORECAST_DIMENSIONS.get(result.dimension, result.dimension)}"
    )

    with st.expander("Gráfica", expanded=True):
        chart_df = pd.DataFrame(result.chart_rows)
        if chart_df.empty:
            st.info("No hay datos suficientes para construir la gráfica del pronóstico.")
        else:
            pivot = chart_df.pivot(index="period", columns="tipo", values="ventas").fillna(0)
            pivot.index = pivot.index.astype(str)
            st.line_chart(pivot, use_container_width=True)

    with st.expander("SQL generado", expanded=False):
        st.code(result.source_sql, language="sql")

    with st.expander("Resultados", expanded=False):
        forecast_df = pd.DataFrame(result.forecast_rows)
        if forecast_df.empty:
            st.warning("No se pudo construir pronóstico con los datos actuales.")
        else:
            st.success(f"Filas de pronóstico: {len(forecast_df)}")
            pretty_forecast_df, _ = _prettify_dataframe_columns(forecast_df)
            st.dataframe(pretty_forecast_df, use_container_width=True)

    with st.expander("Salida JSON", expanded=False):
        payload: dict[str, Any] = {
            "metodo": result.method,
            "metodo_label": result.method_label,
            "horizonte_meses": result.horizon_months,
            "dimension": result.dimension,
            "dimension_label": FORECAST_DIMENSIONS.get(result.dimension, result.dimension),
            "filas_historicas_fuente": result.source_rows,
            "pronostico": result.forecast_rows,
        }
        if cache_stats:
            payload["cache"] = cache_stats
        st.json(payload)


def _render_observability_panel(cache_stats: dict[str, Any] | None = None) -> None:
    with st.expander("Observabilidad y alertas", expanded=False):
        metrics = get_metrics_snapshot()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Consultas", int(metrics.get("total_queries", 0)))
        col2.metric("Éxito", f"{float(metrics.get('success_rate', 0.0)):.1f}%")
        col3.metric("Latencia prom.", f"{float(metrics.get('avg_latency_ms', 0.0)):.1f} ms")
        col4.metric("Latencia p95", f"{float(metrics.get('p95_latency_ms', 0.0)):.1f} ms")

        if cache_stats:
            st.markdown("**Cache SQL**")
            cache_col1, cache_col2, cache_col3 = st.columns(3)
            cache_col1.metric("Entradas", int(cache_stats.get("entries", 0)))
            cache_col2.metric("Hits", int(cache_stats.get("hits", 0)))
            cache_col3.metric("Hit ratio", f"{float(cache_stats.get('hit_ratio', 0.0)) * 100:.1f}%")

        alerts = get_recent_alerts(limit=10)
        st.markdown("**Alertas recientes**")
        if not alerts:
            st.success("Sin alertas recientes.")
        else:
            for alert in alerts:
                st.warning(alert)

        events = get_recent_events(limit=10)
        if events:
            st.markdown("**Eventos recientes**")
            rows = [
                {
                    "timestamp": event.timestamp,
                    "origen": event.source,
                    "ok": "Sí" if event.success else "No",
                    "cache": "Sí" if event.cached else "No",
                    "latencia_ms": event.duration_ms,
                    "filas": event.row_count,
                }
                for event in events
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_field_guide() -> None:
    """Muestra tablas y campos disponibles para orientar preguntas."""
    with st.expander("Guía de campos disponibles", expanded=False):
        st.markdown(
            "Usa esta guía para saber qué puedes preguntar. "
            "Puedes combinar tablas usando sus relaciones."
        )
        st.markdown("**Relaciones principales**")
        st.markdown(
            "- customers.id = vehicles.customer_id\n"
            "- customers.id = sales.customer_id\n"
            "- customers.id = services.customer_id\n"
            "- customers.id = service_appointments.customer_id\n"
            "- customers.id = insurance_policies.customer_id\n"
            "- vehicles.id = sales.vehicle_id\n"
            "- vehicles.id = services.vehicle_id\n"
            "- vehicles.id = service_appointments.vehicle_id\n"
            "- vehicles.id = insurance_policies.vehicle_id"
        )

        st.markdown("**Tablas y campos (con tipo y ejemplo)**")
        for table_name, details in FIELD_GUIDE_DETAILS.items():
            st.markdown(f"**{table_name}**")
            guide_df = pd.DataFrame(details)
            guide_df["campo"] = guide_df["field"].apply(_friendly_column_name)
            guide_df = guide_df.rename(
                columns={
                    "campo": "Campo",
                    "field": "Nombre técnico",
                    "type": "Tipo",
                    "example": "Ejemplo",
                }
            )
            st.dataframe(
                guide_df[["Campo", "Nombre técnico", "Tipo", "Ejemplo"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**Ejemplos de preguntas útiles**")
        st.markdown(
            "- Ventas totales por estado y mes.\n"
            "- Top 10 clientes por monto vendido.\n"
            "- Tiempo promedio de recompra por cliente o segmento.\n"
            "- Clientes sin póliza activa para ofrecer seguro.\n"
            "- Edad promedio de clientes compradores.\n"
            "- Tipo de unidad preferido por rango de edad y género.\n"
            "- Clientes con vehículo pero sin ventas.\n"
            "- Servicios por tipo y costo promedio.\n"
            "- Pronóstico de ventas por canal para 3 meses."
        )


def _render_sidebar_controls(
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    max_rows: int,
    llm_timeout: int,
    cache_ttl_seconds: int,
    cache_max_entries: int,
) -> tuple[str, str, str, int, int, int, int, int, str, str]:
    """Renderiza panel lateral con referencias y configuración."""
    with st.sidebar:
        st.markdown("## Panel lateral")

        with st.expander("Preguntas de referencia", expanded=False):
            st.caption("Selecciona una y se copiará al input de consulta.")
            st.markdown("**Generales**")
            for idx, question in enumerate(RECOMMENDED_QUESTIONS):
                if st.button(question, key=f"q_ref_{idx}", use_container_width=True):
                    st.session_state["question_input"] = question
                    st.rerun()

            st.markdown("**Demo comercial**")
            for idx, question in enumerate(DEMO_COMMERCIAL_QUESTIONS):
                if st.button(question, key=f"q_comm_{idx}", use_container_width=True):
                    st.session_state["question_input"] = question
                    st.rerun()

        default_horizon = _nearest_horizon_option(
            extract_horizon_from_question(st.session_state.get("question_input", ""), default=3)
        )
        default_method = extract_method_from_question(
            st.session_state.get("question_input", ""), default="moving_average"
        )
        default_dimension = extract_dimension_from_question(
            st.session_state.get("question_input", ""), default="total"
        )
        if default_method not in FORECAST_METHODS:
            default_method = "moving_average"
        if default_dimension not in FORECAST_DIMENSIONS:
            default_dimension = "total"

        with st.expander("Configuración", expanded=False):
            dwh_url = st.text_input("DWH_URL", value=dwh_url)
            llm_endpoint = st.text_input(
                "LLM_ENDPOINT",
                value=llm_endpoint,
                help="Si esta app corre en la nube, 127.0.0.1 apunta al servidor cloud, no a tu PC.",
            )
            llm_model = st.text_input("LLM_MODEL", value=llm_model)
            max_rows = int(
                st.number_input(
                    "MAX_ROWS",
                    min_value=1,
                    max_value=10000,
                    value=int(max_rows),
                    step=10,
                )
            )
            llm_timeout = int(
                st.number_input(
                    "LLM_TIMEOUT_SECONDS",
                    min_value=1,
                    max_value=600,
                    value=int(llm_timeout),
                    step=5,
                )
            )
            cache_ttl_seconds = int(
                st.number_input(
                    "CACHE_TTL_SECONDS",
                    min_value=0,
                    max_value=3600,
                    value=int(cache_ttl_seconds),
                    step=10,
                    help="TTL en segundos para cache de resultados SQL (0 deshabilita cache).",
                )
            )
            cache_max_entries = int(
                st.number_input(
                    "CACHE_MAX_ENTRIES",
                    min_value=1,
                    max_value=50000,
                    value=int(cache_max_entries),
                    step=50,
                    help="Número máximo de consultas cacheadas (LRU).",
                )
            )
            st.markdown("---")
            st.caption("Configuración de pronóstico")
            horizon_months = int(
                st.selectbox(
                    "Horizonte (meses)",
                    [1, 3, 6, 12],
                    index=[1, 3, 6, 12].index(default_horizon),
                    help="Cantidad de meses a estimar hacia adelante.",
                )
            )
            forecast_method = st.selectbox(
                "Método",
                list(FORECAST_METHODS.keys()),
                index=list(FORECAST_METHODS.keys()).index(default_method),
                format_func=lambda key: FORECAST_METHODS[key],
            )
            forecast_dimension = st.selectbox(
                "Nivel de agregación",
                list(FORECAST_DIMENSIONS.keys()),
                index=list(FORECAST_DIMENSIONS.keys()).index(default_dimension),
                format_func=lambda key: FORECAST_DIMENSIONS[key],
            )

    return (
        dwh_url,
        llm_endpoint,
        llm_model,
        max_rows,
        llm_timeout,
        cache_ttl_seconds,
        cache_max_entries,
        horizon_months,
        forecast_method,
        forecast_dimension,
    )


def main() -> None:
    st.set_page_config(page_title="Asistente Inteligente de Analítica", page_icon="🧠", layout="wide")
    st.title("Asistente Inteligente de Analítica")
    st.info("Modo demo: solo escribe tu pregunta y presiona Consultar.")
    _render_field_guide()

    demo_info = ensure_demo_db(DEMO_DB_PATH)
    st.success(
        "Base demo lista: "
        f"{demo_info['customers']} clientes, "
        f"{demo_info['vehicles']} vehiculos, "
        f"{demo_info['sales']} ventas, "
        f"{demo_info['services']} servicios, "
        f"{demo_info['service_appointments']} citas servicio, "
        f"{demo_info['insurance_policies']} polizas."
    )

    # Configuracion fija por defecto (puede sobreescribirse por variables de entorno).
    dwh_url = os.getenv("DWH_URL", DEFAULT_DWH_URL)
    llm_endpoint = os.getenv("LLM_ENDPOINT", DEFAULT_LLM_ENDPOINT)
    llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    max_rows = _env_int("MAX_ROWS", 200)
    llm_timeout = _env_int("LLM_TIMEOUT_SECONDS", 180)
    cache_ttl_seconds = _env_int("CACHE_TTL_SECONDS", 120)
    cache_max_entries = _env_int("CACHE_MAX_ENTRIES", 500)
    schema_hint_file = os.getenv("SCHEMA_HINT_FILE", "")

    default_question = "¿Cuántos clientes hay por estado?"
    if "question_input" not in st.session_state:
        st.session_state["question_input"] = default_question

    (
        dwh_url,
        llm_endpoint,
        llm_model,
        max_rows,
        llm_timeout,
        cache_ttl_seconds,
        cache_max_entries,
        horizon_months,
        forecast_method,
        forecast_dimension,
    ) = _render_sidebar_controls(
        dwh_url=dwh_url,
        llm_endpoint=llm_endpoint,
        llm_model=llm_model,
        max_rows=max_rows,
        llm_timeout=llm_timeout,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        question = st.text_area(
            "Pregunta de negocio",
            key="question_input",
            height=110,
            placeholder="Ejemplo: Top 20 agencias por número de clientes consolidados.",
        )
    with col2:
        st.markdown("### Ejecutar")
        run = st.button("Consultar", type="primary", use_container_width=True)
        run_forecast = st.button("Generar pronóstico", use_container_width=True)

    if not run and not run_forecast:
        st.info("Escribe tu pregunta y presiona 'Consultar' o 'Generar pronóstico'.")
        return

    if not dwh_url.strip():
        st.error("Debes indicar DWH_URL.")
        return
    if not question.strip():
        st.error("Debes escribir una pregunta.")
        return

    _prepare_new_result_view()
    schema_hint = _read_schema_hint(schema_hint_file) or DEFAULT_SCHEMA_HINT

    forecast_intent = is_forecast_intent(question.strip())
    if run and forecast_intent and not run_forecast:
        st.info("Se detectó intención de pronóstico; se usará el módulo de forecast en Python.")

    if run_forecast or (run and forecast_intent):
        with st.spinner("Calculando pronóstico de ventas..."):
            try:
                dwh = DwhClient.from_url(
                    dwh_url.strip(),
                    default_limit=int(max_rows),
                    cache_ttl_seconds=int(cache_ttl_seconds),
                    cache_max_entries=int(cache_max_entries),
                )
                forecast_result = compute_sales_forecast(
                    dwh_client=dwh,
                    horizon_months=int(horizon_months),
                    method=forecast_method,
                    dimension=forecast_dimension,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                st.error(f"Error calculando pronóstico: {message}")
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
                if "no encryption" in message:
                    st.info(
                        "El servidor reporta conexion sin cifrado. Si tu instancia exige SSL, "
                        "usa una URL DWH con sslmode=require y habilita SSL en PostgreSQL."
                    )
                _render_observability_panel(cache_stats=dwh.get_cache_stats())
                return

        cache_stats = dwh.get_cache_stats()
        _render_forecast_result(forecast_result, cache_stats=cache_stats)
        _render_observability_panel(cache_stats=cache_stats)
        return

    with st.spinner("Procesando consulta..."):
        cache_stats: dict[str, Any] | None = None
        try:
            agent = _build_agent(
                dwh_url=dwh_url.strip(),
                llm_endpoint=llm_endpoint.strip(),
                llm_model=llm_model.strip(),
                row_limit=int(max_rows),
                llm_timeout_seconds=int(llm_timeout),
                schema_hint=schema_hint,
                cache_ttl_seconds=int(cache_ttl_seconds),
                cache_max_entries=int(cache_max_entries),
            )
            result = agent.answer(question.strip())
            cache_stats = agent._dwh.get_cache_stats()  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            st.error(f"Error ejecutando consulta: {message}")
            if "No se pudo contactar Ollama" in message or "Connection refused" in message:
                st.warning(
                    "No se puede alcanzar Ollama desde este servidor. "
                    "Si tu Ollama corre en tu laptop, debes exponerlo por una URL publica "
                    "(por ejemplo, tunel) y usarla en LLM_ENDPOINT."
                )
            if "HTTP 500" in message or "Internal Server Error" in message:
                st.warning(
                    "Ollama respondió con error interno (HTTP 500), normalmente por falta de memoria "
                    "o saturación del modelo. Se recomienda usar un modelo más liviano."
                )
                if llm_model != FALLBACK_LLM_MODEL:
                    st.info(
                        f"Sugerencia: cambiar LLM_MODEL a {FALLBACK_LLM_MODEL}. "
                        "Aplicando fallback automático para esta consulta..."
                    )
                    try:
                        fallback_agent = _build_agent(
                            dwh_url=dwh_url.strip(),
                            llm_endpoint=llm_endpoint.strip(),
                            llm_model=FALLBACK_LLM_MODEL,
                            row_limit=int(max_rows),
                            llm_timeout_seconds=int(llm_timeout),
                            schema_hint=schema_hint,
                            cache_ttl_seconds=int(cache_ttl_seconds),
                            cache_max_entries=int(cache_max_entries),
                        )
                        result = fallback_agent.answer(question.strip())
                        cache_stats = fallback_agent._dwh.get_cache_stats()  # noqa: SLF001
                        st.success(f"Consulta recuperada usando fallback: {FALLBACK_LLM_MODEL}")
                        _render_query_result(
                            result,
                            model_used=FALLBACK_LLM_MODEL,
                            cache_stats=cache_stats,
                        )
                        _render_observability_panel(cache_stats=cache_stats)
                        return
                    except Exception as fallback_exc:  # noqa: BLE001
                        st.error(f"Fallback falló: {fallback_exc}")
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
            _render_observability_panel(cache_stats=cache_stats)
            return

    _render_query_result(result, cache_stats=cache_stats)
    _render_observability_panel(cache_stats=cache_stats)


if __name__ == "__main__":
    main()
