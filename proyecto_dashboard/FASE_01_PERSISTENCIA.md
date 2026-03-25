# Fase 1 — Persistencia de Consultas Guardadas

## Objetivo

Crear las tablas de plataforma en PostgreSQL y el módulo `saved_queries_repo` que permita
guardar, listar, editar y eliminar consultas generadas por el agente. Agregar un botón
"Guardar al dashboard" en la UI de exploración existente y una página nueva "Mis Consultas".

## Prerequisitos

- PostgreSQL accesible (misma instancia del DWH demo o separada).
- Paquete `agente_dwh` funcional con `sql_guard.py` y `dwh.py`.

---

## Tareas

### T1.1 — Crear `agente_dwh/platform/__init__.py`

Archivo vacío que convierte `platform/` en un sub-paquete Python.

**Archivo:** `agente_dwh/platform/__init__.py`

```python
"""Sub-paquete de plataforma para dashboard persistente."""
```

### T1.2 — Crear `agente_dwh/platform/models.py` (ORM SQLAlchemy)

Definir todas las tablas de plataforma usando SQLAlchemy 2.0 DeclarativeBase.
En esta fase solo se usan `platform_users` y `saved_queries`, pero se definen
todas para que las migraciones futuras no requieran re-crear la base.

**Archivo:** `agente_dwh/platform/models.py`

Tablas a definir:

| Tabla | Columnas clave |
|---|---|
| `platform_users` | `id` SERIAL PK, `username` TEXT UNIQUE NOT NULL, `display_name` TEXT NOT NULL, `password_hash` TEXT NOT NULL, `role` TEXT DEFAULT `'editor'`, `created_at` TIMESTAMPTZ, `last_login_at` TIMESTAMPTZ |
| `saved_queries` | `id` SERIAL PK, `user_id` INT FK→platform_users, `title` TEXT NOT NULL, `original_question` TEXT NOT NULL, `sql_text` TEXT NOT NULL, `chart_type` TEXT DEFAULT `'table'`, `chart_config` JSON DEFAULT `{}`, `refresh_interval` TEXT NULLABLE (almacenado como string: `'5 minutes'`, `'1 hour'`, etc.), `is_active` BOOLEAN DEFAULT true, `tags` JSON DEFAULT `[]`, `created_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ |
| `dashboards` | `id` SERIAL PK, `user_id` INT FK→platform_users, `title` TEXT, `is_default` BOOLEAN, `layout_cols` INT DEFAULT 12, `created_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ |
| `dashboard_widgets` | `id` SERIAL PK, `dashboard_id` INT FK→dashboards CASCADE, `saved_query_id` INT FK→saved_queries CASCADE, `pos_x` INT, `pos_y` INT, `width` INT, `height` INT, `display_order` INT, `widget_config` JSON, `created_at` TIMESTAMPTZ |
| `query_snapshots` | `id` SERIAL PK, `saved_query_id` INT FK→saved_queries CASCADE, `result_data` JSON NOT NULL, `row_count` INT, `executed_at` TIMESTAMPTZ, `duration_ms` FLOAT, `success` BOOLEAN, `error_message` TEXT |
| `refresh_log` | `id` SERIAL PK, `saved_query_id` INT FK→saved_queries CASCADE, `triggered_at` TIMESTAMPTZ, `finished_at` TIMESTAMPTZ, `success` BOOLEAN, `duration_ms` FLOAT, `error_message` TEXT |

Requisitos del código:

1. Usar `from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship`.
2. Usar `from sqlalchemy import String, Integer, Boolean, Float, Text, DateTime, JSON, ForeignKey`.
3. Incluir función `create_all_tables(engine)` que llame `Base.metadata.create_all(engine)`.
4. Incluir función `get_session_factory(engine)` que retorne un `sessionmaker` configurado.
5. Los campos `created_at` deben usar `server_default=func.now()`.
6. Los campos `updated_at` deben usar `onupdate=func.now()`.

### T1.3 — Crear `agente_dwh/platform/saved_queries_repo.py`

Repositorio CRUD para `saved_queries`.

**Archivo:** `agente_dwh/platform/saved_queries_repo.py`

Funciones a implementar:

