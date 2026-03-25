from __future__ import annotations

import unittest

from agente_dwh.sql_vehicle_context import apply_vehicle_focus_sql_rewrites


class SqlVehicleContextTests(unittest.TestCase):
    def test_ultimo_vin_replaced(self) -> None:
        sql = (
            "SELECT customers.full_name FROM sales "
            "JOIN vehicles ON sales.vehicle_id = vehicles.id "
            "JOIN customers ON sales.customer_id = customers.id "
            "WHERE vehicles.vin = 'ultimo_vin' ORDER BY sales.sale_date DESC LIMIT 1"
        )
        out = apply_vehicle_focus_sql_rewrites(sql, {"vin": "VIN00000000001234"})
        self.assertIn("VIN00000000001234", out)
        self.assertNotIn("ultimo_vin", out.lower())

    def test_last_vin_case_insensitive(self) -> None:
        sql = "WHERE v.vin = 'LAST_VIN'"
        out = apply_vehicle_focus_sql_rewrites(sql, {"vin": "ABC"})
        self.assertIn("'ABC'", out)

    def test_vin_apostrophe_escaped(self) -> None:
        sql = "WHERE vin = 'ultimo_vin'"
        out = apply_vehicle_focus_sql_rewrites(sql, {"vin": "O'BRIEN"})
        self.assertIn("O''BRIEN", out)

    def test_vehicle_id_placeholder(self) -> None:
        sql = "WHERE vehicles.id = 'ultimo_vehicle_id'"
        out = apply_vehicle_focus_sql_rewrites(sql, {"vehicle_id": 42})
        self.assertRegex(out, r"=\s*42")

    def test_no_focus_no_change(self) -> None:
        sql = "WHERE vin = 'ultimo_vin'"
        self.assertEqual(apply_vehicle_focus_sql_rewrites(sql, None), sql)
        self.assertEqual(apply_vehicle_focus_sql_rewrites(sql, {}), sql)

    def test_placa_placeholder(self) -> None:
        sql = "WHERE plate = 'ultima_placa'"
        out = apply_vehicle_focus_sql_rewrites(sql, {"plate": "D1234AB"})
        self.assertIn("D1234AB", out)


if __name__ == "__main__":
    unittest.main()
