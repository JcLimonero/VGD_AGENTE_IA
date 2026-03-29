from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import jwt
from datetime import datetime, timedelta
from functools import lru_cache
import os
import bcrypt
import json
from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from agente_dwh.bootstrap_env import load_dotenv_from_project_root

# Igual que Streamlit: cargar raíz/.env antes de leer DWH_URL, JWT_SECRET, etc.
load_dotenv_from_project_root()

from agente_dwh.agent import DwhAgent, QueryResult
from agente_dwh.app_services import build_agent_service
from agente_dwh.config import Config, ConfigError, effective_dwh_url
from agente_dwh.sql_guard import validate_read_only_sql
from agente_dwh.web_layers.adapters import read_schema_hint
from agente_dwh.column_labels import (
    localize_summary_markdown,
    spanish_column_label,
    spanish_labels_map,
)
from agente_dwh.spanish_text import fix_semicolon_enye_typo
from agente_dwh.saved_queries_db import (
    db_create_saved_query,
    db_delete_saved_query,
    db_get_saved_query,
    db_insert_query_snapshot,
    db_list_saved_queries,
    db_update_saved_query,
    user_id_to_int,
)
from agente_dwh.dashboard_db import (
    db_create_dashboard_widget,
    db_delete_dashboard_widget,
    db_get_dashboard_detail,
    db_get_user_dashboard_stats,
    db_list_dashboards,
    db_patch_dashboard_widget,
    resolve_dashboard_id,
)
from agente_dwh.roles_db import (
    db_list_roles,
    db_get_role,
    db_create_role,
    db_update_role,
    db_set_role_agency_permissions,
    db_delete_role,
)
from agente_dwh.users_db import (
    db_list_users,
    db_get_user,
    db_create_user,
    db_update_user,
    db_delete_user,
    db_change_password,
)
from psycopg import errors as pg_errors

# ============ Configuración ============
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

# ============ Modelos Pydantic ============
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserCreate(BaseModel):
    email: str
    display_name: str
    password: str

class QueryCreate(BaseModel):
    title: str
    original_question: str
    sql_text: str
    chart_type: str = "table"
    chart_config: Dict[str, Any] = {}
    refresh_interval: Optional[str] = None
    tags: List[str] = []

class QueryUpdate(BaseModel):
    title: Optional[str] = None
    original_question: Optional[str] = None
    sql_text: Optional[str] = None
    chart_type: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    refresh_interval: Optional[str] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None

class DashboardCreate(BaseModel):
    title: str = "Mi Dashboard"
    layout_cols: int = 12

class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    layout_cols: Optional[int] = None

class WidgetCreate(BaseModel):
    saved_query_id: str
    pos_x: int = 0
    pos_y: int = 0
    width: int = 6
    height: int = 4
    widget_config: Dict[str, Any] = {}


class DashboardWidgetPatch(BaseModel):
    """Fusión parcial en `widget_config` y/o geometría en la cuadrícula (segmentos)."""

    widget_config: Optional[Dict[str, Any]] = None
    pos_x: Optional[int] = None
    pos_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

# ---- Admin: usuarios ----
class AdminUserCreate(BaseModel):
    email: str
    display_name: str
    password: str
    role_id: int

class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = None
    role_id: Optional[int] = None

class AdminPasswordReset(BaseModel):
    new_password: str

# ---- Admin: roles ----
class RoleAgencyPermission(BaseModel):
    id_agency: str
    all_objects: bool = True
    objects: List[str] = []

class AdminRoleCreate(BaseModel):
    name: str
    description: str = ""
    can_create_users: bool = False
    can_access_config: bool = False
    all_agencies: bool = False
    agencies: List[RoleAgencyPermission] = []

class AdminRoleUpdate(BaseModel):
    name: str
    description: str = ""
    can_create_users: bool = False
    can_access_config: bool = False
    all_agencies: bool = False
    agencies: List[RoleAgencyPermission] = []

