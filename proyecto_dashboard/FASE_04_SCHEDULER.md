# Fase 4 — Scheduler de Refresco Automático

## Objetivo

Crear el scheduler que ejecuta automáticamente las queries guardadas según su
`refresh_interval`, almacena snapshots y registra logs de refresco.
Incluye circuit breaker para desactivar queries con fallos recurrentes.

## Prerequisitos

- Fase 2 completa: `SnapshotService` funcional.
- Fase 1 completa: `saved_queries` con campo `refresh_interval`.
- `DwhClient` funcional.
- `observability.py` funcional.

---

## Tareas

### T4.1 — Agregar dependencia APScheduler

Agregar al `pyproject.toml` en `[project.optional-dependencies]`:

```toml
platform = [
    "apscheduler>=3.10",
]
```

### T4.2 — Crear `agente_dwh/platform/scheduler.py`

**Archivo:** `agente_dwh/platform/scheduler.py`

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agente_dwh.dwh import DwhClient
from agente_dwh.observability import record_query_event
from agente_dwh.platform.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


ALLOWED_INTERVALS = {
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 hour": 3600,
    "6 hours": 21600,
    "1 day": 86400,
}


class QueryRefreshScheduler:
    """
    Ejecuta queries guardadas según su refresh_interval.

    Diseño:
    - Un job maestro ("tick") corre cada 60 segundos.
    - En cada tick, busca queries activas cuyo último snapshot
      sea más antiguo que su refresh_interval.
    - Para cada query pendiente, ejecuta SnapshotService.execute_and_store().
    - Registra resultado en refresh_log.
    - Si una query falla N veces consecutivas, la desactiva (circuit breaker).
    """

    def __init__(
        self,
        snapshot_service: SnapshotService,
        session_factory,
        *,
        tick_interval_seconds: int = 60,
        max_consecutive_failures: int = 5,
    ):
        """
        Args:
            snapshot_service: Servicio para ejecutar y almacenar snapshots.
            session_factory: SQLAlchemy sessionmaker.
            tick_interval_seconds: Intervalo del job maestro (default 60s).
            max_consecutive_failures: Fallos consecutivos antes de desactivar (default 5).
        """

    def start(self) -> None:
        """
        Arranca el scheduler con BackgroundScheduler de APScheduler.
        Registra el job maestro con IntervalTrigger.
        No hace nada si ya está corriendo.
        """

    def stop(self) -> None:
        """
        Detiene el scheduler de forma limpia.
        No hace nada si no está corriendo.
        """

    @property
    def is_running(self) -> bool:
        """True si el scheduler está activo."""

    def _tick(self) -> None:
        """
        Job maestro. En cada ejecución:
        1. Consulta BD: queries activas con refresh_interval NOT NULL.
        2. Para cada una, verifica si necesita refresco:
           - Obtiene el último snapshot (executed_at).
           - Calcula seconds_since = (now - executed_at).total_seconds()
           - Si seconds_since >= ALLOWED_INTERVALS[refresh_interval], ejecuta.
           - Si no hay snapshots previos, ejecuta.
        3. Ejecuta _refresh_query() para cada query pendiente.
        """

    def _refresh_query(self, saved_query_id: int) -> None:
        """
        Ejecuta una query individual:
        1. Llama snapshot_service.execute_and_store(saved_query_id).
        2. Registra en refresh_log: triggered_at, finished_at, success, duration_ms.
        3. Si éxito: resetea contador de fallos.
        4. Si falla:
           - Incrementa contador de fallos consecutivos.
           - Registra en refresh_log con error_message.
           - Si fallos >= max_consecutive_failures:
             - Desactiva la query (is_active = False).
             - Registra alerta en observability.
             - Log warning.
        """

    def _get_pending_queries(self) -> list[dict[str, Any]]:
        """
        Retorna queries que necesitan refresco.

        SQL equivalente:
        SELECT sq.id, sq.refresh_interval,
               (SELECT MAX(executed_at) FROM query_snapshots
                WHERE saved_query_id = sq.id) AS last_executed
        FROM saved_queries sq
        WHERE sq.is_active = true
          AND sq.refresh_interval IS NOT NULL
        """

    def _get_consecutive_failures(self, saved_query_id: int) -> int:
        """
        Cuenta los refresh_log más recientes consecutivos con success=False.
        Se detiene al encontrar el primer success=True.
        """

    def _record_refresh_log(
        self,
        saved_query_id: int,
        *,
        triggered_at: datetime,
        finished_at: datetime,
        success: bool,
        duration_ms: float,
        error_message: str | None = None,
    ) -> None:
        """Inserta un registro en refresh_log."""

    def get_refresh_stats(self) -> dict[str, Any]:
        """
        Retorna estadísticas del scheduler:
        - is_running: bool
        - total_refreshes: int (total de refresh_log)
        - successful_refreshes: int
        - failed_refreshes: int
        - last_tick_at: datetime | None
        - active_scheduled_queries: int (queries con refresh_interval activas)
        - circuit_breaker_triggered: int (queries desactivadas por fallos)
        """
