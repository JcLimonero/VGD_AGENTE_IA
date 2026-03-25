# Fase 5 — Autenticación y Multi-tenancy

## Objetivo

Implementar autenticación de usuarios con JWT, hash seguro de passwords con bcrypt,
y multi-tenancy para que cada usuario solo vea y gestione sus propias queries y dashboards.

## Prerequisitos

- Fase 1 completa: tabla `platform_users` creada.
- Fases 2-4 completas: repos y servicios funcionales con `user_id`.

---

## Tareas

### T5.1 — Agregar dependencias

Agregar al `pyproject.toml` en `[project.optional-dependencies.platform]`:

```toml
"python-jose[cryptography]>=3.3",
"passlib[bcrypt]>=1.7",
```

### T5.2 — Crear `agente_dwh/platform/auth.py`

**Archivo:** `agente_dwh/platform/auth.py`

```python
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext


SECRET_KEY = os.getenv("PLATFORM_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Genera hash bcrypt del password."""

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que el plain password coincide con el hash."""

def create_access_token(user_id: int, username: str) -> str:
    """
    Crea JWT con payload:
    - sub: str(user_id)
    - username: username
    - exp: now + ACCESS_TOKEN_EXPIRE_HOURS
    - type: "access"
    """

def create_refresh_token(user_id: int) -> str:
    """
    Crea JWT con payload:
    - sub: str(user_id)
    - exp: now + REFRESH_TOKEN_EXPIRE_DAYS
    - type: "refresh"
    """

def decode_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un JWT.
    Lanza JWTError si el token es inválido o expiró.
    Retorna el payload como dict.
    """

def get_user_id_from_token(token: str) -> int:
    """
    Extrae user_id del token.
    Lanza ValueError si el token es inválido.
    """
```

### T5.3 — Crear `agente_dwh/platform/user_repo.py`

**Archivo:** `agente_dwh/platform/user_repo.py`

```python
class UserRepo:
    def __init__(self, session_factory):
        pass

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        plain_password: str,
        role: str = "editor",
    ) -> PlatformUser:
        """
        Crea usuario con password hasheado con bcrypt.
        Valida:
        - username no vacío, mínimo 3 caracteres, solo alfanumérico y guion bajo.
        - display_name no vacío.
        - plain_password mínimo 8 caracteres.
        - username único (lanza ValueError si duplicado).
        - role es uno de: 'viewer', 'editor', 'admin'.
        """

    def authenticate(self, username: str, plain_password: str) -> PlatformUser | None:
        """
        Busca usuario por username, verifica password.
        Retorna el usuario si es válido, None si no.
        Actualiza last_login_at si es exitoso.
        """

    def get_by_id(self, user_id: int) -> PlatformUser | None:
        """Retorna usuario por id."""

    def get_by_username(self, username: str) -> PlatformUser | None:
        """Retorna usuario por username."""

    def list_users(self) -> list[PlatformUser]:
        """Retorna todos los usuarios (solo para admin)."""

    def update_role(self, user_id: int, *, role: str) -> PlatformUser | None:
        """Actualiza el rol de un usuario."""

    def change_password(
        self, user_id: int, *, old_password: str, new_password: str
    ) -> bool:
        """
        Cambia el password del usuario.
        Verifica old_password antes de cambiar.
        Retorna True si se cambió, False si old_password es incorrecto.
        """
```

### T5.4 — Migrar usuario demo a bcrypt

Actualizar `ensure_default_user()` (de Fase 1) para usar `hash_password()` de `auth.py`
en lugar del hash SHA-256 provisional.

Password del usuario demo: `"demo2026"` (configurable via env `PLATFORM_DEMO_PASSWORD`).

### T5.5 — Integrar login en Streamlit

Agregar al inicio de la app Streamlit un flujo de login:

1. Si no hay token en `st.session_state`:
   - Mostrar formulario con campos `username` y `password`.
   - Al enviar, llamar `user_repo.authenticate()`.
   - Si es válido, crear token con `create_access_token()` y guardarlo en `st.session_state`.
   - Si es inválido, mostrar `st.error("Credenciales inválidas")`.
2. Si hay token en `st.session_state`:
   - Decodificar con `decode_token()`.
   - Si expiró, mostrar mensaje y limpiar sesión para forzar re-login.
   - Si es válido, extraer `user_id` y continuar con la app.
3. Botón "Cerrar sesión" en el sidebar que limpia el token de la sesión.

### T5.6 — Proteger repos con user_id del token

Verificar que todos los repos (`SavedQueriesRepo`, `DashboardRepo`, `SnapshotService`)
reciben el `user_id` correcto del token, no un valor hardcodeado.

En la UI, pasar `user_id = get_user_id_from_token(st.session_state["token"])` a todos
los métodos que lo requieran.

### T5.7 — Página de administración de usuarios

Solo visible para usuarios con `role = 'admin'`:

