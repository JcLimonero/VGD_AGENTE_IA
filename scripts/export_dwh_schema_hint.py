#!/usr/bin/env python3
"""Exporta esquema `public` (hint + JSON) desde PostgreSQL para el LLM.

Lee DWH_URL. Salidas por defecto en la raíz del repo:
  - schema_hint_dwh.txt
  - dwh_schema_catalog.json

Opcional:
  DWH_SCHEMA_HINT_OUT=/ruta/schema_hint_dwh.txt
  DWH_SCHEMA_JSON_OUT=/ruta/dwh_schema_catalog.json

Uso:
  export DWH_URL=postgresql+psycopg://user:pass@host:5432/mi_base
  python scripts/export_dwh_schema_hint.py
"""

from __future__ import annotations

import json
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

# Tablas habituales del demo del repo; se mencionan en el preámbulo solo si NO están en esta BD.
_COMMON_DEMO_TABLES = (
    "sales",
    "vehicles",
    "service_appointments",
    "insurance_policies",
    "mv_sales_monthly",
)


def _sqlalchemy_to_psycopg_url(url: str) -> str:
    u = url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if u.startswith(prefix):
            return "postgresql://" + u.split("://", 1)[1]
    return u


def pg_type(c: dict) -> str:
    t = c["data_type"]
    if c.get("character_maximum_length"):
        return f"{t}({c['character_maximum_length']})"
    p, s = c.get("numeric_precision"), c.get("numeric_scale")
    if p is not None:
        return f"{t}({p},{s or 0})"
    return t


def build_preamble(db_name: str, tables: list[str], meta: dict) -> str:
    """Instrucciones para el LLM según lo que realmente existe en `public`."""
    tset = set(tables)
    missing_demo = [x for x in _COMMON_DEMO_TABLES if x not in tset]
    lines = [
        f"DWH PostgreSQL — esquema `public`, base de datos `{db_name}`.",
        "",
        "=== Instrucciones para el modelo (obligatorio) ===",
        f"- Usa ÚNICAMENTE las tablas y columnas listadas más abajo. En `public` hay {len(tables)} tablas.",
        "- No inventes tablas, vistas ni columnas que no aparezcan en este documento.",
    ]
    if missing_demo:
        lines.append(
            "- En esta instancia NO existen en `public` (no las uses en SQL): "
            + ", ".join(missing_demo)
            + "."
        )
    demo_map_bits: list[str] = []
    if "sales" not in tset and "invoices" in tset:
        demo_map_bits.append(
            "`sales` del demo → usa `invoices` para ventas facturadas (y `orders` o `comissions` si la pregunta es pedidos o comisiones)"
        )
    if "vehicles" not in tset and "inventory" in tset:
        demo_map_bits.append(
            "`vehicles` del demo → usa `inventory` para unidades en stock (VIN y datos de unidad en columnas listadas)"
        )
    if demo_map_bits:
        lines.append("- Equivalencias frente al dataset demo del repo: " + "; ".join(demo_map_bits) + ".")
    if "agencies" in tset:
        lines.append(
            '- Catálogo de agencias / sucursales: tabla `agencies` (p. ej. SELECT COUNT(*) AS n FROM agencies). '
            "No confundas con conteos desde hechos salvo que el usuario pida «agencias con pedidos», etc."
        )
    cust = meta.get("tables", {}).get("customers")
    if cust:
        cnames = {c["name"] for c in cust.get("columns", [])}
        if "idAgency" in cnames and "ndClientDMS" in cnames:
            lines.append(
                '- Cliente DMS: par ("idAgency", "ndClientDMS"). JOIN típico:\n'
                '    ON t."idAgency" = c."idAgency" AND t."ndClientDMS" = c."ndClientDMS"'
            )
        if "state" in cnames:
            lines.append(
                "- «Clientes por estado» (geográfico): usa `customers.state` y `FROM customers` "
                "(no mezcles con tablas inexistentes ni GROUP BY de columnas sin JOIN válido)."
            )
        if "name" in cnames or "bussines_name" in cnames:
            lines.append(
                "- Personas morales: revisa `name` y `bussines_name` en customers según columnas listadas."
            )
    if "agencies" in tset:
        lines.append('- Agencia en hechos: JOIN a agencies ON t."idAgency" = a."idAgency".')
    vin_tables = [t for t in ("comissions", "inventory", "customer_vehicle", "services_by_vin") if t in tset]
    if vin_tables:
        lines.append(
            "- Preguntas por unidad / VIN: columnas `vin` suelen estar en: "
            + ", ".join(vin_tables)
            + " (ver listado de columnas)."
        )
    if "services" in tset:
        lines.append(
            "- La tabla `services` es la de este DWH; no asumas otras tablas de taller salvo que estén listadas arriba."
        )
    lines.append(
        '- Identificadores en camelCase requieren comillas dobles en PostgreSQL (p. ej. "idAgency", "ndClientDMS").'
    )
    return "\n".join(lines)


