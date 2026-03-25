from __future__ import annotations

import unittest

from sqlalchemy import create_engine

from agente_dwh.dwh import DwhClient

_SQLITE = create_engine("sqlite://")


class InsurancePolicyStatusRewriteTests(unittest.TestCase):
    def _norm(self, sql: str) -> str:
        return DwhClient(engine=_SQLITE)._normalize_sql_for_dialect(sql)  # noqa: SLF001

    def test_in_active_vence_pronto_to_activa(self) -> None:
        sql = (
            "SELECT v.vin FROM vehicles v "
            "LEFT JOIN insurance_policies ip ON v.id = ip.vehicle_id "
            "AND ip.policy_status IN ('active', 'vence_pronto')"
        )
        out = self._norm(sql)
        self.assertIn("'activa'", out.lower())
        self.assertNotIn("'active'", out.lower())
        self.assertNotIn("vence_pronto", out.lower())

    def test_unprefixed_policy_status_active(self) -> None:
        sql = (
            "SELECT * FROM insurance_policies WHERE policy_status = 'active'"
        )
        out = self._norm(sql)
        self.assertIn("policy_status = 'activa'", out.lower())

    def test_alias_policy_status_active(self) -> None:
        sql = (
            "SELECT * FROM insurance_policies pol WHERE pol.policy_status = 'active'"
        )
        out = self._norm(sql)
        self.assertIn("pol.policy_status = 'activa'", out.lower())


if __name__ == "__main__":
    unittest.main()
