from __future__ import annotations

import sys
from io import BytesIO
import os
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from agente_dwh.bootstrap_env import load_dotenv_from_project_root

load_dotenv_from_project_root()
import json
import re
import html
from typing import Any

import streamlit as st
import pandas as pd

try:
    from .agent import DwhAgent, resolve_llm_profile
    from .config import (
        REQUIRED_DWH_DATABASE_NAME,
        ConfigError,
        effective_dwh_url,
        normalize_dwh_url_string,
        validate_dwh_url_targets_vgd_prod,
    )
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
    from .llm_local import LLMError, LocalOllamaClient
    from .observability import get_metrics_snapshot, get_recent_alerts, get_recent_events
except ImportError:
    # Cuando Streamlit ejecuta el archivo como script, no hay paquete padre.
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agente_dwh.agent import DwhAgent, resolve_llm_profile
    from agente_dwh.config import (
        REQUIRED_DWH_DATABASE_NAME,
        ConfigError,
        effective_dwh_url,
        normalize_dwh_url_string,
        validate_dwh_url_targets_vgd_prod,
    )
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
    from agente_dwh.llm_local import LLMError, LocalOllamaClient
    from agente_dwh.observability import get_metrics_snapshot, get_recent_alerts, get_recent_events

DEFAULT_DWH_URL = normalize_dwh_url_string(os.getenv("DWH_URL", ""))
DEFAULT_LLM_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_LLM_MODEL = "qwen2.5-coder:7b"
FALLBACK_LLM_MODEL = "qwen2.5:7b"
DEFAULT_SCHEMA_HINT = """Dialecto del DWH: PostgreSQL. Todas las consultas generadas deben usar solo sintaxis válida en PostgreSQL.

Tablas demo disponibles:
- Regla: si la consulta muestra datos por vehículo (vehicles o vehicle_id), incluye siempre vin (JOIN vehicles si hace falta).
- CRÍTICO — columna agency_id / idAgency: en ESTE esquema demo NO EXISTE en sales, services, service_appointments,
  insurance_policies, customers ni vehicles. NUNCA escribas sales.agency_id ni GROUP BY agency_id sobre sales.
  Si preguntan por agencia/sucursal y no hay esa columna en el esquema, usa alternativas del demo: estado del cliente
  (customers.state vía JOIN desde sales), canal (sales.channel), segmento (customers.segment), vendedor (sales.seller),
  o la vista agregada mv_sales_monthly. En otros DWH reales puede existir agency_id solo donde el esquema lo liste explícitamente.
- customers(id, customer_code, full_name, gender, age, birth_date, email, phone, city, state, segment, monthly_income, risk_profile, created_at)
- vehicles(id, customer_id, vin, plate, brand, model, unit_type, year, fuel_type, mileage, created_at)
- sales(id, customer_id, vehicle_id, sale_date, amount, channel, seller, payment_method, status)
- services(id, customer_id, vehicle_id, service_date, service_type, cost, status, workshop, notes)  ← tiene cost y service_date
- service_appointments(id, customer_id, vehicle_id, appointment_date, service_type, appointment_status, workshop, cancellation_reason, attended, created_at, updated_at)  ← NO tiene cost, notes ni service_date

IMPORTANTE — services vs service_appointments:
- services: servicios realizados; tiene cost (monto del servicio), service_date, status y notes.
- service_appointments: agenda de citas; tiene appointment_date, appointment_status, cancellation_reason, attended. NO tiene cost, notes ni service_date.
- Si necesitas costo de servicio, usa la tabla services (columna cost). No intentes obtener cost de service_appointments.
- Si necesitas estado de una cita, usa service_appointments.appointment_status (no status).

- insurance_policies(id, customer_id, vehicle_id, policy_start_date, policy_end_date, insurer, coverage_type, annual_premium, policy_status, claim_count, last_claim_date)  ← policy_status: activa, vencida, cancelada (no 'active')
- mv_sales_monthly(year_month, state, channel, segment, total_sales, sales_count)  ← agregados por mes; útil para tendencias sin fila a fila

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
    "Top 10 talleres con más no show en citas de servicio.",
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
    "¿Qué talleres tienen más citas canceladas o no show?",
    "Top 10 talleres con más no show en citas de servicio.",
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
    "appointment_status": "Estatus Cita",
    "cancellation_reason": "Motivo Cancelación",
    "attended": "Asistió",
    "updated_at": "Última Actualización",
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
    # Alias frecuentes generados por LLM (EN -> ES)
    "frequency": "Cantidad",
    "count": "Conteo",
    "total": "Total",
    "total_count": "Total",
    "total_appointments": "Total Citas",
    "total_programmed_appointments": "Citas Programadas",
    "completed_appointments": "Citas Completadas",
    "cancelled_appointments": "Citas Canceladas",
    "no_show_appointments": "Citas No Show",
    "conversion_rate": "Tasa de Conversión",
    "no_show_rate": "Tasa de No Show",
    "appointment_conversion_rate": "Tasa de Conversión Citas",
    "cancelation_rate": "Tasa de Cancelación",
    "cancellation_rate": "Tasa de Cancelación",
    # Alias frecuentes en agregados (LLM / inglés)
    "sale_year": "Año de venta",
    "sales_year": "Año de venta",
    "year_of_sale": "Año de venta",
    "sales_count": "Cantidad de ventas",
    "sale_count": "Cantidad de ventas",
    "num_sales": "Cantidad de ventas",
    "n_sales": "Cantidad de ventas",
    "total_amount": "Monto total",
    "total_sales": "Total de ventas (monto)",
    "sales_total": "Total de ventas (monto)",
    "sum_amount": "Monto total",
    "year_month": "Mes (año-mes)",
    "revenue": "Ingresos",
    "total_revenue": "Ingresos totales",
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
    "programada": "Programada",
    "no_show": "No Show",
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

NL_SUMMARY_MAX_ROWS_LLM = 35
NL_HEURISTIC_MAX_ROWS = 8
NL_SUMMARY_MAX_COLS_HEURISTIC = 16
NL_TRUNCATE_CELL_LEN = 140

NL_SUMMARY_SYSTEM_PROMPT = """Eres un asistente de analítica que explica resultados de consultas a datos.
Responde SIEMPRE y EXCLUSIVAMENTE en español (tono claro y profesional). No escribas en inglés ni en otro idioma;
ni una frase mezclada. Única excepción: siglas o nombres propios inevitables (p. ej. VIN, SQL, una marca).

Reglas:
1) Usa solo información presente en el JSON de datos; no inventes filas, columnas ni cifras.
2) Entre 1 y 4 frases cortas, o un párrafo breve. Si la pregunta pide un dato concreto (p. ej. un número de póliza, un total), menciónalo en la primera frase.
3) Si hay muchas filas en el total, resume el patrón o los extremos relevantes y aclara que el detalle completo está en la tabla.
4) No uses tablas markdown. Puedes usar listas cortas con guiones si ayudan.
5) No repitas la pregunta literalmente al inicio; ve al resultado.
6) Toda cantidad monetaria debe ir en pesos mexicanos con exactamente dos decimales, formato MXN $X,XXX.XX
   (coma como separador de miles y punto decimal). No mezcles USD u otras divisas salvo que el dato lo indique explícitamente.
7) Idioma: todo el texto visible para el usuario debe estar en español; si el JSON trae etiquetas en inglés,
   tradúcelas al explicar (p. ej. «canal» en lugar de «channel» cuando describas la columna)."""

MXN_COLUMNS = frozenset({"monthly_income", "amount", "cost", "annual_premium"})
_MXN_COLUMN_SYNONYMS = frozenset(
    {
        "total_amount",
        "total_sales",
        "sum_amount",
        "sale_total",
        "sales_total",
        "total_revenue",
        "revenue",
        "subtotal",
        "ingresos",
        "ingresos_totales",
        "monto_total",
        "venta_total",
        "avg_amount",
        "average_amount",
        "mean_amount",
        "max_amount",
        "min_amount",
        "sale_amount",
        "precio",
        "precio_unitario",
    }
)


def _column_is_mxn_formatted(name: Any) -> bool:
    """True si la columna representa dinero y debe mostrarse como MXN $X,XXX.XX."""
    key = str(name).strip().lower()
    if key in MXN_COLUMNS or key in _MXN_COLUMN_SYNONYMS:
        return True
    if key.endswith("_amount"):
        return True
    if "_monto" in key or key.startswith("monto_"):
        return True
    return False


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
        {"field": "service_type", "type": "TEXT", "example": "Mantenimiento preventivo"},
        {"field": "appointment_status", "type": "TEXT", "example": "no_show"},
        {"field": "workshop", "type": "TEXT", "example": "Taller Norte"},
        {"field": "cancellation_reason", "type": "TEXT", "example": "Conflicto de agenda"},
        {"field": "attended", "type": "INTEGER", "example": "0"},
        {"field": "created_at", "type": "DATE/TEXT", "example": "2026-03-12"},
        {"field": "updated_at", "type": "DATE/TEXT", "example": "2026-03-18"},
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


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        v = float(raw)
    except ValueError:
        return default
    return v if 0.0 <= v <= 2.0 else default


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
    llm_temperature: float = 0.2,
    *,
    llm_profile: str = "default",
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
        temperature=llm_temperature,
    )
    return DwhAgent(
        dwh_client=dwh,
        llm_client=llm,
        schema_hint=schema_hint,
        llm_profile=llm_profile,
    )


SESSION_KEY_CACHED_DW_AGENT = "cached_dw_agent_instance"
SESSION_KEY_CACHED_DW_AGENT_CFG = "cached_dw_agent_config_tuple"


def _get_session_agent(
    *,
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    row_limit: int,
    llm_timeout_seconds: int,
    schema_hint: str,
    schema_hint_file: str,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    llm_temperature: float,
) -> DwhAgent:
    """
    Reutiliza DwhAgent en la sesión si la configuración no cambió: mantiene pool SQLAlchemy y caché de
    resultados del DWH entre consultas (menos latencia en repetidas / mismos SQL).
    """
    llm_profile = resolve_llm_profile(schema_hint_file, dwh_url=dwh_url)
    cfg = (
        dwh_url.strip(),
        llm_endpoint.strip(),
        llm_model.strip(),
        int(row_limit),
        int(llm_timeout_seconds),
        schema_hint,
        int(cache_ttl_seconds),
        int(cache_max_entries),
        round(float(llm_temperature), 6),
        llm_profile,
    )
    if st.session_state.get(SESSION_KEY_CACHED_DW_AGENT_CFG) != cfg:
        st.session_state[SESSION_KEY_CACHED_DW_AGENT_CFG] = cfg
        st.session_state[SESSION_KEY_CACHED_DW_AGENT] = _build_agent(
            dwh_url=cfg[0],
            llm_endpoint=cfg[1],
            llm_model=cfg[2],
            row_limit=cfg[3],
            llm_timeout_seconds=cfg[4],
            schema_hint=cfg[5],
            cache_ttl_seconds=cfg[6],
            cache_max_entries=cfg[7],
            llm_temperature=cfg[8],
            llm_profile=cfg[9],
        )
    return st.session_state[SESSION_KEY_CACHED_DW_AGENT]


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
        number = round(float(value), 2)
    except (TypeError, ValueError):
        return str(value)
    return f"MXN ${number:,.2f}"


def _format_money_in_chat_text(text: str) -> str:
    """
    Normaliza cantidades monetarias reconocibles en texto (resúmenes, chat) a MXN $X,XXX.XX.
    Idempotente con textos que ya usan el mismo formato.
    """
    if not text:
        return text

    def norm_num(raw: str) -> float | None:
        t = raw.strip().replace(" ", "").replace(",", "")
        if not t or t in (".", "-", "–"):
            return None
        try:
            return float(t)
        except ValueError:
            return None

    def sub_num_suffix(m: re.Match[str]) -> str:
        n = norm_num(m.group(1))
        if n is None:
            return m.group(0)
        return _format_mxn_value(n)

    out = re.sub(
        r"\b([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
        r"(?:pesos?(?:\s+mexicanos)?|MXN)\b",
        sub_num_suffix,
        text,
        flags=re.IGNORECASE,
    )

    def sub_mxn_leading(m: re.Match[str]) -> str:
        n = norm_num(m.group(1))
        if n is None:
            return m.group(0)
        return _format_mxn_value(n)

    out = re.sub(
        r"\b(?:MXN|mxn)\s*:?\s*\$?\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b",
        sub_mxn_leading,
        out,
        flags=re.IGNORECASE,
    )

    def sub_dollar(m: re.Match[str]) -> str:
        n = norm_num(m.group(1))
        if n is None:
            return m.group(0)
        return _format_mxn_value(n)

    # No volver a procesar $ si ya va tras "MXN " (evita "MXN " + sustitución -> "MXN MXN $…").
    out = re.sub(
        r"(?<![Mm][Xx][Nn] )(?<![\w/])\$\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b",
        sub_dollar,
        out,
    )
    # Por si el modelo o pasos previos dejaron "MXN" repetido antes del símbolo $.
    out = re.sub(
        r"(?:\bMXN\s+)+(?=\$)",
        "MXN ",
        out,
        flags=re.IGNORECASE,
    )
    return out


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
        if _column_is_mxn_formatted(column):
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


def _prepare_result_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Traduce valores, formatea montos/tiempos y renombra columnas a etiquetas legibles."""
    df = _translate_dataframe_values(pd.DataFrame(rows))
    df = _format_mxn_columns(df)
    pretty_df, _ = _prettify_dataframe_columns(df)
    return pretty_df


