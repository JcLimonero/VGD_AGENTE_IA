# CLAUDE.md — Guía de desarrollo VGD Agente IA

Este archivo es leído automáticamente por Claude Code. Contiene las reglas del proyecto que deben seguirse en cualquier equipo y por cualquier colaborador.

---

## Arquitectura general

- **Backend:** FastAPI (`agente_dwh/api_routes.py`) + agente LLM local (`agente_dwh/agent.py`)
- **Frontend:** Next.js en `frontend/`
- **LLM local:** Ollama (genera SQL y resúmenes en lenguaje natural)
- **DWH:** PostgreSQL — base `dwh`, vistas homologadas con prefijo `h_`
- **Plataforma:** PostgreSQL — base `vgd_platform` (usuarios, queries guardadas, dashboards)

---

## Modelo de datos del DWH — REGLAS FIJAS

Estas reglas definen cómo el agente debe generar SQL. No cambiar sin validar contra el DWH real.

### Tablas y relaciones

| Tabla | Clave(s) | Descripción |
|---|---|---|
| `h_agencies` | `id_agency` | Catálogo de agencias del grupo. Todas las demás tablas se relacionan por `id_agency`. |
| `h_customers` | `nd_client_dms` + `id_agency` | Clientes del grupo. |
| `h_inventory` | `vin` | Catálogo maestro de unidades (brand, model, version, year, colores, status, km, amount). |
| `h_invoices` | `order_dms`, `vin`, `id_agency` | Unidades vendidas. |
| `h_orders` | `order_dms`, `nd_client_dms`, `id_agency` | Movimientos del proceso de venta por unidad. |
| `h_services` | `vin`, `id_agency` | Servicios realizados a unidades. |
| `h_customer_vehicle` | `nd_client_dms`, `id_agency`, `vin` | Vehículos que tiene cada cliente. |

### Reglas de JOIN

```sql
-- Agencia (cualquier tabla)
JOIN h_agencies a ON tabla.id_agency = a.id_agency

-- Datos de la unidad
JOIN h_inventory inv ON tabla.vin = inv.vin

-- Cliente (siempre con AMBAS columnas)
JOIN h_customers c ON c.nd_client_dms = o.nd_client_dms AND c.id_agency = o.id_agency

-- Vehículos de un cliente (siempre con AMBAS columnas)
JOIN h_customers c ON c.nd_client_dms = cv.nd_client_dms AND c.id_agency = cv.id_agency

-- Detalle de venta (cuando se necesita cliente o proceso de venta)
JOIN h_orders o ON h_invoices.order_dms = o.order_dms
```

### Ventas — h_invoices

- Filtro **obligatorio**: `state IN ('Vendido', 'Facturacion del vehiculo')`
- Para conteos y montos: usar `h_invoices` sola, sin JOINs extra.
- Para nombre de agencia: `JOIN h_agencies a ON h_invoices.id_agency = a.id_agency`
- Para datos de la unidad: `JOIN h_inventory inv ON h_invoices.vin = inv.vin`
- Para datos del cliente: pasar primero por `h_orders` (h_invoices **no tiene** `nd_client_dms`)
- **NUNCA** usar `stage_name` para filtrar ventas.

### h_services — Servicios

- Se relaciona con `h_inventory` por `vin` y con `h_agencies` por `id_agency`.
- ⚠️ `h_services.order_dms` = folio del servicio. **No tiene relación con `h_orders.order_dms`.**

### Anti-patrones — NUNCA hacer esto

- No agregar JOINs que no sean necesarios para responder la pregunta.
- No usar `h_inventory` para consultas de ventas (usar `h_invoices`).
- No leer `nd_client_dms` desde `h_invoices` (esa columna no existe ahí).
- No unir `h_services` con `h_orders` por `order_dms`.
- No usar tablas inexistentes: `sales`, `vehicles`, `service_appointments`, `insurance_policies`.

### Ejemplos de SQL correcto