# ============ Utilidades ============
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """Verificar JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def hash_password(password: str) -> str:
    """Hash password con bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verificar password contra hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def _schema_hint_text(cfg: Config) -> str:
    t = read_schema_hint(cfg.schema_hint_file)
    if t:
        return t
    root = Path(__file__).resolve().parents[1]
    p = root / "schema_hint_dwh.txt"
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return ""


@lru_cache(maxsize=1)
def get_dwh_agent() -> DwhAgent:
    """Instancia única del agente (misma configuración que Streamlit vía env)."""
    cfg = Config.from_env()
    schema_hint = _schema_hint_text(cfg)
    return build_agent_service(
        dwh_url=cfg.dwh_url,
        llm_endpoint=cfg.llm_endpoint,
        llm_model=cfg.llm_model,
        row_limit=cfg.max_rows,
        llm_timeout_seconds=cfg.llm_timeout_seconds,
        schema_hint=schema_hint,
        cache_ttl_seconds=cfg.cache_ttl_seconds,
        cache_max_entries=cfg.cache_max_entries,
        llm_temperature=cfg.llm_temperature,
        llm_seed=cfg.llm_seed,
        schema_hint_file=cfg.schema_hint_file,
    )


_NL_SUMMARY_SYSTEM_PROMPT = (
    "Eres un asistente de analítica que explica resultados de consultas en español claro y profesional.\n"
    "Reglas:\n"
    "1) Usa solo la información del JSON proporcionado; no inventes datos.\n"
    "2) Entre 1 y 4 frases cortas o un párrafo breve. Ve directo al resultado.\n"
    "3) Si hay muchas filas, resume el patrón o los valores más relevantes.\n"
    "4) No uses tablas markdown. Puedes usar listas cortas con guiones.\n"
    "5) No repitas la pregunta al inicio.\n"
    "6) Cantidades monetarias: formato MXN $X,XXX.XX (pesos mexicanos).\n"
    "7) Todo en español; traduce etiquetas en inglés al explicar.\n"
    "8) No incluyas código SQL en tu respuesta."
)


def _heuristic_nl_summary(rows: list[dict[str, Any]]) -> str | None:
    """Resumen heurístico sin LLM. None solo para conjuntos muy grandes (evita respuestas distintas por LLM)."""
    n = len(rows)
    if n == 0:
        return "La consulta no devolvió ningún resultado. Puedes intentar ampliar los criterios de búsqueda."
    keys = list(rows[0].keys())

    def _lbl(k: str) -> str:
        return spanish_column_label(k)

    if n == 1:
        parts = [f"- **{_lbl(k)}:** {rows[0][k]}" for k in keys]
        return "Según los datos consultados:\n" + "\n".join(parts)
    if n <= 15 and len(keys) <= 6:
        lines: list[str] = []
        for row in rows:
            pairs = [f"**{_lbl(k)}:** {row.get(k)}" for k in keys]
            lines.append("- " + " · ".join(pairs))
        return f"Se encontraron **{n} registros**:\n" + "\n".join(lines)
    if n <= 50 and len(keys) <= 10:
        preview = min(5, n)
        lines = []
        for row in rows[:preview]:
            pairs = [f"**{_lbl(k)}:** {row.get(k)}" for k in keys]
            lines.append("- " + " · ".join(pairs))
        more = (
            f"\n\n…y **{n - preview}** filas más (consulta la tabla para el detalle completo)."
            if n > preview
            else ""
        )
        return f"Se encontraron **{n} registros**:\n" + "\n".join(lines) + more
    return None


