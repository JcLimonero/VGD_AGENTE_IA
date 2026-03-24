"""Paquete del agente IA para consultas de DWH."""

from .agent import DwhAgent, QueryResult
from .config import Config, ConfigError

__all__ = ["DwhAgent", "QueryResult", "Config", "ConfigError"]
