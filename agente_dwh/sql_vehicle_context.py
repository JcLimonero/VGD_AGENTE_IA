"""Sustituye literales placeholder (p. ej. 'ultimo_vin') por el VIN/placa/id reales del contexto."""

from __future__ import annotations

import re
from typing import Any

# Literales que el LLM inventa en vez del VIN real del contexto.
_VIN_LITERAL_PLACEHOLDER = re.compile(
    r"(?i)'("
    r"ultimo[_\s-]?vin|"
    r"last[_\s-]?vin|"
    r"ese[_\s-]?vin|"
    r"el[_\s-]?vin|"
    r"vin[_\s-]?del[_\s-]?chat|"
    r"vin[_\s-]?contexto|"
    r"mismo[_\s-]?vin|"
    r"esta[_\s-]?unidad|"
    r"unidad[_\s-]?actual|"
    r"vin[_\s-]?anterior|"
    r"previous[_\s-]?vin"
    r")'"
)

_PLATE_LITERAL_PLACEHOLDER = re.compile(
    r"(?i)'("
    r"ultima[_\s-]?placa|"
    r"last[_\s-]?plate|"
    r"esa[_\s-]?placa|"
    r"placa[_\s-]?contexto"
    r")'"
)

# Placeholders para vehicle_id en comparaciones con comillas (incorrecto pero frecuente en modelos).
_VEHICLE_ID_LITERAL_PLACEHOLDER = re.compile(
    r"(?i)'("
    r"ultimo[_\s-]?vehicle[_\s-]?id|"
    r"last[_\s-]?vehicle[_\s-]?id|"
    r"vehicle[_\s-]?id[_\s-]?contexto|"
    r"id[_\s-]?vehiculo|"
    r"id[_\s-]?unidad"
    r")'"
)


def _sql_single_quote(value: str) -> str:
    return value.replace("'", "''")


def apply_vehicle_focus_sql_rewrites(sql: str, vehicle_focus: dict[str, Any] | None) -> str:
    """
    Reemplaza comodines en literales '...' por VIN, placa o id numérico del diccionario de foco.

    No modifica el SQL si no hay foco o no hay valores utilizables.
    """
    if not sql or not vehicle_focus:
        return sql

    out = sql

    vin_raw = vehicle_focus.get("vin")
    if isinstance(vin_raw, str) and vin_raw.strip():
        quoted = _sql_single_quote(vin_raw.strip())
        out = _VIN_LITERAL_PLACEHOLDER.sub(f"'{quoted}'", out)

    plate_raw = vehicle_focus.get("plate")
    if isinstance(plate_raw, str) and plate_raw.strip():
        quoted_plate = _sql_single_quote(plate_raw.strip())
        out = _PLATE_LITERAL_PLACEHOLDER.sub(f"'{quoted_plate}'", out)

    vid = vehicle_focus.get("vehicle_id")
    if vid is not None:
        try:
            vid_int = int(vid)
        except (TypeError, ValueError):
            vid_int = None
        if vid_int is not None:
            out = _VEHICLE_ID_LITERAL_PLACEHOLDER.sub(str(vid_int), out)

    return out