1. Tabla con todos los usuarios: username, display_name, role, last_login_at.
2. Formulario para crear usuario nuevo.
3. Dropdown para cambiar role de un usuario existente.
4. No se puede eliminar usuarios (soft-delete futuro).

### T5.8 — Agregar `PLATFORM_SECRET_KEY` al `.env.example`

```
# Clave secreta para firmar tokens JWT (cambiar en producción)
PLATFORM_SECRET_KEY=cambiar-esta-clave-en-produccion
# Password del usuario demo (default: demo2026)
# PLATFORM_DEMO_PASSWORD=demo2026
```

---

## Casos de Prueba

### Archivo: `tests/test_auth.py`

```python
"""Tests para autenticación JWT y hash de passwords."""

import pytest
import time
from agente_dwh.platform.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_token,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mi_password_seguro")
        assert hashed != "mi_password_seguro"
        assert verify_password("mi_password_seguro", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correcto")
        assert verify_password("incorrecto", hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt usa salt aleatorio

    def test_empty_password_works(self):
        """bcrypt acepta passwords vacíos, pero la validación de negocio lo rechaza."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token(user_id=42, username="test")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "test"
        assert payload["type"] == "access"

    def test_get_user_id(self):
        token = create_access_token(user_id=7, username="admin")
        assert get_user_id_from_token(token) == 7

    def test_expired_token_raises(self):
        """Token con expiración en el pasado debe fallar."""
        from jose import jwt as jose_jwt
        from agente_dwh.platform.auth import SECRET_KEY, ALGORITHM
        from datetime import datetime, timezone, timedelta
        expired_payload = {
            "sub": "1",
            "username": "x",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jose_jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(Exception):
            decode_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("esto.no.es.un.jwt.valido")

    def test_tampered_token_raises(self):
        token = create_access_token(user_id=1, username="test")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decode_token(tampered)


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token(user_id=10)
        payload = decode_token(token)
        assert payload["sub"] == "10"
        assert payload["type"] == "refresh"

    def test_refresh_token_longer_expiry(self):
        access = create_access_token(user_id=1, username="x")
        refresh = create_refresh_token(user_id=1)
        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert refresh_payload["exp"] > access_payload["exp"]
```

### Archivo: `tests/test_user_repo.py`

```python
"""Tests para el repositorio de usuarios."""

import pytest
from sqlalchemy import create_engine
from agente_dwh.platform.models import (
    Base, PlatformUser, create_all_tables, get_session_factory,
)
from agente_dwh.platform.user_repo import UserRepo


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
    return UserRepo(session_factory)


class TestCreateUser:
    def test_create_valid(self, repo):
        user = repo.create_user(
            username="nuevo_usuario",
            display_name="Nuevo Usuario",
            plain_password="password123",
            role="editor",
        )
        assert user.id is not None
        assert user.username == "nuevo_usuario"
        assert user.password_hash != "password123"  # debe estar hasheado

    def test_reject_short_username(self, repo):
        with pytest.raises(ValueError, match="username"):
            repo.create_user(
                username="ab", display_name="X", plain_password="password123"
            )

    def test_reject_invalid_username_chars(self, repo):
        with pytest.raises(ValueError, match="username"):
            repo.create_user(
                username="user name!", display_name="X", plain_password="password123"
            )

    def test_reject_short_password(self, repo):
        with pytest.raises(ValueError, match="password"):
            repo.create_user(
                username="validuser", display_name="X", plain_password="short"
            )

    def test_reject_duplicate_username(self, repo):
        repo.create_user(
            username="unico", display_name="A", plain_password="password123"
        )
        with pytest.raises(ValueError, match="existe"):
            repo.create_user(
                username="unico", display_name="B", plain_password="password456"
            )

    def test_reject_invalid_role(self, repo):
        with pytest.raises(ValueError, match="role"):
            repo.create_user(
                username="testuser", display_name="X",
                plain_password="password123", role="superadmin",
            )

    def test_accept_valid_roles(self, repo):
        for role in ("viewer", "editor", "admin"):
            user = repo.create_user(
                username=f"user_{role}", display_name=role.title(),
                plain_password="password123", role=role,
            )
            assert user.role == role


class TestAuthenticate:
    def test_valid_credentials(self, repo):
        repo.create_user(
            username="auth_test", display_name="Test",
            plain_password="correctpassword",
        )
        user = repo.authenticate("auth_test", "correctpassword")
        assert user is not None
        assert user.username == "auth_test"
        assert user.last_login_at is not None

    def test_wrong_password(self, repo):
        repo.create_user(
            username="auth_test2", display_name="Test",
            plain_password="correctpassword",
        )
        assert repo.authenticate("auth_test2", "wrongpassword") is None

    def test_nonexistent_user(self, repo):
        assert repo.authenticate("fantasma", "password") is None

    def test_updates_last_login(self, repo):
        repo.create_user(
            username="login_track", display_name="T",
            plain_password="password123",
        )
        user = repo.authenticate("login_track", "password123")
        first_login = user.last_login_at
        assert first_login is not None
        import time; time.sleep(0.05)
        user2 = repo.authenticate("login_track", "password123")
        # last_login_at debe haberse actualizado
        assert user2.last_login_at >= first_login


class TestChangePassword:
    def test_change_valid(self, repo):
        user = repo.create_user(
            username="changepw", display_name="T", plain_password="oldpassword1"
        )
        result = repo.change_password(
            user.id, old_password="oldpassword1", new_password="newpassword1"
        )
        assert result is True
        assert repo.authenticate("changepw", "newpassword1") is not None
        assert repo.authenticate("changepw", "oldpassword1") is None

    def test_change_wrong_old_password(self, repo):
        user = repo.create_user(
            username="changepw2", display_name="T", plain_password="oldpassword1"
        )
        result = repo.change_password(
            user.id, old_password="wrongold", new_password="newpassword1"
        )
        assert result is False

    def test_change_rejects_short_new_password(self, repo):
        user = repo.create_user(
            username="changepw3", display_name="T", plain_password="oldpassword1"
        )
        with pytest.raises(ValueError, match="password"):
            repo.change_password(
                user.id, old_password="oldpassword1", new_password="short"
            )


class TestUpdateRole:
    def test_update_role(self, repo):
        user = repo.create_user(
            username="roletest", display_name="T",
            plain_password="password123", role="viewer",
        )
        updated = repo.update_role(user.id, role="admin")
        assert updated.role == "admin"

    def test_invalid_role(self, repo):
        user = repo.create_user(
            username="roletest2", display_name="T", plain_password="password123"
        )
        with pytest.raises(ValueError, match="role"):
            repo.update_role(user.id, role="god")


class TestListAndGet:
    def test_list_users(self, repo):
        repo.create_user(username="u1", display_name="U1", plain_password="password123")
        repo.create_user(username="u2", display_name="U2", plain_password="password456")
        users = repo.list_users()
        assert len(users) == 2

    def test_get_by_id(self, repo):
        user = repo.create_user(
            username="byid", display_name="ID", plain_password="password123"
        )
        found = repo.get_by_id(user.id)
        assert found.username == "byid"

    def test_get_by_username(self, repo):
        repo.create_user(
            username="byname", display_name="Name", plain_password="password123"
        )
        found = repo.get_by_username("byname")
        assert found is not None

    def test_get_nonexistent(self, repo):
        assert repo.get_by_id(9999) is None
        assert repo.get_by_username("ghost") is None
```

