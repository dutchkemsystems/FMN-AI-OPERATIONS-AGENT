"""Redis-backed caching layer with graceful fallback to in-memory cache."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("fmn.cache")

_mem_cache: dict[str, tuple[float, Any]] = {}
_DEFAULT_TTL = 60


class Cache:
    """Redis cache with local memory fallback when Redis is unavailable."""

    def __init__(self, redis_url: str | None = None, prefix: str = "fmn:") -> None:
        self._prefix = prefix
        self._client = None
        self._degraded = False
        if redis_url:
            try:
                import redis

                self._client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
                self._client.ping()
                logger.info("Redis cache connected")
            except Exception:
                logger.warning("Redis unavailable — falling back to in-memory cache")
                self._degraded = True

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any | None:
        full_key = self._key(key)
        if self._client and not self._degraded:
            try:
                raw = self._client.get(full_key)
                if raw:
                    return json.loads(raw)
            except Exception:
                self._degraded = True
        now = time.time()
        entry = _mem_cache.get(full_key)
        if entry and entry[0] > now:
            return entry[1]
        if entry:
            del _mem_cache[full_key]
        return None

    def set(self, key: str, value: Any, ttl: int = _DEFAULT_TTL) -> None:
        full_key = self._key(key)
        serialised = json.dumps(value, default=str)
        if self._client and not self._degraded:
            try:
                self._client.setex(full_key, ttl, serialised)
                return
            except Exception:
                self._degraded = True
        _mem_cache[full_key] = (time.time() + ttl, value)

    def delete(self, key: str) -> None:
        full_key = self._key(key)
        if self._client and not self._degraded:
            try:
                self._client.delete(full_key)
            except Exception:
                self._degraded = True
        _mem_cache.pop(full_key, None)

    def flush(self) -> None:
        _mem_cache.clear()
        if self._client and not self._degraded:
            try:
                pattern = f"{self._prefix}*"
                keys = self._client.keys(pattern)
                if keys:
                    self._client.delete(*keys)
            except Exception:
                self._degraded = True

    @property
    def available(self) -> bool:
        return self._client is not None and not self._degraded


_cache_instance: Cache | None = None


def get_cache() -> Cache:
    global _cache_instance
    if _cache_instance is None:
        from ..config import get_settings

        settings = get_settings()
        _cache_instance = Cache(redis_url=settings.redis_url)
    return _cache_instance