def _make_summary_llm_client(
    llm_endpoint: str,
    llm_model: str,
    *,
    llm_timeout_seconds: int,
    llm_temperature: float,
) -> LocalOllamaClient:
    """Cliente Ollama para resumen en lenguaje natural (temperatura ligeramente mayor que SQL)."""
    return LocalOllamaClient(
        base_url=llm_endpoint.strip(),
        model_name=llm_model.strip(),
        timeout_seconds=int(llm_timeout_seconds),
        temperature=min(0.5, float(llm_temperature) + 0.15),
    )


def _truncate_summary_cell(value: Any, max_len: int = NL_TRUNCATE_CELL_LEN) -> str:
    s = _metric_display_value(value)
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _find_vin_column_key(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    for k in rows[0].keys():
        if str(k).lower() == "vin":
            return k
    return None


def _ordered_distinct_vins(rows: list[dict[str, Any]], key: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "<na>"):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _multi_vin_markdown_line(rows: list[dict[str, Any]]) -> str | None:
    """Si hay más de un VIN distinto en el resultado, una línea con todos separados por comas."""
    if len(rows) < 2:
        return None
    key = _find_vin_column_key(rows)
    if not key:
        return None
    ordered = _ordered_distinct_vins(rows, key)
    if len(ordered) <= 1:
        return None
    return "**VINs:** " + ", ".join(ordered)


def _append_multi_vin_summary_line(text: str, rows: list[dict[str, Any]]) -> str:
    line = _multi_vin_markdown_line(rows)
    if not line:
        return text
    return f"{text.rstrip()}\n\n{line}"


def _heuristic_agency_catalog_summary(rows: list[dict[str, Any]]) -> str | None:
    """Resumen fiable cuando el resultado tiene forma de catálogo agencies (conteo o listado id/nombre)."""
    if not rows:
        return None
    keys_lower = {str(k).lower() for k in rows[0].keys()}
    if "total_agencias" in keys_lower and len(rows) == 1:
        r0 = rows[0]
        for k in r0:
            if str(k).lower() == "total_agencias":
                val = r0[k]
                return (
                    f"En el catálogo **agencies** hay **{val}** agencias (conteo directo en base de datos)."
                )
    if "id_agencia" in keys_lower and "nombre" in keys_lower:
        n = len(rows)
        return (
            f"Catálogo **agencies**: se listan **{n}** agencias en este resultado (hasta 500 por consulta). "
            "Usa **Ver datos** para revisar id y nombre de cada una."
        )
    return None


def _heuristic_answer_summary(rows: list[dict[str, Any]]) -> str | None:
    """
    Resumen sin LLM. Devuelve None si conviene delegar al modelo (muchas filas o muchas columnas).
    """
    if not rows:
        return (
            "La consulta no devolvió ninguna fila. Puedes ampliar criterios o revisar el detalle en la tabla."
        )
    df = _prepare_result_dataframe(rows)
    n_rows, n_cols = len(df), len(df.columns)
    if n_rows == 1:
        lines = ["Según los datos consultados:"]
        for col in df.columns:
            label = str(col)
            val = _truncate_summary_cell(df.iloc[0][col])
            lines.append(f"- **{label}:** {val}")
        return "\n".join(lines)
    if n_rows <= NL_HEURISTIC_MAX_ROWS and n_cols <= NL_SUMMARY_MAX_COLS_HEURISTIC:
        vin_raw_key = _find_vin_column_key(rows)
        skip_vin_per_row = bool(
            vin_raw_key and len(_ordered_distinct_vins(rows, vin_raw_key)) > 1
        )
        lines: list[str] = []
        for i in range(n_rows):
            pairs: list[str] = []
            for col in df.columns:
                if skip_vin_per_row and str(col).lower() == "vin":
                    continue
                pairs.append(f"**{col}:** {_truncate_summary_cell(df.iloc[i][col])}")
            lines.append(f"{i + 1}. " + " · ".join(pairs))
        return "\n".join(lines)
    return None


def _llm_answer_summary(
    llm: LocalOllamaClient,
    question: str,
    rows: list[dict[str, Any]],
) -> str:
    total = len(rows)
    cap = min(total, NL_SUMMARY_MAX_ROWS_LLM)
    sample = rows[:cap]
    pretty_df = _prepare_result_dataframe(sample)
    pretty_records = pretty_df.to_dict(orient="records")
    payload = json.dumps(pretty_records, ensure_ascii=False, default=str)
    user_msg = (
        f"Pregunta del usuario:\n{question.strip()}\n\n"
        f"Total de filas devueltas por la consulta: {total}\n"
        f"Muestra en JSON (hasta {cap} filas):\n{payload}\n\n"
        "Redacta la explicación solo en español, sin mezclar otros idiomas."
    )
    return llm.generate_natural_language(
        system_prompt=NL_SUMMARY_SYSTEM_PROMPT,
        user_prompt=user_msg,
    )


def _fallback_summary_after_llm_failure(rows: list[dict[str, Any]]) -> str:
    h = _heuristic_answer_summary(rows)
    if h is not None:
        return h
    return (
        "No se pudo generar un resumen automático con el modelo. "
        "Usa **Ver datos** en el panel inferior para revisar la tabla completa."
    )


def _compute_hybrid_answer_summary(
    question: str,
    rows: list[dict[str, Any]],
    llm: LocalOllamaClient | None,
) -> str:
    if not rows:
        return _append_multi_vin_summary_line(_heuristic_answer_summary(rows) or "", rows)

    agency_txt = _heuristic_agency_catalog_summary(rows)
    if agency_txt:
        return _append_multi_vin_summary_line(agency_txt, rows)

    if len(rows) == 1 and llm is not None:
        try:
            out = _llm_answer_summary(llm, question, rows)
        except LLMError:
            out = _heuristic_answer_summary(rows) or ""
        return _append_multi_vin_summary_line(out, rows)

    h = _heuristic_answer_summary(rows)
    if h is not None:
        return _append_multi_vin_summary_line(h, rows)
    if llm is not None:
        try:
            out = _llm_answer_summary(llm, question, rows)
        except LLMError:
            out = _fallback_summary_after_llm_failure(rows)
        return _append_multi_vin_summary_line(out, rows)
    return _append_multi_vin_summary_line(_fallback_summary_after_llm_failure(rows), rows)


def _rows_have_numeric_for_chart(rows: list[dict[str, Any]]) -> bool:
    """True si hay al menos una columna numérica en bruto (antes de formatear para pantalla)."""
    if not rows:
        return False
    df = pd.DataFrame(rows)
    if df.empty:
        return False
    return any(pd.api.types.is_numeric_dtype(df[col]) for col in df.columns)


def _metric_display_value(value: Any) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except TypeError:
        pass
    s = str(value).strip()
    if s.lower() in ("nan", "none", "<na>"):
        return "—"
    return s


def _norm_col_key(col: str) -> str:
    return str(col).lower().replace(" ", "_").replace("-", "_")


def _is_agency_id_like_column(col: str) -> bool:
    l = _norm_col_key(col)
    return l in (
        "id_agency",
        "agency_id",
        "idagency",
        "cod_agencia",
        "codigo_agencia",
        "agencyid",
        "agency_code",
    )


def _preferred_agency_label_x_column(candidates: list[str]) -> str | None:
    """Primera columna que sirve como etiqueta legible de agencia (evitar solo id)."""
    preferred_exact = (
        "agency_name",
        "nombre_agencia",
        "agencia_nombre",
        "nombre_sucursal",
        "sucursal",
        "branch_name",
        "dealer_name",
        "agencia",
    )
    lc = {_norm_col_key(c): c for c in candidates}
    for p in preferred_exact:
        if p in lc:
            return lc[p]
    has_agency_id = any(_is_agency_id_like_column(c) for c in candidates)
    if has_agency_id and "name" in lc:
        return lc["name"]
    return None


def _ordered_chart_x_candidates(columns: list[str], numeric_cols: list[str]) -> list[str]:
    """Ordena opciones de eje X: nombres de agencia primero; ids de agencia al final."""
    num_set = set(numeric_cols)
    non_num = [c for c in columns if c not in num_set]
    nums = [c for c in columns if c in num_set]

    def sort_key(col: str) -> tuple[int, str]:
        l = _norm_col_key(col)
        if l == "agency_name":
            return (0, col)
        if l in (
            "nombre_agencia",
            "agencia_nombre",
            "nombre_sucursal",
            "sucursal",
            "branch_name",
            "dealer_name",
            "agencia",
        ):
            return (1, col)
        if l == "name":
            return (2, col)
        if _is_agency_id_like_column(col):
            return (80, col)
        if l.endswith("_id"):
            return (60, col)
        if col in num_set:
            return (70, col)
        return (10, col)

    return sorted(non_num, key=sort_key) + sorted(nums, key=sort_key)


def _render_rows(rows: list[dict[str, Any]], *, widget_key_prefix: str = "") -> None:
    if not rows:
        st.info("La consulta no regresó filas.")
        return
    st.success(f"Filas obtenidas: {len(rows)}")
    pretty_df = _prepare_result_dataframe(rows)
    st.dataframe(pretty_df, use_container_width=True)
    try:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            pretty_df.to_excel(writer, index=False, sheet_name="Resultados")
        excel_btn: dict[str, Any] = {
            "label": "Descargar resultados en Excel",
            "data": excel_buffer.getvalue(),
            "file_name": "resultados_consulta.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "use_container_width": True,
        }
        if widget_key_prefix:
            excel_btn["key"] = f"{widget_key_prefix}download_excel_results"
        st.download_button(**excel_btn)
    except ModuleNotFoundError:
        csv_data = pretty_df.to_csv(index=False).encode("utf-8-sig")
        st.info("Exportación Excel no disponible en este entorno. Descarga CSV habilitada.")
        csv_btn: dict[str, Any] = {
            "label": "Descargar resultados en CSV",
            "data": csv_data,
            "file_name": "resultados_consulta.csv",
            "mime": "text/csv",
            "use_container_width": True,
        }
        if widget_key_prefix:
            csv_btn["key"] = f"{widget_key_prefix}download_csv_results"
        st.download_button(**csv_btn)


def _render_chart_options(rows: list[dict[str, Any]], *, widget_key_prefix: str = "") -> None:
    """Gráficas con columnas numéricas; si no hay, tabla y/o tarjetas (métricas)."""
    if not rows:
        return

    kp = widget_key_prefix
    sx = f"{kp}chart_x_col"
    sy = f"{kp}chart_y_col"
    st_chart_type = f"{kp}chart_type"

    df = _translate_dataframe_values(pd.DataFrame(rows))
    if df.empty:
        return

    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if not numeric_cols:
        st.markdown("### Vista sin gráfica numérica")
        st.caption(
            "Este resultado no tiene columnas numéricas para barras o líneas. "
            "Aquí tienes los datos en tabla o como tarjetas."
        )
        pretty_df = _prepare_result_dataframe(rows)
        if len(pretty_df) == 1:
            row = pretty_df.iloc[0]
            items = list(row.items())
            chunk = 4
            for i in range(0, len(items), chunk):
                batch = items[i : i + chunk]
                cols = st.columns(len(batch))
                for j, (raw_key, val) in enumerate(batch):
                    cols[j].metric(_friendly_column_name(raw_key), _metric_display_value(val))
        else:
            st.dataframe(pretty_df, use_container_width=True)
            st.caption("Descarga Excel o CSV en **Detalle (tabla y descarga)**.")
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
            if _column_is_mxn_formatted(value_col):
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
    chart_type = st.selectbox(
        "Tipo de gráfica",
        ["Barras", "Línea", "Área"],
        index=0,
        key=st_chart_type,
    )

    x_candidates = _ordered_chart_x_candidates(list(df.columns), numeric_cols)
    label_map = {col: _friendly_column_name(col) for col in x_candidates}
    preferred_x = _preferred_agency_label_x_column(x_candidates)
    default_x = preferred_x if preferred_x is not None else x_candidates[0]

    # Nuevo resultado (columnas distintas): vuelve a preferir nombre de agencia, no id_agency.
    sig_key = f"{kp}chart_result_sig"
    sig = tuple(sorted(str(c) for c in df.columns))
    if st.session_state.get(sig_key) != sig:
        st.session_state[sig_key] = sig
        st.session_state[sx] = default_x

    # Evita errores cuando cambian las columnas entre consultas y el estado previo queda inválido.
    if sx not in st.session_state or st.session_state[sx] not in x_candidates:
        st.session_state[sx] = default_x
    if sy not in st.session_state or st.session_state[sy] not in numeric_cols:
        st.session_state[sy] = numeric_cols[0]

    x_col = st.selectbox(
        "Columna eje X",
        x_candidates,
        key=sx,
        format_func=lambda value: label_map.get(value, str(value)),
    )
    y_candidates = [col for col in numeric_cols if col != x_col]
    if not y_candidates:
        st.info("No hay una segunda columna numérica disponible para eje Y.")
        return
    if sy not in st.session_state or st.session_state[sy] not in y_candidates:
        st.session_state[sy] = y_candidates[0]
    y_col = st.selectbox(
        "Columna eje Y (numérica)",
        y_candidates,
        key=sy,
        format_func=lambda value: label_map.get(value, str(value)),
    )

    chart_df = df[[x_col, y_col]].copy()
    chart_df = chart_df.dropna()
    if chart_df.empty:
        st.info("No hay datos válidos para construir la gráfica.")
        return

    # Renombramos a etiquetas amigables para que ejes y tooltips no muestren
    # nombres técnicos (snake_case/inglés) al cliente.
    friendly_x = label_map.get(x_col, _friendly_column_name(x_col))
    friendly_y = label_map.get(y_col, _friendly_column_name(y_col))
    chart_df = chart_df.rename(columns={x_col: friendly_x, y_col: friendly_y})

    # index de texto para categorías y fechas convertibles
    chart_df[friendly_x] = chart_df[friendly_x].astype(str)
    chart_df = chart_df.set_index(friendly_x)

    # Pasamos solo la serie Y para evitar errores por columnas faltantes al rerender.
    if chart_type == "Barras":
        st.bar_chart(chart_df[[friendly_y]], use_container_width=True)
    elif chart_type == "Línea":
        st.line_chart(chart_df[[friendly_y]], use_container_width=True)
    else:
        st.area_chart(chart_df[[friendly_y]], use_container_width=True)


CHAT_DATA_DIALOG_REQUEST_KEY = "chat_data_dialog_request"


@st.dialog("Gráfica", width="large")
def _open_chat_chart_dialog(rows: list[dict[str, Any]]) -> None:
    """Modal: misma vista de gráfica / datos que el panel principal."""
    if not rows:
        st.info("Sin filas para mostrar.")
        return
    _render_chart_options(rows, widget_key_prefix="dlg_chat_chart_")


@st.dialog("Detalle", width="large")
def _open_chat_detail_dialog(rows: list[dict[str, Any]]) -> None:
    """Modal: tabla y descarga."""
    _render_rows(rows, widget_key_prefix="dlg_chat_detail_")


def _extract_pg_hba_ip(error_message: str) -> str:
    """Extrae IP origen reportada por PostgreSQL en errores pg_hba."""
    match = re.search(r'host "(\d{1,3}(?:\.\d{1,3}){3})"', error_message)
    return match.group(1) if match else ""


def _nearest_horizon_option(value: int) -> int:
    options = [1, 3, 6, 12]
    return min(options, key=lambda opt: abs(opt - value))


def _format_conversation_transcript(
    turns: list[dict[str, Any]],
    max_turns: int = 6,
    vehicle_focus: dict[str, Any] | None = None,
) -> str:
    if not turns:
        return ""
    recent = turns[-max_turns:]
    lines = [
        "Historial reciente de esta sesión (úsalo para la pregunta actual: referencias como «eso», "
        "«el mismo», «y el dueño?», «sus servicios», «esta unidad», etc.):",
    ]
    for i, t in enumerate(recent, start=1):
        lines.append(f"\n--- Turno {i} ---")
        lines.append(f"Usuario: {t.get('user', '')}")
        if t.get("error"):
            lines.append(f"Error al ejecutar: {t['error']}")
            continue
        if t.get("kind") == "chitchat":
            lines.append(
                f"Asistente: {_format_money_in_chat_text(t.get('answer_summary', '') or '')}"
            )
            continue
        if t.get("kind") == "forecast":
            lines.append("Asistente: pronóstico de ventas (cálculo en Python).")
            fs = (t.get("answer_summary") or "").strip()
            if fs:
                lines.append(f"Resumen al usuario: {_format_money_in_chat_text(fs)}")
            sql = t.get("sql") or ""
            lines.append(f"SQL fuente histórico: {sql[:800]}" + ("..." if len(sql) > 800 else ""))
            lines.append(f"Filas de salida del pronóstico: {t.get('rows', 0)}")
            continue
        sql = t.get("sql") or ""
        lines.append(f"SQL ejecutado: {sql[:1200]}" + ("..." if len(sql) > 1200 else ""))
        if t.get("kpi"):
            lines.append(f"KPI determinístico: {_format_money_in_chat_text(str(t['kpi']))}")
        summary_u = (t.get("answer_summary") or "").strip()
        if summary_u:
            lines.append(f"Resumen entregado al usuario: {_format_money_in_chat_text(summary_u)}")
        lines.append(f"Filas devueltas: {t.get('rows', 0)}")
    if vehicle_focus:
        vf_bits: list[str] = []
        if vehicle_focus.get("vehicle_id") is not None:
            vf_bits.append(f"vehicle_id = {vehicle_focus['vehicle_id']} (PK en vehicles)")
        if vehicle_focus.get("vin"):
            vf_bits.append(f"vin = '{vehicle_focus['vin']}'")
        if vehicle_focus.get("plate"):
            vf_bits.append(f"plate = '{vehicle_focus['plate']}'")
        if vf_bits:
            lines.append(
                "\n--- Unidad fijada en la UI (preguntas como «esta unidad», «a ese VIN», «le vendieron seguro») ---\n"
                "La pregunta nueva se refiere SOLO a esta unidad. Filtra con valores literales en vehicles, por ejemplo:\n"
                f"  {'; '.join(vf_bits)}\n"
                "PROHIBIDO inferir la unidad con subconsultas tipo (SELECT vin FROM services ORDER BY service_date DESC LIMIT 1) "
                "u ordenar por otra tabla para «adivinar» el VIN."
            )
    lines.append("\nLa última línea del usuario es la pregunta nueva; genera SQL coherente con el historial.")
    return "\n".join(lines)


_CHITCHAT_MAX_LEN = 140
_RE_CHITCHAT_GREETING = re.compile(
    r"^\s*(?:"
    r"hola[!¡.\s]*|"
    r"buen(?:os|as)\s+(?:d[ií]as|tardes|noches)[!¡.\s]*|"
    r"(?:hey|hi|hello|buenas)[!¡.\s]*|"
    r"¿?qu[eé]\s+tal\??[!.\s]*|"
    r"¿?c[oó]mo\s+est[aá]s?\??[!.\s]*|"
    r"saludos[!¡.\s]*|"
    r"buen\s+d[ií]a[!¡.\s]*"
    r")\s*$",
    re.IGNORECASE | re.UNICODE,
)
_RE_CHITCHAT_THANKS = re.compile(
    r"^\s*(?:muchas\s+)?gracias(?:\s+(?:todo|mil))?[!¡.\s]*$",
    re.IGNORECASE | re.UNICODE,
)
_RE_CHITCHAT_BYE = re.compile(
    r"^\s*(?:adios|adiós|hasta\s+luego|chao|chau|bye|nos\s+vemos)[!¡.\s]*$",
    re.IGNORECASE | re.UNICODE,
)
_RE_CHITCHAT_HELP = re.compile(
    r"^\s*(?:"
    r"qui[eé]n\s+eres\??|"
    r"qu[eé]\s+eres\??|"
    r"qu[eé]\s+haces\??|"
    r"en\s+qu[eé]\s+me\s+ayudas\??|"
    r"para\s+qu[eé]\s+sirves\??|"
    r"ayuda"
    r")\s*$",
    re.IGNORECASE | re.UNICODE,
)
_RE_CHITCHAT_ACK = re.compile(
    r"^\s*(?:ok|okay|vale|perfecto|entendido|listo|genial)[!¡.\s]*$",
    re.IGNORECASE | re.UNICODE,
)


def _chitchat_reply(user_text: str) -> str | None:
    """
    Mensajes muy cortos y solo conversacionales: respuesta fija sin llamar al DWH ni al LLM.
    Si el texto parece una pregunta de datos, devuelve None.
    """
    t = user_text.strip()
    if not t or len(t) > _CHITCHAT_MAX_LEN:
        return None
    if _RE_CHITCHAT_GREETING.match(t):
        return (
            "¡Hola! Soy el asistente del **Panel de Inteligencia Comercial**. "
            "Puedo ayudarte a consultar tu almacén de datos: clientes, ventas, servicios, citas, seguros, etc."
        )
    if _RE_CHITCHAT_THANKS.match(t):
        return "De nada. Cuando quieras, sigue con otra pregunta sobre tus datos."
    if _RE_CHITCHAT_BYE.match(t):
        return "¡Hasta pronto! Aquí estaré cuando necesites consultar tu negocio."
    if _RE_CHITCHAT_HELP.match(t):
        return (
            "Soy un asistente que **traduce tus preguntas a SQL**, ejecuta la consulta en el DWH y te responde "
            "con un resumen y tablas o gráficas. No sustituyo a un analista para decisiones finales, "
            "pero acelero explorar métricas y listados."
        )
    if _RE_CHITCHAT_ACK.match(t):
        return "Perfecto. Dime qué te gustaría revisar en los datos."
    return None


def _render_user_chat_text(text: str) -> None:
    """Render seguro para identificar mensajes de usuario en CSS."""
    safe = html.escape((text or "").strip()).replace("\n", "<br>")
    st.markdown(f'<div class="chat-user-text">{safe}</div>', unsafe_allow_html=True)


def _render_natural_chat_block() -> tuple[str, bool]:
    """Historial tipo chat + entrada. Devuelve (mensaje efectivo, si hay que ejecutar consulta)."""
    st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, [])
    turns: list[dict[str, Any]] = st.session_state[SESSION_KEY_CHAT_TURNS]
    last_turn_idx = len(turns) - 1
    for turn_idx, turn in enumerate(turns):
        with st.chat_message("user", avatar="👤"):
            _render_user_chat_text(turn.get("user", ""))
        with st.chat_message("assistant"):
            if turn.get("error"):
                st.error(turn["error"])
            elif turn.get("kind") == "chitchat":
                st.markdown(_format_money_in_chat_text(turn.get("answer_summary") or "¡Hola!"))
            elif turn.get("kind") == "forecast":
                fc_reply = (turn.get("answer_summary") or "").strip()
                if fc_reply:
                    st.markdown(_format_money_in_chat_text(fc_reply))
                else:
                    st.markdown("**Pronóstico de ventas** (serie histórica + estimación).")
                if _is_developer_ui() and turn.get("sql"):
                    st.code(turn["sql"], language="sql")
                if not fc_reply:
                    st.caption(f"{turn.get('rows', 0)} filas en la tabla de pronóstico")
            else:
                reply = (turn.get("answer_summary") or "").strip()
                row_n = int(turn.get("rows") or 0)
                show_detail_entry = row_n > 0 and turn_idx == last_turn_idx
                if show_detail_entry:
                    with st.popover(
                        "\u200b",
                        icon=":material/table_view:",
                        help="Gráfica o detalle en ventana emergente",
                        use_container_width=False,
                    ):
                        if st.button(
                            "Gráfica",
                            use_container_width=True,
                            key="chat_data_menu_chart",
                        ):
                            st.session_state[CHAT_DATA_DIALOG_REQUEST_KEY] = "chart"
                            st.rerun()
                        if st.button(
                            "Detalle",
                            use_container_width=True,
                            key="chat_data_menu_detail",
                        ):
                            st.session_state[CHAT_DATA_DIALOG_REQUEST_KEY] = "detail"
                            st.rerun()
                    if reply:
                        st.markdown(_format_money_in_chat_text(reply))
                elif reply:
                    st.markdown(_format_money_in_chat_text(reply))
                if _is_developer_ui():
                    st.code(turn.get("sql") or "", language="sql")
                if not reply:
                    cap = f"{turn.get('rows', 0)} filas"
                    if turn.get("kpi"):
                        cap += f" · KPI: {turn['kpi']}"
                    st.caption(cap)

    dlg_req = st.session_state.pop(CHAT_DATA_DIALOG_REQUEST_KEY, None)
    lr_dlg = st.session_state.get(SESSION_KEY_LAST_QUERY_VIEW)
    if dlg_req and lr_dlg and lr_dlg.get("kind") == "agent":
        _dlg_rows = lr_dlg["result"].rows
        if dlg_req == "chart":
            _open_chat_chart_dialog(_dlg_rows)
        elif dlg_req == "detail":
            _open_chat_detail_dialog(_dlg_rows)

    pending = st.session_state.pop(SESSION_KEY_PENDING_CHAT, None)
    chat_raw = st.chat_input("Escribe tu pregunta…")
    effective = (pending or chat_raw or "").strip()
    should_run = bool(effective)
    # Muestra el mensaje del usuario en el mismo ciclo (antes de la respuesta / spinner en main).
    if should_run:
        with st.chat_message("user", avatar="👤"):
            _render_user_chat_text(effective)
    return effective, should_run


