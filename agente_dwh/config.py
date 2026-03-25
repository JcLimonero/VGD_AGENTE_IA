"""Configuracion del agente via variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import unquote

from sqlalchemy.engine.url import make_url


class ConfigError(ValueError):
    """Error de configuracion del entorno."""


# Única base DWH soportada en producción (nombre en la URL PostgreSQL).
REQUIRED_DWH_DATABASE_NAME = "vgd_dwh_prod_migracion"


def normalize_dwh_url_string(url: str) -> str:
    """Quita espacios y comillas típicas de .env mal copiado."""
    u = (url or "").strip()
    if len(u) >= 2 and u[0] == u[-1] and u[0] in "\"'":
        u = u[1:-1].strip()
    return u


def _db_name_check_skipped() -> bool:
    v = os.getenv("AGENTE_DWH_SKIP_DB_NAME_CHECK", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def postgres_database_name_from_url(url: str) -> str | None:
    """Devuelve el nombre de la base en una URL PostgreSQL, o None si no aplica."""
    u = normalize_dwh_url_string(url)
    if not u:
        return None
    lower = u.lower()
    if not lower.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
    ):
        return None
    try:
        parsed = make_url(u)
    except Exception:
        return None
    db = parsed.database
    if not db:
        return None
    return unquote(str(db))


def prepare_dwh_url(url: str) -> str:
    """
    Si la URL es PostgreSQL y la base es la por defecto «postgres» o falta en la URL,
    sustituye por REQUIRED_DWH_DATABASE_NAME (caso típico: usuario postgres y plantilla .../postgres).
    """
    u = normalize_dwh_url_string(url)
    if not u:
        return u
    lower = u.lower()
    if not lower.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
    ):
        return u
    try:
        parsed = make_url(u)
    except Exception:
        return u
    db = parsed.database
    if db is None or (isinstance(db, str) and db.lower() == "postgres"):
        return parsed.set(database=REQUIRED_DWH_DATABASE_NAME).render_as_string(
            hide_password=False
        )
    return u


def effective_dwh_url(url: str) -> str:
    """URL lista para conectar: aplica prepare_dwh_url salvo que AGENTE_DWH_SKIP_DB_NAME_CHECK esté activo."""
    u = normalize_dwh_url_string(url)
    if not u:
        return u
    if _db_name_check_skipped():
        return u
    return prepare_dwh_url(u)


def validate_dwh_url_targets_vgd_prod(dwh_url: str) -> None:
    """
    Comprueba que DWH_URL sea PostgreSQL y el nombre de base sea vgd_dwh_prod_migracion
    (tras corregir automáticamente «postgres» o BD omitida).

    Para entornos excepcionales (tests, réplicas con otro nombre): AGENTE_DWH_SKIP_DB_NAME_CHECK=1.
    """
    if _db_name_check_skipped():
        return
    prepared = effective_dwh_url(dwh_url)
    name = postgres_database_name_from_url(prepared)
    if name is None:
        raise ConfigError(
            "DWH_URL debe ser una URL PostgreSQL (postgresql:// o postgresql+psycopg://...) "
            f"con base de datos «{REQUIRED_DWH_DATABASE_NAME}» "
            "(o sin nombre de base / con «postgres» para sustitución automática)."
        )
    if name.lower() != REQUIRED_DWH_DATABASE_NAME.lower():
        raise ConfigError(
            f"DWH_URL apunta a la base «{name}»; este proyecto solo usa «{REQUIRED_DWH_DATABASE_NAME}». "
            "Corrige la URL o, solo si es imprescindible, define AGENTE_DWH_SKIP_DB_NAME_CHECK=1."
        )


@dataclass(frozen=True)
class Config:
    """Parametros de ejecucion del agente."""

    dwh_url: str
    llm_endpoint: str
    llm_model: str
    max_rows: int
    llm_timeout_seconds: int
    llm_temperature: float = 0.2
    cache_ttl_seconds: int = 120
    cache_max_entries: int = 500
    schema_hint_file: str = ""

    @staticmethod
    def from_env() -> "Config":
        """Carga y valida configuracion minima."""
        dwh_url = normalize_dwh_url_string(os.getenv("DWH_URL", ""))
        if not dwh_url:
            raise ConfigError(
                f"Falta DWH_URL. Ejemplo: postgresql+psycopg://usuario:pass@host:5432/{REQUIRED_DWH_DATABASE_NAME}"
            )
        validate_dwh_url_targets_vgd_prod(dwh_url)
        dwh_url = effective_dwh_url(dwh_url)

        llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:11434").strip()
        llm_model = os.getenv("LLM_MODEL", "qwen2.5-coder:7b").strip()
        max_rows_raw = os.getenv("MAX_ROWS", "200").strip()
        llm_temp_raw = os.getenv("LLM_TEMPERATURE", "0.2").strip()
        timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "180").strip()
        cache_ttl_raw = os.getenv("CACHE_TTL_SECONDS", "120").strip()
        cache_max_entries_raw = os.getenv("CACHE_MAX_ENTRIES", "500").strip()
        schema_hint_file = os.getenv("SCHEMA_HINT_FILE", "").strip()

        try:
            max_rows = int(max_rows_raw)
        except ValueError as exc:
            raise ConfigError("MAX_ROWS debe ser un entero valido.") from exc
        if max_rows <= 0:
            raise ConfigError("MAX_ROWS debe ser mayor que 0.")

        try:
            llm_timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise ConfigError("LLM_TIMEOUT_SECONDS debe ser un entero valido.") from exc
        if llm_timeout_seconds <= 0:
            raise ConfigError("LLM_TIMEOUT_SECONDS debe ser mayor que 0.")

        try:
            llm_temperature = float(llm_temp_raw)
        except ValueError as exc:
            raise ConfigError("LLM_TEMPERATURE debe ser un número decimal válido.") from exc
        if not 0.0 <= llm_temperature <= 2.0:
            raise ConfigError("LLM_TEMPERATURE debe estar entre 0.0 y 2.0.")

        try:
            cache_ttl_seconds = int(cache_ttl_raw)
        except ValueError as exc:
            raise ConfigError("CACHE_TTL_SECONDS debe ser un entero valido.") from exc
        if cache_ttl_seconds < 0:
            raise ConfigError("CACHE_TTL_SECONDS debe ser mayor o igual que 0.")

        try:
            cache_max_entries = int(cache_max_entries_raw)
        except ValueError as exc:
            raise ConfigError("CACHE_MAX_ENTRIES debe ser un entero valido.") from exc
        if cache_max_entries <= 0:
            raise ConfigError("CACHE_MAX_ENTRIES debe ser mayor que 0.")

        return Config(
            dwh_url=dwh_url,
            llm_endpoint=llm_endpoint,
            llm_model=llm_model,
            max_rows=max_rows,
            llm_timeout_seconds=llm_timeout_seconds,
            llm_temperature=llm_temperature,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_max_entries=cache_max_entries,
            schema_hint_file=schema_hint_file,
        )


def load_settings() -> Config:
    """Alias de compatibilidad para cargar configuracion."""
    return Config.from_env()