```

### T4.3 — Integrar scheduler al arranque de la aplicación

**En `web.py` o `dashboard_ui/app.py`:**

1. Al arrancar, crear instancia de `QueryRefreshScheduler`.
2. Llamar `scheduler.start()` una sola vez (usar `st.session_state` para no duplicar).
3. En la sección de observabilidad (modo desarrollador), mostrar `scheduler.get_refresh_stats()`.

**En `cli.py` (opcional):**

1. Si se usa la opción `--with-scheduler`, arranca el scheduler en background.

### T4.4 — Panel de monitoreo del scheduler en modo desarrollador

En la UI de Streamlit (modo desarrollador), agregar una sección expandible:

1. **Estado del scheduler**: running / stopped.
2. **Estadísticas**: total refreshes, éxitos, fallos, última ejecución.
3. **Queries programadas**: tabla con las queries activas con refresh_interval,
   mostrando: título, intervalo, último refresco, próximo refresco estimado.
4. **Queries desactivadas por circuit breaker**: tabla con queries desactivadas
   por fallos, mostrando: título, error del último fallo, botón "Reactivar".
5. **Refresh log reciente**: últimas 20 entradas del refresh_log.

### T4.5 — Job de limpieza de snapshots

Agregar al scheduler un segundo job que corre cada 24 horas:

```python
self._scheduler.add_job(
    self._cleanup_snapshots,
    trigger=IntervalTrigger(hours=24),
    id="snapshot_cleanup",
)
```

Este job llama `snapshot_service.cleanup_all_old_snapshots(keep_last=100)`.

---

## Casos de Prueba

### Archivo: `tests/test_scheduler.py`

```python
"""Tests para el scheduler de refresco."""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base, PlatformUser, SavedQuery, QuerySnapshot, RefreshLog,
    create_all_tables, get_session_factory,
)
from agente_dwh.platform.scheduler import QueryRefreshScheduler, ALLOWED_INTERVALS
from agente_dwh.platform.snapshot_service import SnapshotService


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    create_all_tables(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return get_session_factory(engine)


@pytest.fixture
def mock_dwh():
    dwh = MagicMock()
    dwh.execute_select.return_value = [{"total": 100}]
    return dwh


@pytest.fixture
def snapshot_service(mock_dwh, session_factory):
    return SnapshotService(dwh_client=mock_dwh, session_factory=session_factory)


@pytest.fixture
def demo_user(session_factory):
    session = session_factory()
    user = PlatformUser(username="demo", display_name="Demo", password_hash="h")
    session.add(user)
    session.commit()
    uid = user.id
    session.close()
    return uid


def _create_query(session_factory, user_id, title="Q", refresh_interval="5 minutes"):
    session = session_factory()
    sq = SavedQuery(
        user_id=user_id, title=title, original_question="q",
        sql_text="SELECT 1", is_active=True,
        refresh_interval=refresh_interval,
    )
    session.add(sq)
    session.commit()
    qid = sq.id
    session.close()
    return qid


class TestAllowedIntervals:
    def test_all_intervals_have_seconds(self):
        expected_keys = {"5 minutes", "15 minutes", "30 minutes", "1 hour", "6 hours", "1 day"}
        assert set(ALLOWED_INTERVALS.keys()) == expected_keys

    def test_seconds_correct(self):
        assert ALLOWED_INTERVALS["5 minutes"] == 300
        assert ALLOWED_INTERVALS["1 hour"] == 3600
        assert ALLOWED_INTERVALS["1 day"] == 86400


class TestSchedulerLifecycle:
    def test_start_stop(self, snapshot_service, session_factory):
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
            tick_interval_seconds=600,  # largo para no disparar en tests
        )
        assert scheduler.is_running is False
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        assert scheduler.is_running is False

    def test_double_start_no_error(self, snapshot_service, session_factory):
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
            tick_interval_seconds=600,
        )
        scheduler.start()
        scheduler.start()  # no debe fallar
        assert scheduler.is_running is True
        scheduler.stop()

    def test_stop_without_start_no_error(self, snapshot_service, session_factory):
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        scheduler.stop()  # no debe fallar