SESSION_KEY_FOCUS_VEHICLE = "focus_vehicle"
SESSION_KEY_FOCUS_AGENCY = "focus_agency"
SESSION_KEY_CHAT_TURNS = "chat_turns"
SESSION_KEY_LAST_QUERY_VIEW = "last_query_result_view"
SESSION_KEY_PENDING_CHAT = "pending_chat_question"
SESSION_KEY_DISAMBIG = "disambig_pending"
SESSION_KEY_DISAMBIG_DONE = "disambig_just_resolved"
SESSION_KEY_DEVELOPER_UI = "developer_ui_mode"
SESSION_KEY_SHOW_QUERY_EXTRA_PANELS = "show_query_extra_panels"


def _is_developer_ui() -> bool:
    """True = modo desarrollo (SQL, JSON, observabilidad); False = modo demo (solo resultados y gráficas)."""
    return bool(st.session_state.get(SESSION_KEY_DEVELOPER_UI, False))


# ---------------------------------------------------------------------------
# Reglas de desambiguación
# ---------------------------------------------------------------------------
# Cada regla tiene:
#   triggers  – al menos un patrón debe coincidir para activarla.
#   excludes  – si cualquiera coincide la regla NO se activa (el usuario ya aclaró).
#   prompt    – pregunta que se muestra al usuario.
#   options   – lista de {label, context}; context se inyecta como prompt_extra al LLM.
_DISAMBIGUATION_RULES: list[dict[str, Any]] = [
    {
        "id": "cost",
        "triggers": [
            r"(?i)\bcost[oó]s?\b",
            r"(?i)\bcu[aá]nto\s+(?:cost|gast|pag)",
            r"(?i)\bprecio\b",
            r"(?i)\bgastos?\b",
        ],
        "excludes": [
            r"(?i)\bservicio\b",
            r"(?i)\breparaci[oó]n\b",
            r"(?i)\bmantenimiento\b",
            r"(?i)\bventa\b",
            r"(?i)\bcompra\b",
            r"(?i)\bunidad\b",
            r"(?i)\bveh[ií]culo\b",
            r"(?i)\bseguro\b",
            r"(?i)\bp[oó]liza\b",
            r"(?i)\bprima\b",
            r"(?i)\bservices\b",
            r"(?i)\bsales\b",
            r"(?i)\binsurance\b",
            r"(?i)\bcita\b",
        ],
        "prompt": "Antes de consultar, necesito aclarar: ¿a qué costo te refieres?",
        "options": [
            {
                "label": "Costo del servicio / reparación",
                "context": (
                    "El usuario pregunta por el costo de un servicio o reparación. "
                    "Usa la tabla services y su columna cost."
                ),
            },
            {
                "label": "Monto de la venta del vehículo",
                "context": (
                    "El usuario pregunta por el monto de la venta/compra del vehículo. "
                    "Usa la tabla sales y su columna amount."
                ),
            },
            {
                "label": "Prima anual del seguro",
                "context": (
                    "El usuario pregunta por el costo del seguro. "
                    "Usa la tabla insurance_policies y su columna annual_premium."
                ),
            },
        ],
    },
    {
        "id": "date_ambiguous",
        "triggers": [
            r"(?i)\bfecha\b(?!.*\b(?:nacimiento|birth)\b)",
            r"(?i)\bcu[aá]ndo\b",
            r"(?i)\b[uú]ltim[oa]\b.*\bfecha\b",
        ],
        "excludes": [
            r"(?i)\bventa\b",
            r"(?i)\bcompra\b",
            r"(?i)\bservicio\b",
            r"(?i)\bcita\b",
            r"(?i)\bappointment\b",
            r"(?i)\bseguro\b",
            r"(?i)\bp[oó]liza\b",
            r"(?i)\bnacimiento\b",
            r"(?i)\bsale_date\b",
            r"(?i)\bservice_date\b",
            r"(?i)\bappointment_date\b",
            r"(?i)\bpolicy_\b",
            r"(?i)\bagenda\b",
            r"(?i)\bprogramada\b",
            r"(?i)\bcompletada\b",
        ],
        "prompt": "¿A qué fecha te refieres?",
        "options": [
            {
                "label": "Fecha de venta",
                "context": (
                    "El usuario pregunta por la fecha de venta. "
                    "Usa la tabla sales y su columna sale_date."
                ),
            },
            {
                "label": "Fecha de servicio realizado",
                "context": (
                    "El usuario pregunta por la fecha de un servicio realizado. "
                    "Usa la tabla services y su columna service_date."
                ),
            },
            {
                "label": "Fecha de cita agendada",
                "context": (
                    "El usuario pregunta por la fecha de una cita de servicio. "
                    "Usa la tabla service_appointments y su columna appointment_date."
                ),
            },
        ],
    },
    {
        "id": "status_ambiguous",
        "triggers": [
            r"(?i)\bestatus\b",
            r"(?i)\bestado\b(?!.*\b(?:rep[uú]blica|m[eé]xico|cdmx|jalisco|nuevo le[oó]n|ciudad|geogr)\b)",
        ],
        "excludes": [
            r"(?i)\bpor\s+estado\b",
            r"(?i)\bcada\s+estado\b",
            r"(?i)\bestado\s+(?:de\s+)?(?:m[eé]xico|cuenta|resultado)",
            r"(?i)\bventa\b",
            r"(?i)\bservicio\b",
            r"(?i)\bcita\b",
            r"(?i)\bseguro\b",
            r"(?i)\bp[oó]liza\b",
            r"(?i)\bappointment\b",
            r"(?i)\bgeogr[aá]fico\b",
            r"(?i)\bclientes?\s+por\s+estado\b",
        ],
        "prompt": "¿A qué estatus/estado te refieres?",
        "options": [
            {
                "label": "Estado geográfico del cliente",
                "context": (
                    "El usuario pregunta por el estado geográfico (entidad federativa). "
                    "Usa la tabla customers y su columna state."
                ),
            },
            {
                "label": "Estatus de una venta",
                "context": (
                    "El usuario pregunta por el estatus de la venta. "
                    "Usa la tabla sales y su columna status."
                ),
            },
            {
                "label": "Estatus de una cita de servicio",
                "context": (
                    "El usuario pregunta por el estatus de cita de servicio. "
                    "Usa la tabla service_appointments y su columna appointment_status "
                    "(valores: completada, programada, no_show, cancelada)."
                ),
            },
            {
                "label": "Estatus de póliza de seguro",
                "context": (
                    "El usuario pregunta por el estatus de la póliza. "
                    "Usa la tabla insurance_policies y su columna policy_status."
                ),
            },
        ],
    },
]

