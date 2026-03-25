# Fase 7 — Catálogo de Templates KPI

## Objetivo

Evolucionar `kpi_templates.py` de un stub vacío a un catálogo de consultas pre-armadas
organizadas por categoría. Los usuarios pueden navegar el catálogo, previsualizar resultados
y agregar templates directamente a su dashboard sin necesidad de usar el LLM.

## Prerequisitos

- Fase 3 completa: Dashboard funcional con widgets.
- Fase 2 completa: SnapshotService para ejecutar templates.
- `kpi_templates.py` existente (actualmente solo define `DeterministicQuery` y retorna `None`).

---

## Tareas

### T7.1 — Refactorizar `agente_dwh/kpi_templates.py`

Reemplazar el contenido actual del archivo con la estructura completa de catálogo.

**Archivo:** `agente_dwh/kpi_templates.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_CATEGORIES = ("ventas", "servicio", "seguros", "clientes")
VALID_CHART_TYPES = ("table", "bar", "line", "kpi", "pie")
VALID_REFRESH_INTERVALS = (
    "5 minutes", "15 minutes", "30 minutes", "1 hour", "6 hours", "1 day",
)


@dataclass(frozen=True)
class TemplateParam:
    """Parámetro que el usuario puede personalizar al usar el template."""
    name: str           # ej: "date_from"
    label: str          # ej: "Fecha inicio"
    param_type: str     # "date" | "text" | "select" | "number"
    default: str        # valor por defecto como string
    options: list[str] = field(default_factory=list)  # para tipo "select"


@dataclass(frozen=True)
class QueryTemplate:
    """Template de consulta KPI pre-armada."""
    id: str                                     # identificador único
    name: str                                   # nombre para mostrar al usuario
    description: str                            # descripción de qué mide
    sql: str                                    # SQL listo para ejecutar (PostgreSQL)
    default_chart_type: str                     # tipo de gráfica sugerida
    default_refresh: str                        # intervalo de refresco sugerido
    category: str                               # categoría de negocio
    parameters: list[TemplateParam] = field(default_factory=list)


# ════════════════════════════════════════════════
# CATÁLOGO DE TEMPLATES
# ════════════════════════════════════════════════

CATALOG: list[QueryTemplate] = [
    # ── VENTAS ───────────────────────────────────
    QueryTemplate(
        id="ventas_canal_mes",
        name="Ventas por canal (mes actual)",
        description="Total de ventas agrupadas por canal del mes en curso.",
        sql="""
            SELECT channel AS canal,
                   COUNT(*) AS cantidad,
                   ROUND(SUM(amount)::numeric, 2) AS total
            FROM sales
            WHERE sale_date >= date_trunc('month', CURRENT_DATE)
              AND status IN ('cerrada', 'facturada', 'entregada')
            GROUP BY channel
            ORDER BY total DESC
        """,
        default_chart_type="bar",
        default_refresh="1 hour",
        category="ventas",
    ),
    QueryTemplate(
        id="ventas_estado_acumulado",
        name="Ventas acumuladas por estado",
        description="Monto total de ventas por estado del cliente.",
        sql="""
            SELECT c.state AS estado,
                   COUNT(*) AS cantidad,
                   ROUND(SUM(s.amount)::numeric, 2) AS total
            FROM sales s
            JOIN customers c ON c.id = s.customer_id
            WHERE s.status IN ('cerrada', 'facturada', 'entregada')
            GROUP BY c.state
            ORDER BY total DESC
        """,
        default_chart_type="bar",
        default_refresh="6 hours",
        category="ventas",
    ),
    QueryTemplate(
        id="ventas_mensuales_tendencia",
        name="Tendencia de ventas mensuales",
        description="Evolución mensual de ventas en monto y cantidad.",
        sql="""
            SELECT year_month AS mes,
                   SUM(sales_count) AS cantidad,
                   ROUND(SUM(total_sales)::numeric, 2) AS monto
            FROM mv_sales_monthly
            GROUP BY year_month
            ORDER BY year_month
        """,
        default_chart_type="line",
        default_refresh="1 day",
        category="ventas",
    ),
    QueryTemplate(
        id="ventas_vendedor_mes",
        name="Ventas por vendedor (mes actual)",
        description="Ranking de vendedores por monto vendido este mes.",
        sql="""
            SELECT seller AS vendedor,
                   COUNT(*) AS ventas,
                   ROUND(SUM(amount)::numeric, 2) AS total
            FROM sales
            WHERE sale_date >= date_trunc('month', CURRENT_DATE)
              AND status IN ('cerrada', 'facturada', 'entregada')
            GROUP BY seller
            ORDER BY total DESC
        """,
        default_chart_type="bar",
        default_refresh="1 hour",
        category="ventas",
    ),
    QueryTemplate(
        id="ticket_promedio_tipo_unidad",
        name="Ticket promedio por tipo de unidad",
        description="Precio promedio de venta por tipo de vehículo.",
        sql="""
            SELECT v.unit_type AS tipo_unidad,
                   COUNT(*) AS ventas,
                   ROUND(AVG(s.amount)::numeric, 2) AS ticket_promedio
            FROM sales s
            JOIN vehicles v ON v.id = s.vehicle_id
            WHERE s.status IN ('cerrada', 'facturada', 'entregada')
            GROUP BY v.unit_type
            ORDER BY ticket_promedio DESC
        """,
        default_chart_type="bar",
        default_refresh="1 day",
        category="ventas",
    ),

    # ── SERVICIO ─────────────────────────────────
    QueryTemplate(
        id="servicios_taller_semana",
        name="Servicios por taller (última semana)",
        description="Cantidad de servicios completados por taller en los últimos 7 días.",
        sql="""
            SELECT workshop AS taller,
                   COUNT(*) AS servicios
            FROM services
            WHERE service_date >= CURRENT_DATE - INTERVAL '7 days'
              AND status IN ('completado', 'entregado', 'facturado')
            GROUP BY workshop
            ORDER BY servicios DESC
        """,
        default_chart_type="bar",
        default_refresh="30 minutes",
        category="servicio",
    ),
    QueryTemplate(
        id="citas_pendientes_hoy",
        name="Citas programadas para hoy",
        description="Citas de servicio programadas para el día actual.",
        sql="""
            SELECT c.full_name AS cliente,
                   v.vin,
                   v.brand || ' ' || v.model AS vehiculo,
                   sa.service_type AS tipo_servicio,
                   sa.workshop AS taller,
                   sa.appointment_status AS estado
            FROM service_appointments sa
            JOIN customers c ON c.id = sa.customer_id
            JOIN vehicles v ON v.id = sa.vehicle_id
            WHERE sa.appointment_date = CURRENT_DATE
            ORDER BY sa.workshop, c.full_name
        """,
        default_chart_type="table",
        default_refresh="15 minutes",
        category="servicio",
    ),
    QueryTemplate(
        id="tasa_no_show_taller",
        name="Tasa de no-show por taller",
        description="Porcentaje de citas con no-show por taller (últimos 90 días).",
        sql="""
            SELECT workshop AS taller,
                   COUNT(*) AS total_citas,
                   SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
                   ROUND(
                       (SUM(CASE WHEN appointment_status = 'no_show' THEN 1 ELSE 0 END)::numeric
                        / NULLIF(COUNT(*), 0)) * 100, 1
                   ) AS pct_no_show
            FROM service_appointments
            WHERE appointment_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY workshop
            ORDER BY pct_no_show DESC
        """,
        default_chart_type="bar",
        default_refresh="6 hours",
        category="servicio",
    ),
    QueryTemplate(
        id="ingreso_servicio_mensual",
        name="Ingreso por servicios (mensual)",
        description="Ingresos totales por servicios agrupados por mes.",
        sql="""
            SELECT to_char(service_date, 'YYYY-MM') AS mes,
                   COUNT(*) AS servicios,
                   ROUND(SUM(cost)::numeric, 2) AS ingreso
            FROM services
            WHERE status IN ('completado', 'entregado', 'facturado')
            GROUP BY 1
            ORDER BY 1
        """,
        default_chart_type="line",
        default_refresh="1 day",
        category="servicio",
    ),

    # ── SEGUROS ──────────────────────────────────
    QueryTemplate(
        id="polizas_por_vencer",
        name="Pólizas por vencer (próximos 30 días)",
        description="Pólizas activas que vencen en los próximos 30 días.",
        sql="""
            SELECT c.full_name AS cliente,
                   v.vin,
                   v.brand || ' ' || v.model AS vehiculo,
                   ip.insurer AS aseguradora,
                   ip.policy_end_date AS vencimiento,
                   ip.annual_premium AS prima
            FROM insurance_policies ip
            JOIN customers c ON c.id = ip.customer_id
            JOIN vehicles v ON v.id = ip.vehicle_id
            WHERE ip.policy_status = 'activa'
              AND ip.policy_end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            ORDER BY ip.policy_end_date
        """,
        default_chart_type="table",
        default_refresh="6 hours",
        category="seguros",
    ),
    QueryTemplate(
        id="distribucion_aseguradoras",
        name="Distribución por aseguradora",
        description="Cantidad de pólizas activas por aseguradora.",
        sql="""
            SELECT insurer AS aseguradora,
                   COUNT(*) AS polizas,
                   ROUND(SUM(annual_premium)::numeric, 2) AS prima_total
            FROM insurance_policies
            WHERE policy_status = 'activa'
            GROUP BY insurer
            ORDER BY polizas DESC
        """,
        default_chart_type="pie",
        default_refresh="1 day",
        category="seguros",
    ),
    QueryTemplate(
        id="vehiculos_sin_seguro",
        name="Vehículos sin seguro activo",
        description="Vehículos que no tienen ninguna póliza activa.",
        sql="""
            SELECT c.full_name AS cliente,
                   v.vin,
                   v.brand || ' ' || v.model AS vehiculo,
                   v.unit_type AS tipo
            FROM vehicles v
            JOIN customers c ON c.id = v.customer_id
            LEFT JOIN insurance_policies ip
              ON ip.vehicle_id = v.id AND ip.policy_status = 'activa'
            WHERE ip.id IS NULL
            ORDER BY c.full_name
        """,
        default_chart_type="table",
        default_refresh="1 day",
        category="seguros",
    ),

    # ── CLIENTES ─────────────────────────────────
    QueryTemplate(
        id="top_clientes_compras",
        name="Top 20 clientes por monto de compras",
        description="Clientes con mayor monto total de compras.",
        sql="""
            SELECT c.full_name AS cliente,
                   c.state AS estado,
                   c.segment AS segmento,
                   lc.purchases AS compras,
                   ROUND(lc.total_amount::numeric, 2) AS monto_total,
                   lc.first_sale_date AS primera_compra,
                   lc.last_sale_date AS ultima_compra
            FROM mv_customer_lifecycle lc
            JOIN customers c ON c.id = lc.customer_id
            ORDER BY lc.total_amount DESC
            LIMIT 20
        """,
        default_chart_type="table",
        default_refresh="1 day",
        category="clientes",
    ),
    QueryTemplate(
        id="distribucion_segmentos",
        name="Distribución de clientes por segmento",
        description="Cantidad de clientes en cada segmento.",
        sql="""
            SELECT segment AS segmento,
                   COUNT(*) AS clientes
            FROM customers
            GROUP BY segment
            ORDER BY clientes DESC
        """,
        default_chart_type="pie",
        default_refresh="1 day",
        category="clientes",
    ),
    QueryTemplate(
        id="clientes_recompra_rapida",
        name="Clientes con mayor frecuencia de recompra",
        description="Top 20 clientes con menor promedio de días entre compras.",
        sql="""
            SELECT c.full_name AS cliente,
                   c.segment AS segmento,
                   lc.purchases AS compras,
                   ROUND(lc.avg_repurchase_days::numeric, 0) AS dias_promedio_recompra
            FROM mv_customer_lifecycle lc
            JOIN customers c ON c.id = lc.customer_id
            WHERE lc.purchases >= 2
              AND lc.avg_repurchase_days IS NOT NULL
            ORDER BY lc.avg_repurchase_days ASC
            LIMIT 20
        """,
        default_chart_type="table",
        default_refresh="1 day",
        category="clientes",
    ),
]


def get_all_templates() -> list[QueryTemplate]:
    """Retorna todos los templates del catálogo."""
    return list(CATALOG)


def get_templates_by_category(category: str) -> list[QueryTemplate]:
    """Retorna templates de una categoría específica."""
    return [t for t in CATALOG if t.category == category]


def get_template_by_id(template_id: str) -> QueryTemplate | None:
    """Retorna un template por su id, o None si no existe."""
    for t in CATALOG:
        if t.id == template_id:
            return t
    return None


def get_categories() -> list[str]:
    """Retorna las categorías únicas disponibles en orden."""
    seen = []
    for t in CATALOG:
        if t.category not in seen:
            seen.append(t.category)
    return seen


def match_kpi_template(question: str) -> QueryTemplate | None:
    """
    Intenta encontrar un template que coincida con la pregunta del usuario.
    Busca palabras clave del nombre y descripción del template en la pregunta.
    Retorna el template con mayor coincidencia, o None si no hay match suficiente.

    Umbral: al menos 2 palabras clave del template presentes en la pregunta.
    """
```

