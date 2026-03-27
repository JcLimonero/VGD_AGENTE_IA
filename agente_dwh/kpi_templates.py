from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DeterministicQuery:
    """Plantilla KPI con SQL fijo que no pasa por el LLM."""

    name: str
    sql: str
    explanation: str


# ---------------------------------------------------------------------------
# Plantillas registradas
# ---------------------------------------------------------------------------

_REPURCHASE_SQL = """
WITH customer_purchases AS (
    SELECT
        cv.nd_client_dms,
        i.billing_date,
        LAG(i.billing_date) OVER (
            PARTITION BY cv.nd_client_dms
            ORDER BY i.billing_date
        ) AS prev_billing_date
    FROM h_customer_vehicle cv
    JOIN h_invoices i ON cv.vin = i.vin
    WHERE i.billing_date IS NOT NULL
      AND cv.nd_client_dms IS NOT NULL
),
intervals AS (
    SELECT (billing_date - prev_billing_date) AS days_between
    FROM customer_purchases
    WHERE prev_billing_date IS NOT NULL
      AND (billing_date - prev_billing_date) > 0
)
SELECT ROUND(AVG(days_between)::numeric, 1) AS avg_repurchase_days
FROM intervals
""".strip()

_KPI_TEMPLATES: list[tuple[list[str], DeterministicQuery]] = [
    (
        [
            r"(?i)tiempo\s+promedio\s+(?:de\s+)?recompra",
            r"(?i)promedio\s+(?:de\s+)?recompra",
            r"(?i)cada\s+cu[aá]nto\s+(?:compran|recompran|vuelven\s+a\s+comprar)",
            r"(?i)frecuencia\s+(?:de\s+)?recompra",
            r"(?i)intervalo\s+(?:de\s+)?recompra",
        ],
        DeterministicQuery(
            name="avg_repurchase_time",
            sql=_REPURCHASE_SQL,
            explanation="Tiempo promedio entre compras consecutivas por cliente, calculado desde h_customer_vehicle → h_invoices.",
        ),
    ),
]


def match_kpi_template(question: str) -> DeterministicQuery | None:
    """Devuelve la plantilla KPI si la pregunta coincide, o None para que pase por el LLM."""
    for patterns, template in _KPI_TEMPLATES:
        if any(re.search(p, question) for p in patterns):
            return template
    return None
