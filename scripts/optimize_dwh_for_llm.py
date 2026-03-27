#!/usr/bin/env python3
"""Aplica optimizaciones del DWH para consultas generadas por LLM.

Incluye:
- Indices para joins/filtros frecuentes.
- Vistas de simplificacion semantica (cliente 360, vehiculo maestro, vendedores).
- Vistas materializadas para agregados por agencia/mes.

Uso:
  export DWH_URL='postgresql+psycopg://user:pass@host:5432/vgd_dwh_prod_migracion'
  python scripts/optimize_dwh_for_llm.py

Opcional:
  python scripts/optimize_dwh_for_llm.py --refresh
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psycopg
except ImportError:
    print("Instala psycopg: pip install psycopg[binary]", file=sys.stderr)
    raise SystemExit(1) from None


def _sqlalchemy_to_psycopg_url(url: str) -> str:
    u = url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if u.startswith(prefix):
            return "postgresql://" + u.split("://", 1)[1]
    return u


INDEXES: tuple[str, ...] = (
    # Dimension de agencias para joins por idAgency.
    'CREATE INDEX IF NOT EXISTS idx_agencies_idagency ON agencies ("idAgency")',
    # Clave natural principal de cliente.
    'CREATE INDEX IF NOT EXISTS idx_customers_agency_client ON customers ("idAgency", "ndClientDMS")',
    'CREATE INDEX IF NOT EXISTS idx_customers_agency_seller ON customers ("idAgency", "ndSeller")',
    # Joins cliente-vehiculo y trazabilidad por VIN.
    'CREATE INDEX IF NOT EXISTS idx_customer_vehicle_agency_client ON customer_vehicle ("idAgency", "ndClientDMS")',
    'CREATE INDEX IF NOT EXISTS idx_customer_vehicle_agency_vin ON customer_vehicle ("idAgency", vin)',
    # Hechos de ventas/pedidos/facturas por agencia y tiempo.
    'CREATE INDEX IF NOT EXISTS idx_orders_agency_delivery_date ON orders ("idAgency", delivery_date)',
    'CREATE INDEX IF NOT EXISTS idx_orders_agency_order_dms ON orders ("idAgency", order_dms)',
    'CREATE INDEX IF NOT EXISTS idx_orders_agency_client ON orders ("idAgency", "ndClientDMS")',
    'CREATE INDEX IF NOT EXISTS idx_orders_agency_vin ON orders ("idAgency", vin)',
    'CREATE INDEX IF NOT EXISTS idx_invoices_agency_billing_date ON invoices ("idAgency", billing_date)',
    'CREATE INDEX IF NOT EXISTS idx_invoices_agency_order_dms ON invoices ("idAgency", order_dms)',
    'CREATE INDEX IF NOT EXISTS idx_invoices_agency_vin ON invoices ("idAgency", vin)',
    'CREATE INDEX IF NOT EXISTS idx_invoices_agency_text_order_dms ON invoices (("idAgency"::text), order_dms)',
    'CREATE INDEX IF NOT EXISTS idx_invoices_agency_text_vin ON invoices (("idAgency"::text), vin)',
    'CREATE INDEX IF NOT EXISTS idx_comissions_agency_delivery_date ON comissions ("idAgency", delivery_date)',
    'CREATE INDEX IF NOT EXISTS idx_comissions_agency_order_dms ON comissions ("idAgency", order_dms)',
    # Historial por unidad.
    'CREATE INDEX IF NOT EXISTS idx_inventory_agency_vin ON inventory ("idAgency", vin)',
    "CREATE INDEX IF NOT EXISTS idx_services_vin_service_date ON services (vin, service_date)",
    'CREATE INDEX IF NOT EXISTS idx_services_agency_service_date ON services ("idAgency", service_date)',
    'CREATE INDEX IF NOT EXISTS idx_services_agency_order_dms ON services ("idAgency", order_dms)',
    'CREATE INDEX IF NOT EXISTS idx_services_agency_vin ON services ("idAgency", vin)',
    'CREATE INDEX IF NOT EXISTS idx_services_agency_text_order_dms ON services (("idAgency"::text), order_dms)',
    'CREATE INDEX IF NOT EXISTS idx_services_agency_text_vin_date ON services (("idAgency"::text), vin, service_date)',
    'CREATE INDEX IF NOT EXISTS idx_services_by_vin_agency_vin ON services_by_vin ("idAgency", vin)',
    'CREATE INDEX IF NOT EXISTS idx_services_by_vin_start_end ON services_by_vin ("startDateTime", "endDateTime")',
)


CREATE_VIEW_VEHICLE_MASTER = """
CREATE OR REPLACE VIEW v_vehicle_master AS
WITH i AS (
  SELECT
    i.*,
    ROW_NUMBER() OVER (
      PARTITION BY i."idAgency", i.vin
      ORDER BY i.timestamp_updated DESC NULLS LAST, i."timestamp" DESC NULLS LAST, i.id DESC
    ) AS rn
  FROM inventory i
),
cv AS (
  SELECT
    cv.*,
    ROW_NUMBER() OVER (
      PARTITION BY cv."idAgency", cv.vin
      ORDER BY cv."timestamp" DESC NULLS LAST, cv.id DESC
    ) AS rn
  FROM customer_vehicle cv
)
SELECT
  COALESCE(i."idAgency", cv."idAgency") AS "idAgency",
  COALESCE(i.vin, cv.vin) AS vin,
  COALESCE(i.brand, cv.brand) AS brand,
  COALESCE(i.model, cv.model) AS model,
  COALESCE(i.version, cv.version) AS version,
  COALESCE(i.year, cv.year) AS year,
  COALESCE(i.exterior_color, cv.external_color) AS exterior_color,
  COALESCE(i.interior_color, cv.internal_color) AS interior_color,
  i.status,
  i."statusDescription" AS status_description,
  i.amount,
  i.km,
  i.timestamp_dms