class TestGetPendingQueries:
    def test_query_without_snapshot_is_pending(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user, refresh_interval="5 minutes")
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        pending = scheduler._get_pending_queries()
        pending_ids = [p["id"] for p in pending]
        assert qid in pending_ids

    def test_recently_refreshed_not_pending(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user, refresh_interval="1 hour")
        snapshot_service.execute_and_store(qid)  # snapshot reciente
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        pending = scheduler._get_pending_queries()
        pending_ids = [p["id"] for p in pending]
        assert qid not in pending_ids

    def test_inactive_query_not_pending(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user, refresh_interval="5 minutes")
        session = session_factory()
        sq = session.query(SavedQuery).get(qid)
        sq.is_active = False
        session.commit()
        session.close()
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        pending = scheduler._get_pending_queries()
        pending_ids = [p["id"] for p in pending]
        assert qid not in pending_ids

    def test_manual_query_not_pending(
        self, snapshot_service, session_factory, demo_user
    ):
        """Query con refresh_interval=None no aparece como pendiente."""
        session = session_factory()
        sq = SavedQuery(
            user_id=demo_user, title="Manual", original_question="q",
            sql_text="SELECT 1", is_active=True,
            refresh_interval=None,
        )
        session.add(sq)
        session.commit()
        qid = sq.id
        session.close()
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        pending = scheduler._get_pending_queries()
        pending_ids = [p["id"] for p in pending]
        assert qid not in pending_ids


class TestRefreshQuery:
    def test_success_creates_snapshot_and_log(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user)
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        scheduler._refresh_query(qid)
        # Verificar snapshot
        snap = snapshot_service.get_latest_snapshot(qid)
        assert snap is not None
        assert snap.success is True
        # Verificar refresh_log
        session = session_factory()
        logs = session.query(RefreshLog).filter_by(saved_query_id=qid).all()
        assert len(logs) == 1
        assert logs[0].success is True
        assert logs[0].duration_ms > 0
        session.close()

    def test_failure_creates_error_log(
        self, session_factory, demo_user
    ):
        failing_dwh = MagicMock()
        failing_dwh.execute_select.side_effect = RuntimeError("DB down")
        failing_svc = SnapshotService(
            dwh_client=failing_dwh, session_factory=session_factory
        )
        qid = _create_query(session_factory, demo_user)
        scheduler = QueryRefreshScheduler(
            snapshot_service=failing_svc,
            session_factory=session_factory,
        )
        scheduler._refresh_query(qid)  # no debe relanzar excepción
        session = session_factory()
        logs = session.query(RefreshLog).filter_by(saved_query_id=qid).all()
        assert len(logs) == 1
        assert logs[0].success is False
        assert "DB down" in logs[0].error_message
        session.close()


class TestCircuitBreaker:
    def test_deactivates_after_max_failures(self, session_factory, demo_user):
        failing_dwh = MagicMock()
        failing_dwh.execute_select.side_effect = RuntimeError("error")
        failing_svc = SnapshotService(
            dwh_client=failing_dwh, session_factory=session_factory
        )
        qid = _create_query(session_factory, demo_user)
        scheduler = QueryRefreshScheduler(
            snapshot_service=failing_svc,
            session_factory=session_factory,
            max_consecutive_failures=3,
        )
        for _ in range(3):
            scheduler._refresh_query(qid)
        # Verificar que la query fue desactivada
        session = session_factory()
        sq = session.query(SavedQuery).get(qid)
        assert sq.is_active is False
        session.close()

    def test_success_resets_failure_count(self, session_factory, demo_user):
        call_count = 0
        def side_effect(sql):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("error")
            return [{"ok": 1}]

        dwh = MagicMock()
        dwh.execute_select.side_effect = side_effect
        svc = SnapshotService(dwh_client=dwh, session_factory=session_factory)
        qid = _create_query(session_factory, demo_user)
        scheduler = QueryRefreshScheduler(
            snapshot_service=svc,
            session_factory=session_factory,
            max_consecutive_failures=5,
        )
        scheduler._refresh_query(qid)  # fallo 1
        scheduler._refresh_query(qid)  # fallo 2
        scheduler._refresh_query(qid)  # éxito → reset
        assert scheduler._get_consecutive_failures(qid) == 0
        # La query sigue activa
        session = session_factory()
        sq = session.query(SavedQuery).get(qid)
        assert sq.is_active is True
        session.close()

    def test_get_consecutive_failures_mixed(self, session_factory, demo_user):
        """Verifica el conteo de fallos consecutivos recientes."""
        qid = _create_query(session_factory, demo_user)
        session = session_factory()
        now = datetime.now(timezone.utc)
        # Log: éxito, fallo, fallo (los 2 últimos son fallos consecutivos)
        for i, success in enumerate([True, False, False]):
            log = RefreshLog(
                saved_query_id=qid,
                triggered_at=now + timedelta(seconds=i),
                finished_at=now + timedelta(seconds=i+1),
                success=success,
                duration_ms=100,
                error_message=None if success else "err",
            )
            session.add(log)
        session.commit()
        session.close()
        scheduler = QueryRefreshScheduler(
            snapshot_service=MagicMock(),
            session_factory=session_factory,
        )
        assert scheduler._get_consecutive_failures(qid) == 2


