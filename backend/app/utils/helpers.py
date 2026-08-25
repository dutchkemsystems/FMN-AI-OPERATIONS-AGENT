"""Shared utility functions."""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def sha256_of(obj) -> str:
    canonical = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}-{uid}" if prefix else uid


def pct_change(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def format_ngn(value: float) -> str:
    return f"\u20a6{value:,.0f}"


def safe_json(obj) -> str:
    return json.dumps(obj, default=str)


def random_walk(n: int, start: float = 1500.0, drift: float = 0.0, vol: float = 0.01, seed: int | None = None) -> list[float]:
    rng = random.Random(seed)
    values = [start]
    for _ in range(n - 1):
        values.append(values[-1] * (1 + drift + rng.gauss(0, vol)))
    return values
