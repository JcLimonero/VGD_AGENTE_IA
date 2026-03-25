"""Configuracion del agente via variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(ValueError):
    """Error de configuracion del entorno."""


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
        dwh_url = os.getenv("DWH_URL", "").strip()
        if not dwh_url:
            raise ConfigError(
                "Falta DWH_URL. Ejemplo: postgresql+psycopg://usuario:pass@host:5432/base"
            )

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