# Mismas reglas de disparo, pero contextos alineados al DWH VGD (sin tabla sales ni demo).
_DISAMBIGUATION_RULES_VGD: list[dict[str, Any]] = [
    {
        "id": "cost",
        "triggers": _DISAMBIGUATION_RULES[0]["triggers"],
        "excludes": _DISAMBIGUATION_RULES[0]["excludes"],
        "prompt": _DISAMBIGUATION_RULES[0]["prompt"],
        "options": [
            {
                "label": "Costo del servicio / reparación",
                "context": (
                    "El usuario pregunta por el costo de un servicio o reparación. "
                    "Usa la tabla services y las columnas de monto o costo que aparezcan en el esquema de referencia. "
                    "La tabla sales NO existe en este DWH: no la uses."
                ),
            },
            {
                "label": "Monto de la operación comercial (pedido / comisión / factura)",
                "context": (
                    "El usuario pregunta por el monto de una venta u operación comercial. "
                    "Usa comissions (p. ej. acquisition_value, dalers_value), invoices u orders según columnas del esquema. "
                    "Nunca uses la tabla sales."
                ),
            },
            {
                "label": "Prima u otro costo de seguro",
                "context": (
                    "El usuario pregunta por costos de seguro. "
                    "Si el esquema de referencia no lista tablas de pólizas, indícalo en SQL o usa solo tablas listadas. "
                    "No inventes insurance_policies ni sales."
                ),
            },
        ],
    },
    {
        "id": "date_ambiguous",
        "triggers": _DISAMBIGUATION_RULES[1]["triggers"],
        "excludes": _DISAMBIGUATION_RULES[1]["excludes"],
        "prompt": _DISAMBIGUATION_RULES[1]["prompt"],
        "options": [
            {
                "label": "Fecha de pedido u orden comercial",
                "context": (
                    "El usuario pregunta por la fecha de pedido u orden. "
                    "Usa comissions.order_timestamp, orders u otras fechas del esquema VGD. "
                    "No uses sale_date ni la tabla sales (no existe)."
                ),
            },
            {
                "label": "Fecha de servicio realizado",
                "context": (
                    "El usuario pregunta por la fecha de un servicio realizado. "
                    "Usa la tabla services y las columnas de fecha del esquema. "
                    "No uses service_appointments si no está en el esquema de referencia."
                ),
            },
            {
                "label": "Fecha de facturación",
                "context": (
                    "El usuario pregunta por fecha de factura. "
                    "Usa invoices, comissions.invoice_data u order_timestamp según el esquema. No uses sales."
                ),
            },
        ],
    },
    {
        "id": "status_ambiguous",
        "triggers": _DISAMBIGUATION_RULES[2]["triggers"],
        "excludes": _DISAMBIGUATION_RULES[2]["excludes"],
        "prompt": _DISAMBIGUATION_RULES[2]["prompt"],
        "options": [
            {
                "label": "Estado geográfico del cliente",
                "context": (
                    "El usuario pregunta por el estado geográfico (entidad federativa). "
                    "Usa la tabla customers y su columna state."
                ),
            },
            {
                "label": "Estatus del pedido u orden comercial",
                "context": (
                    "El usuario pregunta por el estatus de una venta o pedido operativo. "
                    "Usa comissions.order_status y/o columnas de estatus en orders o invoices del esquema VGD. "
                    "No uses sales.status ni la tabla sales."
                ),
            },
            {
                "label": "Estatus del servicio en taller",
                "context": (
                    "El usuario pregunta por el estatus de un servicio. "
                    "Usa columnas de estatus en la tabla services según el esquema de referencia."
                ),
            },
        ],
    },
]


