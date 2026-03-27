# Arquitectura del Frontend - VGD Agente IA

## 🏗️ Visión General

Frontend profesional en **Next.js 14** + **TypeScript** + **Tailwind CSS** + **ShadcN/ui** que se conecta a tu backend Python existente (agente_dwh).

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Dashboard | Chat | Queries | Auth | Admin Panel       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  ShadcN Components | Tailwind CSS | Recharts          │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ HTTP/REST
                   │ (API Client)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│             Backend Python (agente_dwh)                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  /api/agent/chat  | /api/queries | /api/dashboards    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Estructura de Carpetas

```
frontend/
├── app/
│   ├── components/           # Componentes reutilizables
│   │   ├── ui/             # Componentes ShadcN/ui
│   │   ├── layout/         # Header, Sidebar, etc.
│   │   ├── charts/         # Gráficos (Recharts)
│   │   └── dialogs/        # Modales
│   ├── hooks/              # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useQuery.ts
│   │   ├── useChat.ts
│   │   └── useDashboard.ts
│   ├── store/              # Zustand stores
│   │   ├── auth.ts
│   │   ├── queries.ts
│   │   ├── chat.ts
│   │   └── dashboard.ts
│   ├── types/              # TypeScript types
│   ├── services/           # API clients
│   │   └── api.ts          # Instancia axios + métodos
│   ├── utils/              # Utilidades
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home
│   ├── globals.css         # Estilos Tailwind
│   ├── dashboard/
│   │   ├── layout.tsx
│   │   ├── page.tsx        # Dashboard principal
│   │   ├── widgets/        # Widgets del dashboard
│   │   └── new/            # Crear dashboard
│   ├── chat/
│   │   ├── layout.tsx
│   │   ├── page.tsx        # Chat interface
│   │   └── components/
│   ├── queries/
│   │   ├── layout.tsx
│   │   ├── page.tsx        # Lista de queries
│   │   ├── [id]/
│   │   │   ├── page.tsx    # Detalle query
│   │   │   └── edit/
│   │   └── new/            # Crear query
│   └── auth/
│       ├── login/
│       ├── register/
│       └── forgot-password/
├── lib/
│   ├── utils.ts            # cn() para Tailwind
│   └── constants.ts        # Constantes globales
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── .env.example
```

## 🔌 Integración con Backend Python

### 1. **API Client** (`app/services/api.ts`)

```typescript
import { apiClient } from '@/services/api'

// Login
const { token } = await apiClient.login('user@example.com', 'password')
localStorage.setItem('auth_token', token)

// Ejecutar query
const result = await apiClient.executeQuery('query_123')

// Chat con agente
const response = await apiClient.sendMessage('¿Cuál fue la venta del mes?')
```

### 2. **Endpoints del Backend Esperados**

Tu backend Python debe exponer:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/auth/login` | POST | Login y obtener JWT |
| `/api/queries` | GET | Listar queries |
| `/api/queries` | POST | Crear query |
| `/api/queries/{id}` | GET | Detalle query |
| `/api/queries/{id}/execute` | POST | Ejecutar query |
| `/api/agent/chat` | POST | Chat con agente |
| `/api/dashboards/{id}` | GET | Obtener dashboard |
| `/api/schema` | GET | Obtener schema hint |
| `/health` | GET | Health check |

Si usas **Streamlit**, necesitarás crear un **wrapper FastAPI** o exponer estas rutas de otra forma.

### 3. **Modificación del Backend Python**

En tu `agente_dwh/web.py` o donde expongas la API:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Habilitar CORS para Next.js
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
    return {"token": "jwt_token"}

@app.get("/api/queries")
def get_queries():
    # Tus queries
    return []

# ... más endpoints
```

## 🎨 Componentes Disponibles

### ShadcN/ui Components

```typescript
// Botones
<Button>Click me</Button>
<Button variant="outline">Outline</Button>
<Button variant="destructive">Delete</Button>

// Inputs
<Input placeholder="Search..." />
<Select><SelectItem value="1">Option 1</SelectItem></Select>

// Tablas
<Table>
  <TableHeader><TableRow><TableHead>Name</TableHead></TableRow></TableHeader>
  <TableBody>...</TableBody>
</Table>

// Modales
<Dialog>
  <DialogTrigger>Open</DialogTrigger>
  <DialogContent>Content</DialogContent>
</Dialog>

// Alerts
<Alert><AlertTitle>Heads up!</AlertTitle></Alert>
```

### Charts (Recharts)

```typescript
<LineChart data={data}>
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis dataKey="name" />
  <YAxis />
  <Tooltip />
  <Legend />
  <Line type="monotone" dataKey="value" stroke="#8884d8" />
</LineChart>
```

## 🔐 Autenticación

Usando **JWT** tokens:

```typescript
// Hook para autenticación
function useAuth() {
  const { login, logout, user } = useAuthStore()
  
  const handleLogin = async (email, password) => {
    const { token } = await apiClient.login(email, password)
    localStorage.setItem('auth_token', token)
    login({ email })
  }

  return { login: handleLogin, logout, user }
}
```

## 📊 State Management (Zustand)

```typescript
// app/store/queries.ts
import { create } from 'zustand'

const useQueryStore = create((set) => ({
  queries: [],
  selectedQuery: null,
  
  setQueries: (queries) => set({ queries }),
  selectQuery: (query) => set({ selectedQuery: query }),
}))

export default useQueryStore
```

## 🎯 Fases de Implementación

### Fase 1: Setup y Landing
- [x] Estructura Next.js
- [x] Tailwind + ShadcN/ui
- [x] API Client
- [ ] Landing page

### Fase 2: Autenticación
- [ ] Login / Register
- [ ] JWT tokens
- [ ] Protected routes

### Fase 3: Queries
- [ ] Listar queries
- [ ] Créar/Editar queries
- [ ] Ejecutar queries
- [ ] Guardar favoritos

### Fase 4: Dashboard
- [ ] Dashboard grid
- [ ] Widgets
- [ ] Gráficos
- [ ] Drag & drop

### Fase 5: Chat
- [ ] Chat interface
- [ ] Integración agente Python
- [ ] Historia de chat
- [ ] Sugerencias

### Fase 6: Admin
- [ ] Usuarios
- [ ] Permisos
- [ ] Auditoría

## 🚀 Comandos

```bash
# Instalar dependencias
npm install

# Desarrollo
npm run dev

# Build
npm run build

# Producción
npm start

# Type check
npm run type-check

# Lint
npm run lint
```

## 🔗 Variables de Entorno

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8501
NEXT_PUBLIC_JWT_SECRET=your-secret-key
```

## 📚 Recursos

- [Next.js 14 Docs](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com)
- [ShadcN/ui](https://ui.shadcn.com)
- [Recharts](https://recharts.org)
- [Zustand](https://github.com/pmndrs/zustand)
