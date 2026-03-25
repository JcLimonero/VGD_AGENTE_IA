"""Resumen: VINs múltiples concatenados por comas."""

from __future__ import annotations

import unittest

from agente_dwh.web import (
    _append_multi_vin_summary_line,
    _compute_hybrid_answer_summary,
    _multi_vin_markdown_line,
)


class VinSummaryTests(unittest.TestCase):
    def test_multi_vin_line_requires_two_plus_distinct(self) -> None:
        self.assertIsNone(_multi_vin_markdown_line([{"vin": "A"}]))
        self.assertIsNone(_multi_vin_markdown_line([{"vin": "A"}, {"vin": "A"}]))
        self.assertEqual(
            _multi_vin_markdown_line([{"vin": "A"}, {"vin": "B"}]),
            "**VINs:** A, B",
        )

    def test_append_line(self) -> None:
        rows = [{"vin": "X1", "k": 1}, {"vin": "X2", "k": 2}]
        out = _append_multi_vin_summary_line("Resumen corto.", rows)
        self.assertTrue(out.startswith("Resumen corto."))
        self.assertIn("**VINs:** X1, X2", out)

    def test_hybrid_heuristic_appends_vins(self) -> None:
        rows = [{"vin": "VIN001", "n": 1}, {"vin": "VIN002", "n": 2}]
        text = _compute_hybrid_answer_summary("test", rows, llm=None)
        self.assertIn("**VINs:** VIN001, VIN002", text)
        self.assertNotRegex(text, r"\*\*VIN:\*\*\s+VIN001")


if __name__ == "__main__":
    unittest.main()
