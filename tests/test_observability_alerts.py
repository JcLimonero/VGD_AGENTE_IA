"""Umbrales de alertas de latencia."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from agente_dwh.observability import _alert_latency_threshold_ms, record_query_event


class ObservabilityAlertThresholdTests(unittest.TestCase):
    def test_agent_default_threshold_is_higher_than_dwh(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_alert_latency_threshold_ms("dwh"), 2500.0)
            self.assertEqual(_alert_latency_threshold_ms("agent"), 20000.0)

    def test_env_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"AGENTE_DWH_ALERT_LATENCY_MS": "1000", "AGENTE_DWH_ALERT_LATENCY_MS_AGENT": "5000"},
        ):
            self.assertEqual(_alert_latency_threshold_ms("dwh"), 1000.0)
            self.assertEqual(_alert_latency_threshold_ms("agent"), 5000.0)

    def test_latency_18s_does_not_alert_agent_with_default_threshold(self) -> None:
        from agente_dwh import observability

        observability._ALERTS.clear()
        observability._EVENTS.clear()
        with mock.patch.dict(os.environ, {}, clear=True):
            record_query_event(
                source="agent",
                success=True,
                duration_ms=18366.0,
                row_count=1,
                cached=False,
            )
        self.assertEqual(list(observability._ALERTS), [])

    def test_latency_25s_alerts_agent_with_default_threshold(self) -> None:
        from agente_dwh import observability

        observability._ALERTS.clear()
        observability._EVENTS.clear()
        with mock.patch.dict(os.environ, {}, clear=True):
            record_query_event(
                source="agent",
                success=True,
                duration_ms=25001.0,
                row_count=1,
                cached=False,
            )
        self.assertEqual(len(observability._ALERTS), 1)
        self.assertIn("latencia alta", observability._ALERTS[0])


if __name__ == "__main__":
    unittest.main()
