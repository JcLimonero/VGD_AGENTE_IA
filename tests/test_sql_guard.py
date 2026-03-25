from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agente_dwh.sql_guard import (
    clean_sql_output,
    validate_read_only_sql,
    validate_vgd_dwh_sql,
    vgd_execution_guard_enabled,
)


class SqlGuardTests(unittest.TestCase):
    def test_clean_sql_strips_fence(self) -> None:
        raw = "```sql\nSELECT 1 AS x;\n```"
        self.assertEqual(clean_sql_output(raw).strip(), "SELECT 1 AS x;")

    def test_select_simple_ok(self) -> None:
        validate_read_only_sql("SELECT 1")

    def test_select_with_trailing_semicolon_ok(self) -> None:
        validate_read_only_sql("SELECT 1;")

    def test_with_cte_ok(self) -> None:
        validate_read_only_sql("WITH a AS (SELECT 1 AS n) SELECT n FROM a")

    def test_semicolon_inside_string_ok(self) -> None:
        validate_read_only_sql("SELECT ';' AS x")

    def test_delete_in_string_literal_ok(self) -> None:
        validate_read_only_sql("SELECT 1 AS x WHERE note = 'DELETE FROM users'")

    def test_comment_blocks_do_not_hide_delete(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_read_only_sql("SELECT 1 /**/DELETE/**/FROM customers")
        self.assertIn("DELETE", str(ctx.exception).upper())

    def test_double_statement_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("SELECT 1; DROP TABLE customers")

    def test_drop_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_read_only_sql("DROP TABLE customers")
        self.assertIn("SELECT", str(ctx.exception))

    def test_insert_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("INSERT INTO customers VALUES (1)")

    def test_null_byte_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("SELECT 1\x00")

    def test_pg_sleep_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("SELECT pg_sleep(10)")

    def test_copy_to_program_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("COPY customers TO PROGRAM 'true'")

    def test_copy_subquery_to_program_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("COPY (SELECT 1) TO PROGRAM 'true'")

    def test_refresh_materialized_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_read_only_sql("REFRESH MATERIALIZED VIEW mv_sales_monthly")

    def test_begin_date_column_ok(self) -> None:
        validate_read_only_sql("SELECT begin_date FROM customers WHERE id = 1")


class VgdSqlGuardTests(unittest.TestCase):
    def test_count_empty_rejected(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            validate_vgd_dwh_sql("SELECT COUNT() AS n FROM customers")
        self.assertIn("COUNT", str(ctx.exception))

    def test_customers_ok(self) -> None:
        validate_vgd_dwh_sql("SELECT state, COUNT(*) AS n FROM customers GROUP BY state")

    def test_literal_from_sales_not_false_positive(self) -> None:
        validate_vgd_dwh_sql("SELECT 'FROM sales' AS hint FROM agencies")

    def test_from_sales_rejected(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            validate_vgd_dwh_sql(
                "SELECT COUNT(*)::bigint AS n FROM sales s JOIN agencies a ON TRUE"
            )
        self.assertIn("invoices", str(ctx.exception).lower())

    def test_from_vehicles_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_vgd_dwh_sql("SELECT 1 FROM vehicles v LIMIT 1")

    def test_vgd_execution_guard_enabled_by_default(self) -> None:
        self.assertTrue(vgd_execution_guard_enabled(database_url="postgresql://localhost/postgres"))

    @patch.dict(os.environ, {"AGENTE_DWH_DISABLE_SQL_GUARD": "1"}, clear=False)
    def test_vgd_execution_guard_can_disable(self) -> None:
        self.assertFalse(vgd_execution_guard_enabled())


if __name__ == "__main__":
    unittest.main()
