from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeterministicQuery:
    """Reservado para plantillas KPI determinísticas (por definir)."""

    name: str
    sql: str
    explanation: str


def match_kpi_template(question: str) -> DeterministicQuery | None:
    """
    Plantillas KPI desactivadas: todas las preguntas pasan por el LLM.
    Volver a implementar aquí cuando se definan los KPI fijos.
    """
    return None
