from __future__ import annotations

import tempfile
import unittest

from agente_dwh.demo_data import ensure_demo_db
from agente_dwh.dwh import DwhClient
from agente_dwh.forecast import _build_history_query, compute_sales_forecast


class ForecastMvTests(unittest.TestCase):
    def test_history_query_uses_materialized_view(self) -> None:
        for dimension in ("total", "state", "channel", "segment"):
            sql = _build_history_query(dimension)
            self.assertIn("mv_sales_monthly", sql.lower())

    def test_forecast_runs_on_demo_mv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = f"{tmp_dir}/demo.sqlite3"
            ensure_demo_db(db_path)
            dwh = DwhClient.from_url(f"sqlite+pysqlite:///{db_path}", default_limit=500)
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
