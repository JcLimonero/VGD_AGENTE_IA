"""Dashboards y widgets en PostgreSQL (tablas `dashboards`, `dashboard_widgets`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Json

from agente_dwh.saved_queries_db import platform_connect


def ensure_default_dashboard(user_id: int) -> int:
    """Devuelve el id del dashboard marcado is_default; si no hay, crea uno."""
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id FROM dashboards
                WHERE user_id = %s AND is_default = true
                ORDER BY id
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return int(row["id"])
            cur.execute(
                """
                INSERT INTO dashboards (user_id, title, is_default, layout_cols)
                VALUES (%s, %s, true, 12)
                RETURNING id
                """,
                (user_id, "Mi Dashboard"),
            )
            new = cur.fetchone()
        conn.commit()
    assert new is not None
    return int(new["id"])


def resolve_dashboard_id(dashboard_id: str, user_id: int) -> int:
    """
    Resuelve el id numérico del dashboard.
    El path `default` apunta al dashboard por defecto del usuario (creándolo si hace falta).
    """
    key = dashboard_id.strip().lower()
    if key == "default":
        return ensure_default_dashboard(user_id)
    try:
        did = int(dashboard_id)
    except ValueError as e:
        raise ValueError("dashboard_id inválido") from e
    with platform_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM dashboards WHERE id = %s AND user_id = %s",
                (did, user_id),
            )
            if cur.fetchone() is None:
                raise ValueError("dashboard no encontrado")
    return did


def db_list_dashboards(user_id: int) -> List[Dict[str, Any]]:
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, title, is_default, layout_cols, created_at, updated_at
                FROM dashboards
                WHERE user_id = %s
                ORDER BY is_default DESC, id
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "title": r["title"],
                "is_default": bool(r["is_default"]),
                "layout_cols": int(r["layout_cols"]),
                "created_at": _iso(r.get("created_at")),
                "updated_at": _iso(r.get("updated_at")),
            }
        )
    return out


def _iso(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def db_get_dashboard_detail(dashboard_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, title, is_default, layout_cols, created_at, updated_at
                FROM dashboards
                WHERE id = %s AND user_id = %s
                """,
                (dashboard_id, user_id),
            )
            dash = cur.fetchone()
            if not dash:
                return None
            cur.execute(
                """
                SELECT id, dashboard_id, saved_query_id, pos_x, pos_y, width, height,
                       display_order, widget_config, created_at
                FROM dashboard_widgets
                WHERE dashboard_id = %s
                ORDER BY display_order, id
                """,
                (dashboard_id,),
            )
            wrows = cur.fetchall()

    widgets = [_widget_row_to_api(w) for w in wrows]

    return {
        "id": str(dash["id"]),
        "user_id": str(dash["user_id"]),
        "title": dash["title"],
        "is_default": bool(dash["is_default"]),
        "layout_cols": int(dash["layout_cols"]),
        "created_at": _iso(dash.get("created_at")),
        "updated_at": _iso(dash.get("updated_at")),
        "widgets": widgets,
    }


def _widget_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    wc = row.get("widget_config")
    if not isinstance(wc, dict):
        wc = {}
    return {
        "id": str(row["id"]),
        "dashboard_id": str(row["dashboard_id"]),
        "saved_query_id": str(row["saved_query_id"]),
        "pos_x": int(row["pos_x"]),
        "pos_y": int(row["pos_y"]),
        "width": int(row["width"]),
        "height": int(row["height"]),
        "display_order": int(row["display_order"]),
        "widget_config": wc,
        "created_at": _iso(row.get("created_at")),
    }


def db_delete_dashboard_widget(dashboard_id: int, widget_id: int, user_id: int) -> bool:
    with platform_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM dashboard_widgets w
                USING dashboards d
                WHERE w.id = %s AND w.dashboard_id = %s
                  AND w.dashboard_id = d.id AND d.user_id = %s
                """,
                (widget_id, dashboard_id, user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def _clamp_widget_geometry(
    pos_x: int,
    pos_y: int,
    width: int,
    height: int,
    layout_cols: int,
    *,
    max_height: int = 32,
) -> tuple[int, int, int, int]:
    lc = max(1, min(int(layout_cols), 24))
    w = max(1, min(int(width), lc))
    px = max(0, min(int(pos_x), lc - w))
    h = max(1, min(int(height), max_height))
    py = max(0, int(pos_y))
    return px, py, w, h


def db_patch_dashboard_widget(
    dashboard_id: int,
    widget_id: int,
    user_id: int,
    merge_config: Optional[Dict[str, Any]] = None,
    pos_x: Optional[int] = None,
    pos_y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Actualiza widget_config (fusión JSONB ||) y/o posición/tamaño en la cuadrícula.
    Los campos de geometría omitidos conservan el valor actual.
    """
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT w.pos_x, w.pos_y, w.width, w.height, w.widget_config, d.layout_cols
                FROM dashboard_widgets w
                JOIN dashboards d ON d.id = w.dashboard_id
                WHERE w.id = %s AND w.dashboard_id = %s AND d.user_id = %s
                """,
                (widget_id, dashboard_id, user_id),
            )
            cur_row = cur.fetchone()
            if not cur_row:
                return None

            lc = int(cur_row["layout_cols"] or 12)
            nx = int(cur_row["pos_x"]) if pos_x is None else int(pos_x)
            ny = int(cur_row["pos_y"]) if pos_y is None else int(pos_y)
            nw = int(cur_row["width"]) if width is None else int(width)
            nh = int(cur_row["height"]) if height is None else int(height)
            nx, ny, nw, nh = _clamp_widget_geometry(nx, ny, nw, nh, lc)

            do_merge = bool(merge_config)
            if do_merge:
                cur.execute(
                    """
                    UPDATE dashboard_widgets w
                    SET pos_x = %s, pos_y = %s, width = %s, height = %s,
                        widget_config = COALESCE(w.widget_config, '{}'::jsonb) || %s::jsonb
                    FROM dashboards d
                    WHERE w.id = %s AND w.dashboard_id = %s AND w.dashboard_id = d.id AND d.user_id = %s
                    RETURNING w.id, w.dashboard_id, w.saved_query_id, w.pos_x, w.pos_y, w.width, w.height,
                              w.display_order, w.widget_config, w.created_at
                    """,
                    (nx, ny, nw, nh, Json(merge_config), widget_id, dashboard_id, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE dashboard_widgets w
                    SET pos_x = %s, pos_y = %s, width = %s, height = %s
                    FROM dashboards d
                    WHERE w.id = %s AND w.dashboard_id = %s AND w.dashboard_id = d.id AND d.user_id = %s
                    RETURNING w.id, w.dashboard_id, w.saved_query_id, w.pos_x, w.pos_y, w.width, w.height,
                              w.display_order, w.widget_config, w.created_at
                    """,
                    (nx, ny, nw, nh, widget_id, dashboard_id, user_id),
                )
            row = cur.fetchone()
        conn.commit()
    return _widget_row_to_api(row) if row else None


