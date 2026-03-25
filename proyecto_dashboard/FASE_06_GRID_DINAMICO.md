# Fase 6 — Grid Dinámico con Drag-and-Drop

## Objetivo

Reemplazar el layout fijo de columnas del dashboard (Fase 3) por un grid dinámico
donde el usuario puede arrastrar, redimensionar y reorganizar widgets libremente.
Se usa `streamlit-elements` con el componente `dashboard.Grid` de MUI.

## Prerequisitos

- Fase 3 completa: Dashboard básico funcional con widgets y snapshots.
- Fase 5 completa: Autenticación (cada usuario tiene su layout).

---

## Tareas

### T6.1 — Agregar dependencia streamlit-elements

Agregar al `pyproject.toml`:

```toml
[project.optional-dependencies]
platform = [
    # ... deps anteriores ...
    "streamlit-elements>=0.1",
]
```

### T6.2 — Crear `agente_dwh/dashboard_ui/components/grid_layout.py`

**Archivo:** `agente_dwh/dashboard_ui/components/grid_layout.py`

Este módulo encapsula la lógica del grid drag-and-drop.

```python
from __future__ import annotations

from typing import Any, Callable


class GridLayout:
    """
    Wrapper sobre streamlit-elements dashboard.Grid.

    Responsabilidades:
    - Convertir posiciones de BD (pos_x, pos_y, width, height)
      al formato que espera dashboard.Grid (layout items).
    - Capturar eventos de drag/resize y persistir las nuevas posiciones.
    - Renderizar widgets dentro de las celdas del grid.
    """

    def __init__(
        self,
        cols: int = 12,
        row_height: int = 120,
        *,
        on_layout_change: Callable[[list[dict[str, Any]]], None] | None = None,
    ):
        """
        Args:
            cols: Columnas del grid (default 12).
            row_height: Altura en pixeles de cada fila del grid.
            on_layout_change: Callback que recibe la lista de items con
                nuevas posiciones tras un drag/resize. Formato:
                [{"i": "widget_42", "x": 0, "y": 0, "w": 6, "h": 4}, ...]
        """

    def widgets_to_layout_items(
        self, widgets: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Convierte la lista de widgets de BD al formato de layout items.

        Input (de dashboard_repo.get_widgets_with_snapshots):
        [
            {
                "widget": DashboardWidget(id=42, pos_x=0, pos_y=0, width=6, height=4),
                "saved_query": SavedQuery(...),
                "snapshot": QuerySnapshot(...) | None,
            },
            ...
        ]

        Output (formato react-grid-layout):
        [
            {"i": "widget_42", "x": 0, "y": 0, "w": 6, "h": 4},
            ...
        ]
        """

    def layout_items_to_updates(
        self, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Convierte layout items de vuelta a updates para la BD.

        Input: [{"i": "widget_42", "x": 3, "y": 1, "w": 4, "h": 3}, ...]
        Output: [{"widget_id": 42, "pos_x": 3, "pos_y": 1, "width": 4, "height": 3}, ...]
        """

    def render(
        self,
        widgets_data: list[dict[str, Any]],
        render_fn: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Renderiza el grid completo con streamlit-elements.

        1. Crea un elements context con `elements("dashboard")`.
        2. Crea un `dashboard.Grid` con:
           - layout: self.widgets_to_layout_items(widgets_data)
           - cols: self.cols
           - rowHeight: self.row_height
           - onLayoutChange: callback para capturar cambios
        3. Para cada widget, crea un `dashboard.Item` y llama render_fn
           para renderizar el contenido dentro.
        """
```

### T6.3 — Actualizar página Dashboard con grid dinámico

**En `dashboard_ui/pages/03_dashboard.py` o la función correspondiente:**

Reemplazar el layout con `st.columns()` por el `GridLayout`:

```python
from agente_dwh.dashboard_ui.components.grid_layout import GridLayout
from agente_dwh.dashboard_ui.components.widget_renderer import render_widget

def render_dashboard_page(dashboard_repo, snapshot_service, user_id):
    dash = dashboard_repo.get_or_create_default(user_id)
    widgets_data = dashboard_repo.get_widgets_with_snapshots(dash.id, user_id=user_id)

    if not widgets_data:
        st.info("Tu dashboard está vacío. Ve a Explorar para crear consultas y agregarlas.")
        return

    def on_layout_change(new_layout):
        grid = GridLayout()
        updates = grid.layout_items_to_updates(new_layout)
        for update in updates:
            dashboard_repo.update_widget_position(
                update["widget_id"],
                user_id=user_id,
                pos_x=update["pos_x"],
                pos_y=update["pos_y"],
                width=update["width"],
                height=update["height"],
            )

    grid = GridLayout(on_layout_change=on_layout_change)

    def render_single_widget(widget_data):
        sq = widget_data["saved_query"]
        snap = widget_data["snapshot"]
        if snap and snap.success:
            render_widget(
                title=sq.title,
                chart_type=sq.chart_type,
                result_data=snap.result_data,
                chart_config=sq.chart_config,
                executed_at=snap.executed_at.isoformat() if snap.executed_at else None,
            )
        else:
            st.warning(f"Sin datos: {sq.title}")

    grid.render(widgets_data, render_single_widget)
```