### T7.2 — Crear página "Catálogo de KPIs" en Streamlit

Nueva sección en la navegación multi-página.

**Funcionalidad:**

1. **Filtro por categoría**: tabs o selectbox con las categorías (ventas, servicio, seguros, clientes).
2. **Cards de templates**: para cada template en la categoría seleccionada mostrar:
   - Nombre (como título).
   - Descripción.
   - Badges: chart_type sugerido, refresh sugerido, categoría.
   - Botón "Previsualizar": ejecuta el SQL contra el DWH y muestra los resultados.
   - Botón "Agregar al dashboard": crea una `saved_query` y un widget en el dashboard default.
3. **Previsualización**: al hacer click:
   - Ejecuta el SQL del template con `DwhClient.execute_select()`.
   - Muestra los resultados con el renderizador de widgets (chart_type del template).
   - Muestra el SQL generado (colapsable).
4. **Agregar al dashboard**: al hacer click:
   - Crea `saved_query` via `SavedQueriesRepo.create()` con el SQL del template.
   - Crea widget en dashboard default via `DashboardRepo.add_widget()`.
   - Ejecuta `SnapshotService.execute_and_store()` para el primer snapshot.
   - Muestra `st.success("Agregado al dashboard")`.

### T7.3 — Integrar match_kpi_template en el flujo del agente

