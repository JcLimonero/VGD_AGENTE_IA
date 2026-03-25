# Fase 2 — Servicio de Snapshots

## Objetivo

Crear el servicio que ejecuta una consulta guardada contra el DWH, serializa los resultados
como JSON y los almacena en `query_snapshots`. Incluye ejecución manual desde la UI
y limpieza automática de snapshots antiguos.

## Prerequisitos

- Fase 1 completa: tablas `saved_queries` y `query_snapshots` creadas, `SavedQueriesRepo` funcional.
- `DwhClient` funcional (`agente_dwh/dwh.py`).
- `sql_guard.validate_read_only_sql` funcional.

---

## Tareas

### T2.1 — Crear `agente_dwh/platform/snapshot_service.py`

**Archivo:** `agente_dwh/platform/snapshot_service.py`

```python
from __future__ import annotations
from typing import Any
from agente_dwh.dwh import DwhClient
from agente_dwh.sql_guard import validate_read_only_sql
from agente_dwh.observability import StopWatch, record_query_event


class SnapshotService:
    """Ejecuta queries guardadas y almacena resultados como snapshots."""

    def __init__(self, dwh_client: DwhClient, session_factory):
        """
        Args:
            dwh_client: Cliente DWH para ejecutar SQL.
            session_factory: SQLAlchemy sessionmaker para persistir snapshots.
        """

    def execute_and_store(self, saved_query_id: int) -> QuerySnapshot:
        """
        1. Carga la saved_query por id desde la BD.
        2. Valida el SQL con validate_read_only_sql (re-validación obligatoria).
        3. Ejecuta el SQL con dwh_client.execute_select().
        4. Serializa las filas a JSON (lista de dicts).
        5. Inserta un registro en query_snapshots con:
           - result_data: JSON de filas
           - row_count: len(rows)
           - executed_at: now()
           - duration_ms: tiempo medido con StopWatch
           - success: True
        6. Registra evento en observability con source="snapshot".
        7. Retorna el QuerySnapshot creado.

        Si falla la ejecución SQL:
        - Inserta snapshot con success=False y error_message=str(exc).
        - Registra evento de fallo en observability.
        - Relanza la excepción.

        Si la saved_query no existe o is_active=False:
        - Lanza ValueError("Consulta no encontrada o inactiva").
        """

    def get_latest_snapshot(self, saved_query_id: int) -> QuerySnapshot | None:
        """
        Retorna el snapshot más reciente (por executed_at DESC) de la query,
        o None si no hay snapshots.
        """

    def get_snapshots_history(
        self, saved_query_id: int, *, limit: int = 10
    ) -> list[QuerySnapshot]:
        """
        Retorna los últimos N snapshots de la query, ordenados por executed_at DESC.
        """

    def cleanup_old_snapshots(
        self, saved_query_id: int, *, keep_last: int = 100
    ) -> int:
        """
        Elimina snapshots antiguos de una query, conservando los últimos `keep_last`.
        Retorna la cantidad de snapshots eliminados.
        """

    def cleanup_all_old_snapshots(self, *, keep_last: int = 100) -> int:
        """
        Ejecuta cleanup_old_snapshots para TODAS las saved_queries.
        Retorna el total de snapshots eliminados.
        """
```

### T2.2 — Serialización segura de resultados

Los resultados de `DwhClient.execute_select()` son `list[dict[str, Any]]`.
Los valores pueden incluir tipos no serializables en JSON nativo:

- `datetime` / `date` → convertir a ISO string.
- `Decimal` → convertir a `float`.
- `bytes` → convertir a base64 string.
- `None` → mantener como `null`.

Crear función auxiliar `_serialize_rows(rows: list[dict]) -> list[dict]` que recorra
cada valor y lo convierta a un tipo JSON-safe.

### T2.3 — Integrar ejecución manual en la página "Mis Consultas"

En la página "Mis Consultas" (de Fase 1), el botón "Ejecutar ahora" debe:

1. Llamar `snapshot_service.execute_and_store(query_id)`.
2. Mostrar los resultados con `st.dataframe()`.
3. Mostrar `duration_ms` y `row_count` como métricas.
4. Si falla, mostrar `st.error(error_message)`.

### T2.4 — Integrar snapshot automático al guardar

Cuando el usuario guarda una query nueva (Fase 1, T1.6), ejecutar automáticamente
`snapshot_service.execute_and_store()` para generar el primer snapshot.
Si falla la ejecución, la query se guarda igualmente pero se muestra un warning.

