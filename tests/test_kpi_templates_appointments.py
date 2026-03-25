from __future__ import annotations

import unittest

from agente_dwh.kpi_templates import match_kpi_template


class TestKpiTemplatesAppointments(unittest.TestCase):
    def test_match_no_show_rate_template(self) -> None:
        result = match_kpi_template("¿Cuál es la tasa de no show semanal de los últimos 3 meses?")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "appointments_no_show_weekly")
        self.assertIn("service_appointments", result.sql)

    def test_match_cancelation_reasons_template(self) -> None:
        result = match_kpi_template("¿Cuáles son los motivos de cancelación más frecuentes en citas de servicio?")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "appointments_cancellations_by_reason")
        self.assertIn("cancellation_reason", result.sql)

    def test_match_conversion_by_workshop_template(self) -> None:
        result = match_kpi_template("¿Cuál es la conversión de citas programadas a completadas por taller?")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.name, "appointments_conversion_by_workshop")
        self.assertIn("appointment_status", result.sql)


if __name__ == "__main__":
    unittest.main()