```python
class SavedQueriesRepo:
    def __init__(self, session_factory):
        """Recibe un sessionmaker de SQLAlchemy."""

    def create(
        self,
        *,
        user_id: int,
        title: str,
        original_question: str,
        sql_text: str,
        chart_type: str = "table",
        chart_config: dict | None = None,
        refresh_interval: str | None = None,
        tags: list[str] | None = None,
    ) -> SavedQuery:
        """
        Guarda una nueva consulta.
        DEBE llamar validate_read_only_sql(sql_text) antes de insertar.
        Lanza ValueError si el SQL no es válido.
        Lanza ValueError si el usuario ya tiene 20 queries activas (límite).
        """

    def list_by_user(self, user_id: int) -> list[SavedQuery]:
        """Retorna todas las queries del usuario ordenadas por updated_at DESC."""

    def get_by_id(self, query_id: int, *, user_id: int) -> SavedQuery | None:
        """Retorna la query si pertenece al usuario, o None."""

    def update(
        self,
        query_id: int,
        *,
        user_id: int,
        title: str | None = None,
        chart_type: str | None = None,
        chart_config: dict | None = None,
        refresh_interval: str | None = None,
        is_active: bool | None = None,
        tags: list[str] | None = None,
    ) -> SavedQuery | None:
        """
        Actualiza campos opcionales. Retorna la query actualizada o None si no existe.
        NO permite cambiar sql_text (por seguridad; el usuario debe crear una nueva).
        Actualiza updated_at.
        """

    def delete(self, query_id: int, *, user_id: int) -> bool:
        """Elimina la query y retorna True si existía, False si no."""

    def count_active_by_user(self, user_id: int) -> int:
        """Cuenta queries activas del usuario (para validar límite)."""
```

Reglas de negocio:
- `sql_text` se valida con `from agente_dwh.sql_guard import validate_read_only_sql` al crear.
- Máximo 20 queries activas por usuario.
- `chart_type` debe ser uno de: `table`, `bar`, `line`, `kpi`, `pie`.
- `refresh_interval` si se proporciona debe ser uno de: `'5 minutes'`, `'15 minutes'`, `'30 minutes'`, `'1 hour'`, `'6 hours'`, `'1 day'`.

### T1.4 — Crear usuario demo por defecto

Función `ensure_default_user(session_factory)` en `models.py` o en un nuevo archivo
`agente_dwh/platform/bootstrap.py` que:

1. Verifica si existe un usuario con `username = 'demo'`.
2. Si no existe, lo crea con `display_name = 'Usuario Demo'`, `role = 'editor'`,
   y un `password_hash` generado con hashlib (SHA-256 por ahora, se migra a bcrypt en Fase 5).
3. Retorna el `id` del usuario demo.

Esto permite que las fases 1-4 funcionen sin autenticación real (se usa siempre el usuario demo).

### T1.5 — Extender `config.py` con `PLATFORM_DB_URL`

Agregar a la clase `Config`:
- `platform_db_url: str` — lee de `PLATFORM_DB_URL`, si no existe usa `DWH_URL` (misma BD).

Agregar al `.env.example`:
```
# URL de la BD de plataforma (si es diferente al DWH)
# PLATFORM_DB_URL=postgresql+psycopg://usuario:pass@host:5432/plataforma
```

### T1.6 — Integrar botón "Guardar al dashboard" en `web.py`

Después de que una consulta se ejecuta exitosamente (en el flujo actual de exploración),
mostrar un botón `st.button("💾 Guardar al dashboard")`. Al hacer click:

1. Mostrar un `st.form` con:
   - `title`: campo de texto, pre-poblado con los primeros 60 caracteres de la pregunta.
   - `chart_type`: selectbox con opciones `['table', 'bar', 'line', 'kpi', 'pie']`.
   - `refresh_interval`: selectbox con opciones `['Manual', 'Cada 5 min', 'Cada 15 min', 'Cada 30 min', 'Cada hora', 'Cada 6 horas', 'Diario']`.
2. Al enviar el form, llamar `repo.create(...)` con el SQL generado y los parámetros.
3. Mostrar `st.success("Consulta guardada exitosamente")` o `st.error(...)` si falla.

### T1.7 — Crear página "Mis Consultas" en Streamlit

Crear la página como función dentro de `web.py` o como archivo separado según la
estructura multi-page que se prefiera. Debe mostrar:

1. Tabla con todas las queries del usuario: título, chart_type, refresh_interval,
   is_active, created_at, updated_at.
2. Para cada query, botones de acción:
   - **Editar**: abre un form para cambiar título, chart_type, refresh_interval, is_active.
   - **Eliminar**: con confirmación (`st.warning` + botón de confirmación).
   - **Ejecutar ahora**: ejecuta el SQL con `DwhClient` y muestra el resultado (previsualización).
