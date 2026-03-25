"""Reescritura PostgreSQL: EXTRACT(EPOCH FROM (date - date))."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from agente_dwh.dwh import DwhClient


class PostgresqlExtractEpochRewriteTests(unittest.TestCase):
    def _pg_client(self) -> DwhClient:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        return DwhClient(engine=engine)

    def test_casts_simple_date_subtraction_inside_extract_epoch(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT AVG(EXTRACT(EPOCH FROM (sale_date - prev_sale_date)) / 86400) AS avg_repurchase_days "
            "FROM subquery WHERE prev_sale_date IS NOT NULL"
        )
        out = client._normalize_sql_for_dialect(sql)
        lowered = out.lower()
        self.assertIn("sale_date::timestamp", lowered)
        self.assertIn("prev_sale_date::timestamp", lowered)
        self.assertIn("extract(epoch from", lowered)

    def test_leaves_non_binary_inner_expression_unchanged(self) -> None:
        client = self._pg_client()
        sql = "SELECT EXTRACT(EPOCH FROM (now() - col)) FROM t"
        out = client._normalize_sql_for_dialect(sql)
        self.assertEqual(out.replace(" ", "").lower(), sql.replace(" ", "").lower())


if __name__ == "__main__":
    unittest.main()