def main() -> int:
    raw = os.getenv("DWH_URL", "").strip()
    if not raw:
        print("Falta DWH_URL en el entorno.", file=sys.stderr)
        return 2
    pg_url = _sqlalchemy_to_psycopg_url(raw)

    hint_path = Path(os.getenv("DWH_SCHEMA_HINT_OUT", str(ROOT / "schema_hint_dwh.txt")))
    json_path = Path(os.getenv("DWH_SCHEMA_JSON_OUT", str(ROOT / "dwh_schema_catalog.json")))

    with psycopg.connect(pg_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]

            cur.execute("""
                SELECT conrelid::regclass::text AS src, pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                WHERE c.contype = 'f'
                  AND c.connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                ORDER BY 1, 2
            """)
            fk_rows = cur.fetchall()

            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE'
                ORDER BY table_name
            """)
            tables = [r[0] for r in cur.fetchall()]

            meta: dict = {
                "database": db_name,
                "schema": "public",
                "exported_for_llm": True,
                "tables": {},
            }

            for t in tables:
                cur.execute("""
                    SELECT pg_catalog.obj_description(c.oid, 'pg_class')
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind = 'r'
                """, (t,))
                table_comment_row = cur.fetchone()
                table_comment = (table_comment_row[0] or "").strip() or None

                cur.execute("""
                    SELECT a.attname AS col, pg_catalog.col_description(a.attrelid, a.attnum) AS descr
                    FROM pg_catalog.pg_attribute a
                    JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = %s
                      AND a.attnum > 0 AND NOT a.attisdropped
                """, (t,))
                col_comments = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}

                cur.execute("""
                    SELECT column_name, data_type, character_maximum_length,
                           numeric_precision, numeric_scale, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position
                """, (t,))
                cols = []
                for r in cur.fetchall():
                    cname = r[0]
                    cd = col_comments.get(cname, "")
                    entry = {
                        "name": cname,
                        "data_type": r[1],
                        "character_maximum_length": r[2],
                        "numeric_precision": r[3],
                        "numeric_scale": r[4],
                        "is_nullable": r[5],
                    }
                    if cd:
                        entry["comment"] = cd
                    cols.append(entry)
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                n = cur.fetchone()[0]
                meta["tables"][t] = {
                    "row_count_estimate": n,
                    "table_comment": table_comment,
                    "columns": cols,
                }

            cur.execute("""
                SELECT conrelid::regclass::text AS src, pg_get_constraintdef(c.oid) AS def, c.conname
                FROM pg_constraint c
                WHERE c.contype = 'f'
                  AND c.connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                ORDER BY 1, 3
            """)
            meta["foreign_keys"] = [
                {"from_table": r[0].replace("public.", ""), "definition": r[1], "name": r[2]}
                for r in cur.fetchall()
            ]

    preamble = build_preamble(db_name, tables, meta)
    lines = [
        preamble,
        "",
        f"(Generado desde `{db_name}` / `public`.)",
        "",
        "=== Relaciones (FK) ===",
    ]
    for src, defn in fk_rows:
        lines.append(f"- {src}: {defn}")
    lines.append("")
    lines.append("=== Tablas y columnas ===")
    for t in tables:
        tc = meta["tables"][t]
        lines.append(f"\n{t} (~{tc['row_count_estimate']} filas)")
        tc_desc = tc.get("table_comment")
        if tc_desc:
            lines.append(f"  » {tc_desc}")
        for c in tc["columns"]:
            nn = "NULL" if c["is_nullable"] == "YES" else "NOT NULL"
            line = f'  - "{c["name"]}" {pg_type(c)} {nn}'
            cdesc = c.get("comment")
            if cdesc:
                line += f" — {cdesc}"
            lines.append(line)

    hint_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"OK: {hint_path} ({hint_path.stat().st_size} bytes)")
    print(f"OK: {json_path} ({json_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
