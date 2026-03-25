#!/usr/bin/env python3
"""Compatibilidad: mismo export que export_dwh_schema_hint.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "export_dwh_schema_hint", _here / "export_dwh_schema_hint.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.exit(_mod.main())
