# Fase 3 — Dashboard Básico

## Objetivo

Crear la página "Mi Dashboard" en Streamlit que muestra widgets en un grid de columnas fijas.
Cada widget está vinculado a una `saved_query` y renderiza el último `query_snapshot`
según el `chart_type` configurado (tabla, barra, línea, KPI, pie).

## Prerequisitos

- Fase 1 completa: `saved_queries`, `dashboards`, `dashboard_widgets` en BD.
- Fase 2 completa: `SnapshotService` puede ejecutar y almacenar snapshots.
- `SavedQueriesRepo` funcional.

---

## Tareas

### T3.1 — Crear `agente_dwh/platform/dashboard_repo.py`

**Archivo:** `agente_dwh/platform/dashboard_repo.py`

```python
class DashboardRepo:
    def __init__(self, session_factory):
        """Recibe un sessionmaker de SQLAlchemy."""

    def get_or_create_default(self, user_id: int) -> Dashboard:
        """
        Retorna el dashboard con is_default=True del usuario.
        Si no existe, lo crea con title='Mi Dashboard' y is_default=True.
        """

    def get_by_id(self, dashboard_id: int, *, user_id: int) -> Dashboard | None:
        """Retorna el dashboard si pertenece al usuario."""

    def list_by_user(self, user_id: int) -> list[Dashboard]:
        """Retorna todos los dashboards del usuario, ordenados por created_at."""

    def update_title(self, dashboard_id: int, *, user_id: int, title: str) -> Dashboard | None:
        """Actualiza el título del dashboard."""

    def delete(self, dashboard_id: int, *, user_id: int) -> bool:
        """
        Elimina el dashboard y sus widgets (cascade).
        No permite eliminar el dashboard default.
        Retorna True si se eliminó.
        """

    def add_widget(
        self,
        dashboard_id: int,
        *,
        user_id: int,
        saved_query_id: int,
        pos_x: int = 0,
        pos_y: int = 0,
        width: int = 6,
        height: int = 4,
    ) -> DashboardWidget:
        """
        Agrega un widget al dashboard.
        Valida:
        - El dashboard pertenece al usuario.
        - La saved_query existe y pertenece al usuario.
        - No se excede el máximo de 15 widgets por dashboard.
        - pos_x + width <= layout_cols (12).
        """

    def remove_widget(self, widget_id: int, *, user_id: int) -> bool:
        """Elimina un widget. Valida propiedad vía dashboard.user_id."""

    def update_widget_position(
        self,
        widget_id: int,
        *,
        user_id: int,
        pos_x: int,
        pos_y: int,
        width: int,
        height: int,
    ) -> DashboardWidget | None:
        """Actualiza posición y tamaño de un widget en el grid."""

    def get_widgets_with_snapshots(
        self, dashboard_id: int, *, user_id: int
    ) -> list[dict]:
        """
        Retorna lista de dicts con la info de cada widget + último snapshot:
        [
            {
                "widget": DashboardWidget,
                "saved_query": SavedQuery,
                "snapshot": QuerySnapshot | None,
            },
            ...
        ]
        Ordenado por display_order, pos_y, pos_x.
        """
```

### T3.2 — Crear `agente_dwh/dashboard_ui/components/widget_renderer.py`

**Archivo:** `agente_dwh/dashboard_ui/components/widget_renderer.py`

Módulo con función principal:

```python
import streamlit as st
import pandas as pd
import json
from typing import Any


def render_widget(
    title: str,
    chart_type: str,
    result_data: list[dict[str, Any]] | str,
    chart_config: dict | None = None,
    executed_at: str | None = None,
) -> None:
    """
    Renderiza un widget de dashboard dentro de un st.container.

    Args:
        title: Título del widget (se muestra como subheader).
        chart_type: Uno de 'table', 'bar', 'line', 'kpi', 'pie'.
        result_data: Filas del snapshot (lista de dicts o JSON string).
        chart_config: Configuración opcional (eje_x, eje_y, color, formato).
        executed_at: Timestamp ISO del último snapshot (se muestra como caption).
    """
```

Comportamiento por `chart_type`:

| chart_type | Renderizado |
|---|---|
| `table` | `st.dataframe(df, use_container_width=True)` |
| `bar` | `st.bar_chart(df, x=eje_x, y=eje_y)` — si no hay config, usa primera columna como x, segunda como y |
| `line` | `st.line_chart(df, x=eje_x, y=eje_y)` — misma lógica |
| `kpi` | `st.metric(label=title, value=formatted_value)` — toma el primer valor de la primera fila |
| `pie` | `st.pyplot(fig)` con matplotlib pie chart — primera columna labels, segunda valores |

Si `result_data` es string, parsearlo con `json.loads()`.
Si `result_data` está vacío, mostrar `st.info("Sin datos disponibles")`.
Mostrar `executed_at` como caption al pie del widget: `"Actualizado: {executed_at}"`.

### T3.3 — Crear página "Mi Dashboard" en Streamlit

**Archivo:** Puede ser una función nueva en `web.py` o un archivo separado.

La página debe:

1. **Cargar el dashboard default** del usuario demo con `dashboard_repo.get_or_create_default()`.
2. **Obtener widgets con snapshots** usando `dashboard_repo.get_widgets_with_snapshots()`.
3. **Renderizar en grid de 2 o 3 columnas** usando `st.columns()`:
   - Para cada fila de widgets (agrupados por `pos_y`):
     - Crear columnas según `width` relativo.
     - Llamar `render_widget()` dentro de cada columna.
4. **Si no hay widgets**, mostrar un mensaje invitando a explorar y guardar consultas.
5. **Botón "Refrescar todo"**: ejecuta `snapshot_service.execute_and_store()` para cada widget y recarga la página.
6. **Sidebar del dashboard**:
   - Selector de dashboard (si hay más de uno).
   - Botón "Agregar widget" que abre un selectbox con las `saved_queries` del usuario.
   - Cada widget tiene un botón "X" para eliminar.

### T3.4 — Integrar "Agregar al dashboard" desde el flujo de guardado

Cuando el usuario guarda una query (Fase 1), después de la creación exitosa:

1. Mostrar checkbox "Agregar también al dashboard".
2. Si está marcado, llamar `dashboard_repo.add_widget()` al dashboard default.
3. El widget se coloca en la siguiente posición libre (pos_y = max(pos_y) + 1, pos_x = 0).

### T3.5 — Navegación multi-página

Configurar la navegación de Streamlit para que existan las secciones:

1. **Explorar** — flujo actual de NL → SQL.
2. **Mis Consultas** — listado CRUD (Fase 1).
3. **Dashboard** — grid de widgets (esta fase).

Usar `st.sidebar` con radio buttons o `st.navigation` según la versión de Streamlit.

---

## Casos de Prueba

### Archivo: `tests/test_dashboard_repo.py`