class TestGetRefreshStats:
    def test_stats_empty(self, snapshot_service, session_factory):
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        stats = scheduler.get_refresh_stats()
        assert stats["total_refreshes"] == 0
        assert stats["is_running"] is False

    def test_stats_after_refresh(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user)
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        scheduler._refresh_query(qid)
        stats = scheduler.get_refresh_stats()
        assert stats["total_refreshes"] == 1
        assert stats["successful_refreshes"] == 1
        assert stats["active_scheduled_queries"] >= 1


class TestTickIntegration:
    def test_tick_refreshes_pending(
        self, snapshot_service, session_factory, demo_user
    ):
        """El tick ejecuta queries pendientes."""
        qid = _create_query(session_factory, demo_user, refresh_interval="5 minutes")
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        scheduler._tick()
        snap = snapshot_service.get_latest_snapshot(qid)
        assert snap is not None
        assert snap.success is True

    def test_tick_skips_recently_refreshed(
        self, snapshot_service, session_factory, demo_user
    ):
        qid = _create_query(session_factory, demo_user, refresh_interval="1 hour")
        snapshot_service.execute_and_store(qid)  # refresco reciente
        scheduler = QueryRefreshScheduler(
            snapshot_service=snapshot_service,
            session_factory=session_factory,
        )
        initial_count = len(snapshot_service.get_snapshots_history(qid, limit=100))
        scheduler._tick()
        after_count = len(snapshot_service.get_snapshots_history(qid, limit=100))
        assert after_count == initial_count  # no se creó snapshot nuevo
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E4.1 | `agente_dwh/platform/scheduler.py` existe | Importable: `from agente_dwh.platform.scheduler import QueryRefreshScheduler`. |
| E4.2 | Scheduler arranca y se detiene limpiamente | `start()` → `is_running=True`. `stop()` → `is_running=False`. Sin errores. |
| E4.3 | Tick identifica queries pendientes | Una query con `refresh_interval='5 minutes'` sin snapshots aparece como pendiente. |
| E4.4 | Tick ignora queries recién refrescadas | Una query refrescada hace < 5 minutos no se re-ejecuta. |
| E4.5 | Tick ignora queries inactivas y manuales | `is_active=False` o `refresh_interval=None` no aparecen como pendientes. |
| E4.6 | Refresh exitoso crea snapshot y log | `refresh_log` con `success=True`, `query_snapshots` con datos. |
| E4.7 | Refresh fallido crea log de error | `refresh_log` con `success=False` y `error_message`. |
| E4.8 | Circuit breaker desactiva tras N fallos | Tras 5 fallos consecutivos (configurable), `is_active=False`. |
| E4.9 | Éxito resetea contador de fallos | `_get_consecutive_failures()` retorna 0 tras un éxito. |
| E4.10 | `get_refresh_stats()` retorna métricas correctas | Total, éxitos, fallos, queries activas programadas. |
| E4.11 | Job de limpieza configurado | Un segundo job que limpia snapshots antiguos cada 24h. |
| E4.12 | `ALLOWED_INTERVALS` tiene 6 intervalos | 5 min, 15 min, 30 min, 1 hora, 6 horas, 1 día con sus segundos. |
| E4.13 | `tests/test_scheduler.py` pasa | `pytest tests/test_scheduler.py -v` — 0 fallos. |
| E4.14 | Tests de fases anteriores pasan | `pytest tests/ -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Importabilidad
python -c "from agente_dwh.platform.scheduler import QueryRefreshScheduler, ALLOWED_INTERVALS; print('OK')"

# 2. Tests nuevos
pytest tests/test_scheduler.py -v

# 3. Todos los tests
pytest tests/ -v

# 4. Verificar que APScheduler está instalable
pip install "apscheduler>=3.10" --dry-run 2>&1 | head -5
```