3. Badge que muestra "X / 20 consultas activas".

---

## Casos de Prueba

### Archivo: `tests/test_platform_models.py`

```python
"""Tests para el modelo ORM de plataforma."""

import pytest
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base,
    PlatformUser,
    SavedQuery,
    Dashboard,
    DashboardWidget,
    QuerySnapshot,
    RefreshLog,
    create_all_tables,
    get_session_factory,
)


@pytest.fixture
def engine():
    """Engine SQLite en memoria para tests rápidos."""
    eng = create_engine("sqlite:///:memory:")
    create_all_tables(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return get_session_factory(engine)


@pytest.fixture
def session(session_factory):
    session = session_factory()
    yield session
    session.close()


class TestCreateAllTables:
    def test_all_tables_created(self, engine):
        """Verifica que las 6 tablas de plataforma se crean correctamente."""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        expected = {
            "platform_users",
            "saved_queries",
            "dashboards",
            "dashboard_widgets",
            "query_snapshots",
            "refresh_log",
        }
        assert expected.issubset(set(table_names))


class TestPlatformUser:
    def test_create_user(self, session):
        user = PlatformUser(
            username="testuser",
            display_name="Test User",
            password_hash="fakehash",
            role="editor",
        )
        session.add(user)
        session.commit()
        assert user.id is not None
        assert user.username == "testuser"

    def test_username_unique(self, session):
        user1 = PlatformUser(username="dup", display_name="A", password_hash="h1")
        user2 = PlatformUser(username="dup", display_name="B", password_hash="h2")
        session.add(user1)
        session.commit()
        session.add(user2)
        with pytest.raises(Exception):
            session.commit()


class TestSavedQuery:
    def test_create_saved_query(self, session):
        user = PlatformUser(username="u1", display_name="U1", password_hash="h")
        session.add(user)
        session.commit()
        sq = SavedQuery(
            user_id=user.id,
            title="Ventas por canal",
            original_question="¿Cuántas ventas hay por canal?",
            sql_text="SELECT channel, COUNT(*) FROM sales GROUP BY channel",
            chart_type="bar",
        )
        session.add(sq)
        session.commit()
        assert sq.id is not None
        assert sq.user_id == user.id

    def test_cascade_delete_user_does_not_delete_queries(self, session):
        """saved_queries tienen FK a users pero NO cascade delete (protección)."""
        user = PlatformUser(username="u2", display_name="U2", password_hash="h")
        session.add(user)
        session.commit()
        sq = SavedQuery(
            user_id=user.id,
            title="Test",
            original_question="test",
            sql_text="SELECT 1",
        )
        session.add(sq)
        session.commit()
        sq_id = sq.id
        # Intentar eliminar el usuario debería fallar por FK
        session.delete(user)
        with pytest.raises(Exception):
            session.commit()


class TestDashboardAndWidgets:
    def test_create_dashboard_with_widgets(self, session):
        user = PlatformUser(username="u3", display_name="U3", password_hash="h")
        session.add(user)
        session.commit()
        sq = SavedQuery(
            user_id=user.id,
            title="Q1",
            original_question="q",
            sql_text="SELECT 1",
        )
        session.add(sq)
        session.commit()
        dash = Dashboard(user_id=user.id, title="Mi Dashboard")
        session.add(dash)
        session.commit()
        widget = DashboardWidget(
            dashboard_id=dash.id,
            saved_query_id=sq.id,
            pos_x=0,
            pos_y=0,
            width=6,
            height=4,
        )
        session.add(widget)
        session.commit()
        assert widget.id is not None
        assert widget.dashboard_id == dash.id

    def test_cascade_delete_dashboard_deletes_widgets(self, session):
        user = PlatformUser(username="u4", display_name="U4", password_hash="h")
        session.add(user)
        session.commit()
        sq = SavedQuery(
            user_id=user.id,
            title="Q2",
            original_question="q",
            sql_text="SELECT 1",
        )
        session.add(sq)
        session.commit()
        dash = Dashboard(user_id=user.id, title="Dash")
        session.add(dash)
        session.commit()
        widget = DashboardWidget(
            dashboard_id=dash.id,
            saved_query_id=sq.id,
            pos_x=0, pos_y=0, width=6, height=4,
        )
        session.add(widget)
        session.commit()
        session.delete(dash)
        session.commit()
        remaining = session.query(DashboardWidget).filter_by(dashboard_id=dash.id).all()
        assert remaining == []
```