### T6.4 — Persistir cambios de layout automáticamente

Cuando el usuario arrastra o redimensiona un widget:

1. El callback `on_layout_change` recibe las nuevas posiciones.
2. Se llama `dashboard_repo.update_widget_position()` para cada widget cambiado.
3. Las validaciones de grid overflow (`pos_x + width <= 12`) se aplican.
4. Si alguna validación falla, se revierte al layout anterior y se muestra un warning.

### T6.5 — Modo "Editar layout" vs "Ver dashboard"

Agregar toggle en la parte superior del dashboard:

- **Modo ver** (default): widgets estáticos, no se pueden mover ni redimensionar.
  Solo se ven los datos. Auto-refresco activo.
- **Modo editar**: grid habilitado para drag-and-drop. Cada widget muestra
  botones de acción (eliminar, cambiar tamaño, cambiar chart_type).
  Auto-refresco pausado para evitar re-renders durante edición.

### T6.6 — Widget de tamaños predefinidos

Para facilitar la experiencia, ofrecer tamaños predefinidos al agregar un widget:

| Nombre | width | height | Uso ideal |
|---|---|---|---|
| Pequeño | 3 | 3 | KPI numérico |
| Mediano | 6 | 4 | Tabla o gráfica simple |
| Grande | 12 | 5 | Tabla detallada o gráfica grande |
| Medio ancho | 4 | 4 | Gráfica compacta |

### T6.7 — Fallback sin streamlit-elements

Si `streamlit-elements` no está instalado (entorno sin dependencia platform),
caer de vuelta al layout con `st.columns()` de Fase 3 sin error.

```python
try:
    from streamlit_elements import elements, dashboard, mui
    HAS_ELEMENTS = True
except ImportError:
    HAS_ELEMENTS = False
```

---

## Casos de Prueba

### Archivo: `tests/test_grid_layout.py`