---

## Casos de Prueba

### Archivo: `tests/test_snapshot_service.py`

```python
"""Tests para el servicio de snapshots."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base, PlatformUser, SavedQuery, QuerySnapshot,
    create_all_tables, get_session_factory,
)
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
def demo_user_and_query(session_factory):
    """Crea usuario demo y una query guardada, retorna (user_id, query_id, sql_text)."""
    session = session_factory()
    user = PlatformUser(username="demo", display_name="Demo", password_hash="h")
    session.add(user)
    session.commit()
    sq = SavedQuery(
        user_id=user.id,
        title="Ventas",
        original_question="ventas totales",
        sql_text="SELECT SUM(amount) AS total FROM sales",
        is_active=True,
    )
    session.add(sq)
    session.commit()
    result = (user.id, sq.id, sq.sql_text)
    session.close()
    return result


@pytest.fixture
def mock_dwh():
    """DwhClient mock que retorna filas fijas."""
    dwh = MagicMock()
    dwh.execute_select.return_value = [
        {"total": 1500000.0},
    ]
    return dwh


@pytest.fixture
def service(mock_dwh, session_factory):
    return SnapshotService(dwh_client=mock_dwh, session_factory=session_factory)


class TestExecuteAndStore:
    def test_success_creates_snapshot(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        snapshot = service.execute_and_store(query_id)
        assert snapshot.success is True
        assert snapshot.row_count == 1
        assert snapshot.duration_ms >= 0
        assert snapshot.error_message is None
        assert isinstance(snapshot.result_data, (list, str))

    def test_stores_result_data_as_json(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        snapshot = service.execute_and_store(query_id)
        import json
        data = json.loads(snapshot.result_data) if isinstance(snapshot.result_data, str) else snapshot.result_data
        assert isinstance(data, list)
        assert data[0]["total"] == 1500000.0

    def test_failure_creates_error_snapshot(self, mock_dwh, session_factory, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        mock_dwh.execute_select.side_effect = RuntimeError("connection refused")
        svc = SnapshotService(dwh_client=mock_dwh, session_factory=session_factory)
        with pytest.raises(RuntimeError, match="connection refused"):
            svc.execute_and_store(query_id)
        # Verificar que se guardó snapshot con error
        session = session_factory()
        snap = session.query(QuerySnapshot).filter_by(saved_query_id=query_id).first()
        assert snap is not None
        assert snap.success is False
        assert "connection refused" in snap.error_message
        session.close()

    def test_inactive_query_raises(self, service, session_factory, demo_user_and_query):
        user_id, query_id, _ = demo_user_and_query
        session = session_factory()
        sq = session.query(SavedQuery).get(query_id)
        sq.is_active = False
        session.commit()
        session.close()
        with pytest.raises(ValueError, match="inactiva"):
            service.execute_and_store(query_id)

    def test_nonexistent_query_raises(self, service):
        with pytest.raises(ValueError, match="no encontrada"):
            service.execute_and_store(99999)

    def test_revalidates_sql(self, session_factory, mock_dwh):
        """Si alguien modificó el SQL en BD a algo peligroso, debe fallar."""
        session = session_factory()
        user = PlatformUser(username="hacker", display_name="H", password_hash="h")
        session.add(user)
        session.commit()
        sq = SavedQuery(
            user_id=user.id,
            title="Hack",
            original_question="hack",
            sql_text="DROP TABLE sales",  # SQL peligroso inyectado directamente en BD
            is_active=True,
        )
        session.add(sq)
        session.commit()
        query_id = sq.id
        session.close()
        svc = SnapshotService(dwh_client=mock_dwh, session_factory=session_factory)
        with pytest.raises(ValueError):
            svc.execute_and_store(query_id)


class TestGetLatestSnapshot:
    def test_returns_latest(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        service.execute_and_store(query_id)
        service.execute_and_store(query_id)
        latest = service.get_latest_snapshot(query_id)
        assert latest is not None
        history = service.get_snapshots_history(query_id, limit=10)
        assert latest.id == history[0].id

    def test_returns_none_if_no_snapshots(self, service):
        assert service.get_latest_snapshot(99999) is None


class TestGetSnapshotsHistory:
    def test_respects_limit(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        for _ in range(5):
            service.execute_and_store(query_id)
        history = service.get_snapshots_history(query_id, limit=3)
        assert len(history) == 3

    def test_ordered_desc(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        for _ in range(3):
            service.execute_and_store(query_id)
        history = service.get_snapshots_history(query_id, limit=10)
        for i in range(len(history) - 1):
            assert history[i].executed_at >= history[i + 1].executed_at


class TestCleanup:
    def test_cleanup_keeps_last_n(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        for _ in range(10):
            service.execute_and_store(query_id)
        deleted = service.cleanup_old_snapshots(query_id, keep_last=3)
        assert deleted == 7
        remaining = service.get_snapshots_history(query_id, limit=100)
        assert len(remaining) == 3

    def test_cleanup_nothing_to_delete(self, service, demo_user_and_query):
        _, query_id, _ = demo_user_and_query
        service.execute_and_store(query_id)
        deleted = service.cleanup_old_snapshots(query_id, keep_last=10)
        assert deleted == 0

    def test_cleanup_all(self, service, session_factory, demo_user_and_query):
        user_id, query_id, _ = demo_user_and_query
        session = session_factory()
        sq2 = SavedQuery(
            user_id=user_id, title="Q2", original_question="q",
            sql_text="SELECT 1", is_active=True,
        )
        session.add(sq2)
        session.commit()
        q2_id = sq2.id
        session.close()
        for _ in range(5):
            service.execute_and_store(query_id)
            service.execute_and_store(q2_id)
        total_deleted = service.cleanup_all_old_snapshots(keep_last=2)
        assert total_deleted == 6  # 3 de cada query


class TestSerializeRows:
    def test_datetime_serialized(self, service, session_factory):
        """Verifica que datetime en filas se serializa a string ISO."""
        from datetime import datetime, date
        from decimal import Decimal
        from agente_dwh.platform.snapshot_service import _serialize_rows
        rows = [
            {
                "fecha": datetime(2025, 6, 15, 10, 30),
                "dia": date(2025, 6, 15),
                "monto": Decimal("1500.50"),
                "nombre": "Test",
                "nulo": None,
            }
        ]
        result = _serialize_rows(rows)
        assert isinstance(result[0]["fecha"], str)
        assert isinstance(result[0]["dia"], str)
        assert isinstance(result[0]["monto"], float)
        assert result[0]["nombre"] == "Test"
        assert result[0]["nulo"] is None
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E2.1 | `agente_dwh/platform/snapshot_service.py` existe | Importable: `from agente_dwh.platform.snapshot_service import SnapshotService` sin error. |
| E2.2 | `execute_and_store` funciona con query activa | Crea snapshot con `success=True`, `row_count` correcto, `result_data` serializable como JSON. |
| E2.3 | `execute_and_store` maneja fallos | Crea snapshot con `success=False` y `error_message` al fallar SQL. |
| E2.4 | Re-validación de SQL | Si el `sql_text` en BD es `DROP TABLE x`, lanza `ValueError` (no lo ejecuta). |
| E2.5 | Query inactiva rechazada | `execute_and_store` con query `is_active=False` lanza `ValueError`. |
| E2.6 | `get_latest_snapshot` retorna el más reciente | Tras 3 ejecuciones, retorna la tercera. |
| E2.7 | `get_snapshots_history` respeta limit y orden | Retorna máximo N snapshots, ordenados DESC por `executed_at`. |
| E2.8 | `cleanup_old_snapshots` conserva últimos N | Con 10 snapshots y `keep_last=3`, elimina 7 y quedan 3. |
| E2.9 | `cleanup_all_old_snapshots` limpia todas las queries | Limpia snapshots de todas las queries respetando `keep_last`. |
| E2.10 | Serialización de tipos especiales | `datetime`, `date`, `Decimal` se serializan correctamente a tipos JSON-safe. |
| E2.11 | `tests/test_snapshot_service.py` pasa | `pytest tests/test_snapshot_service.py -v` — 0 fallos. |
| E2.12 | Tests de Fase 1 siguen pasando | `pytest tests/test_platform_models.py tests/test_saved_queries_repo.py -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Verificar importabilidad
python -c "from agente_dwh.platform.snapshot_service import SnapshotService, _serialize_rows; print('OK')"

# 2. Ejecutar tests de Fase 2
pytest tests/test_snapshot_service.py -v

# 3. Ejecutar tests de Fase 1 (no regresión)
pytest tests/test_platform_models.py tests/test_saved_queries_repo.py -v

# 4. Ejecutar todos los tests
pytest tests/ -v
```
