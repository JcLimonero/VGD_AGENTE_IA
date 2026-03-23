"""Tests for agente_dwh.dwh module using SQLite."""

import sqlite3

import pytest

from agente_dwh.dwh import DwhClient


@pytest.fixture
def sqlite_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("CREATE TABLE ventas (id INTEGER, tienda TEXT, monto REAL)")
    c.executemany(
        "INSERT INTO ventas VALUES (?, ?, ?)",
        [(1, "Norte", 100.0), (2, "Sur", 200.0), (3, "Centro", 300.0)],
    )
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


class TestDwhClient:
    def test_execute_select(self, sqlite_db):
        client = DwhClient.from_url(sqlite_db)
        rows = client.execute_select("SELECT * FROM ventas")
        assert len(rows) == 3
        assert rows[0]["tienda"] == "Norte"

    def test_limit_injection(self, sqlite_db):
        client = DwhClient.from_url(sqlite_db, default_limit=1)
        rows = client.execute_select("SELECT * FROM ventas")
        assert len(rows) == 1

    def test_existing_limit_preserved(self, sqlite_db):
        client = DwhClient.from_url(sqlite_db, default_limit=1)
        rows = client.execute_select("SELECT * FROM ventas LIMIT 2")
        assert len(rows) == 2

    def test_invalid_sql_raises(self, sqlite_db):
        client = DwhClient.from_url(sqlite_db)
        with pytest.raises(RuntimeError, match="Error ejecutando"):
            client.execute_select("SELECT * FROM tabla_inexistente")
