from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import pandas as pd

from .dwh import DwhClient

FORECAST_METHODS: dict[str, str] = {
    "moving_average": "Media móvil (3 meses)",
    "linear_trend": "Tendencia lineal",
}

FORECAST_DIMENSIONS: dict[str, str] = {
    "total": "Total",
    "state": "Por estado",
    "channel": "Por canal",
    "segment": "Por segmento",
}

_FORECAST_KEYWORDS = (
    "pronostico",
    "pronóstico",
    "forecast",
    "proyeccion",
    "proyección",
    "estimar",
    "estimado",
)


@dataclass
class SalesForecastResult:
    method: str
    method_label: str
    horizon_months: int
    dimension: str
    source_sql: str
    source_rows: int
    forecast_rows: list[dict[str, Any]]
    chart_rows: list[dict[str, Any]]


def is_forecast_intent(question: str) -> bool:
    text = (question or "").strip().lower()
    return any(keyword in text for keyword in _FORECAST_KEYWORDS)


def extract_horizon_from_question(question: str, default: int = 3) -> int:
    text = (question or "").strip().lower()
    month_match = re.search(r"(\d{1,2})\s*mes", text)
    if month_match:
        value = int(month_match.group(1))
        if 1 <= value <= 24:
            return value
    if "trimestre" in text:
        return 3
    if "semestre" in text:
        return 6
    if "año" in text or "anio" in text:
        return 12
    return default


def extract_method_from_question(question: str, default: str = "moving_average") -> str:
    text = (question or "").strip().lower()
    if "tendencia" in text or "lineal" in text:
        return "linear_trend"
    if "media movil" in text or "media móvil" in text:
        return "moving_average"
    return default


def extract_dimension_from_question(question: str, default: str = "total") -> str:
    text = (question or "").strip().lower()
    if "estado" in text or "estados" in text:
        return "state"
    if "canal" in text or "canales" in text:
        return "channel"
    if "segmento" in text or "segmentos" in text:
        return "segment"
    return default


def compute_sales_forecast(
    dwh_client: DwhClient,
    horizon_months: int,
    method: str,
    dimension: str,
) -> SalesForecastResult:
    if method not in FORECAST_METHODS:
        raise ValueError(f"Método de pronóstico no soportado: {method}")
    if dimension not in FORECAST_DIMENSIONS:
        raise ValueError(f"Dimensión de pronóstico no soportada: {dimension}")
    if horizon_months <= 0:
        raise ValueError("El horizonte debe ser mayor a 0.")

    source_sql = _build_history_query(dimension)
    rows = dwh_client.execute_select(source_sql)
    if not rows:
        raise ValueError("No hay ventas históricas para calcular pronóstico.")

    history_df = pd.DataFrame(rows)
    history_df["period"] = pd.to_datetime(
        history_df["year_month"].astype(str) + "-01", errors="coerce"
    )
    history_df["dimension_value"] = history_df["dimension_value"].fillna("SIN_DATO").astype(str)
    history_df["total_sales"] = pd.to_numeric(history_df["total_sales"], errors="coerce").fillna(0.0)
    history_df = history_df.dropna(subset=["period"])
    if history_df.empty:
        raise ValueError("No hay fechas válidas para calcular pronóstico.")

    history_df = history_df.groupby(["dimension_value", "period"], as_index=False)["total_sales"].sum()

    if dimension != "total":
        latest_strength = (
            history_df.sort_values("period")
            .groupby("dimension_value")
            .tail(3)
            .groupby("dimension_value")["total_sales"]
            .sum()
            .sort_values(ascending=False)
        )
        selected = set(latest_strength.head(12).index.tolist())
        history_df = history_df[history_df["dimension_value"].isin(selected)]

    forecast_rows: list[dict[str, Any]] = []
    chart_rows: list[dict[str, Any]] = []

    for dimension_value, group in history_df.groupby("dimension_value"):
        series = group.sort_values("period").set_index("period")["total_sales"]
        full_index = pd.date_range(series.index.min(), series.index.max(), freq="MS")
        series = series.reindex(full_index, fill_value=0.0)
        values = [float(v) for v in series.tolist()]

        if method == "moving_average":
            predictions = _moving_average_forecast(values, horizon_months, window=3)
        else:
            predictions = _linear_trend_forecast(values, horizon_months)

        for period, amount in series.items():
            chart_rows.append(
                {
                    "period": period.strftime("%Y-%m"),
                    "tipo": "Historico",
                    "ventas": round(float(amount), 2),
                }
            )

        last_period = series.index.max()
        for step, prediction in enumerate(predictions, start=1):
            forecast_period = (last_period + pd.DateOffset(months=step)).strftime("%Y-%m")
            lower = prediction * 0.9
            upper = prediction * 1.1
            forecast_rows.append(
                {
                    "periodo": forecast_period,
                    "dimension": dimension_value,
                    "ventas_pronosticadas": round(prediction, 2),
                    "intervalo_bajo": round(lower, 2),
                    "intervalo_alto": round(upper, 2),
                    "metodo": FORECAST_METHODS[method],
                }
            )
            chart_rows.append(
                {
                    "period": forecast_period,
                    "tipo": "Pronostico",
                    "ventas": round(prediction, 2),
                }
            )

    forecast_rows.sort(key=lambda row: (row["periodo"], row["dimension"]))
    chart_df = pd.DataFrame(chart_rows)
    chart_df = chart_df.groupby(["period", "tipo"], as_index=False)["ventas"].sum()
    chart_rows = chart_df.to_dict(orient="records")

    return SalesForecastResult(
        method=method,
        method_label=FORECAST_METHODS[method],
        horizon_months=horizon_months,
        dimension=dimension,
        source_sql=source_sql,
        source_rows=len(rows),
        forecast_rows=forecast_rows,
        chart_rows=chart_rows,
    )


