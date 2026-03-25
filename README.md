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
pip install -U pip setuptools wheel
pip install -e ".[postgres,dev]"
cp .env.example .env
# Edita .env (DWH_URL, credenciales PostgreSQL, LLM_MODEL si aplica)
```

Modelo Ollama recomendado para generar SQL (mismo orden de tamaño que un 7B general):

```bash
ollama pull qwen2.5-coder:7b
```

Comprueba Ollama, PostgreSQL, dataset demo y un ciclo con el LLM:

```bash
python scripts/validate_setup.py
```

La app carga automáticamente el archivo `.env` en la raíz del repo (vía `python-dotenv`).

## Variables de entorno

```bash
export DWH_URL='postgresql+psycopg://usuario:password@host:5432/base'
export LLM_ENDPOINT='http://127.0.0.1:11434'
export LLM_MODEL='qwen2.5-coder:7b'
export LLM_TEMPERATURE='0.2'
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

- **Plantillas KPI determinísticas**: desactivadas por ahora (`match_kpi_template` devuelve siempre `None`); todas las preguntas van al LLM. Se pueden volver a definir en `agente_dwh/kpi_templates.py`.

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
- `agente_dwh/kpi_templates.py`: stub para futuras plantillas KPI (`DeterministicQuery`, `match_kpi_template`).
- `agente_dwh/observability.py`: métricas, eventos y alertas operativas.

## Ejemplo directo con tu base PostgreSQL

Con los datos compartidos, puedes ejecutar así desde una máquina autorizada por `pg_hba.conf`:

```bash
export DWH_URL='postgresql+psycopg://postgres:1234@74.208.78.55:5432/vgd_dwh_migration'
export LLM_ENDPOINT='http://127.0.0.1:11434'
export LLM_MODEL='qwen2.5-coder:7b'
export LLM_TEMPERATURE='0.2'
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

Antes de arrancar, define la URL de PostgreSQL donde vive el dataset demo:

```bash
export DWH_URL='postgresql+psycopg://usuario:clave@127.0.0.1:5432/tu_bd'
# o bien DEMO_DWH_URL (misma forma)
```

En la pantalla:

1. Al iniciar se crean o actualizan las tablas demo en esa base (si hace falta).
2. Configura endpoint/modelo de Ollama y límite de filas en la barra lateral si lo necesitas.
3. (Opcional) `SCHEMA_HINT_FILE` apuntando a `schema_hint_demo.txt`.
4. Escribe la pregunta y pulsa **Consultar**.

La web muestra:
- SQL generado
- resultados en tabla
- JSON completo de respuesta

## Dataset demo en PostgreSQL

Los datos de prueba se generan en Python y se cargan **solo en PostgreSQL** (ya no se usa SQLite).

Tablas: `customers`, `vehicles`, `sales`, `services`, `service_appointments`, `insurance_policies`, y agregados `mv_sales_monthly`, `mv_customer_lifecycle`.

Para sembrar o recrear el demo en tu base local:

```bash
export DWH_URL='postgresql+psycopg://usuario:clave@127.0.0.1:5432/tu_bd'
python3 scripts/seed_postgres_demo.py
# Recrear desde cero aunque exista el esquema:
python3 scripts/seed_postgres_demo.py --force
```

Desde código o tests también puedes usar `agente_dwh.demo_data.ensure_demo_postgres(DWH_URL)`.

Preguntas recomendadas para demo:

- "Top 10 clientes por monto total de ventas"
- "Ventas por marca de vehículo en 2025"
- "Clientes con más servicios realizados"
- "Ingreso mensual por servicios"

## Pruebas automáticas

Algunas pruebas necesitan PostgreSQL accesible. Define por ejemplo:

```bash
export DWH_URL='postgresql+psycopg://usuario:clave@127.0.0.1:5432/tu_bd'
# o export TEST_PG_DSN='...' (misma URL)
```

Luego:

```bash
python3 -m pytest tests/ -q
```

Cobertura incluida:

- Stub de plantillas KPI (sin matches activos).
- Cache SQL (TTL / hit / miss) sobre PostgreSQL.
- Pronóstico usando tabla materializada `mv_sales_monthly`.
- Normalización SQL para citas de servicio (PostgreSQL).

## Prueba de carga (rápida)

Script de carga concurrente (requiere `DWH_URL` y datos demo cargados):

```bash
export DWH_URL='postgresql+psycopg://usuario:clave@127.0.0.1:5432/tu_bd'
python3 scripts/load_test.py --workers 12 --requests 240
```