```python
"""Tests para la lógica del grid layout (sin Streamlit)."""

import pytest
from agente_dwh.dashboard_ui.components.grid_layout import GridLayout


class TestWidgetsToLayoutItems:
    def test_basic_conversion(self):
        grid = GridLayout(cols=12)
        widgets_data = [
            {
                "widget": _make_widget(id=1, pos_x=0, pos_y=0, width=6, height=4),
                "saved_query": _make_query(id=10, title="Q1"),
                "snapshot": None,
            },
            {
                "widget": _make_widget(id=2, pos_x=6, pos_y=0, width=6, height=4),
                "saved_query": _make_query(id=11, title="Q2"),
                "snapshot": None,
            },
        ]
        items = grid.widgets_to_layout_items(widgets_data)
        assert len(items) == 2
        assert items[0] == {"i": "widget_1", "x": 0, "y": 0, "w": 6, "h": 4}
        assert items[1] == {"i": "widget_2", "x": 6, "y": 0, "w": 6, "h": 4}

    def test_empty_widgets(self):
        grid = GridLayout()
        assert grid.widgets_to_layout_items([]) == []


class TestLayoutItemsToUpdates:
    def test_basic_conversion(self):
        grid = GridLayout()
        items = [
            {"i": "widget_42", "x": 3, "y": 1, "w": 4, "h": 3},
            {"i": "widget_7", "x": 0, "y": 0, "w": 12, "h": 2},
        ]
        updates = grid.layout_items_to_updates(items)
        assert len(updates) == 2
        assert updates[0] == {
            "widget_id": 42, "pos_x": 3, "pos_y": 1, "width": 4, "height": 3
        }
        assert updates[1] == {
            "widget_id": 7, "pos_x": 0, "pos_y": 0, "width": 12, "height": 2
        }

    def test_parse_widget_id_from_key(self):
        grid = GridLayout()
        items = [{"i": "widget_123", "x": 0, "y": 0, "w": 6, "h": 4}]
        updates = grid.layout_items_to_updates(items)
        assert updates[0]["widget_id"] == 123

    def test_invalid_key_format_skipped(self):
        grid = GridLayout()
        items = [
            {"i": "widget_1", "x": 0, "y": 0, "w": 6, "h": 4},
            {"i": "invalid_key", "x": 0, "y": 0, "w": 6, "h": 4},
        ]
        updates = grid.layout_items_to_updates(items)
        assert len(updates) == 1

    def test_empty_items(self):
        grid = GridLayout()
        assert grid.layout_items_to_updates([]) == []


class TestGridValidation:
    def test_widget_within_bounds(self):
        grid = GridLayout(cols=12)
        items = [{"i": "widget_1", "x": 0, "y": 0, "w": 12, "h": 4}]
        updates = grid.layout_items_to_updates(items)
        assert updates[0]["pos_x"] + updates[0]["width"] <= 12

    def test_roundtrip_conversion(self):
        """widgets → layout items → updates produce mismos valores."""
        grid = GridLayout(cols=12)
        original_widget = _make_widget(id=5, pos_x=3, pos_y=2, width=6, height=3)
        widgets_data = [{
            "widget": original_widget,
            "saved_query": _make_query(id=1, title="T"),
            "snapshot": None,
        }]
        items = grid.widgets_to_layout_items(widgets_data)
        updates = grid.layout_items_to_updates(items)
        assert updates[0]["widget_id"] == 5
        assert updates[0]["pos_x"] == 3
        assert updates[0]["pos_y"] == 2
        assert updates[0]["width"] == 6
        assert updates[0]["height"] == 3


class TestPredefinedSizes:
    def test_size_presets_exist(self):
        from agente_dwh.dashboard_ui.components.grid_layout import WIDGET_SIZE_PRESETS
        assert "small" in WIDGET_SIZE_PRESETS
        assert "medium" in WIDGET_SIZE_PRESETS
        assert "large" in WIDGET_SIZE_PRESETS

    def test_size_presets_valid(self):
        from agente_dwh.dashboard_ui.components.grid_layout import WIDGET_SIZE_PRESETS
        for name, preset in WIDGET_SIZE_PRESETS.items():
            assert "width" in preset
            assert "height" in preset
            assert 1 <= preset["width"] <= 12
            assert preset["height"] >= 1


# Helpers para crear objetos mock sin ORM completo

class _MockWidget:
    def __init__(self, id, pos_x, pos_y, width, height):
        self.id = id
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.width = width
        self.height = height

class _MockQuery:
    def __init__(self, id, title):
        self.id = id
        self.title = title

def _make_widget(**kwargs):
    return _MockWidget(**kwargs)

def _make_query(**kwargs):
    return _MockQuery(**kwargs)
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E6.1 | `agente_dwh/dashboard_ui/components/grid_layout.py` | Importable, lógica de conversión widget↔layout item funcional. |
| E6.2 | `WIDGET_SIZE_PRESETS` definido | Dict con al menos `small`, `medium`, `large` con width/height válidos. |
| E6.3 | Conversión widgets→items correcta | `widgets_to_layout_items` produce formato `{"i": "widget_N", "x", "y", "w", "h"}`. |
| E6.4 | Conversión items→updates correcta | `layout_items_to_updates` extrae widget_id del key y mapea posiciones. |
| E6.5 | Roundtrip sin pérdida | widget → item → update produce los mismos valores numéricos. |
| E6.6 | Items con key inválido se ignoran | Un item `{"i": "bad_format"}` no aparece en updates. |
| E6.7 | Fallback sin streamlit-elements | Si `streamlit-elements` no está instalado, la app no crashea y usa columnas fijas. |
| E6.8 | Modo editar vs ver | Toggle funcional: en modo ver los widgets son estáticos, en modo editar se pueden mover. |
| E6.9 | Persistencia de posiciones | Tras drag/resize, las nuevas posiciones se guardan en BD via `update_widget_position`. |
| E6.10 | `tests/test_grid_layout.py` pasa | `pytest tests/test_grid_layout.py -v` — 0 fallos. |
| E6.11 | Tests de fases anteriores pasan | `pytest tests/ -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Importabilidad
python -c "from agente_dwh.dashboard_ui.components.grid_layout import GridLayout, WIDGET_SIZE_PRESETS; print('OK')"

# 2. Tests nuevos
pytest tests/test_grid_layout.py -v

# 3. Todos los tests
pytest tests/ -v

# 4. Verificar fallback sin streamlit-elements
python -c "
import sys
# Simular que streamlit_elements no existe
if 'streamlit_elements' in sys.modules:
    del sys.modules['streamlit_elements']
from agente_dwh.dashboard_ui.components.grid_layout import GridLayout
g = GridLayout()
print(f'OK: GridLayout creado sin streamlit-elements')
"
```
