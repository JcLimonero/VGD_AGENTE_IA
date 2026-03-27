"""CRUD de consultas guardadas en PostgreSQL (tabla `saved_queries`, BD de plataforma)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Json

_VALID_CHART = frozenset({"table", "bar", "line", "kpi", "pie", "area"})


def platform_connect():
    url = (os.getenv("PLATFORM_DB_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "PLATFORM_DB_URL no está definida. Las consultas guardadas se persisten ahí "
            "(misma base que el login; ejecuta create_platform_tables.sql)."
        )
    return connect(url.replace("postgresql+psycopg://", "postgresql://"))


def user_id_to_int(user_id: Any) -> int:
    return int(str(user_id))


def _norm_chart(chart_type: str) -> str:
    t = (chart_type or "table").lower().strip()
    return t if t in _VALID_CHART else "table"


def _iso_dt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _interval_to_optional_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    return str(v)


def _norm_tags(tags: Any) -> List[str]:
    if not tags:
        return []
    if isinstance(tags, list):
        return [str(t) for t in tags]
    return [str(tags)]


def row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    cc = row.get("chart_config")
    if isinstance(cc, str):
        import json

        try:
            cc = json.loads(cc)
        except json.JSONDecodeError:
            cc = {}
    if not isinstance(cc, dict):
        cc = {}
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "original_question": row["original_question"],
        "sql_text": row["sql_text"],
        "chart_type": row["chart_type"],
        "chart_config": cc,
        "refresh_interval": _interval_to_optional_str(row.get("refresh_interval")),
        "is_active": bool(row["is_active"]),
        "tags": _norm_tags(row.get("tags")),
        "created_at": _iso_dt(row.get("created_at")),
        "updated_at": _iso_dt(row.get("updated_at")),
    }


def db_list_saved_queries(user_id: int) -> List[Dict[str, Any]]:
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, title, original_question, sql_text, chart_type,
                       chart_config, refresh_interval, is_active, tags, created_at, updated_at
                FROM saved_queries
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [row_to_api(r) for r in rows]


def db_get_saved_query(query_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, title, original_question, sql_text, chart_type,
                       chart_config, refresh_interval, is_active, tags, created_at, updated_at
                FROM saved_queries
                WHERE id = %s AND user_id = %s
                """,
                (query_id, user_id),
            )
            row = cur.fetchone()
    return row_to_api(row) if row else None


def _clean_refresh_interval(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def db_create_saved_query(
    user_id: int,
    title: str,
    original_question: str,
    sql_text: str,
    chart_type: str,
    chart_config: Dict[str, Any],
    refresh_interval: Optional[str],
    tags: List[str],
) -> Dict[str, Any]:
    ct = _norm_chart(chart_type)
    ri = _clean_refresh_interval(refresh_interval)
    tag_list = _norm_tags(tags)
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO saved_queries (
                    user_id, title, original_question, sql_text, chart_type,
                    chart_config, refresh_interval, tags
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s::jsonb, CAST(%s AS interval), %s
                )
                RETURNING id, user_id, title, original_question, sql_text, chart_type,
                          chart_config, refresh_interval, is_active, tags, created_at, updated_at
                """,
                (
                    user_id,
                    title,
                    original_question,
                    sql_text,
                    ct,
                    Json(chart_config or {}),
                    ri,
                    tag_list,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    assert row is not None
    return row_to_api(row)


def db_update_saved_query(query_id: int, user_id: int, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets: List[str] = []
    vals: List[Any] = []

    if "title" in patch:
        sets.append("title = %s")
        vals.append(patch["title"])
    if "original_question" in patch:
        sets.append("original_question = %s")
        vals.append(patch["original_question"])
    if "sql_text" in patch:
        sets.append("sql_text = %s")
        vals.append(patch["sql_text"])
    if "chart_type" in patch:
        sets.append("chart_type = %s")
        vals.append(_norm_chart(str(patch["chart_type"])))
    if "chart_config" in patch:
        sets.append("chart_config = %s::jsonb")
        vals.append(Json(patch["chart_config"] if isinstance(patch["chart_config"], dict) else {}))
    if "refresh_interval" in patch:
        ri = patch["refresh_interval"]
        if ri is None or (isinstance(ri, str) and not str(ri).strip()):
            sets.append("refresh_interval = NULL")
        else:
            sets.append("refresh_interval = CAST(%s AS interval)")
            vals.append(str(ri).strip())
    if "is_active" in patch:
        sets.append("is_active = %s")
        vals.append(bool(patch["is_active"]))
    if "tags" in patch:
        sets.append("tags = %s")
        vals.append(_norm_tags(patch["tags"]))

    if not sets:
        return db_get_saved_query(query_id, user_id)

    vals.extend([query_id, user_id])
    sql = f"""
        UPDATE saved_queries
        SET {", ".join(sets)}
        WHERE id = %s AND user_id = %s
        RETURNING id, user_id, title, original_question, sql_text, chart_type,
                  chart_config, refresh_interval, is_active, tags, created_at, updated_at
    """
    with platform_connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
        conn.commit()
    return row_to_api(row) if row else None


def db_delete_saved_query(query_id: int, user_id: int) -> bool:
    with platform_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM saved_queries WHERE id = %s AND user_id = %s",
                (query_id, user_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0
