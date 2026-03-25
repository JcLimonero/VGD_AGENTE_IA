from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DeterministicQuery:
    name: str
    sql: str
    explanation: str


_TIME_REPURCHASE_SQL = """
WITH sale_gaps AS (
    SELECT
        s.customer_id,
        julianday(s.sale_date)
        - julianday(LAG(s.sale_date) OVER (PARTITION BY s.customer_id ORDER BY s.sale_date)) AS gap_days
    FROM sales s
    WHERE s.status IN ('completed', 'entregada', 'facturada', 'cerrada')
)
SELECT ROUND(AVG(gap_days), 2) AS avg_repurchase_days
FROM sale_gaps
WHERE gap_days IS NOT NULL;
""".strip()


_INSURANCE_OPPORTUNITY_SQL = """
WITH latest_policy_per_vehicle AS (
    SELECT
        ip.*,
        ROW_NUMBER() OVER (
            PARTITION BY ip.vehicle_id
            ORDER BY ip.policy_end_date DESC, ip.id DESC
        ) AS rn
    FROM insurance_policies ip
)
SELECT
    c.id AS customer_id,
    c.full_name,
    c.state,
    c.segment,
    c.risk_profile,
    v.id AS vehicle_id,
    v.unit_type,
    COALESCE(lp.policy_status, 'sin_poliza') AS policy_status,
    lp.policy_end_date
FROM customers c
JOIN vehicles v ON v.customer_id = c.id
LEFT JOIN latest_policy_per_vehicle lp
    ON lp.vehicle_id = v.id
   AND lp.rn = 1
WHERE lp.id IS NULL
   OR lp.policy_status IN ('vencida', 'cancelada')
   OR (lp.policy_status = 'activa' AND julianday(lp.policy_end_date) - julianday('now') <= 60)
ORDER BY c.full_name, v.id;
""".strip()


_AVG_AGE_BUYERS_SQL = """
SELECT
    ROUND(AVG(c.age), 2) AS avg_age_buyers,
    COUNT(DISTINCT s.customer_id) AS buyers_count
FROM sales s
JOIN customers c ON c.id = s.customer_id
WHERE s.status IN ('completed', 'entregada', 'facturada', 'cerrada');
""".strip()


_UNIT_BY_AGE_GENDER_SQL = """
WITH base AS (
    SELECT
        CASE
            WHEN c.age BETWEEN 20 AND 30 THEN '20-30'
            WHEN c.age BETWEEN 31 AND 39 THEN '31-39'
            WHEN c.age BETWEEN 40 AND 50 THEN '40-50'
            ELSE '51+'
        END AS age_range,
        c.gender,
        v.unit_type,
        COUNT(*) AS purchases
    FROM sales s
    JOIN customers c ON c.id = s.customer_id
    JOIN vehicles v ON v.id = s.vehicle_id
    WHERE s.status IN ('completed', 'entregada', 'facturada', 'cerrada')
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT
        base.*,
        ROW_NUMBER() OVER (
            PARTITION BY base.age_range, base.gender
            ORDER BY base.purchases DESC
        ) AS rn
    FROM base
)
SELECT
    age_range,
    gender,
    unit_type AS recommended_unit_type,
    purchases
FROM ranked
WHERE rn = 1
ORDER BY age_range, gender;
""".strip()

_APPT_NO_SHOW_BY_WORKSHOP_SQL = """
SELECT
    workshop,
    COUNT(*) AS total_citas,
    SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END) AS no_show_count,
    ROUND(
        CAST(SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(COUNT(*), 0)
        * 100,
        2
    ) AS no_show_rate
FROM service_appointments
GROUP BY workshop
ORDER BY no_show_rate DESC, no_show_count DESC;
""".strip()

_APPT_CONVERSION_BY_WORKSHOP_SQL = """
SELECT
    workshop,
    SUM(CASE WHEN appointment_status = 'programada' THEN 1 ELSE 0 END) AS citas_programadas,
    SUM(CASE WHEN appointment_status = 'completada' THEN 1 ELSE 0 END) AS citas_completadas,
    ROUND(
        CAST(SUM(CASE WHEN appointment_status = 'completada' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(
            SUM(
                CASE
                    WHEN appointment_status IN ('programada', 'completada') THEN 1
                    ELSE 0
                END
            ),
            0
        )
        * 100,
        2
    ) AS conversion_rate
FROM service_appointments
GROUP BY workshop
ORDER BY conversion_rate DESC, citas_completadas DESC;
""".strip()

_APPT_CANCELLATIONS_BY_REASON_SQL = """
SELECT
    COALESCE(cancellation_reason, 'Sin motivo') AS cancellation_reason,
    COUNT(*) AS cancellation_count
FROM service_appointments
WHERE appointment_status = 'cancelada'
GROUP BY COALESCE(cancellation_reason, 'Sin motivo')
ORDER BY cancellation_count DESC, cancellation_reason ASC;
""".strip()

