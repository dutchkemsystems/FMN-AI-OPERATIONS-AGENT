"""Retry and backoff utilities for external service calls."""
from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger("fmn.retry")


def retry(
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    backoff_max: float = 30.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable | None = None,
) -> Callable:
    """Decorator that retries a function call with exponential backoff."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
                        logger.warning(
                            "Attempt %d/%d for %s failed (%s); retrying in %.1fs",
                            attempt,
                            max_attempts,
                            fn.__name__,
                            exc,
                            delay,
                        )
                        if on_retry:
                            on_retry(attempt, exc)
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts for %s failed", max_attempts, fn.__name__
                        )
            raise last_exc  # type: ignore

        return wrapper

    return decorator


def retry_async(
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    backoff_max: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Async version of retry decorator with exponential backoff."""
    import asyncio

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
                        logger.warning(
                            "Attempt %d/%d for %s failed (%s); retrying in %.1fs",
                            attempt,
                            max_attempts,
                            fn.__name__,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts for %s failed", max_attempts, fn.__name__
                        )
            raise last_exc  # type: ignore

        return wrapper

    return decorator
