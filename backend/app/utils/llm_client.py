"""Thin OpenAI wrapper with graceful degradation when no API key is configured."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import get_settings, Settings
from ..utils.retry import retry

logger = logging.getLogger("fmn.llm")


class LLMUnavailable(RuntimeError):
    """Raised when the LLM is not configured or reachable."""


class LLMClient:
    """Unified LLM client with fallback to template-based responses."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self.model = settings.openai_model
        self._client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI client initialised (model=%s)", self.model)
            except Exception:
                logger.warning("OpenAI SDK unavailable; using template responses")

    @property
    def available(self) -> bool:
        return self._client is not None

    @retry(max_attempts=3, backoff_base=1.0, exceptions=(Exception,))
    def chat(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.4,
        max_tokens: int = 900,
    ) -> str:
        if not self._client:
            raise LLMUnavailable("OPENAI_API_KEY not configured")
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def chat_json(
        self, system: str, user: str, **kwargs: Any
    ) -> dict:
        raw = self.chat(system, user, json_mode=True, **kwargs)
        return _parse_json(raw)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
