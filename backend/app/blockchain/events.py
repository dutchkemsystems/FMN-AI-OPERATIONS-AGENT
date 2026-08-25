"""Blockchain event recording helpers."""
from __future__ import annotations
from typing import Any

EVENT_TYPES = (
    "procurement", "silo_reading", "shipment", "quality_check",
    "energy_switch", "security_event", "waste_report",
    "orchestration", "maintenance",
)

def record_event(ledger: Any, db: Any, event_type: str, payload: dict) -> str | None:
    if ledger is None:
        return None
    try:
        return ledger.append(db, event_type, payload)
    except Exception:
        return None