---

## Entregables

| # | Entregable | Criterio de aceptación |
|---|---|---|
| E5.1 | `agente_dwh/platform/auth.py` | Hash bcrypt, JWT access/refresh, decode, extract user_id. |
| E5.2 | `agente_dwh/platform/user_repo.py` | CRUD de usuarios con validaciones. |
| E5.3 | Hash bcrypt funciona | `hash_password("x")` produce hash diferente a "x". `verify_password` valida correctamente. |
| E5.4 | JWT con expiración | Token access expira en 8h, refresh en 7d. Token expirado lanza excepción. |
| E5.5 | Token tampered rechazado | Un JWT modificado no pasa `decode_token()`. |
| E5.6 | Validación de username | Mínimo 3 chars, alfanumérico + underscore. |
| E5.7 | Validación de password | Mínimo 8 caracteres. |
| E5.8 | Username único | Duplicado lanza `ValueError`. |
| E5.9 | Authenticate funciona | Credenciales correctas → user. Incorrectas → None. |
| E5.10 | Change password funciona | Old password correcto → cambio. Incorrecto → False. |
| E5.11 | Roles válidos | Solo `viewer`, `editor`, `admin`. Otro lanza error. |
| E5.12 | Login en Streamlit | Formulario de login, token en session_state, logout funcional. |
| E5.13 | Multi-tenancy verificado | User A no puede ver queries/dashboards de User B. |
| E5.14 | `tests/test_auth.py` pasa | `pytest tests/test_auth.py -v` — 0 fallos. |
| E5.15 | `tests/test_user_repo.py` pasa | `pytest tests/test_user_repo.py -v` — 0 fallos. |
| E5.16 | Tests de fases anteriores pasan | `pytest tests/ -v` — 0 fallos. |

---

## Validación por agente

```bash
# 1. Importabilidad
python -c "from agente_dwh.platform.auth import hash_password, verify_password, create_access_token, decode_token; print('OK: auth')"
python -c "from agente_dwh.platform.user_repo import UserRepo; print('OK: user_repo')"

# 2. Tests nuevos
pytest tests/test_auth.py -v
pytest tests/test_user_repo.py -v

# 3. Todos los tests
pytest tests/ -v

# 4. Verificar dependencias instalables
pip install "python-jose[cryptography]>=3.3" "passlib[bcrypt]>=1.7" --dry-run 2>&1 | head -5
```
