#!/usr/bin/env python3
"""Crea vistas homologadas (snake_case) para el DWH.

Estrategia segura:
- No renombra columnas físicas ni rompe objetos existentes.
- Genera `h_<tabla>` como capa semántica para NL->SQL.
- Homologa nombres a snake_case y estandariza `id_agency` como text.

Uso:
  export DWH_URL='postgresql+psycopg://user:pass@host:5432/dwh'
  python scripts/homologate_dwh_column_names.py
"""

from __future__ import annotations

import os
import re
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

TARGET_TABLES: tuple[str, ...] = (
    "agencies",
    "customers",
    "customer_vehicle",
    "inventory",
    "orders",
    "invoices",
    "services",
)


def _sqlalchemy_to_psycopg_url(url: str) -> str:
    u = url.strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if u.startswith(prefix):
            return "postgresql://" + u.split("://", 1)[1]
    return u


def _to_snake_case(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s or "col"


def _qident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _unique_aliases(columns: list[str]) -> list[tuple[str, str]]:
    used: dict[str, int] = {}
    out: list[tuple[str, str]] = []
    for c in columns:
        base = _to_snake_case(c)
        n = used.get(base, 0)
        alias = base if n == 0 else f"{base}_{n + 1}"
        used[base] = n + 1
        out.append((c, alias))
    return out


def _build_select_expr(source_col: str, alias: str) -> str:
    qcol = _qident(source_col)
    # Homologar tipo entre tablas (algunas usan bigint y otras text).
    if alias == "id_agency":
        return f"{qcol}::text AS {_qident(alias)}"
    return f"{qcol} AS {_qident(alias)}"


def main() -> int:
    raw = os.getenv("DWH_URL", "").strip()
    if not raw:
        print("Falta DWH_URL en el entorno.", file=sys.stderr)
        return 2
    pg_url = _sqlalchemy_to_psycopg_url(raw)

    with psycopg.connect(pg_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            )
            existing = {r[0] for r in cur.fetchall()}

            for table in TARGET_TABLES:
                if table not in existing:
                    print(f"- SKIP: {table} (no existe en public)")
                    continue

                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                cols = [r[0] for r in cur.fetchall()]
                pairs = _unique_aliases(cols)
                select_list = ",\n  ".join(_build_select_expr(src, alias) for src, alias in pairs)
                view_name = f"h_{table}"

                sql = f"""
CREATE OR REPLACE VIEW {_qident(view_name)} AS
SELECT
  {select_list}
FROM {_qident(table)};
"""
                cur.execute(sql)
                print(f"- OK: {view_name} ({len(cols)} columnas)")

    print("\nListo. Vistas homologadas creadas/actualizadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