def _build_nl_message(question: str, rows: list[dict[str, Any]], agent: "DwhAgent") -> str:
    """Genera el mensaje en lenguaje natural para el usuario."""
    n = len(rows)
    if n == 0:
        return "La consulta no devolvió ningún resultado. Puedes intentar ampliar los criterios de búsqueda."
    h = _heuristic_nl_summary(rows)
    if h is not None:
        return h
    # Delegamos al LLM para conjuntos grandes
    try:
        sample = rows[:50]
        payload = json.dumps(sample, ensure_ascii=False, default=str)
        user_msg = (
            f"Pregunta del usuario:\n{question.strip()}\n\n"
            f"Total de filas devueltas: {n}\n"
            f"Muestra (hasta 50 filas):\n{payload}\n\n"
            "Redacta la explicación en español."
        )
        return agent._llm.generate_natural_language(
            system_prompt=_NL_SUMMARY_SYSTEM_PROMPT,
            user_prompt=user_msg,
        )
    except Exception:
        return f"Se encontraron **{n} registros**. Consulta la tabla de resultados para ver el detalle completo."


def _query_result_to_chat_payload(result: QueryResult, agent: "DwhAgent | None" = None) -> dict[str, Any]:
    """Adapta QueryResult del agente al JSON que espera el frontend Next.js."""
    sql = (result.generated_sql or "").strip()
    direct = result.direct_answer
    n = len(result.rows)
    rows_cap = result.rows[:200]

    if direct is not None:
        message = direct
        query_executed = False
        results = None
    elif sql:
        query_executed = True
        if agent is not None:
            message = _build_nl_message(result.question, result.rows, agent)
        elif n == 0:
            message = "La consulta no devolvió ningún resultado."
        else:
            h = _heuristic_nl_summary(result.rows)
            message = h if h is not None else f"Se encontraron **{n} registros**. Consulta la tabla de resultados para ver el detalle."
        col_names = list(rows_cap[0].keys()) if rows_cap else []
        if col_names:
            message = localize_summary_markdown(message, col_names)
        labels_map = spanish_labels_map(col_names) if col_names else {}
        results = {
            "rows": jsonable_encoder(rows_cap),
            "column_names": col_names,
            "column_labels_es": labels_map,
            "total_rows": n,
            "generated_sql": sql,
        }
    else:
        message = "No se generó una respuesta con SQL ni texto directo."
        query_executed = False
        results = None

    return {
        "message": message,
        "query_executed": query_executed,
        "query_id": None,
        "results": results,
        "suggestions": [],
        "confidence": 1.0 if (direct is not None or (sql and n >= 0)) else 0.5,
    }


def _run_agent_answer(message: str, context: Optional[Dict[str, Any]]) -> dict[str, Any]:
    ctx = context or {}
    transcript = str(ctx.get("conversation_transcript") or ctx.get("transcript") or "")
    extra = str(ctx.get("prompt_extra") or "")
    vf = ctx.get("vehicle_focus")
    vehicle_focus = vf if isinstance(vf, dict) else None
    agent = get_dwh_agent()
    result = agent.answer(
        message,
        prompt_extra=extra,
        conversation_transcript=transcript,
        vehicle_focus=vehicle_focus,
    )
    return _query_result_to_chat_payload(result, agent=agent)

# ============ Dependencias FastAPI ============
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Obtener usuario actual desde JWT token incluyendo permisos del rol."""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido")

    return {
        "id": user_id,
        "email": payload.get("sub", "user@example.com"),
        "display_name": payload.get("display_name") or "Usuario",
        "role": payload.get("role") or "viewer",
        "role_id": payload.get("role_id"),
        "can_create_users": bool(payload.get("can_create_users", False)),
        "can_access_config": bool(payload.get("can_access_config", False)),
    }


def require_sysadmin(current_user: dict = Depends(get_current_user)):
    """Requiere rol sysadmin."""
    if current_user.get("role") != "sysadmin":
        raise HTTPException(status_code=403, detail="Se requiere acceso de SysAdmin")
    return current_user


def require_can_manage_users(current_user: dict = Depends(get_current_user)):
    """Requiere sysadmin o can_create_users=True."""
    if current_user.get("role") != "sysadmin" and not current_user.get("can_create_users"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar usuarios")
    return current_user

# ============ App FastAPI ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Iniciando VGD Agente IA API")
    try:
        Config.from_env()
        print("✅ DWH_URL y configuración del agente cargadas desde el entorno.")
    except ConfigError as exc:
        print(f"⚠️ Agente DWH no disponible hasta corregir el entorno: {exc}")
    yield
    # Shutdown
    print("🛑 Apagando VGD Agente IA API")

app = FastAPI(
    title="VGD Agente IA API",
    description="API para dashboard inteligente de consultas DWH",
    version="0.1.0",
    lifespan=lifespan
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propaga o genera X-Request-ID para enlazar logs cliente ↔ servidor."""

    _HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get(self._HEADER)
        cid = raw.strip() if raw and raw.strip() else str(uuid.uuid4())
        request.state.request_id = cid
        response = await call_next(request)
        response.headers[self._HEADER] = cid
        return response


