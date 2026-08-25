"""Abstract agent lifecycle: observe → think → act.

Each agent follows a standard cycle:
  1. **observe** — pull current state from the database / sensors.
  2. **think**   — decide which actions to take based on observations.
  3. **act**     — execute, simulate, or block each action depending on
                   the configured autonomy level.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any

from ..models.database import ActionLog, AgentRun, SessionLocal, utcnow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class AutonomyLevel(IntEnum):
    OBSERVE = 0
    SIMULATE = 1
    EXECUTE = 2


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class Action:
    action_type: str
    description: str = ""
    params: dict = field(default_factory=dict)
    estimated_impact_ngn: float | None = None


def _slim(obj: Any, max_len: int = 2000) -> Any:
    """Truncate large objects before persisting as JSON."""
    if isinstance(obj, dict):
        return {k: _slim(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_slim(v, max_len) for v in obj[:50]]
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + "…"
    return obj


class BaseAgent(ABC):
    """Abstract base class for all FMN operational agents."""

    agent_type: str = "base"
    description: str = ""
    interval_seconds: int = 3600

    def __init__(
        self,
        settings: Any,
        session_factory: Any = None,
        bus: Any = None,
        ledger: Any = None,
        **kwargs: Any,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory or SessionLocal
        self.bus = bus
        self.ledger = ledger
        self.autonomy = AutonomyLevel(settings.autonomy_level)
        self.status = AgentStatus.IDLE
        self.last_run_at: Any = None
        self.total_runs: int = 0
        self.total_errors: int = 0
        self.logger = logging.getLogger(f"fmn.agent.{self.agent_type}")

    def set_autonomy(self, level: int) -> None:
        self.autonomy = AutonomyLevel(int(level))

    def disable(self) -> None:
        self.status = AgentStatus.DISABLED

    def enable(self) -> None:
        if self.status is AgentStatus.DISABLED:
            self.status = AgentStatus.IDLE

    @abstractmethod
    def observe(self, db: "Session") -> dict:
        ...

    def think(self, observation: dict) -> list[Action]:
        return []

    def perform_action(self, action: Action, db: "Session") -> dict:
        return {"performed": False}

    def _resolve(self, action: Action, db: "Session") -> tuple[dict, str]:
        if self.autonomy is AutonomyLevel.EXECUTE:
            try:
                result = self.perform_action(action, db)
                db.commit()
                return result, "executed"
            except Exception as exc:
                db.rollback()
                self.logger.exception("action %s failed", action.action_type)
                return {"error": str(exc)}, "failed"
        if self.autonomy is AutonomyLevel.SIMULATE:
            return {"simulated": True, "params": action.params}, "simulated"
        return {"blocked": True}, "blocked"

    def run_once(self) -> dict:
        if self.status is AgentStatus.DISABLED:
            return {"agent": self.agent_type, "status": "disabled", "actions": []}

        self.status = AgentStatus.RUNNING
        started = time.perf_counter()
        db = self.session_factory()
        action_summaries: list[dict] = []
        observation: dict = {}
        error_text = None

        try:
            observation = self.observe(db)
            actions = self.think(observation)
            for action in actions:
                result, state = self._resolve(action, db)
                db.add(
                    ActionLog(
                        agent_type=self.agent_type,
                        action_type=action.action_type,
                        description=action.description,
                        params=action.params,
                        result=result,
                        status=state,
                        impact_ngn=action.estimated_impact_ngn,
                    )
                )
                action_summaries.append(
                    {
                        "action_type": action.action_type,
                        "status": state,
                        "description": action.description,
                    }
                )
            db.commit()
        except Exception as exc:
            db.rollback()
            error_text = str(exc)
            self.logger.exception("run_once failed")
            self.total_errors += 1
        else:
            self.status = AgentStatus.IDLE
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                db.add(
                    AgentRun(
                        agent_type=self.agent_type,
                        duration_ms=duration_ms,
                        observation=_slim(observation),
                        num_actions=len(action_summaries),
                        status="ok" if not error_text else "error",
                        error=error_text,
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
            self.total_runs += 1
            self.last_run_at = utcnow()
            db.close()

        summary: dict[str, Any] = {
            "agent": self.agent_type,
            "status": self.status.value,
            "actions": action_summaries,
            "error": error_text,
        }
        if self.bus:
            self.bus.publish("agent.run", summary)
        return summary

    async def tick(self) -> dict:
        return await asyncio.to_thread(self.run_once)

    def status_payload(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "description": self.description,
            "interval_seconds": self.interval_seconds,
            "status": self.status.value,
            "autonomy": int(self.autonomy),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "total_runs": self.total_runs,
            "total_errors": self.total_errors,
        }
