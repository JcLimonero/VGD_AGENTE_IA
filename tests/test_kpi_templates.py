from __future__ import annotations

import unittest

from agente_dwh.kpi_templates import DeterministicQuery, match_kpi_template


class TestKpiTemplates(unittest.TestCase):
    """Plantillas KPI desactivadas hasta nueva definición."""

    def test_match_always_none(self) -> None:
        samples = [
            "¿Cuál es el tiempo promedio de recompra de mis clientes?",
            "¿A qué clientes les puedo ofrecer un seguro hoy?",
            "Top 10 clientes por ventas",
            "¿Cuál es la tasa de no show semanal de los últimos 3 meses?",
            "¿Cuál es la conversión de citas programadas a completadas por taller?",
            "",
        ]
        for q in samples:
            self.assertIsNone(match_kpi_template(q), msg=repr(q))

    def test_deterministic_query_dataclass(self) -> None:
        q = DeterministicQuery(name="x", sql="SELECT 1", explanation="test")
        self.assertEqual(q.name, "x")


if __name__ == "__main__":
    unittest.main()