def _check_disambiguation(question: str, *, llm_profile: str = "default") -> dict[str, Any] | None:
    """Devuelve la primera regla de desambiguación que aplique, o None."""
    rules = _DISAMBIGUATION_RULES_VGD if llm_profile == "vgd" else _DISAMBIGUATION_RULES
    for rule in rules:
        if any(re.search(p, question) for p in rule["triggers"]):
            if not any(re.search(p, question) for p in rule.get("excludes", [])):
                return rule
    return None


def _render_disambiguation_ui(
    question: str, rule: dict[str, Any], natural_chat: bool
) -> None:
    """Muestra las opciones de desambiguación y, al hacer clic, inyecta la pregunta clarificada."""
    if natural_chat:
        with st.chat_message("user", avatar="👤"):
            _render_user_chat_text(question)
        with st.chat_message("assistant"):
            st.markdown(f"**{rule['prompt']}**")
            for i, opt in enumerate(rule["options"]):
                if st.button(
                    opt["label"],
                    key=f"disambig_{rule['id']}_{i}",
                    use_container_width=True,
                ):
                    clarified = f"{question}\n\nContexto: {opt['context']}"
                    st.session_state[SESSION_KEY_PENDING_CHAT] = clarified
                    st.session_state.pop(SESSION_KEY_DISAMBIG, None)
                    st.session_state[SESSION_KEY_DISAMBIG_DONE] = True
                    st.rerun()
    else:
        st.markdown(f"**{rule['prompt']}**")
        for i, opt in enumerate(rule["options"]):
            if st.button(
                opt["label"],
                key=f"disambig_{rule['id']}_{i}",
                use_container_width=True,
            ):
                clarified = f"{question}\n\nContexto: {opt['context']}"
                st.session_state[SESSION_KEY_PENDING_CHAT] = clarified
                st.session_state["natural_chat_mode"] = True
                st.session_state.pop(SESSION_KEY_DISAMBIG, None)
                st.session_state[SESSION_KEY_DISAMBIG_DONE] = True
                st.rerun()


# Columnas típicas de identificador de agencia / sucursal (claves en minúsculas).
_AGENCY_ID_KEYS: tuple[str, ...] = (
    "idagency",
    "id_agency",
    "agency_id",
    "agency_code",
    "cod_agencia",
    "codigo_agencia",
)
_AGENCY_LABEL_KEYS: tuple[str, ...] = (
    "agency_name",
    "nombre_agencia",
    "agencia_nombre",
    "nombre_sucursal",
    "sucursal",
    "branch_name",
    "dealer_name",
    "agencia",
)


def _row_keys_lower(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in row.items()}


