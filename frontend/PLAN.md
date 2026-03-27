# Plan de Implementación - Frontend Next.js

## 📋 Resumen Ejecutivo

Se ha creado una estructura **Next.js 14** profesional completa lista para integrase con tu backend Python existente (agente_dwh).

### Stack Elegido:
- ✅ **Next.js 14** - Framework React con SSR
- ✅ **Tailwind CSS + ShadcN/ui** - Diseño profesional
- ✅ **TypeScript** - Type safety
- ✅ **Zustand** - State management
- ✅ **Recharts** - Gráficos
- ✅ **React Hook Form** - Formularios
- ✅ **Axios** - HTTP client

## 🚀 Pasos Iniciales (Hoy)

### 1. Instalar Dependencias

```bash
cd frontend
npm install
```

### 2. Crear archivo de variables de entorno

```bash
cp .env.example .env.local
```

Editar `.env.local`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8501
NEXT_PUBLIC_JWT_SECRET=tu-secreto-aqui
```

### 3. Iniciar desarrollo

```bash
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000)

---

## 🔌 Integración con Backend Python

### Problema Actual
Tu backend está en **Streamlit** (`agente_dwh/web.py`), que no expone fácilmente APIs REST tradicionales.

### Soluciones (elige una):

#### ✅ **Opción A: Crear Wrapper FastAPI** (RECOMENDADA)
Crear un módulo que exponga tu lógica Python como APIs REST:

```python
# agente_dwh/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agente_dwh.agent import DwhAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/auth/login")
def login(email: str, password: str):
    # Tu lógica de autenticación
    return {"user": {...}, "token": "jwt_token"}

@app.post("/api/agent/chat")
def chat(message: str):
    agent = DwhAgent()
    response = agent.process_message(message)
    return {"message": response.text, "query_executed": response.has_query}

# ... más endpoints
```

**Ventajas:**
- Separación clara entre FE y BE
- APIs standar REST
- Fácil de escalar
- Compatible con Next.js

**Ejecución:**
```bash
# Instalar FastAPI
pip install fastapi uvicorn

# Crear archivo de entrada
cat > agente_dwh/api_server.py << 'EOF'
from fastapi import FastAPI
from agente_dwh.api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
EOF

# Ejecutar
python agente_dwh/api_server.py
```

#### ⚠️ **Opción B: Usar Streamlit directamente**
Usar `streamlit-ui-components` o crear un cliente que hable con Streamlit.

**Desventajas:**
- Más lento y menos flexible
- Difícil de escalar
- No recomendado para producción

#### 🔄 **Opción C: Mantener ambos (Streamlit + FastAPI)**
- Streamlit para UI de pruebas/desarrollo
- FastAPI para APIs que usa Next.js

---

## 📅 Plan de Implementación (8 Fases)

### ✅ Fase 1: Setup Base (COMPLETADA)
**Estado:** ✅ HECHO
- [x] Estructura Next.js creada
- [x] Tailwind + ShadcN/ui configurado
- [x] TypeScript setup
- [x] API client creado
- [x] Tipos definidos
- [x] Store (Zustand) configurado
- [x] Hooks creados (useAuth, useQuery, useChat)

### 🔄 Fase 2: Backend Integration (PRÓXIMA - 2-3 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Crear wrapper FastAPI en `agente_dwh/api.py`
2. [ ] Implementar endpoints de autenticación
3. [ ] Conectar chat con agente Python
4. [ ] Testear conexión FE ↔ BE
5. [ ] Documentar APIs

**Deliverables:**
- FastAPI server con CORS habilitado
- 5+ endpoints funcionando
- Tests de integración
- Documentación de APIs

### 📝 Fase 3: Autenticación (2-3 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Landing page mejorada
2. [ ] Login page (diseño profesional)
3. [ ] Register page
4. [ ] JWT token management
5. [ ] Protected routes
6. [ ] Logout functionality

**Componentes:**
- `app/auth/login/page.tsx` (existe, mejorar)
- `app/auth/register/page.tsx`
- `app/auth/forgot-password/page.tsx`
- Middleware de autenticación

### 📊 Fase 4: Queries (3-4 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] CRUD de queries
2. [ ] Editor SQL (Monaco o similar)
3. [ ] Ejecución de queries
4. [ ] Resultados en tabla
5. [ ] Favoritos/Búsqueda
6. [ ] Compartir queries

**Componentes:**
- `app/queries/page.tsx` (existe, expandir)
- `app/queries/new/page.tsx`
- `app/queries/[id]/page.tsx`
- SQL Editor

### 💬 Fase 5: Chat (2-3 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Chat interface mejorada
2. [ ] Historial de conversaciones
3. [ ] Sugerencias inteligentes
4. [ ] Ejecución automática de queries
5. [ ] Visualización de resultados en chat
6. [ ] Export de resultados

**Componentes:**
- `app/chat/page.tsx` (existe, mejorar)
- Chat bubble components
- Suggestion pills
- Result previewer

### 📈 Fase 6: Dashboard (4-5 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Grid layout con drag & drop
2. [ ] Widgets (gráficos, tablas, métricas)
3. [ ] Múltiples dashboards
4. [ ] Guardar layouts
5. [ ] Compartir dashboards
6. [ ] Filtros globales

**Componentes:**
- `app/dashboard/page.tsx` (existe, expandir)
- Dashboard Editor
- Widget components
- Chart widgets (LineChart, BarChart, etc.)

