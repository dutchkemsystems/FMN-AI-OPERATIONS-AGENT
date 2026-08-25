"""Security Monitor Agent.

Processes camera-triggered intrusion events and access-log anomalies,
escalating unresolved alerts to the security team.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import SecurityAlert, utcnow
from .base_agent import Action, BaseAgent


class SecurityAgent(BaseAgent):
    agent_type = "security"
    description = "Intrusion / perimeter alarm escalation and audit logging"
    interval_seconds = 300

    def observe(self, db: Session) -> dict:
        unresolved = (
            db.query(SecurityAlert)
            .filter(SecurityAlert.resolved == False, SecurityAlert.source != "silo_agent")
            .order_by(SecurityAlert.timestamp.desc())
            .limit(20)
            .all()
        )
        return {
            "unresolved_count": len(unresolved),
            "unresolved": [
                {
                    "id": a.id,
                    "source": a.source,
                    "severity": a.severity,
                    "message": a.message,
                    "age_minutes": (utcnow() - a.timestamp).total_seconds() / 60,
                }
                for a in unresolved
            ],
        }

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []

        for alert in observation.get("unresolved", []):
            if alert["severity"] in ("high", "critical") and alert["age_minutes"] > 5:
                actions.append(
                    Action(
                        action_type="dispatch_alarm",
                        description=f"Escalating unresolved alert #{alert['id']}: {alert['message']}",
                        params={
                            "alert_id": alert["id"],
                            "source": alert["source"],
                            "severity": alert["severity"],
                        },
                    )
                )

        actions.append(
            Action(
                action_type="audit_security_log",
                description="Record security heartbeat",
                params={"unresolved_count": observation.get("unresolved_count", 0)},
            )
        )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        if action.action_type == "dispatch_alarm":
            alert_id = action.params.get("alert_id")
            alert = db.query(SecurityAlert).filter_by(id=alert_id).first()
            if alert:
                details = alert.details or {}
                details["escalated_at"] = utcnow().isoformat()
                details["escalated_by"] = "security_agent"
                alert.details = details

            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "security_event",
                    {"action": "alarm_dispatch", **action.params},
                )
            return {"escalated": True}

        if action.action_type == "audit_security_log":
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "security_event",
                    {"action": "heartbeat", **action.params},
                )
            return {"logged": True}

        return {"performed": False}
