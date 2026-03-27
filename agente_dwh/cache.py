"""Backends de cache para resultados SQL."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Protocol


class QueryCacheBackend(Protocol):
    """Interfaz mínima para cache de resultados SQL."""

    backend_name: str

    def get(self, sql: str) -> list[dict[str, Any]] | None:
        ...

    def set(self, sql: str, rows: list[dict[str, Any]]) -> None:
        ...

    def stats(self) -> dict[str, Any]:
        ...


@dataclass
class NoopQueryCache:
    """Cache deshabilitado."""

    backend_name: str = "none"

    def get(self, sql: str) -> list[dict[str, Any]] | None:
        return None

    def set(self, sql: str, rows: list[dict[str, Any]]) -> None:
        _ = (sql, rows)

    def stats(self) -> dict[str, Any]:
        return {"entries": 0, "hits": 0, "misses": 0, "hit_ratio": 0.0}


@dataclass
class InMemoryQueryCache:
    """Cache local LRU con TTL en memoria del proceso."""

    ttl_seconds: int
    max_entries: int
    backend_name: str = "local"

    def __post_init__(self) -> None:
        self._store: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, sql: str) -> list[dict[str, Any]] | None:
        if self.ttl_seconds <= 0:
            return None
        now = time.time()
        cached = self._store.get(sql)
        if cached is None:
            self._misses += 1
            return None
        created_at, rows = cached
        if now - created_at > self.ttl_seconds:
            self._store.pop(sql, None)
            self._misses += 1
            return None
        self._store.move_to_end(sql)
        self._hits += 1
        return [dict(row) for row in rows]

    def set(self, sql: str, rows: list[dict[str, Any]]) -> None:
        if self.ttl_seconds <= 0:
            return
        self._store[sql] = (time.time(), [dict(row) for row in rows])
        self._store.move_to_end(sql)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_ratio = (self._hits / total) if total else 0.0
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(hit_ratio, 4),
        }


@dataclass
class RedisQueryCache:
    """
    Cache distribuido para multi-instancia.

    Requiere paquete `redis` instalado y REDIS_URL válido.
    """

    redis_url: str
    ttl_seconds: int
    namespace: str = "agente_dwh:sql"
    backend_name: str = "redis"

    def __post_init__(self) -> None:
        try:
            import redis
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Cache redis solicitado pero falta dependencia `redis`."
            ) from exc
        self._redis = redis.from_url(self.redis_url, decode_responses=True)
        self._hits = 0
        self._misses = 0

    def _key(self, sql: str) -> str:
        digest = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        return f"{self.namespace}:{digest}"

    def get(self, sql: str) -> list[dict[str, Any]] | None:
        if self.ttl_seconds <= 0:
            return None
        payload = self._redis.get(self._key(sql))
        if payload is None:
            self._misses += 1
            return None
        self._hits += 1
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list):
            return None
        return [dict(row) for row in parsed if isinstance(row, dict)]

    def set(self, sql: str, rows: list[dict[str, Any]]) -> None:
        if self.ttl_seconds <= 0:
            return
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        self._redis.setex(self._key(sql), self.ttl_seconds, payload)

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_ratio = (self._hits / total) if total else 0.0
        return {
            # Redis no expone cardinalidad por prefijo en O(1) sin escaneo.
            "entries": -1,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(hit_ratio, 4),
        }


def build_query_cache(
    *,
    backend: str,
    ttl_seconds: int,
    max_entries: int,
    redis_url: str = "",
    redis_namespace: str = "agente_dwh:sql",
) -> QueryCacheBackend:
    backend_normalized = (backend or "").strip().lower()
    if ttl_seconds <= 0 or backend_normalized in ("none", "off", "disabled"):
        return NoopQueryCache()
    if backend_normalized in ("redis", "distributed"):
        if not redis_url.strip():
            raise RuntimeError("CACHE_BACKEND=redis requiere REDIS_URL.")
        return RedisQueryCache(
            redis_url=redis_url.strip(),
            ttl_seconds=ttl_seconds,
            namespace=redis_namespace.strip() or "agente_dwh:sql",
        )
    return InMemoryQueryCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
