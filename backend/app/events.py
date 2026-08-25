"""Lightweight in-process event bus for inter-agent communication."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger("fmn.events")

Handler = Callable[[dict], Any]


class EventBus:
    """Publish-subscribe event bus running in-process.

    Replace with Redis pub/sub for multi-process deployments.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._recent: list[dict] = []

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict | None = None) -> dict:
        event: dict[str, Any] = {"type": event_type, "payload": payload or {}}
        self._recent.append(event)
        del self._recent[:-200]
        for handler in self._handlers[event_type] + self._handlers.get("*", []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    logger.debug("Async handler returned coroutine; ignoring")
            except Exception:
                logger.exception("Handler %s failed for event %s", handler, event_type)
        return event

    async def publish_async(
        self, event_type: str, payload: dict | None = None
    ) -> dict:
        return await asyncio.to_thread(self.publish, event_type, payload)

    def recent(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._recent[-limit:]))