_APPT_NO_SHOW_BY_WORKSHOP_ADVISOR_SQL = """
SELECT
    workshop,
    COUNT(*) AS no_show_count
FROM service_appointments
WHERE appointment_status = 'no_show'
GROUP BY workshop
ORDER BY no_show_count DESC, workshop ASC
LIMIT 10;
""".strip()

_APPT_NO_SHOW_WEEKLY_SQL = """
SELECT
    strftime('%Y-%W', appointment_date) AS week,
    COUNT(*) AS total_citas,
    SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END) AS no_show_count,
    ROUND(
        CAST(SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(COUNT(*), 0)
        * 100,
        2
    ) AS no_show_rate
FROM service_appointments
WHERE appointment_date >= date('now', '-3 months')
GROUP BY strftime('%Y-%W', appointment_date)
ORDER BY week;
""".strip()

_APPT_STATUS_THIS_MONTH_SQL = """
SELECT
    appointment_status,
    COUNT(*) AS cantidad
FROM service_appointments
WHERE strftime('%Y-%m', appointment_date) = strftime('%Y-%m', date('now'))
GROUP BY appointment_status
ORDER BY cantidad DESC;
""".strip()


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def match_kpi_template(question: str) -> DeterministicQuery | None:
    normalized = (question or "").strip().lower()
    if not normalized:
        return None

    if _contains_any(normalized, ("recompra", "vuelve a comprar", "volver a comprar")) and _contains_any(
        normalized, ("promedio", "tiempo", "cada cuanto", "cada cuánto", "dias", "días")
    ):
        return DeterministicQuery(
            name="avg_repurchase_time",
            sql=_TIME_REPURCHASE_SQL,
            explanation="Definición determinística: promedio de días entre compras consecutivas por cliente.",
        )

    if _contains_any(normalized, ("ofrecer un seguro", "seguro hoy", "seguro", "poliza por vencer", "póliza por vencer")):
        return DeterministicQuery(
            name="insurance_opportunities",
            sql=_INSURANCE_OPPORTUNITY_SQL,
            explanation="Clientes con oportunidad comercial de seguro (sin póliza, vencida/cancelada o por vencer).",
        )

    if _contains_any(normalized, ("edad promedio", "promedio de edad")) and _contains_any(
        normalized, ("compran", "compradores", "clientes que compran")
    ):
        return DeterministicQuery(
            name="avg_age_buyers",
            sql=_AVG_AGE_BUYERS_SQL,
            explanation="Edad promedio de clientes con al menos una compra cerrada/facturada/entregada.",
        )

    if _contains_any(normalized, ("tipo de unidad", "unidad ofrecer", "rango de edad", "género", "genero")):
        return DeterministicQuery(
            name="unit_type_by_age_gender",
            sql=_UNIT_BY_AGE_GENDER_SQL,
            explanation="Unidad más comprada por rango de edad y género usando datos históricos.",
        )

    if _contains_any(normalized, ("no show", "no_show")) and _contains_any(
        normalized, ("taller", "por taller", "por asesor", "asesor", "top")
    ):
        if _contains_any(normalized, ("top", "asesor")):
            return DeterministicQuery(
                name="appointments_no_show_top",
                sql=_APPT_NO_SHOW_BY_WORKSHOP_ADVISOR_SQL,
                explanation="Top de no-show por taller en agenda de servicio.",
            )
        return DeterministicQuery(
            name="appointments_no_show_rate",
            sql=_APPT_NO_SHOW_BY_WORKSHOP_SQL,
            explanation="Tasa de no-show por taller con base en citas de servicio.",
        )

    if _contains_any(normalized, ("no show", "no_show")) and _contains_any(
        normalized, ("semanal", "semana", "últimos 3 meses", "ultimos 3 meses")
    ):
        return DeterministicQuery(
            name="appointments_no_show_weekly",
            sql=_APPT_NO_SHOW_WEEKLY_SQL,
            explanation="Evolución semanal de no-show en los últimos 3 meses.",
        )

    if _contains_any(normalized, ("motivos de cancelación", "motivos de cancelacion", "cancelaciones por motivo")):
        return DeterministicQuery(
            name="appointments_cancellations_by_reason",
            sql=_APPT_CANCELLATIONS_BY_REASON_SQL,
            explanation="Cancelaciones de citas agrupadas por motivo.",
        )

    if _contains_any(normalized, ("conversión", "conversion")) and _contains_any(
        normalized, ("programadas", "completadas", "citas")
    ):
        return DeterministicQuery(
            name="appointments_conversion_by_workshop",
            sql=_APPT_CONVERSION_BY_WORKSHOP_SQL,
            explanation="Conversión de citas programadas/completadas por taller.",
        )

    if _contains_any(normalized, ("citas de servicio", "citas")) and _contains_any(
        normalized, ("estatus", "estado", "este mes")
    ):
        return DeterministicQuery(
            name="appointments_status_current_month",
            sql=_APPT_STATUS_THIS_MONTH_SQL,
            explanation="Distribución de estatus de citas de servicio en el mes actual.",
        )

    return None