### Archivo: `tests/test_saved_queries_repo.py`

```python
"""Tests para el repositorio de consultas guardadas."""

import pytest
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base, PlatformUser, SavedQuery,
    create_all_tables, get_session_factory,
)
from agente_dwh.platform.saved_queries_repo import SavedQueriesRepo


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
    return SavedQueriesRepo(session_factory)


@pytest.fixture
def demo_user(session_factory):
    session = session_factory()
    user = PlatformUser(
        username="demo", display_name="Demo", password_hash="fakehash"
    )
    session.add(user)
    session.commit()
    uid = user.id
    session.close()
    return uid


class TestCreate:
    def test_create_valid_query(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user,
            title="Ventas totales",
            original_question="¿Cuánto vendimos?",
            sql_text="SELECT SUM(amount) FROM sales",
            chart_type="kpi",
            refresh_interval="1 hour",
        )
        assert sq.id is not None
        assert sq.title == "Ventas totales"
        assert sq.is_active is True

    def test_create_rejects_invalid_sql(self, repo, demo_user):
        with pytest.raises(ValueError, match="no permitida"):
            repo.create(
                user_id=demo_user,
                title="Mala query",
                original_question="borrar todo",
                sql_text="DROP TABLE sales",
            )

    def test_create_rejects_empty_sql(self, repo, demo_user):
        with pytest.raises(ValueError):
            repo.create(
                user_id=demo_user,
                title="Vacía",
                original_question="nada",
                sql_text="",
            )

    def test_create_rejects_invalid_chart_type(self, repo, demo_user):
        with pytest.raises(ValueError, match="chart_type"):
            repo.create(
                user_id=demo_user,
                title="Test",
                original_question="test",
                sql_text="SELECT 1",
                chart_type="radar",
            )

    def test_create_rejects_invalid_refresh_interval(self, repo, demo_user):
        with pytest.raises(ValueError, match="refresh_interval"):
            repo.create(
                user_id=demo_user,
                title="Test",
                original_question="test",
                sql_text="SELECT 1",
                refresh_interval="2 seconds",
            )

    def test_create_enforces_max_20_active(self, repo, demo_user):
        for i in range(20):
            repo.create(
                user_id=demo_user,
                title=f"Q{i}",
                original_question=f"q{i}",
                sql_text="SELECT 1",
            )
        with pytest.raises(ValueError, match="límite"):
            repo.create(
                user_id=demo_user,
                title="Q20",
                original_question="q20",
                sql_text="SELECT 1",
            )


class TestListByUser:
    def test_list_returns_only_user_queries(self, repo, demo_user, session_factory):
        repo.create(
            user_id=demo_user,
            title="Q1",
            original_question="q1",
            sql_text="SELECT 1",
        )
        # Crear otro usuario
        session = session_factory()
        other = PlatformUser(username="other", display_name="Other", password_hash="h")
        session.add(other)
        session.commit()
        other_id = other.id
        session.close()
        repo.create(
            user_id=other_id,
            title="Q2",
            original_question="q2",
            sql_text="SELECT 2",
        )
        results = repo.list_by_user(demo_user)
        assert len(results) == 1
        assert results[0].title == "Q1"

    def test_list_ordered_by_updated_at_desc(self, repo, demo_user):
        repo.create(user_id=demo_user, title="Primero", original_question="q", sql_text="SELECT 1")
        repo.create(user_id=demo_user, title="Segundo", original_question="q", sql_text="SELECT 2")
        results = repo.list_by_user(demo_user)
        assert results[0].title == "Segundo"


class TestGetById:
    def test_get_existing(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        result = repo.get_by_id(sq.id, user_id=demo_user)
        assert result is not None
        assert result.id == sq.id

    def test_get_wrong_user_returns_none(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        result = repo.get_by_id(sq.id, user_id=9999)
        assert result is None

    def test_get_nonexistent_returns_none(self, repo, demo_user):
        result = repo.get_by_id(9999, user_id=demo_user)
        assert result is None


class TestUpdate:
    def test_update_title(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Viejo", original_question="q", sql_text="SELECT 1"
        )
        updated = repo.update(sq.id, user_id=demo_user, title="Nuevo")
        assert updated is not None
        assert updated.title == "Nuevo"

    def test_update_refresh_interval(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        updated = repo.update(sq.id, user_id=demo_user, refresh_interval="5 minutes")
        assert updated.refresh_interval == "5 minutes"

    def test_update_wrong_user_returns_none(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        result = repo.update(sq.id, user_id=9999, title="Hack")
        assert result is None

    def test_update_deactivate(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        updated = repo.update(sq.id, user_id=demo_user, is_active=False)
        assert updated.is_active is False


class TestDelete:
    def test_delete_existing(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        assert repo.delete(sq.id, user_id=demo_user) is True
        assert repo.get_by_id(sq.id, user_id=demo_user) is None

    def test_delete_nonexistent(self, repo, demo_user):
        assert repo.delete(9999, user_id=demo_user) is False

    def test_delete_wrong_user(self, repo, demo_user):
        sq = repo.create(
            user_id=demo_user, title="Test", original_question="q", sql_text="SELECT 1"
        )
        assert repo.delete(sq.id, user_id=9999) is False


class TestCountActive:
    def test_count_only_active(self, repo, demo_user):
        repo.create(
            user_id=demo_user, title="A", original_question="q", sql_text="SELECT 1"
        )
        sq2 = repo.create(
            user_id=demo_user, title="B", original_question="q", sql_text="SELECT 2"
        )
        repo.update(sq2.id, user_id=demo_user, is_active=False)
        assert repo.count_active_by_user(demo_user) == 1
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E1.1 | `agente_dwh/platform/__init__.py` existe | El archivo existe y el paquete es importable: `from agente_dwh.platform import models` no falla. |
| E1.2 | `agente_dwh/platform/models.py` con 6 tablas ORM | `create_all_tables(engine)` crea las 6 tablas en SQLite en memoria sin errores. Las tablas tienen las columnas especificadas. |
| E1.3 | `agente_dwh/platform/saved_queries_repo.py` con CRUD completo | Las 6 clases de test (`TestCreate`, `TestListByUser`, `TestGetById`, `TestUpdate`, `TestDelete`, `TestCountActive`) pasan al 100%. |
| E1.4 | Validación de SQL al crear | `repo.create(sql_text="DROP TABLE x")` lanza `ValueError`. `repo.create(sql_text="SELECT 1")` funciona. |
| E1.5 | Límite de 20 queries activas | Al intentar crear la query #21 para un usuario se lanza `ValueError`. Si se desactiva una y se crea otra, funciona. |
| E1.6 | Validación de `chart_type` | Solo acepta `table`, `bar`, `line`, `kpi`, `pie`. |
| E1.7 | Validación de `refresh_interval` | Solo acepta `None`, `'5 minutes'`, `'15 minutes'`, `'30 minutes'`, `'1 hour'`, `'6 hours'`, `'1 day'`. |
| E1.8 | `config.py` extendido | `Config.from_env()` carga `PLATFORM_DB_URL` (fallback a `DWH_URL`). |
| E1.9 | `tests/test_platform_models.py` pasa | `pytest tests/test_platform_models.py` — 0 fallos. |
| E1.10 | `tests/test_saved_queries_repo.py` pasa | `pytest tests/test_saved_queries_repo.py` — 0 fallos. |
| E1.11 | Tests existentes no se rompen | `pytest tests/` completo sigue verde (no hay regresiones). |

---

## Validación por agente

El agente validador debe ejecutar:

```bash
# 1. Verificar que el paquete platform es importable
python -c "from agente_dwh.platform.models import Base, PlatformUser, SavedQuery, Dashboard, DashboardWidget, QuerySnapshot, RefreshLog, create_all_tables, get_session_factory; print('OK: models importable')"

# 2. Verificar que el repo es importable
python -c "from agente_dwh.platform.saved_queries_repo import SavedQueriesRepo; print('OK: repo importable')"

# 3. Ejecutar tests nuevos
pytest tests/test_platform_models.py -v
pytest tests/test_saved_queries_repo.py -v

# 4. Ejecutar tests existentes (no regresión)
pytest tests/ -v

# 5. Verificar que config.py carga PLATFORM_DB_URL
python -c "
import os; os.environ['DWH_URL'] = 'postgresql+psycopg://x:x@localhost/test'
from agente_dwh.config import Config
c = Config.from_env()
print(f'platform_db_url = {c.platform_db_url}')
assert c.platform_db_url, 'PLATFORM_DB_URL no debe ser vacío'
print('OK: config extendido')
"
```

Todos los comandos deben retornar exit code 0.
