"""Request timing and metrics middleware."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_metrics: dict[str, dict] = {
    "requests_total": defaultdict(int),
    "requests_by_status": defaultdict(int),
    "request_duration_seconds": defaultdict(list),
    "errors_total": defaultdict(int),
}


def get_metrics() -> dict:
    result = {}
    for key, val in _metrics["requests_total"].items():
        result[f"http_requests_total_{key}"] = val
    for key, val in _metrics["request_duration_seconds"].items():
        vals = list(val)
        result[f"http_request_duration_p50_{key}"] = sorted(vals)[len(vals) // 2] if vals else 0
        result[f"http_request_duration_p99_{key}"] = sorted(vals)[int(len(vals) * 0.99)] if vals else 0
    result["http_errors_total"] = sum(_metrics["errors_total"].values())
    return result


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method
        route = f"{method} {path}"
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        _metrics["requests_total"][route] += 1
        _metrics["requests_by_status"][str(response.status_code)] += 1
        _metrics["request_duration_seconds"][route].append(duration)
        if len(_metrics["request_duration_seconds"][route]) > 1000:
            _metrics["request_duration_seconds"][route] = _metrics["request_duration_seconds"][route][-500:]
        if response.status_code >= 500:
            _metrics["errors_total"][route] += 1

        response.headers["X-Process-Time"] = f"{duration:.4f}"
        return response
