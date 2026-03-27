from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import json

from agente_dwh.error_subagent import (
    ErrorFixSubagent,
    log_error_and_run_subagent,
    log_error_file,
)


class ErrorSubagentTests(unittest.TestCase):
    def test_crea_archivo_de_error_unico(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            file_path = log_error_file(
                source="test",
                message="fallo",
                context={"sql": "SELECT COUNT() FROM sales"},
                log_dir=log_dir,
            )
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.parent, log_dir)

    def test_subagente_procesa_y_archiva_archivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            file_path = log_error_file(
                source="test",
                message="function year(date) does not exist",
                context={"sql": "SELECT YEAR(sale_date), COUNT() FROM sales"},
                log_dir=log_dir,
            )
            self.assertTrue(file_path.exists())
            subagent = ErrorFixSubagent(log_dir=log_dir)
            results = subagent.process_pending_files()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "fixed_sql")
            self.assertIn("EXTRACT(YEAR FROM", results[0].fixed_sql or "")
            self.assertIn("COUNT(*)", results[0].fixed_sql or "")
            self.assertFalse(file_path.exists())
            processed_files = list((log_dir / "procesados").glob("error_*.json"))
            archived_original = [p for p in processed_files if not p.stem.endswith("_resultado")]
            archived_reports = [p for p in processed_files if p.stem.endswith("_resultado")]
            self.assertEqual(len(archived_original), 1)
            self.assertEqual(len(archived_reports), 1)
            report_payload = json.loads(archived_reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report_payload["status"], "fixed_sql")
            self.assertIn("EXTRACT(YEAR FROM", report_payload.get("fixed_sql") or "")

    def test_helper_logea_ejecuta_y_archiva(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            results = log_error_and_run_subagent(
                source="test",
                message="error simple",
                context={"sql": "SELECT 1"},
                log_dir=log_dir,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(list(log_dir.glob("error_*.json")), [])
            processed_files = list((log_dir / "procesados").glob("error_*.json"))
            archived_original = [p for p in processed_files if not p.stem.endswith("_resultado")]
            archived_reports = [p for p in processed_files if p.stem.endswith("_resultado")]
            self.assertEqual(len(archived_original), 1)
            self.assertEqual(len(archived_reports), 1)

    def test_heuristica_corrige_agency_id_a_id_agency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            results = log_error_and_run_subagent(
                source="test",
                message="column c.agency_id does not exist",
                context={
                    "sql": (
                        "SELECT a.name AS agency_name, COUNT(DISTINCT c.id) AS customer_count "
                        "FROM h_agencies a "
                        "JOIN h_customers c ON a.id = c.agency_id "
                        "GROUP BY a.name LIMIT 200"
                    )
                },
                log_dir=log_dir,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "fixed_sql")
            fixed = (results[0].fixed_sql or "").lower()
            self.assertIn("c.id_agency", fixed)
            self.assertIn("a.id_agency", fixed)
            self.assertNotIn("c.agency_id", fixed)

    def test_heuristica_corrige_h_clients_id_client_e_id_agency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            results = log_error_and_run_subagent(
                source="test",
                message='relation "h_clients" does not exist',
                context={
                    "sql": (
                        "SELECT a.name, COUNT(DISTINCT c.id_client) FROM h_agencies a "
                        "JOIN h_orders o ON a.id = o.id_agency::bigint "
                        "JOIN h_clients c ON o.nd_client_dms = c.id_client GROUP BY a.name"
                    )
                },
                log_dir=log_dir,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "fixed_sql")
            fixed = (results[0].fixed_sql or "").lower()
            self.assertIn("h_customers", fixed)
            self.assertIn("nd_client_dms", fixed)
            self.assertIn("id_agency", fixed)


if __name__ == "__main__":
    unittest.main()
