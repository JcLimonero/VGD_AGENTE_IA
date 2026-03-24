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
        llm_model = os.getenv("LLM_MODEL", "qwen2.5:14b").strip()
        max_rows_raw = os.getenv("MAX_ROWS", "200").strip()
        timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "180").strip()
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

        return Config(
            dwh_url=dwh_url,
            llm_endpoint=llm_endpoint,
            llm_model=llm_model,
            max_rows=max_rows,
            llm_timeout_seconds=llm_timeout_seconds,
            schema_hint_file=schema_hint_file,
        )


def load_settings() -> Config:
    """Alias de compatibilidad para cargar configuracion."""
    return Config.from_env()
