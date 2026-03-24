# VGD_AGENTE_IA

Agente de IA para consultar un DWH usando un LLM local (Ollama).

## Objetivo

Permitir que un usuario haga preguntas en lenguaje natural y que el sistema:

1. Genere SQL con un LLM local.
2. Valide que la consulta sea de solo lectura.
3. Ejecute la consulta en el DWH.
4. Devuelva SQL + resultados.

## Requisitos

- Python 3.10+
- Acceso al DWH compatible con SQLAlchemy
- Ollama corriendo en local (por defecto `http://127.0.0.1:11434`)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si tu DWH es PostgreSQL, instala también un driver:

```bash
pip install psycopg[binary]
```

## Variables de entorno

```bash
export DWH_URL='postgresql+psycopg://usuario:password@host:5432/base'
export LLM_ENDPOINT='http://127.0.0.1:11434'
export LLM_MODEL='llama3.1'
export MAX_ROWS='200'
export LLM_TIMEOUT_SECONDS='60'
export CACHE_TTL_SECONDS='120'
export CACHE_MAX_ENTRIES='500'
```

Opcional para dar contexto de tablas/columnas:

```bash
export SCHEMA_HINT_FILE='./schema_hint.txt'
```

## Uso CLI

```bash
agente-dwh "¿Cuáles son las 10 tiendas con mayor venta del último mes?"
```

Salida en JSON:

```bash
agente-dwh --json "ventas por región en 2025"
```

## Seguridad aplicada

- Solo permite una sentencia SQL.
- Solo acepta consultas que comiencen con `SELECT` o `WITH`.
- Bloquea operaciones peligrosas (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.).
- Aplica `LIMIT` automático si no existe uno en la consulta.

## Robustez implementada

- **Plantillas determinísticas para KPIs críticos**:
  - Tiempo promedio de recompra.
  - Oportunidades de seguro.
  - Edad promedio de compradores.
  - Unidad recomendada por edad/género.
  - Estas consultas se resuelven sin depender del LLM.

- **Cache SQL en memoria (LRU + TTL)**:
  - Configurable con `CACHE_TTL_SECONDS` y `CACHE_MAX_ENTRIES`.
  - Expone estadísticas de hit/miss para CLI y web.

- **Observabilidad y alertas**:
  - Eventos por consulta (latencia, filas, éxito, cache hit).
  - Alertas de error y de latencia alta.
  - Panel de observabilidad en la UI web.

- **Tablas materializadas en demo**:
  - `mv_sales_monthly`: ventas mensuales por estado/canal/segmento.
  - `mv_customer_lifecycle`: ciclo de vida por cliente (incluye recompra).
  - Pronóstico usa `mv_sales_monthly` para reducir costo de cómputo.

## Arquitectura mínima

- `agente_dwh/llm_local.py`: cliente Ollama local (`/api/chat`).
- `agente_dwh/sql_guard.py`: validación SQL de solo lectura.
- `agente_dwh/dwh.py`: ejecución de SQL en DWH con SQLAlchemy.
- `agente_dwh/agent.py`: orquestador pregunta -> SQL -> ejecución.
- `agente_dwh/cli.py`: interfaz de línea de comandos.
- `agente_dwh/kpi_templates.py`: motor de plantillas determinísticas KPI.
- `agente_dwh/observability.py`: métricas, eventos y alertas operativas.

## Ejemplo directo con tu base PostgreSQL

Con los datos compartidos, puedes ejecutar así desde una máquina autorizada por `pg_hba.conf`:

```bash
export DWH_URL='postgresql+psycopg://postgres:1234@74.208.78.55:5432/vgd_dwh_migration'
export LLM_ENDPOINT='http://127.0.0.1:11434'
export LLM_MODEL='llama3.1'
export MAX_ROWS='200'
export LLM_TIMEOUT_SECONDS='60'
export SCHEMA_HINT_FILE='./schema_hint_customers.txt'

python3 -m agente_dwh.cli --json "cuantos clientes hay por estado"
```

Notas importantes:

- Si ves un error `no pg_hba.conf entry`, debes permitir la IP origen del cliente en el servidor PostgreSQL.
- Si el entorno no tiene `python`, usa `python3`.
- Si el comando `agente-dwh` no existe en PATH, usa `python3 -m agente_dwh.cli`.

## Sitio web para probar en desktop (Streamlit)

Instala dependencias:

```bash
python3 -m pip install -e .
```

Arranca la web:

```bash
python3 -m streamlit run agente_dwh/web.py
```

Luego abre en tu navegador:

```text
http://localhost:8501
```

En la pantalla:

1. Configura conexión (`DWH_URL`, endpoint/modelo de Ollama, límite).
2. (Opcional) marca **Usar schema_hint_customers.txt**.
3. Escribe la pregunta y pulsa **Consultar**.

La web muestra:
- SQL generado
- resultados en tabla
- JSON completo de respuesta

## Demo sin PostgreSQL (datos simulados)

Para demos, la app web puede usar una base local SQLite generada automaticamente con tablas relacionadas:

- `customers`
- `vehicles`
- `sales`
- `services`

La relacion principal es:

- `customers.id` -> `vehicles.customer_id`
- `customers.id` -> `sales.customer_id`
- `customers.id` -> `services.customer_id`
- `vehicles.id` -> `sales.vehicle_id`
- `vehicles.id` -> `services.vehicle_id`

Además, la demo crea tablas materializadas para acelerar analítica:

- `mv_sales_monthly`
- `mv_customer_lifecycle`

En la web se activa por defecto con la variable:

```bash
export USE_DEMO_DATA=1
```

Preguntas recomendadas para demo:

- "Top 10 clientes por monto total de ventas"
- "Ventas por marca de vehículo en 2025"
- "Clientes con más servicios realizados"
- "Ingreso mensual por servicios"

## Pruebas automáticas

Ejecuta pruebas de regresión:

```bash
python3 -m unittest discover -s tests -v
```

Cobertura incluida:

- Plantillas KPI determinísticas.
- Cache SQL (TTL / hit / miss).
- Pronóstico usando tabla materializada `mv_sales_monthly`.

## Prueba de carga (rápida)

Script de carga concurrente sobre la base demo:

```bash
python3 scripts/load_test.py --threads 6 --iters 40 --ttl 120 --cache-size 500
```

Salida esperada:

- QPS aproximado.
- p50/p95 de latencia.
- ratio de éxito.
- estadísticas de cache.
