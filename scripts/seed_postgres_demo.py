#!/usr/bin/env python3
"""
Crea en PostgreSQL las tablas y datos de prueba del demo (sin SQLite).

Uso:
  export DWH_URL='postgresql+psycopg://postgres:root@127.0.0.1:5432/postgres'
  python scripts/seed_postgres_demo.py

  python scripts/seed_postgres_demo.py --dsn 'postgresql+psycopg://...'
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agente_dwh.bootstrap_env import load_dotenv_from_project_root  # noqa: E402
from agente_dwh.demo_data import ensure_demo_postgres  # noqa: E402


def main() -> None:
    load_dotenv_from_project_root()
    parser = argparse.ArgumentParser(description="Sembrar PostgreSQL con datos demo VGD.")
    parser.add_argument(
        "--dsn",
        default="",
        help="URL postgresql+psycopg://... (por defecto DWH_URL)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recrear tablas aunque el esquema ya exista.",
    )
    args = parser.parse_args()

    dsn = (args.dsn or os.getenv("DWH_URL", "")).strip()
    if not dsn or "postgresql" not in dsn.lower():
        print("Falta DWH_URL o --dsn con postgresql+psycopg://...", file=sys.stderr)
        sys.exit(2)

    counts = ensure_demo_postgres(dsn, force_rebuild=args.force)
    print("Tablas en PostgreSQL:")
    for k, v in counts.items():
        print(f"  {k}: {v} filas")


if __name__ == "__main__":
    main()
