from __future__ import annotations

import os
import unittest

from agente_dwh.demo_data import ensure_demo_postgres
from agente_dwh.dwh import DwhClient

_PG_DSN = (os.getenv("TEST_PG_DSN") or os.getenv("DWH_URL") or "").strip()
_HAS_PG = _PG_DSN.lower().startswith("postgresql")


@unittest.skipUnless(_HAS_PG, "definir TEST_PG_DSN o DWH_URL (postgresql+psycopg://...)")
class DwhCacheTests(unittest.TestCase):
    def test_cache_hit_and_stats(self) -> None:
        ensure_demo_postgres(_PG_DSN)
        client = DwhClient.from_url(
            _PG_DSN,
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
