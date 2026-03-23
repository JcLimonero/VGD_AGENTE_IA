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

## Arquitectura mínima

- `agente_dwh/llm_local.py`: cliente Ollama local (`/api/chat`).
- `agente_dwh/sql_guard.py`: validación SQL de solo lectura.
- `agente_dwh/dwh.py`: ejecución de SQL en DWH con SQLAlchemy.
- `agente_dwh/agent.py`: orquestador pregunta -> SQL -> ejecución.
- `agente_dwh/cli.py`: interfaz de línea de comandos.

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