FROM i
FULL OUTER JOIN cv
  ON i."idAgency" = cv."idAgency"
 AND i.vin = cv.vin
WHERE (i.rn = 1 OR i.rn IS NULL)
  AND (cv.rn = 1 OR cv.rn IS NULL);
"""

CREATE_VIEW_VEHICLE_MASTER_FALLBACK = """
CREATE OR REPLACE VIEW v_vehicle_master AS
SELECT
  i."idAgency"::text AS "idAgency",
  i.vin,
  i.brand,
  i.model,
  i.version,
  i.year,
  i.exterior_color,
  i.interior_color,
  i.status,
  i."statusDescription" AS status_description,
  i.amount,
  i.km,
  i.timestamp_dms
FROM inventory i;
"""


CREATE_VIEW_CLIENTE_360 = """
CREATE OR REPLACE VIEW v_cliente_360 AS
WITH cv_stats AS (
  SELECT
    cv."idAgency",
    cv."ndClientDMS",
    COUNT(DISTINCT cv.vin)::bigint AS vehicles_count
  FROM customer_vehicle cv
  GROUP BY cv."idAgency", cv."ndClientDMS"
),
service_stats AS (
  SELECT
    cv."idAgency",
    cv."ndClientDMS",
    COUNT(s."Id")::bigint AS services_count,
    MAX(s.service_date) AS last_service_date,
    SUM(COALESCE(s.amount, 0))::numeric(18,2) AS services_amount_total
  FROM customer_vehicle cv
  LEFT JOIN services s
    ON s."idAgency"::text = cv."idAgency"
   AND s.vin = cv.vin
  GROUP BY cv."idAgency", cv."ndClientDMS"
),
sales_stats AS (
  SELECT
    o."idAgency",
    o."ndClientDMS",
    COUNT(DISTINCT o.order_dms)::bigint AS orders_count,
    MAX(o.delivery_date) AS last_order_delivery_date,
    SUM(COALESCE(o.amount, 0))::numeric(18,2) AS orders_amount_total
  FROM orders o
  GROUP BY o."idAgency", o."ndClientDMS"
)
SELECT
  c."idAgency",
  c."ndClientDMS",
  c.name,
  c.bussines_name,
  c.mail,
  c.mobile_phone,
  c.phone,
  c.state,
  c.city,
  c."customer_source",
  c."preferred_contact_method",
  COALESCE(cv.vehicles_count, 0) AS vehicles_count,
  COALESCE(ss.services_count, 0) AS services_count,
  ss.last_service_date,
  COALESCE(ss.services_amount_total, 0)::numeric(18,2) AS services_amount_total,
  COALESCE(sa.orders_count, 0) AS orders_count,
  sa.last_order_delivery_date,
  COALESCE(sa.orders_amount_total, 0)::numeric(18,2) AS orders_amount_total
FROM customers c
LEFT JOIN cv_stats cv
  ON cv."idAgency" = c."idAgency"
 AND cv."ndClientDMS" = c."ndClientDMS"
