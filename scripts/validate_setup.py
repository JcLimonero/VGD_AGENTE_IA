#!/usr/bin/env python3
"""
Valida instalación: Python, dependencias, PostgreSQL (vgd_dwh_prod_migracion), Ollama y lectura DWH.

Uso desde la raíz del repo:
  source .venv/bin/activate
  python scripts/validate_setup.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _fail(msg: str) -> None:
    print(f"[FALLO] {msg}")


def main() -> int:
    print("=== Validación VGD_AGENTE_IA ===\n")

    # .env
    try:
        from agente_dwh.bootstrap_env import load_dotenv_from_project_root

        load_dotenv_from_project_root()
        env_path = ROOT / ".env"
        if env_path.is_file():
            _ok(f"Archivo .env encontrado ({env_path})")
        else:
            print(f"[AVISO] No hay .env; copia .env.example a .env o exporta variables.")
    except Exception as exc:  # noqa: BLE001
        _fail(f"bootstrap env: {exc}")

    # Imports principales
    try:
        import sqlalchemy  # noqa: F401
        import streamlit  # noqa: F401
        import pandas  # noqa: F401
        import psycopg  # noqa: F401

        _ok("Dependencias Python (SQLAlchemy, Streamlit, pandas, psycopg)")
    except ImportError as exc:
        _fail(f"Dependencias: {exc}")
        return 1

    import os

    from agente_dwh.config import (
        effective_dwh_url,
        normalize_dwh_url_string,
        validate_dwh_url_targets_vgd_prod,
    )

    dwh = normalize_dwh_url_string(os.getenv("DWH_URL", ""))
    if not dwh:
        _fail("DWH_URL no definida (usa .env o export)")
        return 1

    # Postgres + nombre de base (se corrige /postgres o BD omitida → vgd_dwh_prod_migracion)
    try:
        validate_dwh_url_targets_vgd_prod(dwh)
        from agente_dwh.dwh import DwhClient

        _probe = DwhClient.from_url(effective_dwh_url(dwh), default_limit=5)
        _probe.execute_select("SELECT 1 AS ok")
        _ok("PostgreSQL: DWH_URL válida y conexión a vgd_dwh_prod_migracion")
    except Exception as exc:  # noqa: BLE001
        _fail(f"PostgreSQL / DWH: {exc}")
        return 1

    # Ollama tags
    llm_ep = (os.getenv("LLM_ENDPOINT") or "http://127.0.0.1:11434").rstrip("/")
    try:
        with request.urlopen(f"{llm_ep}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "") for m in data.get("models", [])]
        if not models:
            _fail("Ollama responde pero no hay modelos. Ejecuta: ollama pull qwen2.5-coder:7b")
            return 1
        _ok(f"Ollama en {llm_ep}: modelos {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
    except error.URLError as exc:
        _fail(f"Ollama no alcanzable en {llm_ep}: {exc}")
        return 1

    model = (os.getenv("LLM_MODEL") or "qwen2.5-coder:7b").strip()
    if not any(model in m or m.startswith(model.split(":")[0]) for m in models):
        print(f"[AVISO] LLM_MODEL={model!r} no coincide exacto con tags; revisa ollama list")

    # Chat mínimo
    try:
        payload = json.dumps(
            {
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": "Responde solo: OK"}],
            }
        ).encode()
        req = request.Request(
            f"{llm_ep}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
        content = body.get("message", {}).get("content", "")
        _ok(f"Ollama /api/chat con modelo {model!r} (respuesta: {content[:80]!r}...)")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Ollama chat de prueba: {exc}")
        return 1

    # Lectura directa DWH (sin LLM)
    try:
        from agente_dwh.config import load_settings
        from agente_dwh.dwh import DwhClient

        cfg = load_settings()
        dwh_client = DwhClient.from_url(cfg.dwh_url, default_limit=min(50, cfg.max_rows))
        rows = dwh_client.execute_select("SELECT COUNT(*) AS n FROM customers")
        n = int(rows[0]["n"]) if rows else 0
        if n <= 0:
            _fail("Lectura directa: customers vacía")
            return 1
        _ok(f"DWH lectura directa: {n} clientes en tabla customers")
    except Exception as exc:  # noqa: BLE001
        _fail(f"DWH lectura directa: {exc}")
        return 1

    # Agente + LLM (con pista de esquema si SCHEMA_HINT_FILE está en .env)
    try:
        from agente_dwh.agent import DwhAgent, resolve_llm_profile
        from agente_dwh.config import load_settings
        from agente_dwh.dwh import DwhClient
        from agente_dwh.llm_local import LocalOllamaClient

        cfg = load_settings()
        dwh_client = DwhClient.from_url(cfg.dwh_url, default_limit=cfg.max_rows)
        llm = LocalOllamaClient(
            cfg.llm_endpoint,
            cfg.llm_model,
            timeout_seconds=cfg.llm_timeout_seconds,
            temperature=cfg.llm_temperature,
        )
        hint_path = (os.getenv("SCHEMA_HINT_FILE") or "").strip()
        schema_hint = ""
        if hint_path:
            p = Path(hint_path)
            if not p.is_file():
                p = ROOT / hint_path
            if p.is_file():
                schema_hint = p.read_text(encoding="utf-8")
        agent = DwhAgent(
            dwh_client,
            llm,
            schema_hint=schema_hint,
            llm_profile=resolve_llm_profile(hint_path, dwh_url=cfg.dwh_url),
        )
        result = agent.answer(
            "Usa exactamente el nombre de tabla customers. "
            "¿Cuántos clientes hay? Devuelve SQL con SELECT COUNT(*) FROM customers."
        )
        if not result.rows:
            _fail("Agente+LLM: 0 filas (revisa SQL generado y SCHEMA_HINT_FILE)")
            return 1
        _ok(f"Agente+LLM: OK ({len(result.rows)} fila(s), SQL ejecutado)")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Agente+LLM: {exc}")
        return 1

    print("\n=== Todo correcto ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