```sql
-- Ventas totales
SELECT COUNT(*) AS total_ventas
FROM h_invoices
WHERE state IN ('Vendido', 'Facturacion del vehiculo');

-- Ventas por agencia
SELECT a.name AS agency_name, COUNT(i.id) AS total_ventas
FROM h_invoices i
JOIN h_agencies a ON i.id_agency = a.id_agency
WHERE i.state IN ('Vendido', 'Facturacion del vehiculo')
GROUP BY a.name ORDER BY total_ventas DESC;

-- Ventas con datos de la unidad
SELECT i.billing_date, inv.brand, inv.model, inv.year, i.vin
FROM h_invoices i
JOIN h_inventory inv ON i.vin = inv.vin
WHERE i.state IN ('Vendido', 'Facturacion del vehiculo')
ORDER BY i.billing_date DESC;

-- Ventas con datos del cliente
SELECT i.billing_date, c.bussines_name, o.brand, o.model
FROM h_invoices i
JOIN h_orders o ON i.order_dms = o.order_dms
JOIN h_customers c ON c.nd_client_dms = o.nd_client_dms AND c.id_agency = o.id_agency
WHERE i.state IN ('Vendido', 'Facturacion del vehiculo');

-- Vehículos de un cliente
SELECT cv.vin, inv.brand, inv.model, inv.year
FROM h_customer_vehicle cv
JOIN h_inventory inv ON cv.vin = inv.vin
JOIN h_customers c ON c.nd_client_dms = cv.nd_client_dms AND c.id_agency = cv.id_agency
WHERE c.bussines_name = 'NOMBRE_CLIENTE';

-- Servicios de una unidad
SELECT s.vin, a.name AS agency_name, s.service_type, s.service_date
FROM h_services s
JOIN h_agencies a ON s.id_agency = a.id_agency
WHERE s.vin = 'VIN_AQUI';
```

---

## Configuración del agente

### Variables de entorno clave (`.env`)

| Variable | Descripción |
|---|---|
| `DWH_URL` | Conexión al DWH PostgreSQL |
| `PLATFORM_DB_URL` | Conexión a la BD de plataforma (usuarios, dashboards) |
| `LLM_ENDPOINT` | URL de Ollama (default: `http://localhost:11434`) |
| `LLM_MODEL` | Modelo Ollama a usar |
| `AGENTE_DWH_LLM_PROFILE` | Perfil de prompts: `vgd` (producción) o `default` |
| `JWT_SECRET` | Clave para firmar tokens JWT |

### Perfil de prompts

- El perfil `vgd` activa `SYSTEM_PROMPT_VGD` y `SQL_FIX_PROMPT_VGD` en `agent.py`.
- Siempre usar `vgd` para este proyecto. El perfil `default` es genérico y no conoce el modelo de datos.
- El perfil se resuelve automáticamente si `DWH_URL` contiene `vgd_dwh`.

### Schema hint

- Archivo principal: `schema_hint_dwh.txt`
- Contiene el esquema del DWH y las reglas de negocio fijas en la sección `=== MODELO DE DATOS — REGLAS FIJAS ===`.
- Si se modifica el DWH (nuevas columnas, tablas), actualizar también este archivo.
- Cambios en el schema hint requieren reinicio del servidor (el agente lo cachea al arrancar).

---

## Estructura de archivos relevante

```
agente_dwh/
  agent.py          # Lógica del agente: prompts, generación y corrección de SQL
  api_routes.py     # API FastAPI: endpoints, autenticación JWT, respuesta en lenguaje natural
  web.py            # UI Streamlit (modo desarrollo)
  config.py         # Configuración desde variables de entorno
  llm_local.py      # Cliente Ollama
  sql_guard.py      # Validación de SQL (solo lectura, tablas permitidas)

frontend/
  app/chat/page.tsx          # Chat UI: renderiza markdown y tabla de resultados
  app/hooks/useChat.ts       # Hook que llama a la API y guarda resultados
  app/services/api.ts        # Cliente HTTP (axios)
  app/types/index.ts         # Tipos TypeScript

schema_hint_dwh.txt  # Esquema del DWH + reglas de negocio para el LLM
```

---

## Respuestas del agente

- El campo `message` de la API siempre devuelve lenguaje natural (no SQL).
- El SQL generado va en `results.generated_sql` — el frontend lo muestra con el botón "Ver SQL" / "Copiar SQL".
- Para resúmenes de ≤15 filas se usa heurística (sin llamada extra al LLM).
- Para conjuntos mayores se llama al LLM con los primeros 50 registros.

---

## Cómo reiniciar el servidor tras cambios

```bash
# El servidor usa uvicorn --reload (detecta cambios en .py)
# Para forzar recarga tras editar schema_hint_dwh.txt:
touch agente_dwh/agent.py
```