LEFT JOIN service_stats ss
  ON ss."idAgency" = c."idAgency"
 AND ss."ndClientDMS" = c."ndClientDMS"
LEFT JOIN sales_stats sa
  ON sa."idAgency" = c."idAgency"
 AND sa."ndClientDMS" = c."ndClientDMS";
"""

CREATE_VIEW_CLIENTE_360_FALLBACK = """
CREATE OR REPLACE VIEW v_cliente_360 AS
WITH sales_stats AS (
  SELECT
    o."idAgency"::text AS "idAgency",
    o."ndClientDMS",
    COUNT(DISTINCT o.order_dms)::bigint AS orders_count,
    MAX(o.delivery_date) AS last_order_delivery_date,
    SUM(COALESCE(o.amount, 0))::numeric(18,2) AS orders_amount_total
  FROM orders o
  GROUP BY o."idAgency"::text, o."ndClientDMS"
)
SELECT
  c."idAgency"::text AS "idAgency",
  c."ndClientDMS",
  c.name,
  c.bussines_name,
  c.mail,
  c.mobile_phone,
  c.phone,
  c.state,
  c.city,
  c."customer_source",
  c."preferred_contact_method",
  COALESCE(sa.orders_count, 0) AS orders_count,
  sa.last_order_delivery_date,
  COALESCE(sa.orders_amount_total, 0)::numeric(18,2) AS orders_amount_total
FROM customers c
LEFT JOIN sales_stats sa
  ON sa."idAgency" = c."idAgency"::text
 AND sa."ndClientDMS" = c."ndClientDMS";
"""


CREATE_VIEW_DIM_SELLERS = """
CREATE OR REPLACE VIEW dim_sellers AS
SELECT DISTINCT
  s."idAgency",
  s.seller_id,
  MAX(s.seller_name) AS seller_name,
  MAX(s.seller_email) AS seller_email,
  MAX(s.seller_phone) AS seller_phone
FROM (
  SELECT
    c."idAgency",
    c."ndSeller" AS seller_id,
    c."seller_Name" AS seller_name,
    c."seller_Email" AS seller_email,
    NULL::varchar AS seller_phone
  FROM customers c
  WHERE c."ndSeller" IS NOT NULL
  UNION ALL
  SELECT
    o."idAgency",
    o."ndConsultant" AS seller_id,
    o."consultantName" AS seller_name,
    NULL::varchar AS seller_email,
    o.phone_seller AS seller_phone
  FROM orders o
  WHERE o."ndConsultant" IS NOT NULL
  UNION ALL
  SELECT
    cm."idAgency",
    cm."idConsultant" AS seller_id,
    cm.consultant_name AS seller_name,
    cm.consultant_mail AS seller_email,
    NULL::varchar AS seller_phone
  FROM comissions cm
  WHERE cm."idConsultant" IS NOT NULL
) s
GROUP BY s."idAgency", s.seller_id;
"""

CREATE_VIEW_DIM_SELLERS_FALLBACK = """
CREATE OR REPLACE VIEW dim_sellers AS
SELECT DISTINCT
  s."idAgency",
  s.seller_id,
  MAX(s.seller_name) AS seller_name,
  MAX(s.seller_email) AS seller_email,
  MAX(s.seller_phone) AS seller_phone
FROM (
  SELECT
    c."idAgency"::text AS "idAgency",
    c."ndSeller" AS seller_id,
    c."seller_Name" AS seller_name,
    c."seller_Email" AS seller_email,
    NULL::text AS seller_phone
  FROM customers c
  WHERE c."ndSeller" IS NOT NULL
  UNION ALL
  SELECT
    o."idAgency"::text AS "idAgency",
    o."ndConsultant" AS seller_id,
    o."consultantName" AS seller_name,
    NULL::text AS seller_email,
    o.phone_seller AS seller_phone
  FROM orders o
  WHERE o."ndConsultant" IS NOT NULL
) s
GROUP BY s."idAgency", s.seller_id;
"""


CREATE_VIEW_DIM_FECHA = """
CREATE OR REPLACE VIEW dim_fecha AS
WITH bounds AS (
  SELECT
    LEAST(
      COALESCE((SELECT MIN(i.billing_date) FROM invoices i), CURRENT_DATE),
      COALESCE((SELECT MIN(s.service_date) FROM services s), CURRENT_DATE),
      COALESCE((SELECT MIN(o.delivery_date::date) FROM orders o), CURRENT_DATE)
    ) AS min_date,
    GREATEST(
      COALESCE((SELECT MAX(i.billing_date) FROM invoices i), CURRENT_DATE),
      COALESCE((SELECT MAX(s.service_date) FROM services s), CURRENT_DATE),
      COALESCE((SELECT MAX(o.delivery_date::date) FROM orders o), CURRENT_DATE)
    ) AS max_date
),
calendar AS (
  SELECT generate_series(min_date, max_date, interval '1 day')::date AS date_key
  FROM bounds
)
SELECT
  c.date_key,
  EXTRACT(YEAR FROM c.date_key)::int AS year,
  EXTRACT(MONTH FROM c.date_key)::int AS month,
  EXTRACT(DAY FROM c.date_key)::int AS day,
  EXTRACT(QUARTER FROM c.date_key)::int AS quarter,
  EXTRACT(ISODOW FROM c.date_key)::int AS iso_weekday,
  TO_CHAR(c.date_key, 'YYYY-MM') AS month_label