def db_create_dashboard_widget(
    dashboard_id: int,
    user_id: int,
    saved_query_id: int,
    pos_x: int,
    pos_y: int,
    width: int,
    height: int,
    widget_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Inserta un widget si el dashboard y la saved_query pertenecen al usuario.
    Devuelve None si dashboard o consulta no existen / no son del usuario.
    """
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM dashboards WHERE id = %s AND user_id = %s",
                (dashboard_id, user_id),
            )
            if cur.fetchone() is None:
                return None
            cur.execute(
                "SELECT id FROM saved_queries WHERE id = %s AND user_id = %s",
                (saved_query_id, user_id),
            )
            if cur.fetchone() is None:
                return None
            cur.execute(
                """
                SELECT COALESCE(MAX(display_order), -1) AS mo
                FROM dashboard_widgets
                WHERE dashboard_id = %s
                """,
                (dashboard_id,),
            )
            mo = cur.fetchone()
            display_order = int(mo["mo"] if mo else -1) + 1
            cur.execute(
                """
                INSERT INTO dashboard_widgets (
                    dashboard_id, saved_query_id, pos_x, pos_y, width, height,
                    display_order, widget_config
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id, dashboard_id, saved_query_id, pos_x, pos_y, width, height,
                          display_order, widget_config, created_at
                """,
                (
                    dashboard_id,
                    saved_query_id,
                    pos_x,
                    pos_y,
                    width,
                    height,
                    display_order,
                    Json(widget_config or {}),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return _widget_row_to_api(row)


def db_get_user_dashboard_stats(user_id: int) -> Dict[str, Any]:
    """
    Métricas para el panel del dashboard (usuario autenticado).
    - saved_queries: filas en Mis Widgets (consultas guardadas).
    - executions_today: ejecuciones guardadas en query_snapshots con fecha de hoy (TZ del servidor PG).
    - failed_recent: ejecuciones fallidas últimos 7 días (alertas).
    - users_total: solo si el usuario es admin en platform_users; resto None.
    """
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT role FROM platform_users WHERE id = %s", (user_id,))
            prole = cur.fetchone()
            is_admin = bool(prole and str(prole.get("role") or "").lower() == "admin")

            cur.execute(
                "SELECT COUNT(*) AS n FROM saved_queries WHERE user_id = %s",
                (user_id,),
            )
            saved_queries = int(cur.fetchone()["n"])

            cur.execute(
                """
                SELECT COUNT(*) AS n FROM dashboard_widgets w
                INNER JOIN dashboards d ON d.id = w.dashboard_id
                WHERE d.user_id = %s
                """,
                (user_id,),
            )
            dashboard_widgets = int(cur.fetchone()["n"])

            cur.execute(
                """
                SELECT COUNT(*) AS n FROM query_snapshots qs
                INNER JOIN saved_queries sq ON sq.id = qs.saved_query_id
                WHERE sq.user_id = %s AND (qs.executed_at::date = CURRENT_DATE)
                """,
                (user_id,),
            )
            executions_today = int(cur.fetchone()["n"])

            cur.execute(
                """
                SELECT COUNT(*) AS n FROM query_snapshots qs
                INNER JOIN saved_queries sq ON sq.id = qs.saved_query_id
                WHERE sq.user_id = %s
                  AND qs.success = false
                  AND qs.executed_at >= (CURRENT_TIMESTAMP - INTERVAL '7 days')
                """,
                (user_id,),
            )
            failed_recent = int(cur.fetchone()["n"])

            users_total: Optional[int] = None
            if is_admin:
                cur.execute("SELECT COUNT(*) AS n FROM platform_users")
                users_total = int(cur.fetchone()["n"])

    return {
        "saved_queries": saved_queries,
        "dashboard_widgets": dashboard_widgets,
        "executions_today": executions_today,
        "failed_recent": failed_recent,
        "users_total": users_total,
    }