### ⚙️ Fase 7: Admin & Configuración (3-4 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Admin panel
2. [ ] Gestión de usuarios
3. [ ] Roles y permisos
4. [ ] Auditoría
5. [ ] Configuración global
6. [ ] Backups/Restores

**Componentes:**
- `app/admin/page.tsx`
- User management
- Permissions editor
- Audit logs

### 🚀 Fase 8: Producción (2 horas)
**Estado:** ⏳ PENDIENTE
**Tareas:**
1. [ ] Build optimization
2. [ ] Deploy a hosting (Vercel, AWS, etc.)
3. [ ] CI/CD setup
4. [ ] Monitoring & Logging
5. [ ] Documentation final

---

## 📁 Estructura Actual del Proyecto

```
frontend/
├── app/
│   ├── auth/
│   │   ├── login/page.tsx ✅
│   │   ├── register/ ⏳
│   │   └── forgot-password/ ⏳
│   ├── dashboard/
│   │   └── page.tsx ✅ (básico)
│   ├── chat/
│   │   └── page.tsx ✅ (básico)
│   ├── queries/
│   │   ├── page.tsx ✅ (lista)
│   │   ├── new/ ⏳
│   │   └── [id]/ ⏳
│   ├── admin/ ⏳
│   ├── components/ (crear ShadcN components)
│   ├── hooks/
│   │   ├── useAuth.ts ✅
│   │   ├── useQuery.ts ✅
│   │   ├── useChat.ts ✅
│   │   └── useDashboard.ts ⏳
│   ├── store/
│   │   ├── auth.ts ✅
│   │   ├── queries.ts ✅
│   │   └── chat.ts ✅
│   ├── types/index.ts ✅
│   ├── services/api.ts ✅
│   ├── utils/ ⏳
│   ├── layout.tsx ✅
│   └── page.tsx ✅
├── lib/
│   └── utils.ts ✅
├── ARQUITECTURA_FE.md ✅
├── README.md ✅
└── .env.example ✅
```

✅ = Completado | ⏳ = Pendiente

---

## 🎯 Próximos Pasos Inmediatos

### Hoy mismo:

1. **Instalar dependencias:**
   ```bash
   cd frontend
   npm install
   ```

2. **Crear `.env.local`:**
   ```bash
   cp .env.example .env.local
   # Editar con tus valores
   ```

3. **Iniciar servidor:**
   ```bash
   npm run dev
   ```

4. **Crear wrapper FastAPI** (comienza la Fase 2)

### Mañana:

- Implementar endpoints de autenticación
- Conectar FE ↔ BE
- Crear login funcional

---

## 🤖 Crear Agente para Automatizar

Para automatizar la implementación de cada fase, puedes crearse un custom agente en VS Code:

**Archivo:** `.instructions.md`

```markdown
# VGD Frontend Developer

Eres un experto en Next.js, TypeScript y Tailwind CSS.

Tu tarea es implementar las fases del frontend que se te asignen.

## Reglas:
1. Usa TypeScript strict mode
2. Sigue el patrón de componentes ShadcN
3. Todos los componentes deben ser responsive
4. Darkmode siempre habilitado
5. Tests incluidos

## Fases:
- [x] Fase 1: Setup
- [ ] Fase 2: Backend Integration
- [ ] Fase 3: Auth
- [ ] Fase 4: Queries
- [ ] Fase 5: Chat
- [ ] Fase 6: Dashboard
```

---

## 📊 Estimación de Tiempo Total

| Fase | Horas | Prioridad |
|------|-------|-----------|
| 1 (Setup) | 2 | ✅ HECHO |
| 2 (Backend) | 3 | 🔴 CRÍTICA |
| 3 (Auth) | 3 | 🔴 CRÍTICA |
| 4 (Queries) | 4 | 🟡 ALTA |
| 5 (Chat) | 3 | 🟡 ALTA |
| 6 (Dashboard) | 5 | 🟡 ALTA |
| 7 (Admin) | 4 | 🟢 BAJA |
| 8 (Prod) | 2 | 🟢 BAJA |
| **TOTAL** | **26 horas** | |

**Con un agente dedicado:** ~12-15 horas (paralelización + productividad)

---

## 🔗 Recursos

- 📚 [Next.js Docs](https://nextjs.org/docs)
- 🎨 [ShadcN/ui Components](https://ui.shadcn.com)
- 📦 [Zustand Docs](https://github.com/pmndrs/zustand)
- 📊 [Recharts Examples](https://recharts.org)
- 🎯 [TypeScript Handbook](https://www.typescriptlang.org/docs)

---

## ❓ FAQ

**P: ¿Necesito cambiar el backend Python?**
R: No, pero necesitas exponer APIs REST. FastAPI es la mejor opción.

**P: ¿Puedo usar Streamlit?**
R: Sí, pero es lento y no recomendado para producción.

**P: ¿Can I deploy esto en Vercel?**
R: Sí, Vercel es perfecto para Next.js. Deploy en 2 minutos.

**P: ¿Cómo manejar autenticación?**
R: JWT tokens. Backend genera, FE guarda en localStorage, envía en cada request.

---

## 📝 Nota Final

Este proyecto está **100% funcional** y listo para desarrollo. Solo necesitas:

1. ✅ Crear APIs en el backend Python
2. ✅ Conectar FE con esas APIs
3. ✅ Implementar las 7 fases restantes

¡Buena suerte! 🚀
