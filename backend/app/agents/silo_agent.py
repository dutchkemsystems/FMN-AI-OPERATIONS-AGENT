"""Silo & Storage Monitor Agent.

Monitors temperature, humidity and fill levels across the 17 silos.
Alerts on quality degradation and recommends grain rotation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import SecurityAlert, SiloReading, utcnow
from .base_agent import Action, BaseAgent

SILOS = [f"S{i:02d}" for i in range(1, 18)]
TEMP_LIMIT = 32.0
HUMIDITY_LIMIT = 70.0
LOW_FILL = 10.0
HIGH_FILL = 85.0


class SiloAgent(BaseAgent):
    agent_type = "silo"
    description = "Temperature / humidity / fill-level monitor for 17 silos"
    interval_seconds = 3600

    def observe(self, db: Session) -> dict:
        latest: dict[str, dict] = {}
        for silo_id in SILOS:
            reading = (
                db.query(SiloReading)
                .filter_by(silo_id=silo_id)
                .order_by(SiloReading.timestamp.desc())
                .first()
            )
            if reading:
                latest[silo_id] = {
                    "temp_c": reading.temp_c,
                    "humidity_pct": reading.humidity_pct,
                    "fill_pct": reading.fill_pct,
                    "quality_flag": reading.quality_flag,
                    "timestamp": reading.timestamp.isoformat(),
                }
        return {"silos": latest, "total_tracked": len(SILOS)}

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []

        for silo_id, data in observation["silos"].items():
            temp = data.get("temp_c", 25)
            humidity = data.get("humidity_pct", 50)
            fill = data.get("fill_pct", 50)

            if temp > TEMP_LIMIT or humidity > HUMIDITY_LIMIT:
                severity = "critical" if temp > 36 else "high"
                actions.append(
                    Action(
                        action_type="alert_quality_degradation",
                        description=f"{silo_id}: temp={temp}°C humidity={humidity}% — risk of quality loss",
                        params={
                            "silo_id": silo_id,
                            "temp_c": temp,
                            "humidity_pct": humidity,
                            "severity": severity,
                            "recommendation": "Aerate and rotate stock (FIFO)",
                        },
                    )
                )

            if fill < LOW_FILL:
                actions.append(
                    Action(
                        action_type="reorder_grain",
                        description=f"{silo_id}: fill {fill}% — reorder wheat",
                        params={"silo_id": silo_id, "target_tonnage": 500},
                    )
                )
            elif fill > HIGH_FILL:
                actions.append(
                    Action(
                        action_type="rotate_stock",
                        description=f"{silo_id}: fill {fill}% — rotate oldest stock",
                        params={"silo_id": silo_id, "strategy": "FIFO"},
                    )
                )

        actions.append(
            Action(
                action_type="audit_snapshot",
                description=f"Record silo readings for audit ({observation['total_tracked']} silos)",
                params={"silos_reported": observation["total_tracked"]},
            )
        )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        if action.action_type == "alert_quality_degradation":
            params = action.params
            alert = SecurityAlert(
                source="silo_agent",
                severity=params.get("severity", "medium"),
                message=action.description,
                details=params,
            )
            db.add(alert)
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "quality_check",
                    {"silo": params.get("silo_id"), "alert": action.description},
                )
            return {"alerted": True}

        if action.action_type in ("reorder_grain", "rotate_stock"):
            if self.ledger:
                record_event(self.ledger, db, "silo_reading", action.params)
            return {"queued": True}

        if action.action_type == "audit_snapshot":
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "silo_reading",
                    {"silos_reported": action.params.get("silos_reported", 0)},
                )
            return {"logged": True}

        return {"performed": False}
