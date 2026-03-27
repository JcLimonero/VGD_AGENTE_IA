from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import jwt
from datetime import datetime, timedelta
from functools import lru_cache
import os
import uuid
import bcrypt
import json
from contextlib import asynccontextmanager
from pathlib import Path

from agente_dwh.bootstrap_env import load_dotenv_from_project_root

# Igual que Streamlit: cargar raíz/.env antes de leer DWH_URL, JWT_SECRET, etc.
load_dotenv_from_project_root()

from agente_dwh.agent import DwhAgent, QueryResult
from agente_dwh.app_services import build_agent_service
from agente_dwh.config import Config, ConfigError, effective_dwh_url
from agente_dwh.sql_guard import validate_read_only_sql
from agente_dwh.web_layers.adapters import read_schema_hint

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
    saved_query_id: int
    pos_x: int = 0
    pos_y: int = 0
    width: int = 6
    height: int = 4
    widget_config: Dict[str, Any] = {}

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

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
    if n == 1:
        parts = [f"- **{k}:** {rows[0][k]}" for k in keys]
        return "Según los datos consultados:\n" + "\n".join(parts)
    if n <= 15 and len(keys) <= 6:
        lines: list[str] = []
        for row in rows:
            pairs = [f"**{k}:** {row.get(k)}" for k in keys]
            lines.append("- " + " · ".join(pairs))
        return f"Se encontraron **{n} registros**:\n" + "\n".join(lines)
    if n <= 50 and len(keys) <= 10:
        preview = min(5, n)
        lines = []
        for row in rows[:preview]:
            pairs = [f"**{k}:** {row.get(k)}" for k in keys]
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
        results = {
            "rows": jsonable_encoder(rows_cap),
            "column_names": col_names,
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
    """Obtener usuario actual desde JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido")

    # En una implementación real, buscar usuario en BD
    # Por ahora, devolver datos mock
    return {
        "id": user_id,
        "email": payload.get("sub", "user@example.com"),
        "display_name": "Usuario",
        "role": "admin"
    }

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

# ============ CORS ============
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
            "SELECT id, username, display_name, role, password_hash FROM platform_users WHERE username = %s",
            (request.email,),
        ).fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base de datos: {e}") from e

    if row is None or not verify_password(request.password, row[4]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    access_token = create_access_token(
        data={"sub": row[1], "user_id": str(row[0])},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(row[0]),
            "email": row[1],
            "display_name": row[2],
            "role": row[3],
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
# SQL demo alineado con vistas h_* (validate_vgd_dwh_sql rechaza tablas como `sales`).
_STUB_DEMO_SAVED_SQL = (
    "SELECT DATE_TRUNC('month', billing_date) AS month, COUNT(*) AS total "
    "FROM h_invoices "
    "WHERE state IN ('Vendido', 'Facturacion del vehiculo') "
    "GROUP BY DATE_TRUNC('month', billing_date) ORDER BY 1"
)


def _stub_saved_query_row(query_id: str, user_id: str) -> Dict[str, Any]:
    """Documento de ejemplo hasta persistir en BD (misma forma que listado/get)."""
    return {
        "id": query_id,
        "user_id": user_id,
        "title": "Ventas por Mes",
        "original_question": "¿Cuánto vendimos cada mes?",
        "sql_text": _STUB_DEMO_SAVED_SQL,
        "chart_type": "line",
        "chart_config": {"xAxis": "month", "yAxis": "total"},
        "refresh_interval": "1 hour",
        "is_active": True,
        "tags": ["ventas", "mensual"],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


# Queries creadas vía POST (en memoria hasta BD real). id -> documento con user_id.
_queries_by_id: Dict[str, Dict[str, Any]] = {}


def _demo_query_for_list(user_id: Any) -> Dict[str, Any]:
    """Ítem fijo de ejemplo id=1 (no está en _queries_by_id)."""
    uid = str(user_id)
    return {
        "id": "1",
        "user_id": uid,
        "title": "Ventas por Mes",
        "original_question": "¿Cuánto vendimos cada mes?",
        "sql_text": _STUB_DEMO_SAVED_SQL,
        "chart_type": "line",
        "chart_config": {"xAxis": "month", "yAxis": "total"},
        "refresh_interval": "1 hour",
        "is_active": True,
        "tags": ["ventas", "mensual"],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def _list_queries_for_user(user_id: Any) -> list[Dict[str, Any]]:
    uid = str(user_id)
    demo = _demo_query_for_list(uid)
    saved = [d for d in _queries_by_id.values() if str(d.get("user_id")) == uid]
    saved.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
    return [demo] + saved


def _get_query_doc(query_id: str, user_id: Any) -> Dict[str, Any] | None:
    """Documento persistido en memoria o None."""
    doc = _queries_by_id.get(query_id)
    if doc is None:
        return None
    if str(doc.get("user_id")) != str(user_id):
        return None
    return doc


@app.get("/api/queries")
async def get_queries(current_user: dict = Depends(get_current_user)):
    """Listar todas las queries del usuario"""
    # TODO: base de datos real; mientras: demo + creadas en memoria en esta sesión de API
    return _list_queries_for_user(current_user["id"])

@app.post("/api/queries")
async def create_query(query: QueryCreate, current_user: dict = Depends(get_current_user)):
    """Crear nueva query"""
    # Validar SQL
    try:
        validate_read_only_sql(query.sql_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL inválido: {str(e)}")

    # TODO: Guardar en base de datos
    new_query = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "title": query.title,
        "original_question": query.original_question,
        "sql_text": query.sql_text,
        "chart_type": query.chart_type,
        "chart_config": query.chart_config,
        "refresh_interval": query.refresh_interval,
        "is_active": True,
        "tags": query.tags,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    _queries_by_id[new_query["id"]] = new_query
    return new_query

@app.get("/api/queries/{query_id}")
async def get_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Obtener detalle de una query"""
    uid = current_user["id"]
    if query_id == "1":
        return _stub_saved_query_row("1", str(uid))
    doc = _get_query_doc(query_id, uid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    return doc

@app.put("/api/queries/{query_id}")
async def update_query(query_id: str, updates: QueryUpdate, current_user: dict = Depends(get_current_user)):
    """Actualizar query"""
    uid = current_user["id"]
    patch = updates.dict(exclude_unset=True)
    if "sql_text" in patch:
        try:
            validate_read_only_sql(patch["sql_text"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"SQL inválido: {str(e)}")
    if query_id == "1":
        existing = _stub_saved_query_row(query_id, str(uid))
        merged = {**existing, **patch}
        merged["updated_at"] = datetime.utcnow().isoformat()
        return merged
    doc = _get_query_doc(query_id, uid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    merged = {**doc, **patch}
    merged["updated_at"] = datetime.utcnow().isoformat()
    _queries_by_id[query_id] = merged
    return merged

@app.delete("/api/queries/{query_id}")
async def delete_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar query"""
    uid = current_user["id"]
    if query_id == "1":
        raise HTTPException(status_code=400, detail="No se puede eliminar la query de demostración")
    if _get_query_doc(query_id, uid) is None:
        raise HTTPException(status_code=404, detail="Query no encontrada")
    del _queries_by_id[query_id]
    return {"message": "Query eliminada"}

@app.post("/api/queries/{query_id}/execute")
async def execute_query(query_id: str, current_user: dict = Depends(get_current_user)):
    """Ejecutar una query guardada"""
    try:
        uid = current_user["id"]
        if query_id == "1":
            stub = _stub_saved_query_row(query_id, str(uid))
        else:
            doc = _get_query_doc(query_id, uid)
            if doc is None:
                raise HTTPException(status_code=404, detail="Query no encontrada")
            stub = doc

        agent = get_dwh_agent()
        start_time = datetime.utcnow()
        results = agent.execute_read_only_sql(stub["sql_text"])
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds() * 1000

        rows = results or []
        col_names = list(rows[0].keys()) if rows else []

        # TODO: Guardar snapshot en BD
        snapshot = {
            "id": "snapshot_id",
            "saved_query_id": query_id,
            "result_data": rows,
            "row_count": len(rows),
            "executed_at": datetime.utcnow().isoformat(),
            "duration_ms": duration,
            "success": True,
            "error_message": None,
        }

        return {
            "query_id": query_id,
            "executed_at": snapshot["executed_at"],
            "rows": jsonable_encoder(rows[:500]),
            "column_names": col_names,
            "total_rows": len(rows),
            "execution_time_ms": duration,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ Endpoints de Dashboards ============
@app.get("/api/dashboards")
async def get_dashboards(current_user: dict = Depends(get_current_user)):
    """Listar dashboards del usuario"""
    # TODO: Obtener de base de datos
    return [
        {
            "id": "1",
            "user_id": current_user["id"],
            "title": "Mi Dashboard",
            "is_default": True,
            "layout_cols": 12,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
    ]

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
    """Obtener dashboard con widgets"""
    # TODO: Obtener de base de datos con widgets
    dashboard = {
        "id": dashboard_id,
        "user_id": current_user["id"],
        "title": "Mi Dashboard",
        "is_default": True,
        "layout_cols": 12,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "widgets": [
            {
                "id": "1",
                "dashboard_id": dashboard_id,
                "saved_query_id": "1",
                "pos_x": 0,
                "pos_y": 0,
                "width": 6,
                "height": 4,
                "display_order": 0,
                "widget_config": {},
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
    }
    return dashboard

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
    """Crear widget en dashboard"""
    # TODO: Guardar en base de datos
    new_widget = {
        "id": "new_widget_id",
        "dashboard_id": dashboard_id,
        "saved_query_id": widget.saved_query_id,
        "pos_x": widget.pos_x,
        "pos_y": widget.pos_y,
        "width": widget.width,
        "height": widget.height,
        "display_order": 0,
        "widget_config": widget.widget_config,
        "created_at": datetime.utcnow().isoformat(),
    }
    return new_widget

@app.put("/api/dashboards/{dashboard_id}/widgets/{widget_id}")
async def update_widget(dashboard_id: str, widget_id: str, widget: WidgetCreate, current_user: dict = Depends(get_current_user)):
    """Actualizar widget"""
    # TODO: Actualizar en base de datos
    updated = {
        "id": widget_id,
        "dashboard_id": dashboard_id,
        "updated_at": datetime.utcnow().isoformat(),
        **widget.dict()
    }
    return updated

@app.delete("/api/dashboards/{dashboard_id}/widgets/{widget_id}")
async def delete_widget(dashboard_id: str, widget_id: str, current_user: dict = Depends(get_current_user)):
    """Eliminar widget"""
    # TODO: Eliminar de base de datos
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