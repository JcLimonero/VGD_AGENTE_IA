from __future__ import annotations

import unittest

from sqlalchemy import create_engine

from agente_dwh.dwh import DwhClient


class ServiceAppointmentsRewriteTests(unittest.TestCase):
    def test_rewrites_status_to_appointment_status_for_service_appointments(self) -> None:
        client = DwhClient(engine=create_engine("sqlite+pysqlite:///:memory:"))
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
        client = DwhClient(engine=create_engine("sqlite+pysqlite:///:memory:"))
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
        client = DwhClient(engine=create_engine("sqlite+pysqlite:///:memory:"))
        sql = (
            "SELECT scheduled_date, COUNT(*) "
            "FROM service_appointments "
            "WHERE scheduled_date >= date('now') "
            "GROUP BY scheduled_date"
        )
        normalized = client._normalize_sql_for_dialect(sql)  # noqa: SLF001
        self.assertIn("appointment_date", normalized.lower())
        self.assertNotIn("scheduled_date", normalized.lower())


if __name__ == "__main__":
    unittest.main()
