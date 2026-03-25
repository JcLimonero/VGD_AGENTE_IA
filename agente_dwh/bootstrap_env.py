"""Carga variables desde .env en la raíz del repo si python-dotenv está instalado."""

from __future__ import annotations

from pathlib import Path


def load_dotenv_from_project_root() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