```python
"""Tests para el repositorio de dashboards."""

import pytest
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base, PlatformUser, SavedQuery, Dashboard, DashboardWidget,
    create_all_tables, get_session_factory,
)
from agente_dwh.platform.dashboard_repo import DashboardRepo


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    create_all_tables(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return get_session_factory(engine)


@pytest.fixture
def repo(session_factory):
    return DashboardRepo(session_factory)


@pytest.fixture
def demo_user(session_factory):
    session = session_factory()
    user = PlatformUser(username="demo", display_name="Demo", password_hash="h")
    session.add(user)
    session.commit()
    uid = user.id
    session.close()
    return uid


@pytest.fixture
def demo_query(session_factory, demo_user):
    session = session_factory()
    sq = SavedQuery(
        user_id=demo_user, title="Q1", original_question="q",
        sql_text="SELECT 1", is_active=True,
    )
    session.add(sq)
    session.commit()
    qid = sq.id
    session.close()
    return qid


class TestGetOrCreateDefault:
    def test_creates_default_if_missing(self, repo, demo_user):
        dash = repo.get_or_create_default(demo_user)
        assert dash.is_default is True
        assert dash.user_id == demo_user
        assert dash.title == "Mi Dashboard"

    def test_returns_existing_default(self, repo, demo_user):
        d1 = repo.get_or_create_default(demo_user)
        d2 = repo.get_or_create_default(demo_user)
        assert d1.id == d2.id

    def test_different_users_different_defaults(self, repo, demo_user, session_factory):
        session = session_factory()
        u2 = PlatformUser(username="u2", display_name="U2", password_hash="h")
        session.add(u2)
        session.commit()
        u2_id = u2.id
        session.close()
        d1 = repo.get_or_create_default(demo_user)
        d2 = repo.get_or_create_default(u2_id)
        assert d1.id != d2.id


class TestAddWidget:
    def test_add_widget_success(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        widget = repo.add_widget(
            dash.id, user_id=demo_user, saved_query_id=demo_query,
            pos_x=0, pos_y=0, width=6, height=4,
        )
        assert widget.id is not None
        assert widget.dashboard_id == dash.id

    def test_add_widget_max_15(self, repo, demo_user, session_factory):
        dash = repo.get_or_create_default(demo_user)
        session = session_factory()
        for i in range(15):
            sq = SavedQuery(
                user_id=demo_user, title=f"Q{i}", original_question="q",
                sql_text="SELECT 1", is_active=True,
            )
            session.add(sq)
        session.commit()
        queries = session.query(SavedQuery).filter_by(user_id=demo_user).all()
        session.close()
        for sq in queries:
            repo.add_widget(dash.id, user_id=demo_user, saved_query_id=sq.id)
        extra = SavedQuery(
            user_id=demo_user, title="Extra", original_question="q",
            sql_text="SELECT 1", is_active=True,
        )
        session = session_factory()
        session.add(extra)
        session.commit()
        extra_id = extra.id
        session.close()
        with pytest.raises(ValueError, match="máximo"):
            repo.add_widget(dash.id, user_id=demo_user, saved_query_id=extra_id)

    def test_add_widget_wrong_user(self, repo, demo_user, demo_query, session_factory):
        dash = repo.get_or_create_default(demo_user)
        with pytest.raises(ValueError):
            repo.add_widget(dash.id, user_id=9999, saved_query_id=demo_query)

    def test_add_widget_overflow_x(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        with pytest.raises(ValueError, match="grid"):
            repo.add_widget(
                dash.id, user_id=demo_user, saved_query_id=demo_query,
                pos_x=10, width=6,  # 10 + 6 = 16 > 12
            )


class TestRemoveWidget:
    def test_remove_existing(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        widget = repo.add_widget(dash.id, user_id=demo_user, saved_query_id=demo_query)
        assert repo.remove_widget(widget.id, user_id=demo_user) is True

    def test_remove_nonexistent(self, repo, demo_user):
        assert repo.remove_widget(9999, user_id=demo_user) is False

    def test_remove_wrong_user(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        widget = repo.add_widget(dash.id, user_id=demo_user, saved_query_id=demo_query)
        assert repo.remove_widget(widget.id, user_id=9999) is False


class TestUpdateWidgetPosition:
    def test_update_position(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        widget = repo.add_widget(
            dash.id, user_id=demo_user, saved_query_id=demo_query,
            pos_x=0, pos_y=0, width=6, height=4,
        )
        updated = repo.update_widget_position(
            widget.id, user_id=demo_user,
            pos_x=6, pos_y=1, width=6, height=3,
        )
        assert updated.pos_x == 6
        assert updated.pos_y == 1
        assert updated.height == 3

    def test_update_overflow_rejected(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        widget = repo.add_widget(
            dash.id, user_id=demo_user, saved_query_id=demo_query,
        )
        with pytest.raises(ValueError, match="grid"):
            repo.update_widget_position(
                widget.id, user_id=demo_user,
                pos_x=8, pos_y=0, width=6, height=4,
            )


class TestDeleteDashboard:
    def test_delete_non_default(self, repo, demo_user, session_factory):
        session = session_factory()
        dash = Dashboard(user_id=demo_user, title="Otro", is_default=False)
        session.add(dash)
        session.commit()
        dash_id = dash.id
        session.close()
        assert repo.delete(dash_id, user_id=demo_user) is True

    def test_cannot_delete_default(self, repo, demo_user):
        dash = repo.get_or_create_default(demo_user)
        with pytest.raises(ValueError, match="default"):
            repo.delete(dash.id, user_id=demo_user)


class TestGetWidgetsWithSnapshots:
    def test_returns_widget_with_none_snapshot(self, repo, demo_user, demo_query):
        dash = repo.get_or_create_default(demo_user)
        repo.add_widget(dash.id, user_id=demo_user, saved_query_id=demo_query)
        items = repo.get_widgets_with_snapshots(dash.id, user_id=demo_user)
        assert len(items) == 1
        assert items[0]["snapshot"] is None
        assert items[0]["saved_query"].id == demo_query

    def test_empty_dashboard(self, repo, demo_user):
        dash = repo.get_or_create_default(demo_user)
        items = repo.get_widgets_with_snapshots(dash.id, user_id=demo_user)
        assert items == []
```

