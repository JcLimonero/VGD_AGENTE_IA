#!/usr/bin/env python3
"""Aplica COMMENT ON TABLE/COLUMN en PostgreSQL para documentación y LLM.

Uso:
  export DWH_URL=postgresql+psycopg://user:pass@host:5432/tu_base
  python scripts/apply_vgd_table_comments.py
  python scripts/export_dwh_schema_hint.py   # actualiza schema_hint_dwh.txt + dwh_schema_catalog.json

Solo comenta tablas que existan en `public`. Idempotente.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psycopg
    from psycopg import sql as psql
except ImportError:
    print("Instala psycopg: pip install psycopg[binary]", file=sys.stderr)
    raise SystemExit(1) from None


def _sqlalchemy_to_psycopg_url(url: str) -> str:
    u = url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if u.startswith(prefix):
            return "postgresql://" + u.split("://", 1)[1]
    return u


# Descripciones de negocio en español (para humanos y LLM)
TABLE_COMMENTS: dict[str, str] = {
    "agencies": (
        "Catálogo maestro de agencias (concesionarios o sucursales). "
        "Clave de negocio visible: idAgency (varchar). Sirve para filtrar casi todos los hechos del DWH."
    ),
    "agencies_config": (
        "Configuración operativa e integración por agencia: DMS, matriz, citas, tokens, RFC de la razón, "
        "API keys. Complementa agencies; no sustituye el catálogo de nombres."
    ),
    "agencies_detail": (
        "Datos extendidos de la agencia: razón social, domicilio, mapas, teléfonos, WhatsApp por área "
        "(servicio, refacciones, ventas) y datos bancarios para cobro."
    ),
    "customers": (
        "Clientes del DMS por agencia. Clave natural compuesta: (idAgency, ndClientDMS). "
        "Persona física o moral; para morales el nombre comercial suele ir en bussines_name "
        "(name puede estar vacío). Incluye contacto, dirección y datos fiscales."
    ),
    "orders": (
        "Pedidos de unidades u órdenes de pedido en el DMS, ligados a cliente (idAgency, ndClientDMS) "
        "y agencia. Base para análisis de pipeline o volumen de pedidos."
    ),
    "inventory": (
        "Inventario de unidades (vehículos en stock o disponibles) por agencia: VIN, modelo, color, "
        "estatus, fechas y valores. Hecho principal para preguntas de stock."
    ),
    "invoices": (
        "Facturas registradas en el DWH por agencia: importes, fechas, cliente DMS, orden y datos de "
        "facturación. Sirve para ingresos facturados y conciliación de alto nivel."
    ),
    "services": (
        "Servicios de taller/recepción en el DMS (órdenes de servicio o líneas de servicio según origen). "
        "No es la tabla de citas del demo: usar columnas reales del esquema. Ligado a agencia."
    ),
    "services_by_vin": (
        "Hechos o resúmenes de servicio asociados al VIN (y agencia). Útil para historial de servicio "
        "por unidad sin pasar por otra tabla intermedia."
    ),
    "spares": (
        "Refacciones o piezas (catálogo/movimientos de spare parts en el DMS). Incluye existencias, "
        "precios y referencias; granularidad por part_number y agencia."
    ),
    "comissions": (
        "Comisiones de venta con detalle comercial: pedido, factura, vehículo (VIN), cliente DMS, "
        "asesor y montos. Tabla analítica típica para desempeño de ventas y entregas."
    ),
    "customer_vehicle": (
        "Relación cliente–vehículo: qué VIN/placa está asociado a qué cliente (idAgency, ndClientDMS). "
        "Puente entre clientes e inventario o historial de unidad."
    ),
    "last_customer_seller": (
        "Último vendedor o asesor de ventas asignado al cliente en el DMS (por agencia y ndClientDMS). "
        "Sirve para rotación comercial o seguimiento del ejecutivo actual."
    ),
}

# Comentarios en columnas frecuentes en joins (opcional pero ayuda al LLM)
COLUMN_COMMENTS: list[tuple[str, str, str]] = [
    ("agencies", "idAgency", "Identificador de agencia en el DMS (texto); FK en casi todas las tablas de hechos."),
    ("customers", "idAgency", "Agencia a la que pertenece el cliente; forma clave natural con ndClientDMS."),
    ("customers", "ndClientDMS", "ID del cliente en el DMS; único solo en combinación con idAgency."),
    ("customers", "name", "Nombre de persona física o contacto; puede ir vacío en persona moral."),
    ("customers", "bussines_name", "Razón social o nombre comercial (persona moral); usar para mostrar cliente PM."),
    ("orders", "idAgency", "Agencia del pedido; FK a agencies."),
    ("orders", "ndClientDMS", "Cliente DMS del pedido; unir a customers con idAgency."),
    ("inventory", "idAgency", "Agencia donde está la unidad en inventario."),
    ("inventory", "vin", "Número de identificación vehicular (único por unidad)."),
    ("comissions", "vin", "VIN del vehículo asociado a la comisión de venta."),
    ("comissions", "ndClientDMS", "Cliente DMS asociado a la operación de comisión."),
    ("customer_vehicle", "vin", "VIN del vehículo ligado al cliente."),
    ("invoices", "idAgency", "Agencia emisora o de registro de la factura."),
    ("services", "idAgency", "Agencia donde se registró el servicio."),
    ("services_by_vin", "vin", "VIN sobre el que se reporta el servicio."),
    ("spares", "idAgency", "Agencia dueña del inventario o catálogo de refacción."),
]


def main() -> int:
    raw = os.getenv("DWH_URL", "").strip()
    if not raw:
        print("Falta DWH_URL en el entorno.", file=sys.stderr)
        return 2
    pg_url = _sqlalchemy_to_psycopg_url(raw)

    with psycopg.connect(pg_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            existing = {r[0] for r in cur.fetchall()}

        missing = [t for t in TABLE_COMMENTS if t not in existing]
        if missing:
            print("Advertencia: tablas no encontradas (omitidas):", ", ".join(missing), file=sys.stderr)

        with conn.cursor() as cur:
            for table, comment in TABLE_COMMENTS.items():
                if table not in existing:
                    continue
                stmt = psql.SQL("COMMENT ON TABLE {} IS {}").format(
                    psql.Identifier(table),
                    psql.Literal(comment),
                )
                cur.execute(stmt)
                print(f"COMMENT TABLE {table}")

            for table, column, comment in COLUMN_COMMENTS:
                if table not in existing:
                    continue
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                    """,
                    (table, column),
                )
                if cur.fetchone():
                    cstmt = psql.SQL("COMMENT ON COLUMN {}.{} IS {}").format(
                        psql.Identifier(table),
                        psql.Identifier(column),
                        psql.Literal(comment),
                    )
                    cur.execute(cstmt)
                    print(f"COMMENT COLUMN {table}.{column}")

    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