FROM calendar c;
"""


CREATE_MV_VENTAS_MENSUALES = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ventas_mensuales_agencia AS
SELECT
  i."idAgency"::text AS "idAgency",
  DATE_TRUNC('month', i.billing_date)::date AS month_start,
  COUNT(*)::bigint AS invoices_count,
  COUNT(DISTINCT i.vin)::bigint AS vin_count,
  SUM(COALESCE(i.sub_total, 0))::numeric(18,2) AS sub_total_amount,
  SUM(COALESCE(i.amount_accesories, 0))::numeric(18,2) AS accessories_amount
FROM invoices i
WHERE i.billing_date IS NOT NULL
GROUP BY i."idAgency"::text, DATE_TRUNC('month', i.billing_date)::date;
"""


CREATE_MV_SERVICIOS_MENSUALES = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_servicios_mensuales_agencia AS
SELECT
  s."idAgency"::text AS "idAgency",
  DATE_TRUNC('month', s.service_date)::date AS month_start,
  COUNT(*)::bigint AS services_count,
  COUNT(DISTINCT s.vin)::bigint AS vin_count,
  SUM(COALESCE(s.amount, 0))::numeric(18,2) AS services_amount
FROM services s
WHERE s.service_date IS NOT NULL
GROUP BY s."idAgency"::text, DATE_TRUNC('month', s.service_date)::date;
"""


CREATE_MV_INVENTARIO_ACTUAL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inventario_actual_agencia AS
SELECT
  i."idAgency"::text AS "idAgency",
  COUNT(*)::bigint AS units_count,
  COUNT(DISTINCT i.vin)::bigint AS vin_count,
  SUM(COALESCE(i.amount, 0))::numeric(18,2) AS inventory_amount
FROM inventory i
GROUP BY i."idAgency"::text;
"""


CREATE_MV_PERFORMANCE_AGENCIA = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_performance_agencia AS
WITH ventas AS (
  SELECT
    v."idAgency",
    SUM(v.invoices_count)::bigint AS invoices_count,
    SUM(v.sub_total_amount)::numeric(18,2) AS sales_amount
  FROM mv_ventas_mensuales_agencia v
  GROUP BY v."idAgency"
),
servicios AS (
  SELECT
    s."idAgency",
    SUM(s.services_count)::bigint AS services_count,
    SUM(s.services_amount)::numeric(18,2) AS services_amount
  FROM mv_servicios_mensuales_agencia s
  GROUP BY s."idAgency"
)
SELECT
  a."idAgency",
  a.name AS agency_name,
  COALESCE(v.invoices_count, 0) AS invoices_count,
  COALESCE(v.sales_amount, 0)::numeric(18,2) AS sales_amount,
  COALESCE(s.services_count, 0) AS services_count,
  COALESCE(s.services_amount, 0)::numeric(18,2) AS services_amount,
  COALESCE(i.units_count, 0) AS inventory_units,
  COALESCE(i.inventory_amount, 0)::numeric(18,2) AS inventory_amount