### Archivo: `tests/test_widget_renderer.py`

```python
"""Tests para el renderizador de widgets (lógica pura, sin Streamlit)."""

import pytest
import json
from agente_dwh.dashboard_ui.components.widget_renderer import (
    _prepare_dataframe,
    _format_kpi_value,
)


class TestPrepareDataframe:
    def test_from_list_of_dicts(self):
        data = [{"canal": "Digital", "total": 100}, {"canal": "Showroom", "total": 200}]
        df = _prepare_dataframe(data)
        assert len(df) == 2
        assert list(df.columns) == ["canal", "total"]

    def test_from_json_string(self):
        data = json.dumps([{"a": 1, "b": 2}])
        df = _prepare_dataframe(data)
        assert len(df) == 1

    def test_empty_data(self):
        df = _prepare_dataframe([])
        assert df.empty

    def test_none_data(self):
        df = _prepare_dataframe(None)
        assert df.empty


class TestFormatKpiValue:
    def test_numeric(self):
        assert _format_kpi_value(1500000.0) == "$1,500,000.00"  # o formato MXN

    def test_integer(self):
        result = _format_kpi_value(42)
        assert "42" in result

    def test_string_passthrough(self):
        assert _format_kpi_value("N/A") == "N/A"

    def test_none(self):
        assert _format_kpi_value(None) == "—"
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E3.1 | `agente_dwh/platform/dashboard_repo.py` | Importable, CRUD completo de dashboards y widgets. |
| E3.2 | `agente_dwh/dashboard_ui/components/widget_renderer.py` | Función `render_widget()` renderiza los 5 chart_types. `_prepare_dataframe` y `_format_kpi_value` exportadas para tests. |
| E3.3 | Dashboard default auto-creado | `get_or_create_default()` crea el dashboard en primera visita, reutiliza en siguientes. |
| E3.4 | Máximo 15 widgets por dashboard | El widget #16 lanza `ValueError`. |
| E3.5 | Validación de grid overflow | `pos_x + width > 12` rechazado con error. |
| E3.6 | Cascade delete de widgets | Al eliminar un dashboard no-default, sus widgets se eliminan. |
| E3.7 | No se puede eliminar dashboard default | Lanza `ValueError`. |
| E3.8 | Navegación multi-página funciona | La app Streamlit tiene 3 secciones: Explorar, Mis Consultas, Dashboard. |
| E3.9 | Widget muestra último snapshot | Cada widget en el dashboard muestra datos del snapshot más reciente. |
| E3.10 | Widget sin snapshot muestra placeholder | Si no hay snapshot, muestra "Sin datos disponibles". |
| E3.11 | `tests/test_dashboard_repo.py` pasa | `pytest tests/test_dashboard_repo.py -v` — 0 fallos. |
| E3.12 | `tests/test_widget_renderer.py` pasa | `pytest tests/test_widget_renderer.py -v` — 0 fallos. |
| E3.13 | Tests de fases anteriores siguen pasando | `pytest tests/ -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Importabilidad
python -c "from agente_dwh.platform.dashboard_repo import DashboardRepo; print('OK: dashboard_repo')"
python -c "from agente_dwh.dashboard_ui.components.widget_renderer import render_widget; print('OK: widget_renderer')"

# 2. Tests nuevos
pytest tests/test_dashboard_repo.py -v
pytest tests/test_widget_renderer.py -v

# 3. Tests acumulados
pytest tests/ -v

# 4. Verificar estructura de archivos
python -c "
from pathlib import Path
required = [
    'agente_dwh/platform/dashboard_repo.py',
    'agente_dwh/dashboard_ui/__init__.py',
    'agente_dwh/dashboard_ui/components/__init__.py',
    'agente_dwh/dashboard_ui/components/widget_renderer.py',
]
for f in required:
    assert Path(f).exists(), f'Falta: {f}'
print('OK: todos los archivos existen')
"
```
