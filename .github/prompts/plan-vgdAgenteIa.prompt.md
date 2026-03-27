## Plan: Agregar Diferenciadores a VGD_AGENTE_IA para Grupos de Agencias Automotrices

TL;DR: Implementar funcionalidades avanzadas como dashboards personalizados automatizados, insights predictivos y alertas en tiempo real para diferenciar el producto de herramientas como Power BI, permitiendo a los clientes obtener información precisa sin modificaciones manuales.

**Steps**
1. Implementar persistencia de consultas y resultados (Fase 01 del roadmap) para almacenar snapshots de datos clave.
2. Agregar scheduler para ejecución automática de consultas (Fase 04) y generación de reportes diarios/semanalmente.
3. Desarrollar dashboard básico con widgets personalizables (Fase 03), enfocados en KPIs automotrices como ventas por agencia, pronósticos de servicio.
4. Integrar autenticación y RBAC (Fase 05) para dashboards personalizados por usuario/agencia.
5. Crear catálogo de templates de KPIs (Fase 07) con plantillas predefinidas para agencias automotrices.
6. Agregar alertas en tiempo real para métricas críticas (ventas bajas, cancelaciones de citas).
7. Implementar insights automáticos usando IA para detectar anomalías en ventas o servicios.
8. Desarrollar API para integración con Power BI u otras herramientas, permitiendo push de datos sin modificaciones.

**Relevant files**
- [proyecto_dashboard/FASE_01_PERSISTENCIA.md](proyecto_dashboard/FASE_01_PERSISTENCIA.md) — Guía para snapshots.
- [proyecto_dashboard/FASE_03_DASHBOARD_BASICO.md](proyecto_dashboard/FASE_03_DASHBOARD_BASICO.md) — Diseño de dashboard.
- [proyecto_dashboard/FASE_04_SCHEDULER.md](proyecto_dashboard/FASE_04_SCHEDULER.md) — Automatización.
- [agente_dwh/forecast.py](agente_dwh/forecast.py) — Base para pronósticos.
- [agente_dwh/kpi_templates.py](agente_dwh/kpi_templates.py) — Templates existentes.

**Verification**
1. Probar persistencia guardando y recuperando snapshots de consultas.
2. Validar scheduler ejecutando consultas automáticas y verificando logs.
3. Revisar dashboard renderizando KPIs en UI web.
4. Probar autenticación creando usuarios y asignando dashboards.
5. Ejecutar templates y verificar resultados precisos.
6. Simular alertas y confirmar notificaciones.
7. Evaluar insights automáticos con datos demo.
8. Integrar API y push datos a Power BI mock.

**Decisions**
- Enfoque en agencias automotrices: Priorizar KPIs como ventas por agencia, pronósticos de demanda de repuestos, alertas de cancelaciones.
- Integración con Power BI: API para exportar datos sin requerir cambios en reportes existentes.
- IA local: Mantener privacidad usando Ollama para insights.

**Further Considerations**
1. ¿Qué métricas específicas son críticas para las agencias? (ej. ROI por campaña, satisfacción del cliente)
2. ¿Necesitan integración con sistemas CRM específicos?
3. ¿Qué nivel de personalización requieren los dashboards?