FROM agencies a
LEFT JOIN ventas v ON v."idAgency"::text = a."idAgency"::text
LEFT JOIN servicios s ON s."idAgency"::text = a."idAgency"::text
LEFT JOIN mv_inventario_actual_agencia i ON i."idAgency"::text = a."idAgency"::text;
"""


MV_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_ventas_mensuales_agencia_pk ON mv_ventas_mensuales_agencia (\"idAgency\", month_start)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_servicios_mensuales_agencia_pk ON mv_servicios_mensuales_agencia (\"idAgency\", month_start)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_inventario_actual_agencia_pk ON mv_inventario_actual_agencia (\"idAgency\")",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_performance_agencia_pk ON mv_performance_agencia (\"idAgency\")",
)


REFRESH_MVS: tuple[str, ...] = (
    "REFRESH MATERIALIZED VIEW mv_ventas_mensuales_agencia",
    "REFRESH MATERIALIZED VIEW mv_servicios_mensuales_agencia",
    "REFRESH MATERIALIZED VIEW mv_inventario_actual_agencia",
    "REFRESH MATERIALIZED VIEW mv_performance_agencia",
)

REQUIRED_BASE_TABLES: tuple[str, ...] = (
    "agencies",
    "customers",
    "inventory",
    "orders",
    "invoices",
    "services",
)


def _run_many(cur: psycopg.Cursor, statements: tuple[str, ...], title: str) -> None:
    print(f"\n[{title}]")
    for stmt in statements:
        first_line = stmt.strip().splitlines()[0]
        try:
            cur.execute(stmt)
            print(f"- OK: {first_line[:120]}")
        except psycopg.Error as exc:
            print(f"- SKIP: {first_line[:90]} :: {exc.__class__.__name__}: {exc}")


def _execute_named(cur: psycopg.Cursor, sql: str, name: str) -> None:
    try:
        cur.execute(sql)
        print(f"- OK: {name}")
    except psycopg.Error as exc:
        print(f"- SKIP: {name} :: {exc.__class__.__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimiza DWH para consultas de LLM.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresca las vistas materializadas al final.",
    )
    args = parser.parse_args()

    raw = os.getenv("DWH_URL", "").strip()
    if not raw:
        print("Falta DWH_URL en el entorno.", file=sys.stderr)
        return 2

    pg_url = _sqlalchemy_to_psycopg_url(raw)
    with psycopg.connect(pg_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            )
            existing_tables = {r[0] for r in cur.fetchall()}
            missing = [t for t in REQUIRED_BASE_TABLES if t not in existing_tables]
            if missing:
                print(
                    "La base conectada no coincide con el DWH esperado para esta optimización.\n"
                    f"- Base actual: {db_name}\n"
                    f"- Tablas faltantes en public: {', '.join(missing)}\n"
                    "Verifica DWH_URL hacia el esquema de vgd_dwh_prod_migracion.",
                    file=sys.stderr,
                )
                return 3

            _run_many(cur, INDEXES, "Indices base")

            print("\n[Vistas semanticas]")
            if "customer_vehicle" in existing_tables:
                _execute_named(cur, CREATE_VIEW_VEHICLE_MASTER, "v_vehicle_master")
            else:
                _execute_named(cur, CREATE_VIEW_VEHICLE_MASTER_FALLBACK, "v_vehicle_master")

            if "customer_vehicle" in existing_tables:
                _execute_named(cur, CREATE_VIEW_CLIENTE_360, "v_cliente_360")
            else:
                _execute_named(cur, CREATE_VIEW_CLIENTE_360_FALLBACK, "v_cliente_360")

            if "comissions" in existing_tables:
                _execute_named(cur, CREATE_VIEW_DIM_SELLERS, "dim_sellers")
            else:
                _execute_named(cur, CREATE_VIEW_DIM_SELLERS_FALLBACK, "dim_sellers")
            _execute_named(cur, CREATE_VIEW_DIM_FECHA, "dim_fecha")

            print("\n[Vistas materializadas]")
            _execute_named(cur, CREATE_MV_VENTAS_MENSUALES, "mv_ventas_mensuales_agencia")
            _execute_named(cur, CREATE_MV_SERVICIOS_MENSUALES, "mv_servicios_mensuales_agencia")
            _execute_named(cur, CREATE_MV_INVENTARIO_ACTUAL, "mv_inventario_actual_agencia")
            _execute_named(cur, CREATE_MV_PERFORMANCE_AGENCIA, "mv_performance_agencia")

            _run_many(cur, MV_INDEXES, "Indices de MVs")

            if args.refresh:
                _run_many(cur, REFRESH_MVS, "Refresh MVs")

    print("\nListo. Optimización aplicada.")
    if not args.refresh:
        print("Tip: ejecuta con --refresh para materializar datos actuales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

