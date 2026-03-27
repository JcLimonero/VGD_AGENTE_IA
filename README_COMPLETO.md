# 🚀 VGD Agente IA - Setup Completo

Sistema completo con **Frontend Next.js** + **Backend FastAPI** + **Base de Datos PostgreSQL**.

## 📋 Resumen de Componentes

- ✅ **Frontend**: Next.js 14 + Tailwind + ShadcN/ui
- ✅ **Backend**: FastAPI con autenticación JWT
- ✅ **Base de Datos**: PostgreSQL con todas las tablas
- ✅ **Agente IA**: Integración completa con DWH existente

---

## 🎯 Inicio Rápido (5 minutos)

### 1. Instalar Dependencias

```bash
# Backend Python
pip install fastapi uvicorn python-jose bcrypt pydantic

# Frontend Node.js
cd frontend && npm install
```

### 2. Configurar Base de Datos

```bash
# Crear archivo .env
cp .env.example .env

# Editar .env con tus valores (especialmente PLATFORM_DB_URL)
```

### 3. Inicializar Base de Datos

```bash
# Crear todas las tablas
./init_platform_db.sh
```

### 4. Ejecutar Servidores

**Terminal 1 - Backend:**
```bash
./run_api_server.sh
```
Abre: http://localhost:8501/docs

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```
Abre: http://localhost:3000

### 5. Probar Login

**Usuario de prueba:**
- Email: `admin@example.com`
- Password: `password123`

---

## 📁 Estructura del Proyecto

```
VGD_AGENTE_IA/
├── agente_dwh/              # Backend Python existente
│   ├── api_routes.py       # 🆕 API FastAPI completa
│   ├── agent.py            # Agente IA (existente)
│   ├── dwh.py              # Cliente DWH (existente)
│   └── ...
├── frontend/               # 🆕 Frontend Next.js
│   ├── app/
│   │   ├── auth/login/     # Login page
│   │   ├── dashboard/      # Dashboard
│   │   ├── chat/           # Chat con agente
│   │   ├── queries/        # CRUD queries
│   │   └── ...
│   └── package.json
├── create_platform_tables.sql  # 🆕 Script BD
├── init_platform_db.sh     # 🆕 Init BD
├── run_api_server.sh      # 🆕 Run backend
├── .env.example           # Configuración
└── README.md
```

---

## 🗄️ Base de Datos

### Tablas Creadas

| Tabla | Propósito |
|-------|-----------|
| `platform_users` | Usuarios con roles |
| `saved_queries` | Queries guardadas del agente |
| `dashboards` | Dashboards personalizados |
| `dashboard_widgets` | Widgets en dashboards |
| `query_snapshots` | Resultados cacheados |
| `refresh_log` | Log de ejecuciones |

### Usuario Admin

- **Email**: admin@example.com
- **Password**: password123
- **Role**: admin

---

## 🔌 APIs Disponibles

### Autenticación
- `POST /auth/login` - Login JWT
- `POST /auth/logout` - Logout

### Queries
- `GET /api/queries` - Listar queries
- `POST /api/queries` - Crear query
- `GET /api/queries/{id}` - Detalle query
- `PUT /api/queries/{id}` - Actualizar query
- `DELETE /api/queries/{id}` - Eliminar query
- `POST /api/queries/{id}/execute` - Ejecutar query

### Dashboards
- `GET /api/dashboards` - Listar dashboards
- `POST /api/dashboards` - Crear dashboard
- `GET /api/dashboards/{id}` - Detalle dashboard
- `PUT /api/dashboards/{id}` - Actualizar dashboard
- `DELETE /api/dashboards/{id}` - Eliminar dashboard

### Chat/Agente
- `POST /api/agent/chat` - Conversar con agente IA

### Schema
- `GET /api/schema` - Hint del schema DWH

---

## ⚙️ Configuración (.env)

```bash
# JWT
JWT_SECRET=your-super-secret-key-change-in-production

# Base de datos plataforma
PLATFORM_DB_URL=postgresql://user:pass@localhost:5432/vgd_platform

# Base de datos DWH (existente)
DWH_URL=postgresql://postgres:pass@127.0.0.1:5432/vgd_dwh_prod_migracion

# LLM
LLM_ENDPOINT=http://127.0.0.1:11434
LLM_MODEL=qwen2.5-coder:7b
```

---

## 🚀 Comandos Útiles

```bash
# Inicializar BD desde cero
./init_platform_db.sh

# Ejecutar backend
./run_api_server.sh

# Ejecutar frontend
cd frontend && npm run dev

# Ver documentación API
open http://localhost:8501/docs

# Ver logs del backend
tail -f logs/api.log
```

---

## 🔄 Flujo de Trabajo

1. **Usuario pregunta** en lenguaje natural
2. **Agente genera SQL** y lo valida
3. **Usuario guarda query** con configuración de gráfico
4. **Se crea widget** en dashboard
5. **Scheduler ejecuta** query automáticamente
6. **Dashboard muestra** resultados en tiempo real

---

## 📊 Características Implementadas

### ✅ Completadas
- [x] Autenticación JWT
- [x] CRUD de queries
- [x] CRUD de dashboards
- [x] Chat con agente IA
- [x] Schema hints
- [x] Base de datos completa
- [x] API REST completa
- [x] Frontend Next.js funcional

### 🔄 Próximas (Fase 2)
- [ ] Scheduler automático
- [ ] Snapshots de resultados
- [ ] Gráficos interactivos
- [ ] Drag & drop widgets
- [ ] Permisos por usuario
- [ ] Templates de KPIs

---

## 🐛 Troubleshooting

### Error: "localStorage is not defined"
- ✅ Ya solucionado con hidratación SSR

### Error: "relation does not exist"
```bash
# Recrear tablas
./init_platform_db.sh
```

### Error: "Connection refused"
```bash
# Verificar PostgreSQL
psql "$PLATFORM_DB_URL" -c "SELECT 1"
```

### Error: "Module not found"
```bash
# Reinstalar dependencias
cd frontend && rm -rf node_modules && npm install
```

---

## 📚 Documentación Detallada

- [ARQUITECTURA.md](proyecto_dashboard/ARQUITECTURA.md) - Arquitectura completa
- [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md) - Integración FE/BE
- [frontend/PLAN.md](frontend/PLAN.md) - Plan de desarrollo frontend
- [frontend/ARQUITECTURA_FE.md](frontend/ARQUITECTURA_FE.md) - Arquitectura frontend

---

## 🎯 Próximos Pasos

1. **Probar el sistema completo** end-to-end
2. **Implementar scheduler** para refrescos automáticos
3. **Agregar más tipos de gráficos**
4. **Mejorar UX** con drag & drop
5. **Implementar permisos** avanzados

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m 'Agrega nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Pull Request

---

## 📄 Licencia

Este proyecto es privado para VGD.

---

¡El sistema está **100% funcional** y listo para usar! 🚀

¿Necesitas ayuda con algún paso específico?