# Guía de Integración Backend Python ↔ Frontend Next.js

## 🔌 Arquitectura de Integración

```
┌──────────────────┐          ┌──────────────────┐
│   Next.js        │  HTTP    │   FastAPI        │
│   (Frontend)     │◄────────►│   (Python)       │
│   :3000          │  JSON    │   :8501          │
└──────────────────┘          └──────────────────┘
                                      │
                                      ▼
                              ┌──────────────────┐
                              │  agente_dwh      │
                              │  (Lógica IA)     │
                              │  + DWH           │
                              └──────────────────┘
```

---

## 📦 Paso 1: Crear Wrapper FastAPI

### Instalar dependencias

```bash
cd /Users/jclimonero/Developer/VGD_AGENTE_IA

# Activar venv Python
source .venv/bin/activate

# Instalar FastAPI
pip install fastapi uvicorn python-jose bcrypt python-dotenv pydantic
```

### Crear archivo API

**Archivo:** `agente_dwh/api_routes.py`

```python
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
from functools import lru_cache
import os

from agente_dwh.agent import DwhAgent, resolve_llm_profile
from agente_dwh.app_services import build_dwh_client, build_llm_client
from agente_dwh.config import effective_dwh_url

# ============ Configuración ============
secret_key = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
algorithm = "HS256"
access_token_expire_minutes = 30

# ============ Modelos Pydantic ============
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class ChatMessage(BaseModel):
    message: str
    context: Optional[dict] = None

class QueryRequest(BaseModel):
    name: str
    description: str
    sql: str
    tags: Optional[List[str]] = []

# ============ App FastAPI ============
app = FastAPI(
    title="VGD Agente IA API",
    description="API para frontend Next.js",
    version="0.1.0",
)

# ============ CORS ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Utilidades ============
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """Verificar JWT token"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

@lru_cache(maxsize=1)
def get_dwh_agent():
    """Obtener instancia del agente (caché)"""
    llm_profile = resolve_llm_profile()
    dwh_client = build_dwh_client()
    llm_client = build_llm_client(llm_profile)
    return DwhAgent(dwh_client=dwh_client, llm_client=llm_client)

# ============ Auth Endpoints ============
@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login y obtener JWT token
    
    Credenciales de prueba:
    - email: admin@example.com
    - password: password123
    """
    # TODO: Validar contra base de datos real
    # Por ahora: validación dummy
    if request.email == "admin@example.com" and request.password == "password123":
        access_token_expires = timedelta(minutes=access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": request.email, "user_id": "1"},
            expires_delta=access_token_expires
        )
        
        return LoginResponse(
            access_token=access_token,
            user={
                "id": "1",
                "email": request.email,
                "name": "Admin User",
                "role": "admin",
            }
        )
    
    raise HTTPException(status_code=401, detail="Credenciales inválidas")

@app.post("/auth/logout")
async def logout():
    """Logout (ya que usamos JWT, solo es simbólico)"""
    return {"message": "Logout exitoso"}

# ============ Health Check ============
@app.get("/health")
async def health_check():
    """Health check del servidor"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "backend": effective_dwh_url(),
    }

# ============ Agent Chat ============
@app.post("/api/agent/chat")
async def agent_chat(request: ChatMessage):
    """
    Chat con el agente IA
    
    Ejemplo:
    {
        "message": "¿Cuál fue la venta total del mes?",
        "context": {}
    }
    """
    try:
        agent = get_dwh_agent()
        response = agent.process_message(request.message, context=request.context)
        
        return {
            "message": response.text,
            "query_executed": hasattr(response, 'query_executed') and response.query_executed,
            "query_id": getattr(response, 'query_id', None),
            "results": getattr(response, 'results', None),
            "suggestions": getattr(response, 'suggestions', []),
            "confidence": getattr(response, 'confidence', 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ Queries CRUD ============
@app.get("/api/queries")
async def get_queries():
    """Listar todas las queries"""
    # TODO: Conectar con base de datos
    return [
        {
            "id": "1",
            "name": "Ventas Mes Actual",
            "description": "Total de ventas del mes en curso",
            "sql": "SELECT SUM(amount) FROM sales WHERE ...",
            "created_by": "admin@example.com",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_favorite": True,
            "tags": ["ventas", "mes"],
        }
    ]

@app.post("/api/queries")
async def create_query(request: QueryRequest):
    """Crear nueva query"""
    # TODO: Guardar en base de datos
    new_query = {
        "id": "new_id",
        "name": request.name,
        "description": request.description,
        "sql": request.sql,
        "created_by": "admin@example.com",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "is_favorite": False,
        "tags": request.tags,
    }
    return new_query

@app.get("/api/queries/{query_id}")
async def get_query(query_id: str):
    """Obtener detalle de una query"""
    # TODO: Obtener de base de datos
    return {
        "id": query_id,
        "name": "Ventas Ejemplo",
        "sql": "SELECT * FROM sales",
    }

@app.post("/api/queries/{query_id}/execute")
async def execute_query(query_id: str):
    """Ejecutar una query guardada"""
    try:
        agent = get_dwh_agent()
        # TODO: Obtener SQL de base de datos
        sql = "SELECT 1 as test"
        
        results = agent.execute_sql(sql)
        
        return {
            "query_id": query_id,
            "executed_at": datetime.now().isoformat(),
            "rows": results,
            "column_names": ["test"],
            "total_rows": len(results),
            "execution_time_ms": 100,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ Schema ============
@app.get("/api/schema")
async def get_schema_hint():
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
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ Dashboards ============
@app.get("/api/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Obtener configuración de dashboard"""
    # TODO: Obtener de base de datos
    return {
        "id": dashboard_id,
        "name": "Dashboard Principal",
        "widgets": [],
    }

@app.put("/api/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, data: dict):
    """Actualizar configuración de dashboard"""
    # TODO: Guardar en base de datos
    return {"id": dashboard_id, "status": "updated"}

# ============ Entrada ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
```

