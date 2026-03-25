from __future__ import annotations

import unittest

from agente_dwh.kpi_templates import match_kpi_template


class TestKpiTemplates(unittest.TestCase):
    def test_match_repurchase_template(self) -> None:
        result = match_kpi_template("¿Cuál es el tiempo promedio de recompra de mis clientes?")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "avg_repurchase_time")
        self.assertIn("sale_gaps", result.sql)

    def test_match_insurance_template(self) -> None:
        result = match_kpi_template("¿A qué clientes les puedo ofrecer un seguro hoy?")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "insurance_opportunities")
        self.assertIn("insurance_policies", result.sql)

    def test_no_match_for_generic_question(self) -> None:
        result = match_kpi_template("Top 10 clientes por ventas")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