En `web.py`, antes de llamar al LLM:

1. Llamar `match_kpi_template(question)`.
2. Si retorna un template:
   - Mostrar al usuario: "Encontré un KPI pre-definido que coincide: {name}".
   - Ofrecer: "Usar este KPI" (ejecuta SQL del template) o "Consultar al agente IA" (flujo normal).
   - Si el usuario elige el KPI, ejecutar el SQL del template directamente sin pasar por Ollama.
3. Si no hay match, continuar con el flujo normal del LLM.

### T7.4 — Documentar cómo agregar nuevos templates

Agregar un comentario bloque al inicio de `CATALOG` en `kpi_templates.py` que explique:

```python
# Para agregar un nuevo template:
# 1. Definir un QueryTemplate con id único.
# 2. SQL debe ser PostgreSQL válido de solo lectura.
# 3. Usar tablas del esquema: customers, vehicles, sales, services,
#    service_appointments, insurance_policies, mv_sales_monthly, mv_customer_lifecycle.
# 4. Probar el SQL manualmente contra la BD demo antes de agregar.
# 5. Ejecutar tests: pytest tests/test_kpi_templates.py -v
```

---

## Casos de Prueba

### Archivo: `tests/test_kpi_templates.py` (reemplaza el existente)

```python
"""Tests para el catálogo de templates KPI."""

import pytest
from agente_dwh.kpi_templates import (
    CATALOG,
    VALID_CATEGORIES,
    VALID_CHART_TYPES,
    VALID_REFRESH_INTERVALS,
    QueryTemplate,
    TemplateParam,
    get_all_templates,
    get_templates_by_category,
    get_template_by_id,
    get_categories,
    match_kpi_template,
)
from agente_dwh.sql_guard import validate_read_only_sql


class TestCatalogIntegrity:
    def test_catalog_not_empty(self):
        assert len(CATALOG) >= 10

    def test_all_ids_unique(self):
        ids = [t.id for t in CATALOG]
        assert len(ids) == len(set(ids)), f"IDs duplicados: {[i for i in ids if ids.count(i) > 1]}"

    def test_all_have_required_fields(self):
        for t in CATALOG:
            assert t.id, f"Template sin id"
            assert t.name, f"Template {t.id} sin name"
            assert t.description, f"Template {t.id} sin description"
            assert t.sql.strip(), f"Template {t.id} sin sql"
            assert t.default_chart_type, f"Template {t.id} sin chart_type"
            assert t.default_refresh, f"Template {t.id} sin refresh"
            assert t.category, f"Template {t.id} sin category"

    def test_all_chart_types_valid(self):
        for t in CATALOG:
            assert t.default_chart_type in VALID_CHART_TYPES, (
                f"Template {t.id}: chart_type '{t.default_chart_type}' no válido"
            )

    def test_all_refresh_intervals_valid(self):
        for t in CATALOG:
            assert t.default_refresh in VALID_REFRESH_INTERVALS, (
                f"Template {t.id}: refresh '{t.default_refresh}' no válido"
            )

    def test_all_categories_valid(self):
        for t in CATALOG:
            assert t.category in VALID_CATEGORIES, (
                f"Template {t.id}: category '{t.category}' no válida"
            )

    def test_all_sql_passes_guard(self):
        """Cada SQL del catálogo debe pasar validate_read_only_sql."""
        for t in CATALOG:
            try:
                validate_read_only_sql(t.sql)
            except ValueError as e:
                pytest.fail(f"Template {t.id} no pasa sql_guard: {e}")

    def test_all_sql_starts_with_select(self):
        for t in CATALOG:
            stripped = t.sql.strip().upper()
            assert stripped.startswith("SELECT") or stripped.startswith("WITH"), (
                f"Template {t.id}: SQL no inicia con SELECT/WITH"
            )

    def test_all_categories_represented(self):
        cats = {t.category for t in CATALOG}
        for cat in VALID_CATEGORIES:
            assert cat in cats, f"Categoría '{cat}' sin templates"


class TestGetAllTemplates:
    def test_returns_full_catalog(self):
        result = get_all_templates()
        assert len(result) == len(CATALOG)

    def test_returns_copies(self):
        """Modificar la lista retornada no afecta el catálogo."""
        result = get_all_templates()
        result.clear()
        assert len(CATALOG) > 0


class TestGetTemplatesByCategory:
    def test_ventas(self):
        templates = get_templates_by_category("ventas")
        assert len(templates) >= 3
        assert all(t.category == "ventas" for t in templates)

    def test_servicio(self):
        templates = get_templates_by_category("servicio")
        assert len(templates) >= 2
        assert all(t.category == "servicio" for t in templates)

    def test_seguros(self):
        templates = get_templates_by_category("seguros")
        assert len(templates) >= 2
        assert all(t.category == "seguros" for t in templates)

    def test_clientes(self):
        templates = get_templates_by_category("clientes")
        assert len(templates) >= 2
        assert all(t.category == "clientes" for t in templates)

    def test_nonexistent_category(self):
        assert get_templates_by_category("inexistente") == []


class TestGetTemplateById:
    def test_existing(self):
        t = get_template_by_id("ventas_canal_mes")
        assert t is not None
        assert t.id == "ventas_canal_mes"

    def test_nonexistent(self):
        assert get_template_by_id("no_existe_xyz") is None


class TestGetCategories:
    def test_returns_all(self):
        cats = get_categories()
        assert set(cats) == set(VALID_CATEGORIES)

    def test_preserves_order(self):
        cats = get_categories()
        assert isinstance(cats, list)
        assert len(cats) == len(set(cats))  # sin duplicados


class TestMatchKpiTemplate:
    def test_matches_ventas_por_canal(self):
        result = match_kpi_template("¿Cuáles son las ventas por canal este mes?")
        assert result is not None
        assert result.category == "ventas"

    def test_matches_polizas_por_vencer(self):
        result = match_kpi_template("Pólizas que están por vencer")
        assert result is not None
        assert "seguros" == result.category or "poliza" in result.id

    def test_matches_citas_hoy(self):
        result = match_kpi_template("¿Qué citas hay programadas para hoy?")
        assert result is not None

    def test_no_match_gibberish(self):
        result = match_kpi_template("asdfghjkl")
        assert result is None

    def test_no_match_empty(self):
        result = match_kpi_template("")
        assert result is None

    def test_no_match_unrelated(self):
        result = match_kpi_template("¿Cuál es el clima en Cancún?")
        assert result is None


class TestTemplateParam:
    def test_basic_param(self):
        param = TemplateParam(
            name="date_from",
            label="Fecha inicio",
            param_type="date",
            default="2025-01-01",
        )
        assert param.name == "date_from"
        assert param.options == []

    def test_select_param(self):
        param = TemplateParam(
            name="estado",
            label="Estado",
            param_type="select",
            default="CDMX",
            options=["CDMX", "Jalisco", "Nuevo Leon"],
        )
        assert len(param.options) == 3
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E7.1 | `kpi_templates.py` refactorizado | Contiene al menos 15 templates en 4 categorías. |
| E7.2 | Todos los IDs únicos | No hay templates con el mismo `id`. |
| E7.3 | Todos los SQL pasan sql_guard | `validate_read_only_sql` no lanza error para ningún template. |
| E7.4 | Todas las categorías representadas | `ventas`, `servicio`, `seguros`, `clientes` tienen al menos 2 templates cada una. |
| E7.5 | `chart_type` y `refresh` válidos | Todos usan valores del conjunto permitido. |
| E7.6 | `get_all_templates()` retorna catálogo completo | Longitud igual a `len(CATALOG)`. |
| E7.7 | `get_templates_by_category()` filtra correctamente | Solo retorna templates de la categoría solicitada. |
| E7.8 | `get_template_by_id()` funciona | Retorna template correcto o None. |
| E7.9 | `match_kpi_template()` funciona | Encuentra templates relevantes para preguntas relacionadas. Retorna None para preguntas irrelevantes. |
| E7.10 | Página "Catálogo" en Streamlit | Navegación por categorías, previsualización, botón agregar al dashboard. |
| E7.11 | Integración con flujo del agente | Si hay match, se ofrece el KPI como alternativa antes de llamar al LLM. |
| E7.12 | `tests/test_kpi_templates.py` pasa | `pytest tests/test_kpi_templates.py -v` — 0 fallos. |
| E7.13 | Tests de fases anteriores pasan | `pytest tests/ -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Importabilidad
python -c "
from agente_dwh.kpi_templates import (
    CATALOG, get_all_templates, get_templates_by_category,
    get_template_by_id, get_categories, match_kpi_template,
    VALID_CATEGORIES, VALID_CHART_TYPES, VALID_REFRESH_INTERVALS,
)
print(f'OK: {len(CATALOG)} templates en {len(get_categories())} categorías')
"

# 2. Validar todos los SQL contra sql_guard
python -c "
from agente_dwh.kpi_templates import CATALOG
from agente_dwh.sql_guard import validate_read_only_sql
errors = []
for t in CATALOG:
    try:
        validate_read_only_sql(t.sql)
    except ValueError as e:
        errors.append(f'{t.id}: {e}')
if errors:
    print('ERRORES:')
    for e in errors:
        print(f'  {e}')
    exit(1)
print(f'OK: {len(CATALOG)} templates pasan sql_guard')
"

# 3. Tests nuevos
pytest tests/test_kpi_templates.py -v

# 4. Todos los tests
pytest tests/ -v
```