---

## 🚀 Paso 2: Ejecutar FastAPI

```bash
# Desde la raíz del proyecto
cd /Users/jclimonero/Developer/VGD_AGENTE_IA

# Opción 1: Ejecutar directamente
python -m uvicorn agente_dwh.api_routes:app --reload --port 8501

# Opción 2: Crear script
cat > run_api.sh << 'EOF'
#!/bin/bash
source .venv/bin/activate
python -m uvicorn agente_dwh.api_routes:app --reload --port 8501
EOF

chmod +x run_api.sh
./run_api.sh
```

---

## 🧪 Paso 3: Testear Integración

### Test 1: Health Check

```bash
curl http://localhost:8501/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "backend": "..."
}
```

### Test 2: Login

```bash
curl -X POST http://localhost:8501/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password123"}'
```

Respuesta esperada:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "1",
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "admin"
  }
}
```

### Test 3: Chat

```bash
curl -X POST http://localhost:8501/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué tal?"}'
```

---

## 🔐 Paso 4: Variables de Entorno

**Archivo:** `.env`

```
# Backend
BACKEND_URL=http://localhost:8501

# JWT
JWT_SECRET=your-super-secret-key-change-in-production

# Database (si usas)
DATABASE_URL=postgresql://user:pass@localhost/dbname

# LLM
LLM_PROVIDER=ollama
LLM_MODEL=mistral

# DWH
DWH_DATABASE_URL=postgresql://user:pass@dwh-server/dwh_name
```

---

## ✅ Paso 5: Conectar Frontend

El frontend Next.js ya está configurado en `app/services/api.ts`:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8501'

// Ya puedes hacer:
const result = await apiClient.login('admin@example.com', 'password123')
const response = await apiClient.sendMessage('Mi pregunta')
```

---

## 📝 Paso 6: Próximas Implementaciones

### Backend (Python):

1. **Autenticación real:**
   - Conectar con base de datos MySQL/PostgreSQL
   - Hash de passwords con bcrypt
   - Refresh tokens

2. **Queries CRUD:**
   - Guardar queries en BD
   - Recuperar historial
   - Validar SQL (SQL Guard)

3. **Chat mejorado:**
   - Historial persistente
   - Intent recognition
   - Query suggestions

4. **Dashboards:**
   - Guardar configuraciones
   - Permisos por usuario
   - Compartir dashboards

### Frontend (Next.js):

1. **Mejorar componentes:**
   - Agregar ShadcN components
   - Tablas interactivas
   - Gráficos con Recharts

2. **Validaciones:**
   - Cliente-side form validation
   - Error boundaries
   - Loading states

3. **Caché:**
   - React Query para data fetching
   - SWR para sync
   - Offline support

---

## 🎯 Checklist de Integración

- [ ] Dependencias de FastAPI instaladas
- [ ] Archivo `agente_dwh/api_routes.py` creado
- [ ] FastAPI corriendo en puerto 8501
- [ ] Health check retorna 200
- [ ] Login funciona
- [ ] Frontend se conecta al backend
- [ ] Chat funciona end-to-end
- [ ] Queries se ejecutan
- [ ] Token JWT válido

---

## 🔗 Referencias

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [JWT en Python](https://python-jose.readthedocs.io/)
- [Pydantic Validation](https://docs.pydantic.dev/)
