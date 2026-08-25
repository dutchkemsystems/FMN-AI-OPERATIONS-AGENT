"""Rate limiting middleware using Redis-backed sliding window."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP.

    Defaults to 120 requests/minute for all endpoints, with per-path overrides.
    """

    def __init__(
        self,
        app,
        default_limit: int = 120,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.default_limit = default_limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._overrides: dict[str, int] = {}

    def set_override(self, path: str, limit: int) -> None:
        self._overrides[path] = limit

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit(self, path: str) -> int:
        for pattern, limit in self._overrides.items():
            if path.startswith(pattern):
                return limit
        return self.default_limit

    async def dispatch(self, request: Request, call_next: Callable):
        client = self._client_ip(request)
        path = request.url.path
        limit = self._get_limit(path)
        now = time.time()
        window_start = now - self.window

        key = f"{client}:{path}"
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > window_start]

        if len(self._hits[key]) >= limit:
            retry_after = int(self._hits[key][0] + self.window - now) + 1
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limit_exceeded", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[key].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(self._hits[key])))
        return response
