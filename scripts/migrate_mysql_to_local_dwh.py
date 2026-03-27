#!/usr/bin/env python3
"""
Migra tablas desde MySQL (vgd_dwh_prod) a PostgreSQL local en la base `dwh`.

Variables de entorno (o .env en la raíz del repo):

  Origen MySQL (una de dos formas):
    MYSQL_SOURCE_URL=mysql+pymysql://user:pass@host:3306/vgd_dwh_prod
    o bien:
    MYSQL_HOST, MYSQL_PORT (default 3306), MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

  Destino PostgreSQL:
    LOCAL_PG_ADMIN_URL — URL SQLAlchemy al servidor, base `postgres`, para CREATE DATABASE.
      Por defecto se deriva de DWH_URL sustituyendo el nombre de BD por `postgres`.

Tablas migradas: customers, agencies, invoices, orders, services, inventory, customer_vehicle.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

# Raíz del repo (scripts/ -> padre)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.types import Date

DEFAULT_TABLES = (
    "customers",
    "agencies",
    "invoices",
    "orders",
    "services",
    "inventory",
    "customer_vehicle",
)


def _load_env() -> None:
    if load_dotenv:
        load_dotenv(_REPO_ROOT / ".env")


def _mysql_engine_from_env() -> Engine:
    url_s = (os.getenv("MYSQL_SOURCE_URL") or "").strip()
    if url_s:
        if not url_s.startswith("mysql"):
            raise SystemExit(
                "MYSQL_SOURCE_URL debe empezar por mysql+pymysql:// o mysql+mysqldb://"
            )
        return create_engine(url_s, pool_pre_ping=True)

    host = os.getenv("MYSQL_HOST", "").strip()
    user = os.getenv("MYSQL_USER", "").strip()
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "").strip()
    port = os.getenv("MYSQL_PORT", "3306").strip()
    if not all([host, user, database]):
        raise SystemExit(
            "Define MYSQL_SOURCE_URL o MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE"
        )
    safe_user = quote_plus(user)
    safe_pass = quote_plus(password)
    url = f"mysql+pymysql://{safe_user}:{safe_pass}@{host}:{port}/{database}"
    return create_engine(url, pool_pre_ping=True)


def _admin_pg_url() -> URL:
    """URL al servidor PostgreSQL, base `postgres` (para CREATE DATABASE).

    No usar str(URL) para pasar credenciales: SQLAlchemy puede enmascarar la
    contraseña como el literal «***» y romper la conexión.
    """
    explicit = (os.getenv("LOCAL_PG_ADMIN_URL") or "").strip()
    if explicit:
        u = make_url(explicit)
    else:
        dwh = (os.getenv("DWH_URL") or "").strip()
        if not dwh:
            raise SystemExit(
                "Define LOCAL_PG_ADMIN_URL (postgresql+psycopg://.../postgres) o DWH_URL."
            )
        u = make_url(dwh)
    if (u.database or "").lower() != "postgres":
        u = u.set(database="postgres")
    return u


def ensure_database(admin_u: URL, dbname: str) -> None:
    """Crea la base `dbname` si no existe (conexión a postgres)."""
    u = admin_u
    if (u.database or "").lower() != "postgres":
        u = u.set(database="postgres")
    kwargs: dict = {
        "host": u.host or "127.0.0.1",
        "port": int(u.port or 5432),
        "user": u.username,
        "dbname": "postgres",
        "autocommit": True,
    }
    if u.password is not None:
        kwargs["password"] = u.password
    with psycopg.connect(**kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (dbname,),
            )
            if cur.fetchone():
                print(f"Base '{dbname}' ya existe.")
                return
            # Identificador simple: solo letras/números/guiones bajos
            if not dbname.replace("_", "").isalnum():
                raise SystemExit(f"Nombre de base no seguro: {dbname!r}")
            cur.execute(f'CREATE DATABASE "{dbname}"')
            print(f"Base '{dbname}' creada.")


def migrate_table(
    mysql_engine: Engine,
    pg_engine: Engine,
    table: str,
    chunksize: int,
) -> int:
    q = f"SELECT * FROM `{table}`"
    total = 0
    first = True
    for chunk in pd.read_sql_query(text(q), mysql_engine, chunksize=chunksize):
        n = len(chunk)
        if n == 0:
            continue
        # customer_vehicle en origen puede traer fechas como texto/mixto.
        # Normalizamos para que psycopg las envíe como DATE y no VARCHAR.
        dtype_map: dict[str, Date] = {}
        if table == "customer_vehicle":
            for col in ("insurance_expiration_date", "timestamp_insurance_info"):
                if col in chunk.columns:
                    chunk[col] = pd.to_datetime(chunk[col], errors="coerce").dt.date
                    dtype_map[col] = Date()
        # PostgreSQL limita ~65535 parámetros por consulta; multi-row INSERT usa cols×filas.
        ncol = max(len(chunk.columns), 1)
        pg_batch = max(1, min(50_000 // ncol, 2000))
        chunk.to_sql(
            table,
            pg_engine,
            if_exists="replace" if first else "append",
            index=False,
            method="multi",
            chunksize=pg_batch,
            dtype=dtype_map or None,
        )
        total += n
        first = False
    if first:
        # Sin filas: crear estructura con LIMIT 0
        empty = pd.read_sql_query(text(f"SELECT * FROM `{table}` LIMIT 0"), mysql_engine)
        empty.to_sql(table, pg_engine, if_exists="replace", index=False)
        print(f"  {table}: 0 filas.")
        return 0
    print(f"  {table}: {total} filas.")
    return total


def main() -> int:
    _load_env()
    p = argparse.ArgumentParser(description="MySQL -> PostgreSQL local (bd dwh)")
    p.add_argument(
        "--database",
        default=os.getenv("TARGET_PG_DATABASE", "dwh"),
        help="Nombre de la base PostgreSQL destino (default: dwh)",
    )
    p.add_argument(
        "--chunksize",
        type=int,
        default=10_000,
        help="Filas por lote al leer desde MySQL",
    )
    p.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="Lista de tablas separada por comas",
    )
    args = p.parse_args()
    dbname = args.database.strip()
    tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    print("Conectando a MySQL...")
    mysql_engine = _mysql_engine_from_env()

    admin_u = _admin_pg_url()
    print(f"Asegurando base PostgreSQL '{dbname}'...")
    ensure_database(admin_u, dbname)

    target_u = admin_u.set(database=dbname)
    print(f"Destino: {target_u.render_as_string(hide_password=True)}")
    pg_engine = create_engine(target_u, pool_pre_ping=True)

    print("Migrando tablas...")
    grand = 0
    for t in tables:
        try:
            grand += migrate_table(mysql_engine, pg_engine, t, args.chunksize)
        except Exception as exc:
            print(f"ERROR en tabla {t}: {exc}", file=sys.stderr)
            raise
    print(f"Listo. Total filas migradas (suma por tabla): {grand}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
