"""Servicios de aplicación para ensamblar agente, DWH y LLM."""

from __future__ import annotations

import os

from .agent import DwhAgent, resolve_llm_profile
from .dwh_client import DwhClient
from .llm_local import LocalOllamaClient
from .llm_worker import WorkerLlmClient


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def build_dwh_client(
    *,
    dwh_url: str,
    row_limit: int,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    cache_backend: str | None = None,
    cache_redis_url: str | None = None,
    cache_redis_namespace: str | None = None,
) -> DwhClient:
    backend = (cache_backend or os.getenv("CACHE_BACKEND", "local")).strip()
    redis_url = (cache_redis_url or os.getenv("REDIS_URL", "")).strip()
    redis_ns = (cache_redis_namespace or os.getenv("CACHE_REDIS_NAMESPACE", "agente_dwh:sql")).strip()
    return DwhClient.from_url(
        dwh_url,
        default_limit=row_limit,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
        cache_backend=backend,
        cache_redis_url=redis_url,
        cache_redis_namespace=redis_ns,
    )


def build_llm_client(
    *,
    llm_endpoint: str,
    llm_model: str,
    llm_timeout_seconds: int,
    llm_temperature: float,
):
    base = LocalOllamaClient(
        base_url=llm_endpoint,
        model_name=llm_model,
        timeout_seconds=llm_timeout_seconds,
        temperature=llm_temperature,
    )
    if _env_flag("LLM_USE_WORKER", default=False):
        return WorkerLlmClient(base)
    return base


def build_agent_service(
    *,
    dwh_url: str,
    llm_endpoint: str,
    llm_model: str,
    row_limit: int,
    llm_timeout_seconds: int,
    schema_hint: str,
    cache_ttl_seconds: int,
    cache_max_entries: int,
    llm_temperature: float = 0.2,
    llm_profile: str | None = None,
    schema_hint_file: str = "",
) -> DwhAgent:
    dwh = build_dwh_client(
        dwh_url=dwh_url,
        row_limit=row_limit,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_max_entries=cache_max_entries,
    )
    llm = build_llm_client(
        llm_endpoint=llm_endpoint,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_temperature=llm_temperature,
    )
    resolved_profile = llm_profile or resolve_llm_profile(schema_hint_file, dwh_url=dwh_url)
    return DwhAgent(
        dwh_client=dwh,
        llm_client=llm,
        schema_hint=schema_hint,
        llm_profile=resolved_profile,
    )
