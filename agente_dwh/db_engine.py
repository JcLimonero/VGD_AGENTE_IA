"""Configuración estándar de SQLAlchemy Engine para el proyecto."""

from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class EnginePoolConfig:
    """Parámetros comunes del pool para runtime web/cli."""

    pool_pre_ping: bool = True
    pool_size: int = 8
    max_overflow: int = 16
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 1800

    @staticmethod
    def from_env() -> "EnginePoolConfig":
        pre_ping = os.getenv("DB_POOL_PRE_PING", "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        return EnginePoolConfig(
            pool_pre_ping=pre_ping,
            pool_size=max(1, _env_int("DB_POOL_SIZE", 8)),
            max_overflow=max(0, _env_int("DB_MAX_OVERFLOW", 16)),
            pool_timeout_seconds=max(1, _env_int("DB_POOL_TIMEOUT_SECONDS", 30)),
            pool_recycle_seconds=max(60, _env_int("DB_POOL_RECYCLE_SECONDS", 1800)),
        )


def create_dwh_engine(database_url: str, *, config: EnginePoolConfig | None = None) -> Engine:
    cfg = config or EnginePoolConfig.from_env()
    is_sqlite = database_url.lower().startswith("sqlite:")
    kwargs: dict[str, object] = {"pool_pre_ping": cfg.pool_pre_ping}
    if not is_sqlite:
        kwargs.update(
            {
                "pool_size": cfg.pool_size,
                "max_overflow": cfg.max_overflow,
                "pool_timeout": cfg.pool_timeout_seconds,
                "pool_recycle": cfg.pool_recycle_seconds,
            }
        )
    return create_engine(database_url, **kwargs)


def get_platform_db_engine() -> Engine:
    """Crea engine para la base de datos de plataforma usando PLATFORM_DB_URL."""
    from .config import Config
    config = Config.from_env()
    return create_dwh_engine(config.platform_db_url)
