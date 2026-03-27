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

    def test_mysql_year_and_count_to_postgresql(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT year(sale_date) AS year, COUNT() AS sales_count, SUM(amount) AS total_sales "
            "FROM sales WHERE EXTRACT(YEAR FROM sale_date) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY year(sale_date) ORDER BY year(sale_date) LIMIT 200"
        )
        out = client._normalize_sql_for_dialect(sql)
        lowered = out.lower()
        self.assertNotRegex(lowered, r"\byear\s*\(")
        self.assertNotIn("count()", lowered.replace(" ", ""))
        self.assertIn("count(*)", lowered.replace(" ", ""))
        self.assertGreaterEqual(lowered.count("extract(year from "), 3)

    def test_month_day_functions_rewritten(self) -> None:
        client = self._pg_client()
        sql = "SELECT MONTH(sale_date), DAY(sale_date) FROM sales"
        out = client._normalize_sql_for_dialect(sql)
        lo = out.lower()
        self.assertIn("extract(month from", lo)
        self.assertIn("extract(day from", lo)

    def test_removes_invalid_interval_day_cast_after_date_subtraction(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT (s2.sale_date - s1.sale_date) :: interval 'day' AS gap FROM sales s1 JOIN sales s2 ON true"
        )
        out = client._normalize_sql_for_dialect(sql)
        self.assertNotRegex(out.lower(), r"::\s*interval\s+'day'")
        compact = out.replace(" ", "").lower()
        self.assertIn("s2.sale_date-s1.sale_date", compact)

    def test_h_views_rewrite_legacy_camel_case_columns(self) -> None:
        client = self._pg_client()
        sql = (
            'SELECT COUNT(DISTINCT o."ndClientDMS") AS n '
            'FROM h_orders o JOIN h_agencies a ON o."idAgency" = a."idAgency"'
        )
        out = client._normalize_sql_for_dialect(sql)
        self.assertIn('"nd_client_dms"', out)
        self.assertIn('"id_agency"', out)
        self.assertNotIn('"ndClientDMS"', out)

    def test_non_h_views_keep_legacy_camel_case_columns(self) -> None:
        client = self._pg_client()
        sql = 'SELECT COUNT(DISTINCT o."ndClientDMS") AS n FROM orders o'
        out = client._normalize_sql_for_dialect(sql)
        self.assertIn('"ndClientDMS"', out)

    def test_h_views_rewrite_unquoted_alias_dot_camel_case_columns(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT COUNT(DISTINCT o.ndClientDMS) AS n "
            "FROM h_orders o JOIN h_agencies a ON o.idAgency = a.idAgency"
        )
        out = client._normalize_sql_for_dialect(sql)
        self.assertIn('o."nd_client_dms"', out)
        self.assertIn('o."id_agency"', out)
        self.assertIn('a."id_agency"', out)
        self.assertNotIn("o.ndClientDMS", out)

    def test_h_views_rewrite_unknown_quoted_camel_case_columns(self) -> None:
        client = self._pg_client()
        sql = 'SELECT o."CustomLegacyField" FROM h_orders o'
        out = client._normalize_sql_for_dialect(sql)
        self.assertIn('"custom_legacy_field"', out)
        self.assertNotIn('"CustomLegacyField"', out)

    def test_retry_rewrite_for_undefined_column_alias_dot_legacy(self) -> None:
        client = self._pg_client()
        sql = (
            'SELECT COUNT(DISTINCT o."ndClientDMS") AS n '
            "FROM h_orders o JOIN h_agencies a ON o.id_agency = a.id_agency"
        )
        err = 'column o.ndClientDMS does not exist'
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        self.assertIn('o."nd_client_dms"', out or "")

    def test_retry_rewrite_ignored_for_non_h_queries(self) -> None:
        client = self._pg_client()
        sql = 'SELECT COUNT(DISTINCT o."ndClientDMS") AS n FROM orders o'
        err = 'column o.ndClientDMS does not exist'
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNone(out)

    def test_retry_rewrite_created_at_for_h_customers(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT COUNT(*) AS n FROM h_customers "
            "WHERE EXTRACT(YEAR FROM created_at) = 2025"
        )
        err = 'column "created_at" does not exist'
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        self.assertIn('EXTRACT(YEAR FROM "timestamp_dms")', out or "")

    def test_retry_rewrite_agency_name_for_h_agencies(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT h_customers.id_agency, h_agencies.agency_name "
            "FROM h_customers JOIN h_agencies ON h_customers.id_agency = h_agencies.id_agency"
        )
        err = "column h_agencies.agency_name does not exist"
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        self.assertIn('h_agencies."name"', out or "")

    def test_retry_rewrite_agency_id_to_id_agency_in_h_customers(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT a.name AS agency_name, COUNT(DISTINCT c.id) AS customer_count "
            "FROM h_agencies a "
            "JOIN h_customers c ON a.id = c.agency_id "
            "GROUP BY a.name LIMIT 200"
        )
        err = "column c.agency_id does not exist"
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        lowered = (out or "").lower().replace('"', "")
        self.assertIn("c.id_agency", lowered)
        self.assertIn("a.id_agency", lowered)
        self.assertNotIn("c.agency_id", lowered)

    def test_retry_rewrite_undefined_table_h_clients(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT a.name AS agency_name, COUNT(DISTINCT c.id_client) AS number_of_customers "
            "FROM h_agencies a "
            "JOIN h_orders o ON a.id = o.id_agency::bigint "
            "JOIN h_clients c ON o.nd_client_dms = c.id_client "
            "GROUP BY a.name LIMIT 200"
        )
        err = 'relation "h_clients" does not exist'
        out = client._rewrite_postgresql_undefined_table_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        lowered = (out or "").lower()
        self.assertIn("h_customers", lowered)
        self.assertIn("nd_client_dms", lowered)
        self.assertIn("id_agency", lowered)


    def test_proactive_h_agencies_surrogate_id_fix(self) -> None:
        """La normalización proactiva corrige a.id → a.id_agency en JOINs con h_agencies."""
        from agente_dwh.sql_rewrites import rewrite_h_agencies_surrogate_id_in_joins

        sql = (
            "SELECT a.name AS agency_name, COUNT(DISTINCT c.id) AS cnt "
            "FROM h_customers c "
            "JOIN h_agencies a ON c.id_agency = a.id "
            "GROUP BY a.name LIMIT 200"
        )
        out = rewrite_h_agencies_surrogate_id_in_joins(sql)
        self.assertIn("a.id_agency", out)
        self.assertNotRegex(out, r'\ba\.id\b(?!_)')

    def test_proactive_h_agencies_no_change_without_h_agencies(self) -> None:
        from agente_dwh.sql_rewrites import rewrite_h_agencies_surrogate_id_in_joins

        sql = "SELECT * FROM h_customers LIMIT 10"
        self.assertEqual(rewrite_h_agencies_surrogate_id_in_joins(sql), sql)

    def test_id_client_fallback_in_h_customers(self) -> None:
        client = self._pg_client()
        sql = (
            "SELECT c.id_client, c.name "
            "FROM h_customers c LIMIT 200"
        )
        err = 'column c.id_client does not exist'
        out = client._rewrite_postgresql_undefined_column_retry(sql, err)  # noqa: SLF001
        self.assertIsNotNone(out)
        lowered = (out or "").lower().replace('"', "")
        self.assertIn("nd_client_dms", lowered)


if __name__ == "__main__":
    unittest.main()
