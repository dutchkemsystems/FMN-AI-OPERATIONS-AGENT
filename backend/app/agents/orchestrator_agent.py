"""Orchestrator Agent (Master).

Coordinates all agents, resolves inter-agent conflicts, and produces
executive dashboards and reports.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import AgentRun, PowerSwitchEvent, Report, ActionLog, utcnow
from ..services.report_service import build_executive_report
from .base_agent import Action, BaseAgent

logger = logging.getLogger("fmn.agent.orchestrator")


class OrchestratorAgent(BaseAgent):
    agent_type = "orchestrator"
    description = "Master coordinator — runs all agents, resolves conflicts, builds reports"
    interval_seconds = 21600

    def __init__(self, settings: Any, session_factory: Any = None, bus: Any = None,
                 ledger: Any = None, agents: dict[str, BaseAgent] | None = None, **kwargs: Any) -> None:
        super().__init__(settings, session_factory, bus, ledger, **kwargs)
        self._agents: dict[str, BaseAgent] = agents or {}

    def observe(self, db: Session) -> dict:
        return {
            "registered_agents": list(self._agents.keys()),
            "agent_count": len(self._agents),
            "diesel_price": self.settings.diesel_price_per_litre,
        }

    def think(self, observation: dict) -> list[Action]:
        return []

    def run_once(self) -> dict:
        if self.status.value == "disabled":
            return {"agent": self.agent_type, "status": "disabled", "actions": []}

        self.status = self.__import_status__("running")
        import time as _time
        started = _time.perf_counter()
        db = self.session_factory()
        agent_summaries: dict[str, dict] = {}
        error_text = None

        try:
            for name, agent in self._agents.items():
                if name == self.agent_type:
                    continue
                try:
                    agent_summaries[name] = agent.run_once()
                except Exception as exc:
                    agent_summaries[name] = {"error": str(exc)}
                    logger.exception("Agent %s failed during orchestration", name)

            self._resolve_conflicts(db)
            report = build_executive_report(db, self.settings, list(agent_summaries.values()))

            if self.ledger:
                record_event(
                    self.ledger, db, "orchestration",
                    {"report_id": report.id, "agents": list(agent_summaries.keys())},
                )

            db.add(
                AgentRun(
                    agent_type=self.agent_type,
                    duration_ms=int((_time.perf_counter() - started) * 1000),
                    observation={"agents_ran": len(agent_summaries)},
                    num_actions=0,
                    status="ok",
                )
            )
            db.commit()

        except Exception as exc:
            db.rollback()
            error_text = str(exc)
            logger.exception("Orchestrator run_once failed")
            db.add(
                AgentRun(
                    agent_type=self.agent_type,
                    duration_ms=int((_time.perf_counter() - started) * 1000),
                    observation={},
                    num_actions=0,
                    status="error",
                    error=error_text,
                )
            )
            db.commit()
        finally:
            self.total_runs += 1
            self.last_run_at = utcnow()
            self.status = self.__import_status__("idle")
            db.close()

        if self.bus:
            self.bus.publish("dashboard.refresh", {"agents": len(agent_summaries)})

        return {
            "agent": self.agent_type,
            "status": "ok" if not error_text else "error",
            "agents_ran": len(agent_summaries),
            "agent_summaries": agent_summaries,
            "error": error_text,
        }

    def _resolve_conflicts(self, db: Session) -> None:
        last_switch = (
            db.query(PowerSwitchEvent)
            .order_by(PowerSwitchEvent.timestamp.desc())
            .first()
        )
        if (
            last_switch
            and last_switch.to_source == "diesel"
            and self.settings.diesel_price_per_litre > 800
        ):
            db.add(
                ActionLog(
                    agent_type="orchestrator",
                    action_type="conflict_resolution",
                    description="Diesel switch flagged — fuel price exceeds ₦800/litre threshold",
                    params={
                        "facility": last_switch.facility,
                        "diesel_price": self.settings.diesel_price_per_litre,
                    },
                    status="executed",
                )
            )

    @staticmethod
    def __import_status__(val: str) -> Any:
        from .base_agent import AgentStatus
        return AgentStatus(val)