def _vehicle_focus_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Extrae identificadores de unidad si la fila los trae (claves insensibles a mayúsculas)."""
    lk = _row_keys_lower(row)
    vid = lk.get("vehicle_id")
    vin = lk.get("vin")
    plate = lk.get("plate")
    if vid is None and vin is None and plate is None:
        return None
    out: dict[str, Any] = {}
    if vid is not None:
        out["vehicle_id"] = vid
    if vin is not None and str(vin).strip():
        out["vin"] = str(vin).strip()
    if plate is not None and str(plate).strip():
        out["plate"] = str(plate).strip()
    return out or None


def _vehicle_focus_to_prompt_extra(
    focus: dict[str, Any] | None, *, llm_profile: str = "default"
) -> str:
    if not focus:
        return ""
    lines = [
        "Contexto de seguimiento (aplica a la pregunta siguiente esta misma unidad si no indicas otra):",
    ]
    if llm_profile == "vgd":
        if focus.get("vin"):
            lines.append(f"- vin: {focus['vin']}")
        if focus.get("plate"):
            lines.append(f"- placa (columna plate en tablas con unidad): {focus['plate']}")
        if focus.get("vehicle_id") is not None:
            lines.append(
                f"- id numérico de contexto (no asumas tabla vehicles; filtra en tablas del esquema VGD): {focus['vehicle_id']}"
            )
        lines.append(
            "OBLIGATORIO (DWH VGD): filtra con literales usando vin y/o plate en tablas que existan en el esquema "
            "(p. ej. inventory, comissions, customer_vehicle, services_by_vin). "
            "No uses tabla vehicles ni sales (no existen en este DWH)."
        )
        lines.append(
            "PROHIBIDO: subconsultas para inventar otro VIN; no uses sales, service_appointments ni insurance_policies "
            "salvo que aparezcan en el esquema de referencia."
        )
        lines.append(
            "PROHIBIDO: literales ficticios ('ultimo_vin', 'last_vin', 'esta_unidad'). "
            "Incluye columna vin en el SELECT cuando la pregunta sea por unidad."
        )
        return "\n".join(lines)

    if focus.get("vehicle_id") is not None:
        lines.append(f"- vehicle_id (PK en tabla vehicles): {focus['vehicle_id']}")
    if focus.get("vin"):
        lines.append(f"- vin: {focus['vin']}")
    if focus.get("plate"):
        lines.append(f"- placa (columna plate): {focus['plate']}")
    lines.append(
        "OBLIGATORIO: filtra la unidad con literales tomados de arriba, por ejemplo "
        "`WHERE vehicles.id = <vehicle_id>` o `WHERE vehicles.vin = '<vin exacto>'` (o el alias de vehicles en el FROM)."
    )
    lines.append(
        "PROHIBIDO: no uses subconsultas para «obtener» el VIN desde services, sales, service_appointments "
        "ni ORDER BY service_date/sale_date para elegir otra unidad distinta a la del contexto."
    )
    lines.append(
        "PROHIBIDO: no uses literales ficticios como 'ultimo_vin', 'last_vin' o 'esta_unidad' en SQL; "
        "copia el valor exacto de vin (o vehicle_id) indicado arriba entre comillas o como número."
    )
    lines.append(
        "Resuelve la pregunta con JOIN a vehicles (y sales, services, service_appointments, insurance_policies "
        "según corresponda) usando solo esos identificadores. Incluye vin en el SELECT cuando muestres datos de vehículo."
    )
    return "\n".join(lines)


def _agency_focus_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    lk = _row_keys_lower(row)
    raw_id: str | None = None
    for k in _AGENCY_ID_KEYS:
        if k in lk and lk[k] is not None and str(lk[k]).strip() != "":
            raw_id = str(lk[k]).strip()
            break
    if raw_id is None:
        return None
    out: dict[str, Any] = {"id_agency": raw_id}
    for nk in _AGENCY_LABEL_KEYS:
        if nk in lk and lk[nk] is not None and str(lk[nk]).strip() != "":
            out["agency_label"] = str(lk[nk]).strip()
            break
    return out


def _all_rows_same_agency_focus(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    first = _agency_focus_from_row(rows[0])
    if first is None:
        return None
    idv = first.get("id_agency")
    for row in rows[1:]:
        other = _agency_focus_from_row(row)
        if other is None or other.get("id_agency") != idv:
            return None
    return first


def _agency_focus_to_prompt_extra(
    focus: dict[str, Any] | None, *, llm_profile: str = "default"
) -> str:
    if not focus:
        return ""
    lines = [
        "Contexto de seguimiento (misma agencia / sucursal para la pregunta siguiente si no indicas otra):",
        f"- Identificador de agencia (en VGD suele ser la columna \"idAgency\"): {focus['id_agency']}",
    ]
    if focus.get("agency_label"):
        lines.append(f"- Nombre o etiqueta de agencia: {focus['agency_label']}")
    if llm_profile == "vgd":
        lines.append(
            "Filtra con WHERE tabla_homologada.id_agency = '<valor exacto de arriba>' (vistas `h_*` solamente). "
            "Catálogo: `h_agencies` (columnas id_agency, name). Para listar o agrupar por sucursal incluye "
            "`h_agencies.name AS agency_name` vía JOIN; no uses tablas base ni `sales`."
        )
    else:
        lines.append(
            "Filtra o haz JOIN en las tablas que tengan ese identificador (p. ej. customers.idAgency) "
            "cuando la pregunta sea sobre clientes, ventas o métricas de esa agencia."
        )
    return "\n".join(lines)


def _build_follow_up_prompt_extra() -> str:
    prof = resolve_llm_profile(
        os.getenv("SCHEMA_HINT_FILE", ""),
        dwh_url=effective_dwh_url(normalize_dwh_url_string(os.getenv("DWH_URL", ""))),
    )
    chunks: list[str] = []
    v = st.session_state.get(SESSION_KEY_FOCUS_VEHICLE)
    a = st.session_state.get(SESSION_KEY_FOCUS_AGENCY)
    if v:
        chunks.append(_vehicle_focus_to_prompt_extra(v, llm_profile=prof))
    if a:
        chunks.append(_agency_focus_to_prompt_extra(a, llm_profile=prof))
    return "\n\n".join(c for c in chunks if c.strip())


def _render_follow_up_banners() -> None:
    v = st.session_state.get(SESSION_KEY_FOCUS_VEHICLE)
    a = st.session_state.get(SESSION_KEY_FOCUS_AGENCY)
    if not v and not a:
        return
    st.markdown("##### Contexto de seguimiento")
    st.caption(
        "Las siguientes consultas al agente incluyen este contexto en el prompt. "
        "Para frases como «esta unidad» o «¿le vendieron seguro?» necesitas tener la unidad fijada aquí "
        "(elige fila y pulsa el botón en «Seguimiento por unidad» del resultado anterior)."
    )
    if v:
        bits: list[str] = []
        if v.get("vehicle_id") is not None:
            bits.append(f"vehicle_id **{v['vehicle_id']}**")
        if v.get("vin"):
            bits.append(f"VIN **{v['vin']}**")
        if v.get("plate"):
            bits.append(f"Placa **{v['plate']}**")
        st.markdown("🚗 **Unidad:** " + " · ".join(bits))
        if st.button("Quitar unidad", key="clear_focus_vehicle_btn"):
            st.session_state.pop(SESSION_KEY_FOCUS_VEHICLE, None)
            st.session_state.pop("vehicle_follow_up_pick", None)
            st.rerun()
    if a:
        lab = (a.get("agency_label") or "").strip()
        idv = a.get("id_agency")
        if lab:
            st.markdown(f"🏢 **Agencia:** **{lab}** (`id_agency`={idv})")
        else:
            st.markdown(f"🏢 **Agencia:** **{idv}**")
        if st.button("Quitar agencia", key="clear_focus_agency_btn"):
            st.session_state.pop(SESSION_KEY_FOCUS_AGENCY, None)
            st.session_state.pop("agency_follow_up_pick", None)
            st.rerun()


def _apply_auto_agency_focus_and_show_banners(rows: list[dict[str, Any]]) -> None:
    """Si está activada la opción, fija agencia cuando todas las filas coinciden; luego muestra banners."""
    if st.session_state.get("auto_focus_agency_homogeneous", False):
        hom = _all_rows_same_agency_focus(rows)
        if hom:
            st.session_state[SESSION_KEY_FOCUS_AGENCY] = hom
    _render_follow_up_banners()


def _render_vehicle_follow_up_section(rows: list[dict[str, Any]]) -> None:
    """Permite fijar una fila del resultado como contexto para preguntas siguientes."""
    eligible: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        foc = _vehicle_focus_from_row(row)
        if foc is not None:
            eligible.append((idx, row, foc))
    if not eligible:
        return
    with st.expander("Seguimiento por unidad", expanded=False):
        st.caption(
            "Elige una fila de este resultado y pulsa el botón: las siguientes preguntas "
            "llevarán VIN / vehicle_id / placa al modelo sin que tengas que repetirlos."
        )
        labels: list[str] = []
        for idx, _row, foc in eligible:
            parts = [f"Fila {idx + 1}"]
            if foc.get("vin"):
                parts.append(f"VIN {foc['vin']}")
            if foc.get("vehicle_id") is not None:
                parts.append(f"id {foc['vehicle_id']}")
            if foc.get("plate"):
                parts.append(f"Placa {foc['plate']}")
            labels.append(" · ".join(parts))
        pick = st.selectbox(
            "Fila del resultado",
            range(len(eligible)),
            format_func=lambda i: labels[i],
            key="vehicle_follow_up_pick",
        )
        if st.button("Usar esta unidad en las siguientes consultas", key="vehicle_follow_up_set_btn"):
            _idx, _row, foc = eligible[int(pick)]
            st.session_state[SESSION_KEY_FOCUS_VEHICLE] = foc
            st.rerun()


def _render_agency_follow_up_section(rows: list[dict[str, Any]]) -> None:
    eligible: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        foc = _agency_focus_from_row(row)
        if foc is not None:
            eligible.append((idx, row, foc))
    if not eligible:
        return
    with st.expander("Seguimiento por agencia", expanded=False):
        st.caption(
            "Elige una fila con identificador de agencia (p. ej. idAgency) y pulsa el botón: "
            "las siguientes preguntas añadirán ese contexto al modelo."
        )
        labels: list[str] = []
        for idx, _row, foc in eligible:
            parts = [f"Fila {idx + 1}", f"id **{foc['id_agency']}**"]
            if foc.get("agency_label"):
                parts.append(foc["agency_label"])
            labels.append(" · ".join(parts))
        pick = st.selectbox(
            "Fila del resultado",
            range(len(eligible)),
            format_func=lambda i: labels[i],
            key="agency_follow_up_pick",
        )
        if st.button("Usar esta agencia en las siguientes consultas", key="agency_follow_up_set_btn"):
            _idx, _row, foc = eligible[int(pick)]
            st.session_state[SESSION_KEY_FOCUS_AGENCY] = foc
            st.rerun()


def _prepare_new_result_view() -> None:
    """Resetea estado visual de resultados para una búsqueda nueva."""
    st.session_state.pop("chart_x_col", None)
    st.session_state.pop("chart_y_col", None)
    st.session_state.pop("chart_type", None)
    st.session_state.pop("chart_result_sig", None)
    st.session_state.pop("vehicle_follow_up_pick", None)
    st.session_state.pop("agency_follow_up_pick", None)
    st.session_state.pop(SESSION_KEY_SHOW_QUERY_EXTRA_PANELS, None)
    for _k in list(st.session_state.keys()):
        if isinstance(_k, str) and (
            _k.startswith("dlg_chat_chart_") or _k.startswith("dlg_chat_detail_")
        ):
            st.session_state.pop(_k, None)


def _maybe_cache_answer_summary(result: Any, text: str) -> None:
    """Evita llamadas repetidas al LLM al re-renderizar la última vista del chat."""
    lr = st.session_state.get(SESSION_KEY_LAST_QUERY_VIEW)
    if (
        lr
        and lr.get("kind") == "agent"
        and lr.get("result") is result
        and not (lr.get("answer_summary") or "").strip()
    ):
        st.session_state[SESSION_KEY_LAST_QUERY_VIEW] = {**lr, "answer_summary": text}


def _render_query_result(
    result: Any,
    model_used: str | None = None,
    cache_stats: dict[str, Any] | None = None,
    *,
    llm_for_summary: LocalOllamaClient | None = None,
    answer_summary_cached: str | None = None,
) -> None:
    """Resumen en lenguaje natural arriba; gráfica; detalle en tabla (expander)."""
    rows = result.rows
    cached = (answer_summary_cached or "").strip()
    if cached:
        summary_text = cached
    else:
        summary_text = _compute_hybrid_answer_summary(result.question, rows, llm_for_summary)
    _maybe_cache_answer_summary(result, summary_text)

    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.markdown("### Respuesta")
    with head_r:
        panels_open = bool(st.session_state.get(SESSION_KEY_SHOW_QUERY_EXTRA_PANELS, False))
        toggle_label = "Ocultar datos" if panels_open else "Ver datos"
        if st.button(
            toggle_label,
            key="btn_toggle_query_extra_panels",
            use_container_width=True,
            help="Muestra u oculta gráfica o vista de datos, tabla con descarga y seguimiento por unidad/agencia.",
        ):
            st.session_state[SESSION_KEY_SHOW_QUERY_EXTRA_PANELS] = not panels_open
            st.rerun()

    st.markdown(_format_money_in_chat_text(summary_text))

    if _is_developer_ui():
        with st.expander("SQL generado", expanded=False):
            st.code(result.generated_sql, language="sql")
            if model_used:
                st.caption(f"Modelo usado: {model_used}")

    if st.session_state.get(SESSION_KEY_SHOW_QUERY_EXTRA_PANELS, False):
        has_numeric = _rows_have_numeric_for_chart(rows) if rows else False
        first_title = "Gráfica" if not rows or has_numeric else "Vista de datos"

        with st.expander(first_title, expanded=False):
            _render_chart_options(rows)

        with st.expander("Detalle (tabla y descarga)", expanded=False):
            _render_rows(rows)

        _render_vehicle_follow_up_section(rows)
        _render_agency_follow_up_section(rows)
        hom_ag = _all_rows_same_agency_focus(rows) if rows else None
        if hom_ag and not st.session_state.get("auto_focus_agency_homogeneous", False):
            lab = (hom_ag.get("agency_label") or "").strip()
            idv = hom_ag.get("id_agency")
            ag_txt = f"**{lab}** (`id_agency`={idv})" if lab else f"**{idv}**"
            st.info(
                f"Todas las filas corresponden a la agencia {ag_txt}. "
                "Puedes fijarla arriba en **Seguimiento por agencia**, o activar en Configuración "
                "«Auto: fijar agencia si todas las filas coinciden» para hacerlo solo al consultar."
            )

    if _is_developer_ui():
        with st.expander("Salida JSON", expanded=False):
            payload: dict[str, Any] = {
                "pregunta": result.question,
                "sql": result.generated_sql,
                "rows": result.rows,
            }
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

    with st.expander("Gráfica", expanded=False):
        chart_df = pd.DataFrame(result.chart_rows)
        if chart_df.empty:
            st.info("No hay datos suficientes para construir la gráfica del pronóstico.")
        else:
            pivot = chart_df.pivot(index="period", columns="tipo", values="ventas").fillna(0)
            pivot.index = pivot.index.astype(str)
            st.line_chart(pivot, use_container_width=True)

    if _is_developer_ui():
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

    if _is_developer_ui():
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
    if not _is_developer_ui():
        return
    with st.expander("Observabilidad y alertas", expanded=False):
        metrics = get_metrics_snapshot()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Consultas", int(metrics.get("total_queries", 0)))
        col2.metric("Éxito", f"{float(metrics.get('success_rate', 0.0)):.1f}%")
        col3.metric("Latencia prom.", f"{float(metrics.get('avg_latency_ms', 0.0)):.1f} ms")
        col4.metric("Latencia p95", f"{float(metrics.get('p95_latency_ms', 0.0)):.1f} ms")

        if cache_stats:
            st.markdown("**Caché SQL**")
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


def _render_field_guide_content() -> None:
    """Contenido de la guía de tablas/campos (sin contenedor expander)."""
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
    dwh_sidebar_md: str,
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    max_rows: int,
    llm_timeout: int,
    llm_temperature: float,
    cache_ttl_seconds: int,
    cache_max_entries: int,
) -> tuple[str, str, str, int, int, float, int, int, int, str, str]:
    """Renderiza panel lateral con referencias y configuración."""
    with st.sidebar:
        st.markdown("## Panel lateral")

        with st.expander("Ayuda y estado del DWH", expanded=False):
            st.markdown(
                "**Modo presentación** — Con **Modo desarrollo** desactivado en el menú lateral, "
                "solo verás gráficas y tablas de resultados (sin SQL ni JSON). Actívalo para depurar consultas."
            )
            st.markdown(
                "**Chat** — Usa el **chat** (modo conversación) o desactiva esa opción para el "
                "**cuadro de texto clásico** y el botón Consultar. El historial del chat ayuda al modelo "
                "en preguntas de seguimiento."
            )
            st.caption(
                "En modo chat, escribe abajo en el área principal; el historial se envía al modelo en cada nueva pregunta."
            )
            st.divider()
            st.markdown("**Conexión**")
            st.markdown(dwh_sidebar_md)
            st.divider()
            st.markdown("**Guía de campos disponibles**")
            _render_field_guide_content()

        st.checkbox(
            "Modo conversación (chat + historial)",
            value=True,
            key="natural_chat_mode",
            help="Vista tipo chat: el historial se envía al modelo para seguimientos naturales.",
        )
        st.checkbox(
            "Modo desarrollo (mostrar SQL, JSON y observabilidad)",
            key=SESSION_KEY_DEVELOPER_UI,
            help=(
                "Activado: ves el SQL generado, salida JSON y panel de observabilidad. "
                "Desactivado (modo demo): solo gráficas y tablas de resultados."
            ),
        )
        if st.session_state.get("natural_chat_mode", True):
            if st.button("Limpiar historial del chat", key="clear_chat_history_sidebar", use_container_width=True):
                st.session_state[SESSION_KEY_CHAT_TURNS] = []
                st.session_state.pop(SESSION_KEY_LAST_QUERY_VIEW, None)
                st.rerun()

        with st.expander("Preguntas de referencia", expanded=False):
            st.caption("Selecciona una: en modo chat se envía como siguiente mensaje.")
            st.markdown("**Generales**")
            for idx, question in enumerate(RECOMMENDED_QUESTIONS):
                if st.button(question, key=f"q_ref_{idx}", use_container_width=True):
                    if st.session_state.get("natural_chat_mode", True):
                        st.session_state[SESSION_KEY_PENDING_CHAT] = question
                    else:
                        st.session_state["question_input"] = question
                    st.rerun()

            st.markdown("**Demo comercial**")
            for idx, question in enumerate(DEMO_COMMERCIAL_QUESTIONS):
                if st.button(question, key=f"q_comm_{idx}", use_container_width=True):
                    if st.session_state.get("natural_chat_mode", True):
                        st.session_state[SESSION_KEY_PENDING_CHAT] = question
                    else:
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
            env_dwh = effective_dwh_url(
                normalize_dwh_url_string(os.getenv("DWH_URL", dwh_url))
            )
            _dwh_widget_key = "sidebar_dwh_url"
            if _dwh_widget_key not in st.session_state:
                st.session_state[_dwh_widget_key] = env_dwh
            if st.button(
                "Restaurar DWH_URL desde .env",
                key="reset_dwh_url_from_env",
                help="Streamlit recuerda el texto del campo aunque corrijas .env; usa esto para volver al valor del entorno.",
            ):
                st.session_state[_dwh_widget_key] = env_dwh
                st.rerun()
            dwh_url = st.text_input(
                "DWH_URL",
                key=_dwh_widget_key,
                help=(
                    "Si la URL termina en /postgres o sin nombre de base, se sustituye automáticamente por "
                    f"/{REQUIRED_DWH_DATABASE_NAME}. Usuario y clave van antes del @."
                ),
            )
            llm_endpoint = st.text_input(
                "LLM_ENDPOINT",
                value=llm_endpoint,
                help="Si esta app corre en la nube, 127.0.0.1 apunta al servidor cloud, no a tu PC.",
            )
            llm_model = st.text_input("LLM_MODEL", value=llm_model)
            llm_temperature = float(
                st.number_input(
                    "LLM_TEMPERATURE",
                    min_value=0.0,
                    max_value=2.0,
                    value=float(llm_temperature),
                    step=0.05,
                    help="Baja (0.1–0.3) para SQL más estable; sube para más variación.",
                )
            )
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
            st.checkbox(
                "Auto: fijar agencia si todas las filas coinciden",
                key="auto_focus_agency_homogeneous",
                help=(
                    "Tras cada consulta al agente, si todas las filas traen el mismo identificador "
                    "de agencia (idAgency, agency_id, etc.), se guarda como contexto para la siguiente "
                    "pregunta sin pulsar «Usar esta agencia»."
                ),
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
        llm_temperature,
        cache_ttl_seconds,
        cache_max_entries,
        horizon_months,
        forecast_method,
        forecast_dimension,
    )


def main() -> None:
    st.set_page_config(page_title="Panel de Inteligencia Comercial", page_icon="🧠", layout="wide")
    if SESSION_KEY_DEVELOPER_UI not in st.session_state:
        st.session_state[SESSION_KEY_DEVELOPER_UI] = os.getenv(
            "AGENTE_DWH_DEVELOPER_UI", ""
        ).lower() in ("1", "true", "yes")
    _hide_streamlit_header_chrome = ""
    if not _is_developer_ui():
        _hide_streamlit_header_chrome = """
        /* Deploy / decoración: ocultos en modo demo. No ocultar [data-testid="stToolbar"]
           entero: ahí va el botón para expandir el panel lateral en Streamlit reciente. */
        [data-testid="stDecoration"] { display: none !important; }
        .stAppDeployButton { display: none !important; }
        [data-testid="stDeployButton"] { display: none !important; }
        """
    st.markdown(
        f"""
        <style>
        div.stButton > button[kind="primary"] {{
            background-color: #1d4ed8;
            border-color: #1d4ed8;
            color: white;
        }}
        div.stButton > button[kind="primary"]:hover {{
            background-color: #1e40af;
            border-color: #1e40af;
            color: white;
        }}
        /* Chat tipo mensajería: usuario a la derecha, asistente a la izquierda */
        [data-testid="stChatMessage"] {{
            display: flex;
            width: 100%;
            align-items: flex-start;
        }}
        [data-testid="stChatMessage"]:has(.chat-user-text) {{
            flex-direction: row-reverse;
            justify-content: flex-start;
            margin-left: auto;
            margin-right: 0;
            max-width: min(92%, 42rem);
        }}
        [data-testid="stChatMessage"]:has(.chat-user-text) [data-testid="stChatMessageContent"],
        [data-testid="stChatMessage"]:has(.chat-user-text) [data-testid="stMarkdownContainer"] {{
            text-align: right;
        }}
        [data-testid="stChatMessage"]:not(:has(.chat-user-text)) {{
            flex-direction: row;
            justify-content: flex-start;
            margin-right: auto;
            margin-left: 0;
            max-width: min(92%, 48rem);
        }}
        [data-testid="stChatMessage"]:not(:has(.chat-user-text))
            [data-testid="stChatMessageContent"] {{
            text-align: left;
        }}
        /* Sin panel/burbuja: mensajes sobre el fondo de la app */
        [data-testid="stChatMessage"] {{
            background: transparent !important;
            box-shadow: none !important;
            border: none !important;
        }}
        [data-testid="stChatMessageContent"],
        [data-testid="stChatMessageContent"] > div {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        /* Avatares del chat: sin marco de color (solo icono), misma caja que el popover */
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"],
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 0 !important;
            width: 2.25rem !important;
            height: 2.25rem !important;
            min-width: 2.25rem !important;
            min-height: 2.25rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] img,
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] svg,
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] img,
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] svg {{
            width: 1.5rem !important;
            height: 1.5rem !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] > div,
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] > div {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        /* Popover «detalle» en chat: solo icono, misma huella que el avatar */
        [data-testid="stChatMessage"] [data-testid="stPopover"] > button {{
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: inherit !important;
            padding: 0 !important;
            margin: 0 !important;
            min-height: 2.25rem !important;
            width: 2.25rem !important;
            height: 2.25rem !important;
            min-width: 2.25rem !important;
            max-width: 2.25rem !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            line-height: 1 !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] > button:hover {{
            background: rgba(255, 255, 255, 0.08) !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] > button:focus-visible {{
            outline: 2px solid rgba(96, 165, 250, 0.85);
            outline-offset: 2px;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] > button svg {{
            width: 1.5rem !important;
            height: 1.5rem !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] > button [data-testid="stMarkdownContainer"] {{
            display: none !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] button svg:last-of-type {{
            display: none !important;
        }}
        [data-testid="stChatMessage"] [data-testid="stPopover"] [data-testid="stIconKeyboardArrowDown"],
        [data-testid="stChatMessage"] [data-testid="stPopover"] [data-testid="stChevronDownIcon"] {{
            display: none !important;
        }}
        /* Menos hueco superior: título y contenido más arriba */
        header[data-testid="stHeader"] {{
            height: auto !important;
            min-height: 0 !important;
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }}
        [data-testid="stAppViewContainer"] .main .block-container,
        [data-testid="stMain"] .block-container,
        section.main .block-container,
        div.block-container {{
            padding-top: 0.5rem !important;
        }}
        [data-testid="stMain"] h1,
        .main h1 {{
            margin-top: 0 !important;
            margin-bottom: 0.35rem !important;
        }}
        {_hide_streamlit_header_chrome}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Panel de Inteligencia Comercial")

    if not DEFAULT_DWH_URL:
        st.error(
            f"Define DWH_URL en .env con PostgreSQL y base «{REQUIRED_DWH_DATABASE_NAME}», "
            "por ejemplo: postgresql+psycopg://usuario:clave@host:5432/vgd_dwh_prod_migracion"
        )
        st.stop()
    if "postgresql" not in DEFAULT_DWH_URL.lower():
        st.error("DWH_URL debe ser una URL PostgreSQL (postgresql:// o postgresql+psycopg://...).")
        st.stop()
    try:
        validate_dwh_url_targets_vgd_prod(DEFAULT_DWH_URL)
    except ConfigError as exc:
        st.error(str(exc))
        st.stop()
    try:
        DwhClient.from_url(
            effective_dwh_url(DEFAULT_DWH_URL), default_limit=5
        ).execute_select("SELECT 1 AS ok")
    except Exception as exc:
        st.error(
            f"No se pudo conectar al DWH ({REQUIRED_DWH_DATABASE_NAME}): {exc}. "
            "Comprueba red, credenciales y que PostgreSQL acepte la conexión."
        )
        st.stop()

    dwh_sidebar_md = (
        f"**Base:** `{REQUIRED_DWH_DATABASE_NAME}` (PostgreSQL). "
        "Sin carga de dataset demo: todas las consultas usan el DWH configurado en **DWH_URL**."
    )

    # Configuracion fija por defecto (puede sobreescribirse por variables de entorno).
    dwh_url = normalize_dwh_url_string(os.getenv("DWH_URL", DEFAULT_DWH_URL))
    llm_endpoint = os.getenv("LLM_ENDPOINT", DEFAULT_LLM_ENDPOINT)
    llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
    max_rows = _env_int("MAX_ROWS", 200)
    llm_timeout = _env_int("LLM_TIMEOUT_SECONDS", 180)
    llm_temperature = _env_float("LLM_TEMPERATURE", 0.2)
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
        llm_temperature,
        cache_ttl_seconds,
        cache_max_entries,
        horizon_months,
        forecast_method,
        forecast_dimension,
    ) = _render_sidebar_controls(
        dwh_sidebar_md=dwh_sidebar_md,
        dwh_url=dwh_url,
        llm_endpoint=llm_endpoint,
        llm_model=llm_model,
        max_rows=max_rows,
        llm_timeout=llm_timeout,
        llm_temperature=llm_temperature,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
    )

    dwh_url = effective_dwh_url(dwh_url)

    natural_chat = st.session_state.get("natural_chat_mode", True)
    effective_question = ""
    should_run = False

    if natural_chat:
        effective_question, should_run = _render_natural_chat_block()
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            question = st.text_area(
                "Pregunta de negocio",
                key="question_input",
                height=110,
                placeholder="Ejemplo: Top 20 agencias por número de clientes consolidados.",
            )
        with col2:
            run = st.button("Consultar", type="primary", use_container_width=True)
        effective_question = (question or "").strip()
        should_run = bool(run and effective_question)

    # --- Desambiguación: si hay una pendiente, renderizar opciones ---
    disambig_state = st.session_state.get(SESSION_KEY_DISAMBIG)
    if disambig_state and not should_run:
        _render_disambiguation_ui(
            disambig_state["question"], disambig_state["rule"], natural_chat
        )
        return
    if should_run and disambig_state:
        st.session_state.pop(SESSION_KEY_DISAMBIG, None)

    # --- Desambiguación: comprobar si la pregunta nueva es ambigua ---
    if should_run and not st.session_state.pop(SESSION_KEY_DISAMBIG_DONE, False):
        _ui_llm_profile = resolve_llm_profile(
            schema_hint_file, dwh_url=dwh_url.strip()
        )
        disambig_rule = _check_disambiguation(
            effective_question, llm_profile=_ui_llm_profile
        )
        if disambig_rule:
            st.session_state[SESSION_KEY_DISAMBIG] = {
                "question": effective_question,
                "rule": disambig_rule,
            }
            _render_disambiguation_ui(effective_question, disambig_rule, natural_chat)
            return

    if natural_chat and not should_run:
        _render_follow_up_banners()
        # El resumen y el detalle viven en el hilo del chat (y el icono de detalle con diálogos).
        # No duplicamos «Respuesta» / pronóstico debajo para dejar solo la conversación.
        lr = st.session_state.get(SESSION_KEY_LAST_QUERY_VIEW)
        if lr and _is_developer_ui():
            _render_observability_panel(cache_stats=lr.get("cache_stats"))
        return

    if not natural_chat and not should_run:
        _render_follow_up_banners()
        st.info("Escribe tu pregunta y presiona 'Consultar'.")
        return

    if not effective_question.strip():
        st.error("Debes escribir una pregunta.")
        return

    if should_run:
        small_talk = _chitchat_reply(effective_question.strip())
        if small_talk is not None:
            _prepare_new_result_view()
            if natural_chat:
                st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, []).append(
                    {
                        "user": effective_question.strip(),
                        "kind": "chitchat",
                        "sql": "",
                        "rows": 0,
                        "error": None,
                        "kpi": "",
                        "answer_summary": small_talk,
                    }
                )
                st.session_state.pop(SESSION_KEY_LAST_QUERY_VIEW, None)
                st.rerun()
            st.markdown(small_talk)
            return

    if not dwh_url.strip():
        st.error("Debes indicar DWH_URL.")
        return
    try:
        validate_dwh_url_targets_vgd_prod(dwh_url.strip())
    except ConfigError as exc:
        st.error(str(exc))
        return

    _prepare_new_result_view()
    if natural_chat:
        st.session_state.pop(SESSION_KEY_LAST_QUERY_VIEW, None)

    schema_hint = _read_schema_hint(schema_hint_file) or DEFAULT_SCHEMA_HINT

    forecast_intent = is_forecast_intent(effective_question.strip())
    if should_run and forecast_intent:
        st.info(
            "Se detectó intención de pronóstico de ventas; se calculará con el módulo de pronóstico en Python."
        )

    if should_run and forecast_intent:
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
                            "host    vgd_dwh_prod_migracion    postgres    "
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
        if natural_chat:
            fc_n = len(forecast_result.forecast_rows)
            st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, []).append(
                {
                    "user": effective_question,
                    "kind": "forecast",
                    "sql": forecast_result.source_sql,
                    "rows": fc_n,
                    "error": None,
                    "answer_summary": (
                        f"Pronóstico de ventas listo: **{fc_n}** periodos en la tabla de resultados. "
                        "Puedes abrir la gráfica y el detalle cuando los necesites."
                    ),
                }
            )
            st.session_state[SESSION_KEY_LAST_QUERY_VIEW] = {
                "kind": "forecast",
                "forecast": forecast_result,
                "cache_stats": cache_stats,
            }
            st.rerun()
        _render_forecast_result(forecast_result, cache_stats=cache_stats)
        _render_observability_panel(cache_stats=cache_stats)
        return

    with st.spinner("Procesando consulta..."):
        cache_stats: dict[str, Any] | None = None
        try:
            agent = _get_session_agent(
                dwh_url=dwh_url.strip(),
                llm_endpoint=llm_endpoint.strip(),
                llm_model=llm_model.strip(),
                row_limit=int(max_rows),
                llm_timeout_seconds=int(llm_timeout),
                schema_hint=schema_hint,
                schema_hint_file=schema_hint_file,
                cache_ttl_seconds=int(cache_ttl_seconds),
                cache_max_entries=int(cache_max_entries),
                llm_temperature=float(llm_temperature),
            )
            prompt_extra = _build_follow_up_prompt_extra()
            vf = st.session_state.get(SESSION_KEY_FOCUS_VEHICLE)
            transcript = (
                _format_conversation_transcript(
                    st.session_state.get(SESSION_KEY_CHAT_TURNS, []),
                    vehicle_focus=vf,
                )
                if natural_chat
                else ""
            )
            result = agent.answer(
                effective_question.strip(),
                prompt_extra=prompt_extra,
                conversation_transcript=transcript,
                vehicle_focus=vf,
            )
            cache_stats = agent._dwh.get_cache_stats()  # noqa: SLF001
            summary_llm = _make_summary_llm_client(
                llm_endpoint.strip(),
                llm_model.strip(),
                llm_timeout_seconds=int(llm_timeout),
                llm_temperature=float(llm_temperature),
            )
            answer_summary_precomputed = _compute_hybrid_answer_summary(
                result.question,
                result.rows,
                summary_llm,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            st.error(f"Error ejecutando consulta: {message}")
            if natural_chat:
                st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, []).append(
                    {
                        "user": effective_question,
                        "sql": "",
                        "rows": 0,
                        "error": message,
                    }
                )
                st.session_state.pop(SESSION_KEY_LAST_QUERY_VIEW, None)
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
                            llm_temperature=float(llm_temperature),
                            llm_profile=resolve_llm_profile(
                                schema_hint_file, dwh_url=dwh_url.strip()
                            ),
                        )
                        extra_fb = _build_follow_up_prompt_extra()
                        vf_fb = st.session_state.get(SESSION_KEY_FOCUS_VEHICLE)
                        tr_fb = (
                            _format_conversation_transcript(
                                st.session_state.get(SESSION_KEY_CHAT_TURNS, []),
                                vehicle_focus=vf_fb,
                            )
                            if natural_chat
                            else ""
                        )
                        result = fallback_agent.answer(
                            effective_question.strip(),
                            prompt_extra=extra_fb,
                            conversation_transcript=tr_fb,
                            vehicle_focus=vf_fb,
                        )
                        cache_stats = fallback_agent._dwh.get_cache_stats()  # noqa: SLF001
                        summary_llm_fb = _make_summary_llm_client(
                            llm_endpoint.strip(),
                            FALLBACK_LLM_MODEL,
                            llm_timeout_seconds=int(llm_timeout),
                            llm_temperature=float(llm_temperature),
                        )
                        answer_summary_fb = _compute_hybrid_answer_summary(
                            result.question,
                            result.rows,
                            summary_llm_fb,
                        )
                        st.success(f"Consulta recuperada usando fallback: {FALLBACK_LLM_MODEL}")
                        _apply_auto_agency_focus_and_show_banners(result.rows)
                        if natural_chat:
                            st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, []).append(
                                {
                                    "user": effective_question,
                                    "sql": result.generated_sql,
                                    "rows": len(result.rows),
                                    "error": None,
                                    "kpi": "",
                                    "answer_summary": answer_summary_fb,
                                }
                            )
                            st.session_state[SESSION_KEY_LAST_QUERY_VIEW] = {
                                "kind": "agent",
                                "result": result,
                                "cache_stats": cache_stats,
                                "model_used": FALLBACK_LLM_MODEL,
                                "answer_summary": answer_summary_fb,
                            }
                            st.rerun()
                        _render_query_result(
                            result,
                            model_used=FALLBACK_LLM_MODEL,
                            cache_stats=cache_stats,
                            answer_summary_cached=answer_summary_fb,
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
                        "host    vgd_dwh_prod_migracion    postgres    "
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

    _apply_auto_agency_focus_and_show_banners(result.rows)
    if natural_chat:
        st.session_state.setdefault(SESSION_KEY_CHAT_TURNS, []).append(
            {
                "user": effective_question,
                "sql": result.generated_sql,
                "rows": len(result.rows),
                "error": None,
                "kpi": "",
                "answer_summary": answer_summary_precomputed,
            }
        )
        st.session_state[SESSION_KEY_LAST_QUERY_VIEW] = {
            "kind": "agent",
            "result": result,
            "cache_stats": cache_stats,
            "model_used": llm_model.strip(),
            "answer_summary": answer_summary_precomputed,
        }
        st.rerun()
    _render_query_result(
        result,
        model_used=llm_model.strip(),
        cache_stats=cache_stats,
        answer_summary_cached=answer_summary_precomputed,
    )
    _render_observability_panel(cache_stats=cache_stats)


if __name__ == "__main__":
    main()
