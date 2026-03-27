"""Servicios de aplicación para la capa web."""

from __future__ import annotations

import streamlit as st

from ..agent import DwhAgent, resolve_llm_profile
from ..app_services import build_agent_service

SESSION_KEY_CACHED_DW_AGENT = "cached_dw_agent_instance"
SESSION_KEY_CACHED_DW_AGENT_CFG = "cached_dw_agent_config_tuple"


def build_agent(
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    row_limit: int,
    llm_timeout_seconds: int,
    schema_hint: str,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    llm_temperature: float = 0.2,
    *,
    llm_profile: str = "default",
    schema_hint_file: str = "",
) -> DwhAgent:
    return build_agent_service(
        dwh_url=dwh_url,
        llm_endpoint=llm_endpoint,
        llm_model=llm_model,
        row_limit=row_limit,
        llm_timeout_seconds=llm_timeout_seconds,
        schema_hint=schema_hint,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
        llm_temperature=llm_temperature,
        llm_profile=llm_profile,
        schema_hint_file=schema_hint_file,
    )


def get_session_agent(
    *,
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    row_limit: int,
    llm_timeout_seconds: int,
    schema_hint: str,
    schema_hint_file: str,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    llm_temperature: float,
) -> DwhAgent:
    llm_profile = resolve_llm_profile(schema_hint_file, dwh_url=dwh_url)
    cfg = (
        dwh_url.strip(),
        llm_endpoint.strip(),
        llm_model.strip(),
        int(row_limit),
        int(llm_timeout_seconds),
        schema_hint,
        int(cache_ttl_seconds),
        int(cache_max_entries),
        round(float(llm_temperature), 6),
        llm_profile,
    )
    if st.session_state.get(SESSION_KEY_CACHED_DW_AGENT_CFG) != cfg:
        st.session_state[SESSION_KEY_CACHED_DW_AGENT_CFG] = cfg
        st.session_state[SESSION_KEY_CACHED_DW_AGENT] = build_agent(
            dwh_url=cfg[0],
            llm_endpoint=cfg[1],
            llm_model=cfg[2],
            row_limit=cfg[3],
            llm_timeout_seconds=cfg[4],
            schema_hint=cfg[5],
            cache_ttl_seconds=cfg[6],
            cache_max_entries=cfg[7],
            llm_temperature=cfg[8],
            llm_profile=cfg[9],
            schema_hint_file=schema_hint_file,
        )
    return st.session_state[SESSION_KEY_CACHED_DW_AGENT]
