"""Tests for agente_dwh.sql_guard module."""

import pytest

from agente_dwh.sql_guard import clean_sql_output, validate_read_only_sql


class TestCleanSqlOutput:
    def test_removes_markdown_code_fence(self):
        raw = "```sql\nSELECT * FROM ventas;\n```"
        assert clean_sql_output(raw) == "SELECT * FROM ventas;"

    def test_plain_sql_unchanged(self):
        assert clean_sql_output("SELECT 1") == "SELECT 1"

    def test_strips_whitespace(self):
        assert clean_sql_output("  SELECT 1  ") == "SELECT 1"

    def test_removes_generic_code_fence(self):
        raw = "```\nSELECT 1\n```"
        assert clean_sql_output(raw) == "SELECT 1"


class TestValidateReadOnlySql:
    def test_valid_select(self):
        validate_read_only_sql("SELECT * FROM ventas")

    def test_valid_with_cte(self):
        validate_read_only_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="vacia"):
            validate_read_only_sql("")

    def test_insert_blocked(self):
        with pytest.raises(ValueError, match="INSERT"):
            validate_read_only_sql("SELECT INSERT FROM t")

    def test_drop_blocked(self):
        with pytest.raises(ValueError, match="Solo se permiten"):
            validate_read_only_sql("DROP TABLE ventas")

    def test_update_in_select_blocked(self):
        with pytest.raises(ValueError, match="UPDATE"):
            validate_read_only_sql("SELECT * FROM t WHERE UPDATE = 1")

    def test_multiple_statements_blocked(self):
        with pytest.raises(ValueError, match="una sentencia"):
            validate_read_only_sql("SELECT 1; SELECT 2")

    def test_delete_blocked(self):
        with pytest.raises(ValueError, match="Solo se permiten"):
            validate_read_only_sql("DELETE FROM ventas")