def _build_history_query(dimension: str) -> str:
    if dimension == "total":
        return """
SELECT
    m.year_month AS year_month,
    'TOTAL' AS dimension_value,
    SUM(m.total_sales) AS total_sales
FROM mv_sales_monthly m
GROUP BY 1
ORDER BY 1
LIMIT 50000;
""".strip()

    if dimension == "channel":
        return """
SELECT
    m.year_month AS year_month,
    COALESCE(m.channel, 'SIN_DATO') AS dimension_value,
    SUM(m.total_sales) AS total_sales
FROM mv_sales_monthly m
GROUP BY 1, 2
ORDER BY 1, 2
LIMIT 50000;
""".strip()

    dimension_column = "m.state" if dimension == "state" else "m.segment"
    return f"""
SELECT
    m.year_month AS year_month,
    COALESCE({dimension_column}, 'SIN_DATO') AS dimension_value,
    SUM(m.total_sales) AS total_sales
FROM mv_sales_monthly m
GROUP BY 1, 2
ORDER BY 1, 2
LIMIT 50000;
""".strip()


def _moving_average_forecast(values: list[float], horizon: int, window: int = 3) -> list[float]:
    if not values:
        return [0.0] * horizon

    forecast = []
    history = values.copy()
    for _ in range(horizon):
        base = history[-window:] if len(history) >= window else history
        prediction = sum(base) / len(base)
        prediction = max(prediction, 0.0)
        history.append(prediction)
        forecast.append(float(prediction))
    return forecast


def _linear_trend_forecast(values: list[float], horizon: int) -> list[float]:
    if not values:
        return [0.0] * horizon
    if len(values) == 1:
        return [max(float(values[0]), 0.0)] * horizon

    n = len(values)
    x_values = list(range(n))
    mean_x = sum(x_values) / n
    mean_y = sum(values) / n

    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, values))
    den = sum((x - mean_x) ** 2 for x in x_values)
    slope = (num / den) if den else 0.0
    intercept = mean_y - slope * mean_x

    forecast = []
    for step in range(1, horizon + 1):
        future_x = n - 1 + step
        prediction = intercept + slope * future_x
        forecast.append(max(float(prediction), 0.0))
    return forecast
