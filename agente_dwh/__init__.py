"""Paquete del agente IA para consultas de DWH."""

from .agent import DwhAgent, QueryResult
from .config import Config, ConfigError
from .kpi_templates import DeterministicQuery, match_kpi_template

__all__ = [
    "DwhAgent",
    "QueryResult",
    "Config",
    "ConfigError",
    "DeterministicQuery",
    "match_kpi_template",
]
