from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from agente_dwh.demo_data import ensure_demo_db
from agente_dwh.dwh import DwhClient


class DwhCacheTests(unittest.TestCase):
    def test_cache_hit_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "demo.sqlite3"
            ensure_demo_db(db_path.as_posix())
            client = DwhClient.from_url(
                f"sqlite+pysqlite:///{db_path.as_posix()}",
                default_limit=50,
                cache_ttl_seconds=120,
                cache_max_entries=10,
            )

            sql = "SELECT state, COUNT(*) AS total FROM customers GROUP BY state ORDER BY state"
            rows_first = client.execute_select(sql)
            rows_second = client.execute_select(sql)

            self.assertEqual(rows_first, rows_second)
            stats = client.get_cache_stats()
            self.assertGreaterEqual(int(stats["hits"]), 1)
            self.assertGreaterEqual(int(stats["entries"]), 1)


if __name__ == "__main__":
    unittest.main()
