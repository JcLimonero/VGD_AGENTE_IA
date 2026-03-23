# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

**VGD_AGENTE_IA** is a natural-language-to-SQL CLI agent. Users ask business questions in Spanish; the system generates SQL via a local LLM (Ollama), validates it as read-only, executes it against a Data Warehouse (any SQLAlchemy-compatible database), and returns the results. See `README.md` for full architecture details.

### Running services

| Service | How to start | Notes |
|---------|-------------|-------|
| **Ollama** | `ollama serve` (background) | Must be running before the CLI can work. Default endpoint: `http://127.0.0.1:11434` |
| **Database (DWH)** | Set `DWH_URL` env var | For local dev, use SQLite: `export DWH_URL="sqlite:////workspace/test_dwh.db"` |

### Quick-start for development

```bash
pip install -e .
pip install pytest ruff
```

### Running the CLI

The CLI requires these env vars at minimum:
- `DWH_URL` — SQLAlchemy connection string (required)
- `LLM_MODEL` — Ollama model name (default `llama3.1`; use `qwen2.5:0.5b` for fast CPU-only dev)
- `SCHEMA_HINT_FILE` — path to a text file describing the DB schema (improves SQL generation accuracy)

Example:
```bash
export DWH_URL="sqlite:////workspace/test_dwh.db"
export LLM_MODEL="qwen2.5:0.5b"
export SCHEMA_HINT_FILE="./schema_hint.txt"
python3 -m agente_dwh.cli "¿Cuántas tiendas hay?"
```

### Non-obvious caveats

- **No GPU required**: Ollama works on CPU; use a small model like `qwen2.5:0.5b` for development.
- **Ollama must be started manually**: `ollama serve &` — there is no systemd in the cloud VM environment.
- **Small models may hallucinate table names**: Always provide `SCHEMA_HINT_FILE` to give the LLM context about available tables/columns.
- **Double LIMIT bug**: The `_inject_limit_if_missing` in `dwh.py` appends `LIMIT N` even when the LLM already generated one. The check is case-sensitive on the ` limit ` substring, so it may produce `LIMIT 3 LIMIT 200` errors. This is a known issue in the existing code.
- **ruff format**: Two files (`cli.py`, `llm_local.py`) have minor formatting differences from ruff defaults. Running `ruff format` would change them.
- **No existing test suite**: Tests in `tests/` were added during environment setup. Run with `pytest tests/ -v`.

### Commands reference

| Task | Command |
|------|---------|
| Install deps | `pip install -e .` |
| Lint | `ruff check .` |
| Format check | `ruff format --check .` |
| Tests | `pytest tests/ -v` |
| Run CLI | `python3 -m agente_dwh.cli "pregunta"` |
