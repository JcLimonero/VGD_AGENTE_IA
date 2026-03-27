"""Etiquetas en español para alias de columnas en resultados (UI y resúmenes)."""

from __future__ import annotations

# Alias típicos del LLM / SQL (snake_case) → texto para el usuario
_SPANISH_BY_ALIAS: dict[str, str] = {
    # Agencias / ventas
    "agency_name": "Nombre de agencia",
    "name": "Nombre",
    "sales_count": "Número de ventas",
    "total_ventas": "Total de ventas",
    "total_sales": "Total de ventas",
    "ventas": "Ventas",
    "count": "Cantidad",
    "cnt": "Cantidad",
    "n": "Cantidad",
    "total": "Total",
    "month": "Mes",
    "mes": "Mes",
    "year": "Año",
    "año": "Año",
    "billing_date": "Fecha de facturación",
    "sale_date": "Fecha de venta",
    "service_date": "Fecha de servicio",
    "created_at": "Fecha de creación",
    "updated_at": "Fecha de actualización",
    "state": "Estado",
    "status": "Estado",
    "vin": "VIN",
    "brand": "Marca",
    "model": "Modelo",
    "version": "Versión",
    "amount": "Importe",
    "km": "Kilometraje",
    "order_dms": "Pedido DMS",
    "nd_client_dms": "Cliente DMS",
    "id_agency": "ID agencia",
    "bussines_name": "Nombre del cliente",
    "business_name": "Nombre del cliente",
    "customer_name": "Nombre del cliente",
    "service_type": "Tipo de servicio",
    "exterior_color": "Color exterior",
    "interior_color": "Color interior",
    "exterior_color_name": "Color exterior",
    "interior_color_name": "Color interior",
    "stage_name": "Etapa",
    "test": "Prueba",
    "value": "Valor",
}

# Partes comunes en snake_case (orden compuesto: más largas primero en heurística)
_TOKEN_ES: list[tuple[str, str]] = [
    ("agency", "agencia"),
    ("sales", "ventas"),
    ("billing", "facturación"),
    ("customer", "cliente"),
    ("service", "servicio"),
    ("invoice", "factura"),
    ("inventory", "inventario"),
    ("vehicle", "vehículo"),
    ("count", "conteo"),
    ("total", "total"),
    ("name", "nombre"),
    ("date", "fecha"),
    ("time", "hora"),
    ("month", "mes"),
    ("year", "año"),
    ("brand", "marca"),
    ("model", "modelo"),
    ("amount", "importe"),
    ("price", "precio"),
    ("order", "pedido"),
    ("state", "estado"),
    ("status", "estado"),
    ("type", "tipo"),
    ("id", "id"),
]


def spanish_column_label(key: str) -> str:
    """Devuelve etiqueta en español para un alias de columna."""
    if not key or not str(key).strip():
        return key
    k = str(key).strip()
    lower = k.lower()
    if lower in _SPANISH_BY_ALIAS:
        return _SPANISH_BY_ALIAS[lower]
    # camelCase → snake
    s = lower
    parts = s.split("_")
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        pl = p.lower()
        replaced = False
        for en, es in _TOKEN_ES:
            if pl == en:
                out.append(es)
                replaced = True
                break
        if not replaced:
            out.append(p)
    if not out:
        return k
    label = " ".join(out)
    return label[0].upper() + label[1:] if len(label) > 1 else label.upper()


def spanish_labels_map(keys: list[str]) -> dict[str, str]:
    return {k: spanish_column_label(k) for k in keys}


def localize_summary_markdown(text: str, keys: list[str]) -> str:
    """Sustituye **nombre_columna:** por **Etiqueta español:** en texto ya generado."""
    if not text or not keys:
        return text
    out = text
    for k in sorted(set(keys), key=len, reverse=True):
        sp = spanish_column_label(k)
        if sp == k:
            continue
        out = out.replace(f"**{k}:**", f"**{sp}:**")
        out = out.replace(f"**{k}**:", f"**{sp}**:")
    return out
