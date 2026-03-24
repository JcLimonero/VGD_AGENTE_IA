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


if __name__ == "__main__":
    unittest.main()