# ============ CORS ============
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Endpoints de Autenticación ============
def _get_platform_db_conn():
    """Conexión a la BD de plataforma (usuarios, dashboards)."""
    import psycopg
    url = os.getenv("PLATFORM_DB_URL", "")
    # psycopg acepta DSN postgresql://... directamente
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login con credenciales de platform_users."""
    try:
        conn = _get_platform_db_conn()
        row = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.password_hash,
                   r.id AS role_id, r.name AS role_name,
                   r.can_create_users, r.can_access_config
            FROM platform_users u
            LEFT JOIN platform_roles r ON u.role_id = r.id
            WHERE u.username = %s
            """,
            (request.email,),
        ).fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e

    if row is None or not verify_password(request.password, row[3]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    role_name = row[5] or "viewer"
    access_token = create_access_token(
        data={
            "sub": row[1],
            "user_id": str(row[0]),
            "role": role_name,
            "role_id": str(row[4]) if row[4] else None,
            "can_create_users": bool(row[6]) if row[6] is not None else False,
            "can_access_config": bool(row[7]) if row[7] is not None else False,
            "display_name": row[2],
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(row[0]),
            "email": row[1],
            "display_name": row[2],
            "role": role_name,
            "role_id": row[4],
            "can_create_users": bool(row[6]) if row[6] is not None else False,
            "can_access_config": bool(row[7]) if row[7] is not None else False,
        },
    )

@app.post("/auth/register")
async def register(user: UserCreate):
    """Registrar nuevo usuario"""
    # TODO: Implementar registro real con BD
    raise HTTPException(status_code=501, detail="Registro no implementado aún")

@app.post("/auth/logout")
async def logout():
    """Logout (ya que usamos JWT, solo es simbólico)"""
    return {"message": "Logout exitoso"}


@app.get("/auth/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    """Perfil del usuario autenticado (valida el Bearer JWT)."""
    return current_user


@app.get("/api/auth/me")
async def api_auth_me(current_user: dict = Depends(get_current_user)):
    """Alias por si el cliente o un proxy espera prefijo `/api`."""
    return current_user


# ============ Endpoints de Administración ============

@app.get("/api/admin/agencies")
async def admin_list_agencies(current_user: dict = Depends(require_can_manage_users)):
    """Lista las agencias del DWH para configurar permisos de roles."""
    try:
        import psycopg
        dwh_url = os.getenv("DWH_URL", "").replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(dwh_url)
        rows = conn.execute(
            "SELECT id_agency, name FROM h_agencies WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        conn.close()
        return [{"id_agency": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error consultando agencias: {e}") from e


# --- Gestión de Usuarios ---

@app.get("/api/admin/users")
async def admin_list_users(current_user: dict = Depends(require_can_manage_users)):
    """Lista todos los usuarios de la plataforma."""
    try:
        return db_list_users()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.post("/api/admin/users", status_code=201)
async def admin_create_user(
    body: AdminUserCreate,
    current_user: dict = Depends(require_can_manage_users),
):
    """Crea un nuevo usuario. Solo sysadmin o usuarios con can_create_users."""
    try:
        pw_hash = hash_password(body.password)
        user = db_create_user(
            username=body.email,
            display_name=body.display_name,
            password_hash=pw_hash,
            role_id=body.role_id,
        )
        return user
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(
    user_id: int,
    body: AdminUserUpdate,
    current_user: dict = Depends(require_sysadmin),
):
    """Actualiza nombre o rol de un usuario. Solo sysadmin."""
    try:
        updated = db_update_user(user_id, body.display_name, body.role_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.delete("/api/admin/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: int,
    current_user: dict = Depends(require_sysadmin),
):
    """Elimina un usuario. Solo sysadmin. No puede eliminar su propia cuenta."""
    if str(user_id) == str(current_user.get("id")):
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    try:
        deleted = db_delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.post("/api/admin/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    body: AdminPasswordReset,
    current_user: dict = Depends(require_sysadmin),
):
    """Resetea la contraseña de un usuario. Solo sysadmin."""
    try:
        pw_hash = hash_password(body.new_password)
        updated = db_change_password(user_id, pw_hash)
        if not updated:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"message": "Contraseña actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


# --- Gestión de Roles ---

@app.get("/api/admin/roles")
async def admin_list_roles(current_user: dict = Depends(require_can_manage_users)):
    """Lista todos los roles disponibles."""
    try:
        return db_list_roles()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.get("/api/admin/roles/{role_id}")
async def admin_get_role(
    role_id: int,
    current_user: dict = Depends(require_sysadmin),
):
    """Obtiene un rol con sus permisos completos."""
    try:
        role = db_get_role(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        return role
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.post("/api/admin/roles", status_code=201)
async def admin_create_role(
    body: AdminRoleCreate,
    current_user: dict = Depends(require_sysadmin),
):
    """Crea un nuevo rol dinámico. Solo sysadmin."""
    try:
        role = db_create_role(
            name=body.name,
            description=body.description,
            can_create_users=body.can_create_users,
            can_access_config=body.can_access_config,
            all_agencies=body.all_agencies,
        )
        if not body.all_agencies and body.agencies:
            db_set_role_agency_permissions(
                role["id"],
                [a.model_dump() for a in body.agencies],
            )
        return db_get_role(role["id"])
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre")
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.put("/api/admin/roles/{role_id}")
async def admin_update_role(
    role_id: int,
    body: AdminRoleUpdate,
    current_user: dict = Depends(require_sysadmin),
):
    """Actualiza un rol dinámico y sus permisos. Solo sysadmin."""
    try:
        updated = db_update_role(
            role_id=role_id,
            name=body.name,
            description=body.description,
            can_create_users=body.can_create_users,
            can_access_config=body.can_access_config,
            all_agencies=body.all_agencies,
        )
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail="Rol no encontrado o es un rol base (no editable)",
            )
        db_set_role_agency_permissions(
            role_id,
            [a.model_dump() for a in body.agencies],
        )
        return db_get_role(role_id)
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre")
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


@app.delete("/api/admin/roles/{role_id}", status_code=204)
async def admin_delete_role(
    role_id: int,
    current_user: dict = Depends(require_sysadmin),
):
    """Elimina un rol dinámico. No permite eliminar roles base. Solo sysadmin."""
    try:
        deleted = db_delete_role(role_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Rol no encontrado o es un rol base (no eliminable)",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e


# ============ Raíz (evita confusión con el frontend Next.js) ============
@app.get("/")
async def root():
    """
    Este proceso es solo la API REST (JSON). No sirve `/_next/*` ni CSS/JS del dashboard.

    Si ves 404 en layout.css / main-app.js, el navegador está pidiendo estáticos de Next.js
    a este puerto: abre el frontend en http://localhost:3000 (npm run dev en frontend/).
    Streamlit (portal legacy) suele ir en otro puerto, p. ej. 8502, para no chocar con la API.
    """
    return {
        "service": "vgd-agente-api",
        "docs": "/docs",
        "health": "/health",
        "hint": (
            "La UI Next.js no está aquí. Ejecuta `npm run dev` en frontend/ y abre "
            "http://localhost:3000 — la API sigue en este puerto (NEXT_PUBLIC_API_BASE_URL)."
        ),
    }


# ============ Endpoints de Health ============
@app.get("/health")
async def health_check():
    """Health check del servidor"""
    try:
        backend_url = effective_dwh_url(os.getenv("DWH_URL", ""))
    except Exception:
        backend_url = "config_error"
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "backend": backend_url,
        "timestamp": datetime.utcnow().isoformat()
    }

# ============ Endpoints de Queries ============
def _api_user_int_id(current_user: dict) -> int:
    try:
        return user_id_to_int(current_user["id"])
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=401, detail="Usuario inválido") from e


def _parse_saved_query_id_param(query_id: str) -> int:
    try:
        return int(query_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Query no encontrada")


def _raise_platform_db_error(exc: BaseException) -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            "No se pudo usar la base de datos de plataforma: "
            f"{exc}. Comprueba PLATFORM_DB_URL y el esquema "
            "(create_platform_tables.sql o init_platform_db.sh)."
        ),
    ) from exc


@app.get("/api/queries")
async def get_queries(current_user: dict = Depends(get_current_user)):
    """Listar queries guardadas del usuario (PostgreSQL / saved_queries)."""
    try:
        return db_list_saved_queries(_api_user_int_id(current_user))
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)


@app.post("/api/queries")
async def create_query(query: QueryCreate, current_user: dict = Depends(get_current_user)):
    """Crear nueva query"""
    try:
        validate_read_only_sql(query.sql_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL inválido: {str(e)}")
    try:
        return db_create_saved_query(
            _api_user_int_id(current_user),
            fix_semicolon_enye_typo(query.title.strip()),
            fix_semicolon_enye_typo(query.original_question.strip()),
            query.sql_text,
            query.chart_type,
            query.chart_config,
            query.refresh_interval,
            query.tags,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)


@app.get("/api/queries/{query_id}")
async def get_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener detalle de una query"""
    qid = _parse_saved_query_id_param(query_id)
    try:
        doc = db_get_saved_query(qid, _api_user_int_id(current_user))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    return doc


@app.put("/api/queries/{query_id}")
async def update_query(query_id: str, updates: QueryUpdate, current_user: dict = Depends(get_current_user)):
    """Actualizar query"""
    qid = _parse_saved_query_id_param(query_id)
    patch = updates.dict(exclude_unset=True)
    if "title" in patch and isinstance(patch["title"], str):
        patch["title"] = fix_semicolon_enye_typo(patch["title"].strip())
    if "original_question" in patch and isinstance(patch["original_question"], str):
        patch["original_question"] = fix_semicolon_enye_typo(patch["original_question"].strip())
    if "sql_text" in patch:
        try:
            validate_read_only_sql(patch["sql_text"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"SQL inválido: {str(e)}")
    try:
        updated = db_update_saved_query(qid, _api_user_int_id(current_user), patch)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if updated is None:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    return updated


@app.delete("/api/queries/{query_id}")
async def delete_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar query"""
    qid = _parse_saved_query_id_param(query_id)
    try:
        ok = db_delete_saved_query(qid, _api_user_int_id(current_user))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if not ok:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    return {"message": "Query eliminada"}


@app.post("/api/queries/{query_id}/execute")
async def execute_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Ejecutar una query guardada"""
    qid: int | None = None
    try:
        qid = _parse_saved_query_id_param(query_id)
        try:
            stub = db_get_saved_query(qid, _api_user_int_id(current_user))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except pg_errors.Error as e:
            _raise_platform_db_error(e)
        if stub is None:
            raise HTTPException(status_code=404, detail="Query no encontrada")

        agent = get_dwh_agent()
        start_time = datetime.utcnow()
        err_msg: str | None = None
        rows: list[dict[str, Any]] = []
        try:
            results = agent.execute_read_only_sql(stub["sql_text"])
            rows = results or []
        except Exception as run_exc:
            err_msg = str(run_exc)
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            try:
                db_insert_query_snapshot(
                    qid,
                    {"error": True},
                    0,
                    duration,
                    False,
                    err_msg[:2000],
                )
            except (RuntimeError, pg_errors.Error):
                pass
            raise HTTPException(status_code=500, detail=err_msg) from run_exc

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000

        col_names = list(rows[0].keys()) if rows else []
        enc_rows = jsonable_encoder(rows[:500])
        snapshot_payload = {
            "columns": col_names,
            "total_rows": len(rows),
            "preview_rows": enc_rows[:40],
            "truncated_preview": len(rows) > 40,
        }
        try:
            db_insert_query_snapshot(qid, snapshot_payload, len(rows), duration, True, None)
        except (RuntimeError, pg_errors.Error):
            pass

        executed_at = datetime.utcnow().isoformat()
        return {
            "query_id": query_id,
            "executed_at": executed_at,
            "rows": enc_rows,
            "column_names": col_names,
            "column_labels_es": spanish_labels_map(col_names) if col_names else {},
            "total_rows": len(rows),
            "execution_time_ms": duration,
            "generated_sql": stub.get("sql_text") or "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# ============ Endpoints de Dashboards ============
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Métricas del usuario para el panel principal (consultas, ejecuciones, fallos, usuarios si admin)."""
    uid = _api_user_int_id(current_user)
    try:
        return db_get_user_dashboard_stats(uid)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)


@app.get("/api/dashboards")
async def get_dashboards(current_user: dict = Depends(get_current_user)):
    """Listar dashboards del usuario (PostgreSQL)."""
    try:
        return db_list_dashboards(_api_user_int_id(current_user))
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)

@app.post("/api/dashboards")
async def create_dashboard(dashboard: DashboardCreate, current_user: dict = Depends(get_current_user)):
    """Crear nuevo dashboard"""
    # TODO: Guardar en base de datos
    new_dashboard = {
        "id": "new_id",
        "user_id": current_user["id"],
        "title": dashboard.title,
        "is_default": False,
        "layout_cols": dashboard.layout_cols,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return new_dashboard

@app.get("/api/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener dashboard con widgets. Usa `default` como alias del dashboard por defecto."""
    uid = _api_user_int_id(current_user)
    try:
        did = resolve_dashboard_id(dashboard_id, uid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard no encontrado")
    try:
        detail = db_get_dashboard_detail(did, uid)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if detail is None:
        raise HTTPException(status_code=404, detail="Dashboard no encontrado")
    return detail

@app.put("/api/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, updates: DashboardUpdate, current_user: dict = Depends(get_current_user)):
    """Actualizar dashboard"""
    # TODO: Actualizar en base de datos
    updated = {
        "id": dashboard_id,
        "user_id": current_user["id"],
        "updated_at": datetime.utcnow().isoformat(),
        **updates.dict(exclude_unset=True)
    }
    return updated

@app.delete("/api/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar dashboard"""
    # TODO: Eliminar de base de datos
    return {"message": "Dashboard eliminado"}

# ============ Endpoints de Widgets ============
@app.post("/api/dashboards/{dashboard_id}/widgets")
async def create_widget(dashboard_id: str, widget: WidgetCreate, current_user: dict = Depends(get_current_user)):
    """Crear widget en dashboard. `dashboard_id` puede ser numérico o la palabra `default`."""
    uid = _api_user_int_id(current_user)
    try:
        did = resolve_dashboard_id(dashboard_id, uid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard no encontrado")
    try:
        sqid = int(str(widget.saved_query_id).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="saved_query_id inválido")
    wc = dict(widget.widget_config or {})
    if isinstance(wc.get("title"), str) and wc["title"].strip():
        wc["title"] = fix_semicolon_enye_typo(wc["title"].strip())
    try:
        new_widget = db_create_dashboard_widget(
            did,
            uid,
            sqid,
            widget.pos_x,
            widget.pos_y,
            widget.width,
            widget.height,
            wc,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if new_widget is None:
        raise HTTPException(
            status_code=400,
            detail="No se pudo crear el widget: dashboard o consulta guardada no encontrada, o no te pertenecen.",
        )
    return new_widget

@app.put("/api/dashboards/{dashboard_id}/widgets/{widget_id}")
async def update_widget(dashboard_id: str, widget_id: str, widget: WidgetCreate, current_user: dict = Depends(get_current_user)):
    """Actualizar widget (compat; preferir PATCH para fusionar widget_config)."""
    # TODO: PUT completo en BD
    updated = {
        "id": widget_id,
        "dashboard_id": dashboard_id,
        "updated_at": datetime.utcnow().isoformat(),
        **widget.dict()
    }
    return updated


@app.patch("/api/dashboards/{dashboard_id}/widgets/{widget_id}")
async def patch_dashboard_widget(
    dashboard_id: str,
    widget_id: str,
    body: DashboardWidgetPatch,
    current_user: dict = Depends(get_current_user),
):
    """Fusiona widget_config y/o actualiza pos_x, pos_y, width, height (cuadrícula del dashboard)."""
    uid = _api_user_int_id(current_user)
    try:
        did = resolve_dashboard_id(dashboard_id, uid)
        wid = int(widget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard o widget no encontrado")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    if "widget_config" in patch and patch["widget_config"] is not None and not patch["widget_config"]:
        patch.pop("widget_config", None)
    if not patch:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    merge_cfg = patch.get("widget_config")
    if isinstance(merge_cfg, dict) and isinstance(merge_cfg.get("title"), str) and merge_cfg["title"].strip():
        merge_cfg = {**merge_cfg, "title": fix_semicolon_enye_typo(merge_cfg["title"].strip())}
        patch = {**patch, "widget_config": merge_cfg}
    try:
        updated = db_patch_dashboard_widget(
            did,
            wid,
            uid,
            merge_config=patch.get("widget_config"),
            pos_x=patch.get("pos_x"),
            pos_y=patch.get("pos_y"),
            width=patch.get("width"),
            height=patch.get("height"),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if updated is None:
        raise HTTPException(status_code=404, detail="Widget no encontrado")
    return updated


@app.delete("/api/dashboards/{dashboard_id}/widgets/{widget_id}")
async def delete_widget(dashboard_id: str, widget_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar widget del dashboard."""
    uid = _api_user_int_id(current_user)
    try:
        did = resolve_dashboard_id(dashboard_id, uid)
        wid = int(widget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard o widget no encontrado")
    try:
        ok = db_delete_dashboard_widget(did, wid, uid)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except pg_errors.Error as e:
        _raise_platform_db_error(e)
    if not ok:
        raise HTTPException(status_code=404, detail="Widget no encontrado")
    return {"message": "Widget eliminado"}

# ============ Endpoints de Chat/Agent ============
@app.post("/api/agent/chat")
async def agent_chat(request: ChatMessage, current_user: dict = Depends(get_current_user)):
    """
    Chat con el agente IA (requiere autenticación)

    Ejemplo:
    {
        "message": "¿Cuál fue la venta total del mes?",
        "context": {}
    }
    """
    try:
        return _run_agent_answer(request.message, request.context)
    except ConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/api/agent/chat/public")
async def agent_chat_public(request: ChatMessage):
    """
    Chat público con el agente IA (sin autenticación - solo para testing)

    Ejemplo:
    {
        "message": "¿Cuál fue la venta total del mes?",
        "context": {}
    }
    """
    try:
        return _run_agent_answer(request.message, request.context)
    except ConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# ============ Endpoints de Schema ============
@app.get("/api/schema")
async def get_schema_hint(current_user: dict = Depends(get_current_user)):
    """Obtener hint del schema del DWH"""
    try:
        # Leer archivo de hint si existe
        hint_path = "schema_hint_dwh.txt"
        if os.path.exists(hint_path):
            with open(hint_path, "r") as f:
                schema_hint = f.read()
        else:
            schema_hint = "No schema hint available"

        return {
            "schema": schema_hint,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ Entrada ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)