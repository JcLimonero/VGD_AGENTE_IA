"""Operaciones CRUD de roles y permisos en la base de datos de plataforma."""

import os
from typing import Any

import psycopg


def _conn() -> psycopg.Connection:
    url = os.getenv("PLATFORM_DB_URL", "")
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def db_list_roles() -> list[dict[str, Any]]:
    """Lista todos los roles con conteo de usuarios asignados."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT r.id, r.name, r.description, r.is_base_role,
                   r.can_create_users, r.can_access_config, r.all_agencies,
                   r.created_at,
                   COUNT(u.id) AS user_count
            FROM platform_roles r
            LEFT JOIN platform_users u ON u.role_id = r.id
            GROUP BY r.id
            ORDER BY r.is_base_role DESC, r.name
            """
        ).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "is_base_role": r[3],
                "can_create_users": r[4],
                "can_access_config": r[5],
                "all_agencies": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
                "user_count": r[8],
            }
            for r in rows
        ]
    finally:
        conn.close()


def db_get_role(role_id: int) -> dict[str, Any] | None:
    """Obtiene un rol con sus permisos completos de agencias y objetos."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT id, name, description, is_base_role,
                   can_create_users, can_access_config, all_agencies, created_at
            FROM platform_roles WHERE id = %s
            """,
            (role_id,),
        ).fetchone()
        if not row:
            return None

        agency_perms = conn.execute(
            """
            SELECT id_agency, all_objects
            FROM role_agency_permissions
            WHERE role_id = %s
            ORDER BY id_agency
            """,
            (role_id,),
        ).fetchall()

        obj_perms = conn.execute(
            """
            SELECT id_agency, dwh_object
            FROM role_object_permissions
            WHERE role_id = %s
            ORDER BY id_agency, dwh_object
            """,
            (role_id,),
        ).fetchall()

        obj_by_agency: dict[str, list[str]] = {}
        for op in obj_perms:
            obj_by_agency.setdefault(op[0], []).append(op[1])

        agencies = [
            {
                "id_agency": ap[0],
                "all_objects": ap[1],
                "objects": obj_by_agency.get(ap[0], []),
            }
            for ap in agency_perms
        ]

        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "is_base_role": row[3],
            "can_create_users": row[4],
            "can_access_config": row[5],
            "all_agencies": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "agencies": agencies,
        }
    finally:
        conn.close()


def db_create_role(
    name: str,
    description: str,
    can_create_users: bool,
    can_access_config: bool,
    all_agencies: bool,
) -> dict[str, Any]:
    """Crea un nuevo rol dinámico."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            INSERT INTO platform_roles
                (name, description, is_base_role, can_create_users, can_access_config, all_agencies)
            VALUES (%s, %s, false, %s, %s, %s)
            RETURNING id, name, description, is_base_role,
                      can_create_users, can_access_config, all_agencies, created_at
            """,
            (name, description, can_create_users, can_access_config, all_agencies),
        ).fetchone()
        conn.commit()
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "is_base_role": row[3],
            "can_create_users": row[4],
            "can_access_config": row[5],
            "all_agencies": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "agencies": [],
            "user_count": 0,
        }
    finally:
        conn.close()


def db_update_role(
    role_id: int,
    name: str,
    description: str,
    can_create_users: bool,
    can_access_config: bool,
    all_agencies: bool,
) -> dict[str, Any] | None:
    """Actualiza los datos básicos de un rol dinámico (no base roles)."""
    conn = _conn()
    try:
        row = conn.execute(
            """
            UPDATE platform_roles
            SET name = %s, description = %s,
                can_create_users = %s, can_access_config = %s,
                all_agencies = %s
            WHERE id = %s AND is_base_role = false
            RETURNING id
            """,
            (name, description, can_create_users, can_access_config, all_agencies, role_id),
        ).fetchone()
        conn.commit()
        if not row:
            return None
    finally:
        conn.close()
    return db_get_role(role_id)


def db_set_role_agency_permissions(
    role_id: int,
    agencies: list[dict[str, Any]],
) -> None:
    """
    Reemplaza completamente los permisos de agencias de un rol.
    agencies: [{id_agency: str, all_objects: bool, objects: [str, ...]}]
    """
    conn = _conn()
    try:
        conn.execute("DELETE FROM role_agency_permissions WHERE role_id = %s", (role_id,))
        conn.execute("DELETE FROM role_object_permissions WHERE role_id = %s", (role_id,))

        for agency in agencies:
            id_agency = agency["id_agency"]
            all_obj = bool(agency.get("all_objects", True))
            conn.execute(
                """
                INSERT INTO role_agency_permissions (role_id, id_agency, all_objects)
                VALUES (%s, %s, %s)
                ON CONFLICT (role_id, id_agency) DO UPDATE SET all_objects = EXCLUDED.all_objects
                """,
                (role_id, id_agency, all_obj),
            )
            if not all_obj:
                for obj in agency.get("objects", []):
                    conn.execute(
                        """
                        INSERT INTO role_object_permissions (role_id, id_agency, dwh_object)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (role_id, id_agency, obj),
                    )
        conn.commit()
    finally:
        conn.close()


def db_delete_role(role_id: int) -> bool:
    """Elimina un rol dinámico (no base roles). Devuelve True si se eliminó."""
    conn = _conn()
    try:
        row = conn.execute(
            "DELETE FROM platform_roles WHERE id = %s AND is_base_role = false RETURNING id",
            (role_id,),
        ).fetchone()
        conn.commit()
        return row is not None
    finally:
        conn.close()
