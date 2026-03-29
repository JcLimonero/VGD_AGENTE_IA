"""Operaciones CRUD de usuarios en la base de datos de plataforma."""

import os
from typing import Any

import psycopg


def _conn() -> psycopg.Connection:
    url = os.getenv("PLATFORM_DB_URL", "")
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def db_list_users() -> list[dict[str, Any]]:
    """Lista todos los usuarios con su rol."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.display_name,
                   r.id AS role_id, r.name AS role_name,
                   r.can_create_users, r.can_access_config,
                   u.created_at, u.last_login_at
            FROM platform_users u
            LEFT JOIN platform_roles r ON u.role_id = r.id
            ORDER BY u.created_at DESC
            """
        ).fetchall()
        return [
            {
                "id": r[0],
                "username": r[1],
                "display_name": r[2],
                "role_id": r[3],
                "role_name": r[4],
                "can_create_users": bool(r[5]) if r[5] is not None else False,
                "can_access_config": bool(r[6]) if r[6] is not None else False,
                "created_at": r[7].isoformat() if r[7] else None,
                "last_login_at": r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ]
    finally:
        conn.close()


def db_get_user(user_id: int) -> dict[str, Any] | None:
    """Obtiene un usuario por ID con datos de su rol."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.display_name,
                   r.id AS role_id, r.name AS role_name,
                   r.can_create_users, r.can_access_config,
                   u.created_at, u.last_login_at
            FROM platform_users u
            LEFT JOIN platform_roles r ON u.role_id = r.id
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "role_id": row[3],
            "role_name": row[4],
            "can_create_users": bool(row[5]) if row[5] is not None else False,
            "can_access_config": bool(row[6]) if row[6] is not None else False,
            "created_at": row[7].isoformat() if row[7] else None,
            "last_login_at": row[8].isoformat() if row[8] else None,
        }
    finally:
        conn.close()


def db_create_user(
    username: str,
    display_name: str,
    password_hash: str,
    role_id: int,
) -> dict[str, Any]:
    """Crea un nuevo usuario y devuelve sus datos básicos."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            INSERT INTO platform_users (username, display_name, password_hash, role, role_id)
            VALUES (%s, %s, %s, 'viewer', %s)
            RETURNING id, username, display_name, created_at
            """,
            (username, display_name, password_hash, role_id),
        ).fetchone()
        conn.commit()
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
    finally:
        conn.close()


def db_update_user(
    user_id: int,
    display_name: str | None,
    role_id: int | None,
) -> dict[str, Any] | None:
    """Actualiza display_name y/o role_id de un usuario."""
    conn = _conn()
    try:
        sets: list[str] = []
        params: list[Any] = []
        if display_name is not None:
            sets.append("display_name = %s")
            params.append(display_name)
        if role_id is not None:
            sets.append("role_id = %s")
            params.append(role_id)
        if not sets:
            return db_get_user(user_id)
        params.append(user_id)
        row = conn.execute(
            f"UPDATE platform_users SET {', '.join(sets)} WHERE id = %s RETURNING id",
            params,
        ).fetchone()
        conn.commit()
        if not row:
            return None
    finally:
        conn.close()
    return db_get_user(user_id)


def db_delete_user(user_id: int) -> bool:
    """Elimina un usuario. Devuelve True si se eliminó."""
    conn = _conn()
    try:
        row = conn.execute(
            "DELETE FROM platform_users WHERE id = %s RETURNING id",
            (user_id,),
        ).fetchone()
        conn.commit()
        return row is not None
    finally:
        conn.close()


def db_change_password(user_id: int, password_hash: str) -> bool:
    """Cambia la contraseña de un usuario. Devuelve True si se actualizó."""
    conn = _conn()
    try:
        row = conn.execute(
            "UPDATE platform_users SET password_hash = %s WHERE id = %s RETURNING id",
            (password_hash, user_id),
        ).fetchone()
        conn.commit()
        return row is not None
    finally:
        conn.close()
