from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any


@dataclass(frozen=True)
class QueryEvent:
    timestamp: str
    source: str
    success: bool
    duration_ms: float
    row_count: int
    cached: bool
    message: str = ""


_EVENTS: deque[QueryEvent] = deque(maxlen=500)
_ALERTS: deque[str] = deque(maxlen=200)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_query_event(
    *,
    source: str,
    success: bool,
    duration_ms: float,
    row_count: int,
    cached: bool,
    message: str = "",
) -> QueryEvent:
    event = QueryEvent(
        timestamp=_utc_now_iso(),
        source=source,
        success=success,
        duration_ms=round(duration_ms, 2),
        row_count=row_count,
        cached=cached,
        message=message.strip(),
    )
    _EVENTS.append(event)
    _maybe_emit_alert(event)
    return event


def _maybe_emit_alert(event: QueryEvent) -> None:
    if not event.success:
        _ALERTS.appendleft(
            f"[{event.timestamp}] ALERTA error en {event.source}: {event.message or 'fallo sin detalle'}"
        )
    if event.duration_ms > 2500:
        _ALERTS.appendleft(
            f"[{event.timestamp}] ALERTA latencia alta en {event.source}: {event.duration_ms:.2f} ms"
        )


def get_recent_events(limit: int = 50) -> list[QueryEvent]:
    if limit <= 0:
        return []
    events = list(_EVENTS)
    return events[-limit:]


def get_recent_alerts(limit: int = 20) -> list[str]:
    if limit <= 0:
        return []
    alerts = list(_ALERTS)
    return alerts[:limit]


def get_metrics_snapshot() -> dict[str, Any]:
    events = list(_EVENTS)
    total = len(events)
    if total == 0:
        return {
            "total_queries": 0,
            "success_queries": 0,
            "failed_queries": 0,
            "cached_queries": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "sources": {},
        }

    success_queries = sum(1 for event in events if event.success)
    failed_queries = total - success_queries
    cached_queries = sum(1 for event in events if event.cached)
    latencies = sorted(event.duration_ms for event in events)
    avg_latency = sum(latencies) / total
    p95_index = min(total - 1, max(0, int(total * 0.95) - 1))
    p95_latency = latencies[p95_index]

    sources: dict[str, dict[str, float | int]] = {}
    for event in events:
        source_metrics = sources.setdefault(
            event.source,
            {
                "total": 0,
                "success": 0,
                "failed": 0,
                "cached": 0,
                "avg_latency_ms": 0.0,
            },
        )
        source_metrics["total"] = int(source_metrics["total"]) + 1
        source_metrics["success"] = int(source_metrics["success"]) + int(event.success)
        source_metrics["failed"] = int(source_metrics["failed"]) + int(not event.success)
        source_metrics["cached"] = int(source_metrics["cached"]) + int(event.cached)
        source_metrics["avg_latency_ms"] = float(source_metrics["avg_latency_ms"]) + event.duration_ms

    for source_metrics in sources.values():
        total_source = int(source_metrics["total"])
        source_metrics["avg_latency_ms"] = round(float(source_metrics["avg_latency_ms"]) / total_source, 2)

    return {
        "total_queries": total,
        "success_queries": success_queries,
        "failed_queries": failed_queries,
        "cached_queries": cached_queries,
        "success_rate": round((success_queries / total) * 100, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "sources": sources,
    }


class StopWatch:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0
