# Arquitectura — Dashboard Dinámico con Consultas Persistentes

## Índice

1. [Visión General](#1-visión-general)
2. [Diagrama de Arquitectura](#2-diagrama-de-arquitectura)
3. [Modelo de Datos de Plataforma](#3-modelo-de-datos-de-plataforma)
4. [Estructura de Módulos Python](#4-estructura-de-módulos-python)
5. [Flujo de Vida de una Consulta](#5-flujo-de-vida-de-una-consulta)
6. [Scheduler de Refresco](#6-scheduler-de-refresco)
7. [Integración con kpi_templates.py](#7-integración-con-kpi_templatespy)
8. [Estrategia de UI](#8-estrategia-de-ui)
9. [Seguridad](#9-seguridad)
10. [Fases de Implementación](#10-fases-de-implementación)
11. [Dependencias Nuevas](#11-dependencias-nuevas)

---

## 1. Visión General

### Estado actual

El sistema funciona de forma **reactiva**: el usuario hace una pregunta en lenguaje natural,
el agente genera SQL, lo ejecuta contra el DWH y muestra el resultado. Cada consulta es
**efímera** — se hace, se ve, y se pierde (salvo el historial del chat de sesión).

### Objetivo final

Evolucionar a un **dashboard dinámico y personalizable por usuario** donde:

1. El usuario explora datos con preguntas en lenguaje natural (flujo actual).
2. Cuando encuentra una consulta útil, la **guarda como "consulta base"**.
3. Le asigna un nombre, tipo de gráfica y **frecuencia de refresco** (cada 5 min, 1 hora, diario, etc.).
4. La coloca en un **dashboard tipo grid** que puede reorganizar libremente.
5. Un **scheduler** ejecuta las queries según la cadencia, almacena los resultados como snapshots.
6. El dashboard siempre muestra el **último snapshot**, sin esperar ejecución en tiempo real.

En esencia: convertir el agente en un **generador de widgets de BI personalizados**, donde el LLM
es el puente entre la intención del usuario y el SQL, pero una vez que el SQL está validado y el
usuario lo "fija", se vuelve una consulta programada que alimenta un panel visual.

### Componentes que ya existen y sirven de base

| Componente | Archivo | Rol en la nueva arquitectura |
|---|---|---|
| Agente NL→SQL | `agent.py` | Motor de exploración — no cambia |
| Guard SQL | `sql_guard.py` | Valida que todo SQL sea de solo lectura — crítico para ejecución automática |
| Cliente DWH | `dwh.py` | Ejecuta queries con caché y normalización — el scheduler lo reutiliza |
| Observabilidad | `observability.py` | Se integra con el `refresh_log` del scheduler |
| KPI Templates | `kpi_templates.py` | Evoluciona a catálogo de consultas pre-armadas |
| Config | `config.py` | Se extiende con `PLATFORM_DB_URL` |
| Web UI | `web.py` | Se convierte en la página "Exploración" del multi-page |

---

## 2. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO                                        │
│                                                                             │
│   ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐  │
│   │  Exploración  │    │  Mis Consultas    │    │  Mi Dashboard            │  │
│   │  (NL → SQL)   │───▶│  (CRUD guardadas) │───▶│  (grid de widgets)       │  │
│   │  [ya existe]  │    │  [nuevo]          │    │  [nuevo]                 │  │
│   └──────────────┘    └──────────────────┘    └──────────────────────────┘  │
└─────────────────────────────┬───────────────────────────┬──────────────────┘
                              │                           │
                    ┌─────────▼─────────┐       ┌────────▼────────────┐
                    │   API / Backend    │       │   Scheduler         │
                    │   (FastAPI)        │       │   (APScheduler)     │
                    │                   │       │                     │
                    │  • auth (JWT)     │       │  • Ejecuta queries  │
                    │  • saved queries  │       │    según cadencia   │
                    │  • dashboard CRUD │       │  • Guarda snapshot  │
                    │  • agent proxy    │       │    de resultados    │
                    │  • snapshots API  │       │  • Emite alertas    │
                    └────────┬──────────┘       └────────┬────────────┘
                             │                           │
              ┌──────────────▼───────────────────────────▼──────────────┐
              │                    PostgreSQL                            │
              │                                                         │
              │  ┌─────────────────┐  ┌──────────────────────────────┐  │
              │  │ Tablas de        │  │ Tablas de negocio (DWH)      │  │
              │  │ plataforma       │  │ [ya existen]                 │  │
              │  │ [nuevas]         │  │ customers, vehicles, sales…  │  │
              │  │                  │  │                              │  │
              │  │ • users          │  │                              │  │
              │  │ • saved_queries  │  │                              │  │
              │  │ • dashboards     │  │                              │  │
              │  │ • dashboard_     │  │                              │  │
              │  │   widgets        │  │                              │  │
              │  │ • query_         │  │                              │  │
              │  │   snapshots      │  │                              │  │
              │  │ • refresh_log    │  │                              │  │
              │  └─────────────────┘  └──────────────────────────────┘  │
              └─────────────────────────────────────────────────────────┘
```

---

## 3. Modelo de Datos de Plataforma

Todas las tablas nuevas van en el schema `platform` para separación lógica
(o en `public` con prefijo `platform_` si se prefiere simplicidad).

### 3.1 Usuarios

```sql
CREATE TABLE platform_users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'viewer',   -- viewer | editor | admin
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
```

### 3.2 Consultas Guardadas

```sql
CREATE TABLE saved_queries (
    id                SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES platform_users(id),
    title             TEXT NOT NULL,
    original_question TEXT NOT NULL,          -- pregunta en NL que generó el SQL
    sql_text          TEXT NOT NULL,          -- SQL validado por sql_guard
    chart_type        TEXT NOT NULL DEFAULT 'table',  -- table | bar | line | kpi | pie
    chart_config      JSONB NOT NULL DEFAULT '{}',    -- ejes, colores, formato MXN, etc.
    refresh_interval  INTERVAL,              -- NULL = manual; '5 minutes', '1 hour', '1 day'
    is_active         BOOLEAN NOT NULL DEFAULT true,
    tags              TEXT[] DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sq_user ON saved_queries(user_id);
CREATE INDEX idx_sq_active_refresh ON saved_queries(is_active, refresh_interval)
    WHERE is_active AND refresh_interval IS NOT NULL;
```

### 3.3 Dashboards

```sql
CREATE TABLE dashboards (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES platform_users(id),
    title       TEXT NOT NULL DEFAULT 'Mi Dashboard',
    is_default  BOOLEAN NOT NULL DEFAULT false,
    layout_cols INT NOT NULL DEFAULT 12,     -- grid de 12 columnas (estilo CSS grid)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.4 Widgets del Dashboard

```sql
CREATE TABLE dashboard_widgets (
    id              SERIAL PRIMARY KEY,
    dashboard_id    INT NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    pos_x           INT NOT NULL DEFAULT 0,    -- columna en el grid (0-11)
    pos_y           INT NOT NULL DEFAULT 0,    -- fila en el grid
    width           INT NOT NULL DEFAULT 6,    -- ancho en columnas (1-12)
    height          INT NOT NULL DEFAULT 4,    -- alto en unidades de fila
    display_order   INT NOT NULL DEFAULT 0,
    widget_config   JSONB NOT NULL DEFAULT '{}',  -- overrides de chart_config
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dw_dashboard ON dashboard_widgets(dashboard_id);
```

### 3.5 Snapshots de Resultados

```sql
CREATE TABLE query_snapshots (
    id              SERIAL PRIMARY KEY,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    result_data     JSONB NOT NULL,           -- filas como array de objetos
    row_count       INT NOT NULL,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms     DOUBLE PRECISION NOT NULL,
    success         BOOLEAN NOT NULL DEFAULT true,
    error_message   TEXT
);

CREATE INDEX idx_qs_query_time ON query_snapshots(saved_query_id, executed_at DESC);
CREATE INDEX idx_qs_cleanup ON query_snapshots(saved_query_id, executed_at);
```

### 3.6 Log de Refrescos

```sql
CREATE TABLE refresh_log (
    id              SERIAL PRIMARY KEY,
    saved_query_id  INT NOT NULL REFERENCES saved_queries(id) ON DELETE CASCADE,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    success         BOOLEAN,
    duration_ms     DOUBLE PRECISION,
    error_message   TEXT
);
```

### Diagrama ER simplificado

```
platform_users ──1:N──▶ saved_queries ──1:N──▶ query_snapshots
       │                      │
       │                      └──1:N──▶ refresh_log
       │
       └──1:N──▶ dashboards ──1:N──▶ dashboard_widgets ──N:1──▶ saved_queries
```

---

## 4. Estructura de Módulos Python

```
agente_dwh/
├── __init__.py
├── agent.py                    # [ya existe] — sin cambios
├── dwh.py                      # [ya existe] — sin cambios
├── sql_guard.py                # [ya existe] — sin cambios
├── llm_local.py                # [ya existe] — sin cambios
├── observability.py            # [ya existe] — se integra con refresh_log
├── config.py                   # [ya existe] — se extiende con PLATFORM_DB_URL
├── demo_data.py                # [ya existe] — sin cambios
├── forecast.py                 # [ya existe] — sin cambios
├── kpi_templates.py            # [ya existe] — evoluciona a catálogo de templates
├── sql_vehicle_context.py      # [ya existe] — sin cambios
├── web.py                      # [ya existe] — se convierte en página "Exploración"
│
├── platform/                   # ══════ NUEVO ══════
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy ORM: platform_users, saved_queries,
│   │                           #   dashboards, dashboard_widgets, query_snapshots,
│   │                           #   refresh_log
│   ├── auth.py                 # Autenticación JWT (login, hash, middleware)
│   ├── saved_queries_repo.py   # CRUD de saved_queries + snapshots
│   ├── dashboard_repo.py       # CRUD de dashboards + widgets
│   ├── scheduler.py            # APScheduler — ejecuta queries según refresh_interval
│   ├── snapshot_service.py     # Ejecuta query → guarda snapshot → limpia antiguos
│   └── api.py                  # FastAPI app con todos los endpoints
│
├── dashboard_ui/               # ══════ NUEVO ══════
│   ├── __init__.py
│   ├── app.py                  # Streamlit multi-page: punto de entrada principal
│   ├── pages/
│   │   ├── 01_explorar.py      # Flujo actual de NL → SQL → resultado
│   │   │                       #   + botón "Guardar al dashboard"
│   │   ├── 02_mis_consultas.py # Lista de saved_queries del usuario
│   │   │                       #   editar título, intervalo, chart_type
│   │   │                       #   activar / desactivar / eliminar
│   │   └── 03_dashboard.py     # Grid de widgets con auto-refresco
│   │                           #   lee último snapshot de cada widget
│   └── components/
│       ├── widget_renderer.py  # Renderiza un widget según chart_type
│       │                       #   (tabla, barra, línea, KPI, pie)
│       ├── query_saver.py      # Diálogo modal "Guardar esta consulta"
│       │                       #   título, chart_type, refresh_interval
│       └── grid_layout.py      # Wrapper de streamlit-elements para
│                               #   grid drag-and-drop (MUI Dashboard)
```

### Responsabilidad de cada módulo nuevo

| Módulo | Responsabilidad |
|---|---|
| `models.py` | Define tablas ORM con SQLAlchemy 2.0 (DeclarativeBase). Centraliza la creación de tablas con `Base.metadata.create_all()`. |
| `auth.py` | Hashea passwords con bcrypt, genera/valida tokens JWT, middleware de FastAPI para proteger endpoints. |
| `saved_queries_repo.py` | `create()`, `list_by_user()`, `update()`, `delete()`, `get_with_latest_snapshot()`. Siempre re-valida SQL con `sql_guard` antes de guardar. |
| `dashboard_repo.py` | `create_dashboard()`, `add_widget()`, `update_layout()`, `remove_widget()`. Gestiona posiciones del grid. |
| `scheduler.py` | Arranca `BackgroundScheduler` con un job maestro que cada 60s busca queries vencidas y las ejecuta. Circuit breaker integrado. |
| `snapshot_service.py` | Ejecuta SQL vía `DwhClient`, serializa filas a JSONB, inserta en `query_snapshots`, limpia snapshots antiguos (retención configurable). |
| `api.py` | FastAPI con routers: `/auth`, `/queries`, `/dashboards`, `/snapshots`. El frontend (Streamlit o futuro React) consume esta API. |

---

## 5. Flujo de Vida de una Consulta

```
                                  ┌─────────────────────────┐
    ① Usuario pregunta en NL ────▶│  Exploración (web.py)   │
                                  │  DwhAgent.answer()      │
                                  └──────────┬──────────────┘
                                             │
                            "Me gusta, guardar"
                                             │
                                  ┌──────────▼──────────────┐
    ② Se persiste ───────────────▶│  saved_queries_repo     │
       • sql_text (validado)      │  .create(               │
       • título, chart_type       │    user_id, title,      │
       • refresh_interval         │    sql, interval, ...)  │
                                  └──────────┬──────────────┘
                                             │
    ③ Ejecución inicial ─────────▶  snapshot_service.execute_and_store()
       (snapshot #1)                         │
                                             ▼
                                  ┌──────────────────────────┐
    ④ Scheduler recoge ──────────▶│  scheduler.py            │
       queries con                │  cada tick:              │
       refresh_interval           │   - busca queries        │
       activas y vencidas         │     WHERE is_active      │
                                  │     AND next_run <= now  │
                                  │   - ejecuta via DwhClient│
                                  │   - guarda snapshot      │
                                  │   - registra refresh_log │
                                  └──────────────────────────┘
                                             │
                                             ▼
                                  ┌──────────────────────────┐
    ⑤ Dashboard lee último ──────▶│  dashboard (03_dashboard) │
       snapshot de cada widget    │  cada widget pide:       │
       (NO re-ejecuta SQL)        │  GET /snapshots/latest   │
                                  │  y renderiza tabla/chart │
                                  └──────────────────────────┘
```

### Principio fundamental

> El dashboard **nunca ejecuta SQL directamente contra el DWH**. Siempre lee el último
> `query_snapshot`. Esto garantiza:
>
> - **Carga instantánea** del dashboard (no espera a Ollama ni al DWH).
> - **Control total de la carga** al DWH (solo el scheduler ejecuta).
> - **Historial de resultados** para detectar tendencias o anomalías entre snapshots.

---

## 6. Scheduler de Refresco

### Tecnología: APScheduler

Se eligió APScheduler porque:
- Es Python puro, no requiere infraestructura adicional (Redis, RabbitMQ).
- Se integra como `BackgroundScheduler` dentro del mismo proceso FastAPI.
- Soporta `IntervalTrigger` y `CronTrigger` si se necesitan horarios específicos.

### Diseño conceptual

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

class QueryRefreshScheduler:
    """Ejecuta queries guardadas según su refresh_interval."""

    def __init__(self, dwh_client, db_session_factory):
        self._dwh = dwh_client
        self._db = db_session_factory
        self._scheduler = BackgroundScheduler()
        self._consecutive_failures: dict[int, int] = {}
        self._max_failures = 5  # circuit breaker

    def start(self):
        self._scheduler.add_job(
            self._check_pending_refreshes,
            trigger=IntervalTrigger(seconds=60),
            id="refresh_checker",
        )
        self._scheduler.start()

    def _check_pending_refreshes(self):
        """
        Busca queries que necesitan refresco:

        SELECT sq.* FROM saved_queries sq
        LEFT JOIN LATERAL (
            SELECT executed_at FROM query_snapshots
            WHERE saved_query_id = sq.id
            ORDER BY executed_at DESC LIMIT 1
        ) latest ON true
        WHERE sq.is_active = true
          AND sq.refresh_interval IS NOT NULL
          AND (latest.executed_at IS NULL
               OR latest.executed_at + sq.refresh_interval <= now())
        """
        # Para cada query pendiente:
        #   1. Verificar circuit breaker (si falló >= max_failures, desactivar)
        #   2. validate_read_only_sql(sql_text)  — re-validar siempre
        #   3. dwh_client.execute_select(sql_text)
        #   4. INSERT INTO query_snapshots (result_data, row_count, duration_ms)
        #   5. INSERT INTO refresh_log (triggered_at, finished_at, success)
        #   6. Si falla: incrementar contador de fallos, registrar en refresh_log
        #   7. Si éxito: resetear contador de fallos

    def stop(self):
        self._scheduler.shutdown()
```

### Intervalos soportados

| Etiqueta UI | Valor INTERVAL |
|---|---|
| Cada 5 minutos | `'5 minutes'` |
| Cada 15 minutos | `'15 minutes'` |
| Cada 30 minutos | `'30 minutes'` |
| Cada hora | `'1 hour'` |
| Cada 6 horas | `'6 hours'` |
| Diario | `'1 day'` |
| Manual | `NULL` (no se auto-refresca) |

### Circuit Breaker

Si una query falla **5 veces consecutivas**:
1. Se marca `is_active = false` en `saved_queries`.
2. Se registra una alerta en `observability` y en `refresh_log`.
3. Se notifica al usuario en la página "Mis Consultas" con un banner de error.
4. El usuario puede corregir el SQL o reactivar manualmente.

### Limpieza de snapshots

Job nocturno (o configurable) que elimina snapshots antiguos:

```sql
DELETE FROM query_snapshots
WHERE id NOT IN (
    SELECT id FROM query_snapshots qs2
    WHERE qs2.saved_query_id = query_snapshots.saved_query_id
    ORDER BY executed_at DESC
    LIMIT 100  -- conservar últimos 100 por query
);
```

---

## 7. Integración con kpi_templates.py

El archivo `kpi_templates.py` que ya existe como stub es el puente natural hacia un
**catálogo de consultas pre-armadas**.

### Evolución propuesta

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class TemplateParam:
    """Parámetro que el usuario puede personalizar al usar el template."""
    name: str           # "date_from"
    label: str          # "Fecha inicio"
    param_type: str     # "date" | "text" | "select"
    default: str        # "date_trunc('month', CURRENT_DATE)"
    options: list[str] = field(default_factory=list)  # para tipo "select"

@dataclass(frozen=True)
class QueryTemplate:
    """Template de consulta KPI pre-armada."""
    id: str
    name: str                      # "Ventas por canal este mes"
    description: str
    sql: str                       # SQL con {date_from}, {date_to}, etc.
    default_chart_type: str        # "bar"
    default_refresh: str           # "1 hour"
    category: str                  # "ventas", "servicio", "seguros"
    parameters: list[TemplateParam] = field(default_factory=list)

CATALOG: list[QueryTemplate] = [
    QueryTemplate(
        id="ventas_canal_mes",
        name="Ventas por canal (mes actual)",
        description="Total de ventas agrupadas por canal del mes en curso",
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
        id="servicios_taller_semana",
        name="Servicios por taller (última semana)",
        description="Cantidad de servicios completados por taller en los últimos 7 días",
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
        id="polizas_por_vencer",
        name="Pólizas por vencer (próximos 30 días)",
        description="Pólizas activas que vencen en los próximos 30 días",
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
        id="citas_pendientes_hoy",
        name="Citas programadas para hoy",
        description="Citas de servicio programadas para el día actual",
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
        id="top_clientes_compras",
        name="Top 20 clientes por monto de compras",
        description="Clientes con mayor monto total de compras",
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
        category="ventas",
    ),
]

def get_templates_by_category(category: str | None = None) -> list[QueryTemplate]:
    if category is None:
        return list(CATALOG)
    return [t for t in CATALOG if t.category == category]

def get_template_by_id(template_id: str) -> QueryTemplate | None:
    for t in CATALOG:
        if t.id == template_id:
            return t
    return None
```

### Dos caminos para poblar el dashboard

| Camino | Descripción |
|---|---|
| **Exploración libre** | Pregunta en NL → agente genera SQL → usuario revisa resultado → "Guardar al dashboard" |
| **Catálogo de templates** | Usuario navega categorías (ventas, servicio, seguros) → elige un KPI → personaliza parámetros → agrega al dashboard |

---

## 8. Estrategia de UI

### Fase A — Streamlit Multi-Page (corto plazo, 2-4 semanas)

Usar `st.navigation` / páginas de Streamlit para crear la experiencia multi-sección:

| Página | Función | Detalles |
|---|---|---|
| **Explorar** | Flujo actual de `web.py` | NL → SQL → resultado + botón "Guardar al dashboard" |
| **Mis Consultas** | Gestión de queries guardadas | Tabla con título, intervalo, último refresco, estado. Editar, activar/desactivar, eliminar |
| **Dashboard** | Grid de widgets | Layout con `streamlit-elements` (MUI grid) o columnas fijas. Cada widget muestra último snapshot |
| **Catálogo** | Templates pre-armados | Navegar por categoría, previsualizar, agregar al dashboard con un click |
| **Admin** | Solo rol admin | Gestión de usuarios, logs de refresco, métricas de observabilidad |

#### Tecnología para el grid

La librería `streamlit-elements` soporta:
- `mui.Grid` para layouts responsivos.
- `nivo` para charts (bar, line, pie) con interactividad.
- `dashboard.Grid` para drag-and-drop real.

#### Auto-refresco del dashboard

Streamlit tiene `st.rerun()` y `st_autorefresh` (componente comunitario) para polling
periódico. El dashboard puede hacer auto-refresh cada 30-60 segundos para leer nuevos
snapshots sin que el usuario recargue manualmente.

### Fase B — Frontend separado (mediano plazo, si el producto crece)

Si la complejidad del dashboard supera lo que Streamlit maneja bien (> 50 usuarios
concurrentes, interacciones complejas de drag-and-drop, SSO corporativo):

```
Frontend:  React + react-grid-layout + Recharts (o Nivo)
Backend:   FastAPI (api.py del paquete platform)
Agente:    Se expone como endpoint POST /api/ask
Auth:      JWT con refresh tokens, opcionalmente integración LDAP/SAML
```

La Fase A es perfectamente funcional para un MVP y para producción con < 50 usuarios.
La Fase B es una evolución natural si el producto despega.

---

## 9. Seguridad

### 9.1 Ejecución automática sin supervisión

Dado que el scheduler ejecuta SQL **automáticamente**, las medidas de seguridad son críticas:

| Medida | Descripción |
|---|---|
| **Re-validación** | El scheduler llama `validate_read_only_sql()` antes de CADA ejecución, incluso si el SQL fue validado al guardarse. Defensa contra manipulación directa en BD. |
| **Conexión de solo lectura** | Crear un rol PostgreSQL dedicado con `GRANT SELECT` únicamente para las ejecuciones del scheduler. |
| **Statement timeout** | Configurar `SET statement_timeout = '30s'` en la conexión del scheduler para evitar queries que bloqueen recursos. |
| **Circuit breaker** | Desactivar automáticamente queries que fallan N veces consecutivas (ver sección 6). |

### 9.2 Límites por usuario

| Límite | Valor sugerido |
|---|---|
| Máximo de queries guardadas activas | 20 por usuario |
| Intervalo mínimo de refresco | 5 minutos |
| Máximo de widgets por dashboard | 15 |
| Máximo de dashboards por usuario | 5 |
| Retención de snapshots | 100 por query o 30 días |

### 9.3 Autenticación y autorización

| Aspecto | Implementación |
|---|---|
| Hash de passwords | bcrypt vía `passlib` |
| Tokens | JWT con expiración de 8 horas, refresh token de 7 días |
| Roles | `viewer` (solo ve dashboards compartidos), `editor` (crea queries y dashboards), `admin` (gestiona usuarios y ve logs) |
| Multi-tenancy | Cada query y dashboard está asociado a un `user_id`; los endpoints filtran por usuario autenticado |
| Queries compartidas | Futuro: campo `is_shared` en `saved_queries` para que otros usuarios puedan agregar la query a sus dashboards |

---

## 10. Fases de Implementación

| Fase | Alcance | Estimado | Dependencias |
|---|---|---|---|
| **1. Persistencia** | Tablas de plataforma + `models.py` + `saved_queries_repo.py` + botón "Guardar" en la UI de exploración + página "Mis Consultas" | 1-2 semanas | Ninguna |
| **2. Snapshots** | `snapshot_service.py` + ejecución manual desde "Mis Consultas" + almacenamiento de resultados en `query_snapshots` | 1 semana | Fase 1 |
| **3. Dashboard básico** | Página dashboard con widgets en grid fijo (2-3 columnas) + lectura de último snapshot + renderizado por chart_type | 1-2 semanas | Fase 2 |
| **4. Scheduler** | APScheduler + `refresh_log` + circuit breaker + re-validación + job de limpieza de snapshots | 1-2 semanas | Fase 2 |
| **5. Autenticación** | `platform_users` + `auth.py` + login en UI + JWT + multi-tenant | 1 semana | Fase 1 |
| **6. Grid dinámico** | Drag-and-drop con `streamlit-elements` o migración a React + `react-grid-layout` | 2-3 semanas | Fase 3 |
| **7. Catálogo de templates** | KPIs pre-armados en `kpi_templates.py` + UI para navegar, previsualizar y agregar al dashboard | 1 semana | Fase 3 |

### Orden recomendado

```
Fase 1 ──▶ Fase 2 ──▶ Fase 3 ──▶ Fase 6
                  │         │
                  ▼         ▼
               Fase 4    Fase 7
                  │
                  ▼
               Fase 5
```

Las fases 4, 5 y 7 pueden desarrollarse en paralelo una vez que Fase 2 y Fase 3 estén listas.

---

## 11. Dependencias Nuevas

Agregar al `pyproject.toml`:

```toml
[project.optional-dependencies]
platform = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "apscheduler>=3.10",
    "streamlit-elements>=0.1",
]
```

### Justificación

| Dependencia | Razón |
|---|---|
| `fastapi` | API REST para CRUD de queries/dashboards, consumida por el frontend |
| `uvicorn` | Servidor ASGI para FastAPI |
| `python-jose` | Generación y validación de tokens JWT |
| `passlib` | Hash seguro de passwords con bcrypt |
| `apscheduler` | Scheduler de background para ejecución periódica de queries |
| `streamlit-elements` | Grid drag-and-drop y charts interactivos en Streamlit (Fase A) |

---

## Apéndice: Ejemplo de endpoint FastAPI

```python
# platform/api.py — fragmento ilustrativo

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

app = FastAPI(title="VGD Dashboard Platform")

class SaveQueryRequest(BaseModel):
    title: str
    original_question: str
    sql_text: str
    chart_type: str = "table"
    chart_config: dict = {}
    refresh_interval: str | None = None  # "5 minutes", "1 hour", etc.

class SaveQueryResponse(BaseModel):
    id: int
    title: str
    created_at: str

@app.post("/api/queries", response_model=SaveQueryResponse)
def create_saved_query(
    req: SaveQueryRequest,
    user=Depends(get_current_user),
    repo=Depends(get_saved_queries_repo),
):
    validate_read_only_sql(req.sql_text)  # re-validar siempre
    query = repo.create(
        user_id=user.id,
        title=req.title,
        original_question=req.original_question,
        sql_text=req.sql_text,
        chart_type=req.chart_type,
        chart_config=req.chart_config,
        refresh_interval=req.refresh_interval,
    )
    return SaveQueryResponse(
        id=query.id,
        title=query.title,
        created_at=query.created_at.isoformat(),
    )

@app.get("/api/queries/{query_id}/snapshot/latest")
def get_latest_snapshot(
    query_id: int,
    user=Depends(get_current_user),
    repo=Depends(get_saved_queries_repo),
):
    snapshot = repo.get_latest_snapshot(query_id, user_id=user.id)
    if not snapshot:
        raise HTTPException(404, "Sin snapshots disponibles")
    return {
        "result_data": snapshot.result_data,
        "row_count": snapshot.row_count,
        "executed_at": snapshot.executed_at.isoformat(),
        "duration_ms": snapshot.duration_ms,
    }
```
