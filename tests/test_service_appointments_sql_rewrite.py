from __future__ import annotations

import os
import unittest

from sqlalchemy import create_engine

from agente_dwh.dwh import DwhClient

_SQLITE = create_engine("sqlite://")

_PG_DSN = (os.getenv("TEST_PG_DSN") or os.getenv("DWH_URL") or "").strip()
_HAS_PG = _PG_DSN.lower().startswith("postgresql")


class ServiceAppointmentsRewriteLocalTests(unittest.TestCase):
    """Reescrituras sin PostgreSQL (SQLite en memoria)."""

    def _normalize(self, sql: str) -> str:
        return DwhClient(engine=_SQLITE)._normalize_sql_for_dialect(sql)  # noqa: SLF001

    # --- service_date con alias de tabla ---

    def test_alias_service_date_to_appointment_date(self) -> None:
        sql = (
            "SELECT v.vin, v.brand, v.model, sa.service_date "
            "FROM service_appointments sa JOIN vehicles v ON sa.vehicle_id = v.id "
            "WHERE sa.appointment_status = 'completada' "
            "ORDER BY sa.service_date DESC LIMIT 1"
        )
        result = self._normalize(sql)
        self.assertIn("appointment_date", result.lower())
        self.assertNotIn("service_date", result.lower())

    # --- service_date SIN prefijo, solo service_appointments ---

    def test_unprefixed_service_date_only_appointments(self) -> None:
        sql = (
            "SELECT service_date, service_type "
            "FROM service_appointments "
            "WHERE appointment_status = 'completada'"
        )
        result = self._normalize(sql)
        self.assertIn("appointment_date", result.lower())
        self.assertNotIn("service_date", result.lower())

    # --- service_date SIN prefijo NO se toca si services está en el query ---

    def test_unprefixed_service_date_preserved_when_services_present(self) -> None:
        sql = (
            "SELECT service_date, service_type "
            "FROM services "
            "JOIN service_appointments ON services.customer_id = service_appointments.customer_id"
        )
        result = self._normalize(sql)
        self.assertIn("service_date", result.lower())

    # --- JOIN services + service_appointments con aliases distintos ---

    def test_join_services_and_appointments_different_aliases(self) -> None:
        sql = (
            "SELECT s.service_date, sa.service_date "
            "FROM services s "
            "JOIN service_appointments sa ON sa.vehicle_id = s.vehicle_id"
        )
        result = self._normalize(sql)
        self.assertIn("s.service_date", result)
        self.assertIn("sa.appointment_date", result)
        self.assertNotIn("sa.service_date", result)

    # --- appointment_date ya correcto NO se rompe ---

    def test_already_correct_appointment_date_unchanged(self) -> None:
        sql = (
            "SELECT sa.appointment_date, sa.appointment_status "
            "FROM service_appointments sa "
            "WHERE sa.appointment_status = 'completada'"
        )
        result = self._normalize(sql)
        self.assertIn("sa.appointment_date", result)
        self.assertIn("sa.appointment_status", result)
        self.assertEqual(result.lower().count("appointment_date"), 1)

    # --- appointment_status ya correcto NO se duplica ---

    def test_already_correct_appointment_status_not_doubled(self) -> None:
        sql = (
            "SELECT appointment_status, COUNT(*) "
            "FROM service_appointments "
            "GROUP BY appointment_status"
        )
        result = self._normalize(sql)
        self.assertNotIn("appointment_appointment_status", result.lower())

    # --- status con prefijo de tabla completo ---

    def test_full_table_prefix_status(self) -> None:
        sql = (
            "SELECT service_appointments.status "
            "FROM service_appointments"
        )
        result = self._normalize(sql)
        self.assertIn("service_appointments.appointment_status", result)

    # --- service_date con nombre completo de tabla ---

    def test_full_table_prefix_service_date(self) -> None:
        sql = (
            "SELECT service_appointments.service_date "
            "FROM service_appointments"
        )
        result = self._normalize(sql)
        self.assertIn("service_appointments.appointment_date", result)

    # --- advisor con alias ---

    def test_alias_advisor_to_workshop(self) -> None:
        sql = (
            "SELECT sa.advisor, COUNT(*) "
            "FROM service_appointments sa "
            "GROUP BY sa.advisor"
        )
        result = self._normalize(sql)
        self.assertIn("sa.workshop", result)
        self.assertNotIn("advisor", result.lower())

    # --- No tocar tablas que no son service_appointments ---

    def test_services_table_unaffected(self) -> None:
        sql = (
            "SELECT s.service_date, s.status, s.workshop "
            "FROM services s"
        )
        result = self._normalize(sql)
        self.assertIn("s.service_date", result)
        self.assertIn("s.status", result)
        self.assertIn("s.workshop", result)

    # --- AS explícito en alias ---

    def test_as_keyword_in_alias(self) -> None:
        sql = (
            "SELECT sa.service_date, sa.status "
            "FROM service_appointments AS sa "
            "WHERE sa.status = 'programada'"
        )
        result = self._normalize(sql)
        self.assertIn("sa.appointment_date", result)
        self.assertIn("sa.appointment_status", result)
        self.assertNotIn("sa.service_date", result)
        self.assertNotIn("sa.status", result.split("appointment_status")[0].split("sa.")[-1] if "sa.status" in result else "")


@unittest.skipUnless(_HAS_PG, "definir TEST_PG_DSN o DWH_URL (postgresql+psycopg://...)")
class ServiceAppointmentsRewriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._engine = create_engine(_PG_DSN)

    def test_rewrites_status_to_appointment_status_for_service_appointments(self) -> None:
        client = DwhClient(engine=self._engine)
        sql = (
            "SELECT workshop, COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'completada' THEN 1 ELSE 0 END) AS completed "
            "FROM service_appointments WHERE status IN ('programada', 'completada') "
            "GROUP BY workshop"
        )
        normalized = client._normalize_sql_for_dialect(sql)  # noqa: SLF001
        self.assertIn("appointment_status", normalized)
        self.assertNotIn(" status ", normalized.lower())

    def test_rewrites_advisor_to_workshop(self) -> None:
        client = DwhClient(engine=self._engine)
        sql = (
            "SELECT advisor, COUNT(*) AS total_no_show "
            "FROM service_appointments "
            "WHERE status = 'no_show' "
            "GROUP BY advisor"
        )
        normalized = client._normalize_sql_for_dialect(sql)  # noqa: SLF001
        self.assertIn("workshop", normalized.lower())
        self.assertNotIn("advisor", normalized.lower())

    def test_rewrites_scheduled_date_to_appointment_date(self) -> None:
        client = DwhClient(engine=self._engine)
        sql = (
            "SELECT scheduled_date, COUNT(*) "
            "FROM service_appointments "
            "WHERE scheduled_date >= CURRENT_DATE "
            "GROUP BY scheduled_date"
        )
        normalized = client._normalize_sql_for_dialect(sql)  # noqa: SLF001
        self.assertIn("appointment_date", normalized.lower())
        self.assertNotIn("scheduled_date", normalized.lower())


if __name__ == "__main__":
    unittest.main()
