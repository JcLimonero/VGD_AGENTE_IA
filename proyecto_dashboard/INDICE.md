# Proyecto Dashboard — Índice de Fases

## Orden de implementación

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

## Archivos

| Fase | Archivo | Enfoque | Tests asociados |
|---|---|---|---|
| 1 | [FASE_01_PERSISTENCIA.md](FASE_01_PERSISTENCIA.md) | Tablas ORM + CRUD saved_queries + botón guardar | `test_platform_models.py`, `test_saved_queries_repo.py` |
| 2 | [FASE_02_SNAPSHOTS.md](FASE_02_SNAPSHOTS.md) | Servicio de ejecución y almacenamiento de resultados | `test_snapshot_service.py` |
| 3 | [FASE_03_DASHBOARD_BASICO.md](FASE_03_DASHBOARD_BASICO.md) | Dashboard repo + widget renderer + página dashboard | `test_dashboard_repo.py`, `test_widget_renderer.py` |
| 4 | [FASE_04_SCHEDULER.md](FASE_04_SCHEDULER.md) | Scheduler APScheduler + circuit breaker + refresh_log | `test_scheduler.py` |
| 5 | [FASE_05_AUTENTICACION.md](FASE_05_AUTENTICACION.md) | JWT + bcrypt + user_repo + login Streamlit | `test_auth.py`, `test_user_repo.py` |
| 6 | [FASE_06_GRID_DINAMICO.md](FASE_06_GRID_DINAMICO.md) | Grid drag-and-drop con streamlit-elements | `test_grid_layout.py` |
| 7 | [FASE_07_CATALOGO_TEMPLATES.md](FASE_07_CATALOGO_TEMPLATES.md) | Catálogo de KPIs pre-armados + match automático | `test_kpi_templates.py` |

---

## Documento de arquitectura

- [ARQUITECTURA.md](ARQUITECTURA.md) — Visión completa, modelo de datos, diagramas.

---

## Instrucciones para el agente implementador

1. **Lee primero** `ARQUITECTURA.md` para entender la visión completa.
2. **Implementa cada fase en orden**: las dependencias entre fases están explicitadas.
3. **Cada archivo de fase contiene**:
   - Tareas numeradas (T{fase}.{número}).
   - Código de referencia con firmas de funciones y clases.
   - Reglas de negocio y validaciones requeridas.
   - Casos de prueba completos con código pytest listo para copiar.
   - Tabla de entregables con criterios de aceptación.
   - Comandos de validación para que un agente validador los ejecute.
4. **Criterio de éxito por fase**: todos los tests de la fase pasan + tests de fases anteriores siguen pasando (no regresión).
5. **No modificar** archivos existentes del agente (`agent.py`, `dwh.py`, `sql_guard.py`, etc.) salvo donde la fase lo indique explícitamente (ej: extender `config.py` en Fase 1).

---

## Resumen de archivos nuevos por fase

### Fase 1
- `agente_dwh/platform/__init__.py`
- `agente_dwh/platform/models.py`
- `agente_dwh/platform/saved_queries_repo.py`
- `tests/test_platform_models.py`
- `tests/test_saved_queries_repo.py`

### Fase 2
- `agente_dwh/platform/snapshot_service.py`
- `tests/test_snapshot_service.py`

### Fase 3
- `agente_dwh/platform/dashboard_repo.py`
- `agente_dwh/dashboard_ui/__init__.py`
- `agente_dwh/dashboard_ui/components/__init__.py`
- `agente_dwh/dashboard_ui/components/widget_renderer.py`
- `tests/test_dashboard_repo.py`
- `tests/test_widget_renderer.py`

### Fase 4
- `agente_dwh/platform/scheduler.py`
- `tests/test_scheduler.py`

### Fase 5
- `agente_dwh/platform/auth.py`
- `agente_dwh/platform/user_repo.py`
- `tests/test_auth.py`
- `tests/test_user_repo.py`

### Fase 6
- `agente_dwh/dashboard_ui/components/grid_layout.py`
- `tests/test_grid_layout.py`

### Fase 7
- `agente_dwh/kpi_templates.py` (reemplaza el existente)
- `tests/test_kpi_templates.py` (reemplaza el existente)
