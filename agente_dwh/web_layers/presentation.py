"""Helpers de presentación (UI)."""

from __future__ import annotations

import streamlit as st


def show_missing_dwh_url_error(required_db_name: str) -> None:
    st.error(
        f"Define DWH_URL en .env con PostgreSQL y base «{required_db_name}», "
        "por ejemplo: postgresql+psycopg://usuario:clave@host:5432/vgd_dwh_prod_migracion"
    )


def show_dwh_connection_error(required_db_name: str, error_message: str) -> None:
    st.error(
        f"No se pudo conectar al DWH ({required_db_name}): {error_message}. "
        "Comprueba red, credenciales y que PostgreSQL acepte la conexión."
    )
