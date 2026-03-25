from __future__ import annotations

import unittest

from agente_dwh.demo_data import _validate_sales_vehicle_integrity, generate_demo_dataset


class DemoSalesVehicleTests(unittest.TestCase):
    def test_validate_integrity_accepts_valid_row(self) -> None:
        _validate_sales_vehicle_integrity(
            [(1, 10, 100, "2024-01-01")],
            valid_vehicle_ids={100},
            vehicle_meta={100: {"customer_id": 10, "unit_type": "Sedan"}},
        )

    def test_validate_integrity_rejects_wrong_owner(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _validate_sales_vehicle_integrity(
                [(1, 10, 100, "2024-01-01")],
                valid_vehicle_ids={100},
                vehicle_meta={100: {"customer_id": 99, "unit_type": "Sedan"}},
            )
        self.assertIn("dueño", str(ctx.exception).lower())

    def test_generate_demo_all_sales_reference_vehicles(self) -> None:
        ds = generate_demo_dataset()
        vehicle_ids = {v[0] for v in ds.vehicles}
        vehicle_owner = {v[0]: v[1] for v in ds.vehicles}
        self.assertTrue(ds.sales, "debe haber al menos una venta en el demo")
        for row in ds.sales:
            _sale_pk, customer_id, vehicle_id = row[0], row[1], row[2]
            self.assertIsNotNone(vehicle_id, msg=f"venta {row} sin vehicle_id")
            self.assertIn(
                vehicle_id,
                vehicle_ids,
                msg=f"venta {_sale_pk} referencia vehicle_id={vehicle_id} inexistente",
            )
            self.assertEqual(
                vehicle_owner[vehicle_id],
                customer_id,
                msg=f"venta {_sale_pk}: cliente {customer_id} no es dueño del vehículo {vehicle_id}",
            )


if __name__ == "__main__":
    unittest.main()
