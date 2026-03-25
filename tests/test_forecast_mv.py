from __future__ import annotations

import os
import unittest

from agente_dwh.demo_data import ensure_demo_postgres
from agente_dwh.dwh import DwhClient
from agente_dwh.forecast import _build_history_query, compute_sales_forecast

_PG_DSN = (os.getenv("TEST_PG_DSN") or os.getenv("DWH_URL") or "").strip()
_HAS_PG = _PG_DSN.lower().startswith("postgresql")


@unittest.skipUnless(_HAS_PG, "definir TEST_PG_DSN o DWH_URL (postgresql+psycopg://...)")
class ForecastMvTests(unittest.TestCase):
    def test_history_query_uses_materialized_view(self) -> None:
        for dimension in ("total", "state", "channel", "segment"):
            sql = _build_history_query(dimension)
            self.assertIn("mv_sales_monthly", sql.lower())

    def test_forecast_runs_on_demo_mv(self) -> None:
        ensure_demo_postgres(_PG_DSN)
        dwh = DwhClient.from_url(_PG_DSN, default_limit=500)
        result = compute_sales_forecast(
            dwh_client=dwh,
            horizon_months=3,
            method="moving_average",
            dimension="total",
        )
        self.assertGreater(result.source_rows, 0)
        self.assertGreater(len(result.forecast_rows), 0)


if __name__ == "__main__":
    unittest.main()
