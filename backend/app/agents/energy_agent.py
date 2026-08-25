"""Energy Optimiser Agent.

Monitors real-time energy consumption and switches between power sources
(grid, gas, diesel, solar) to minimise cost while maintaining reliability.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import EnergyReading, PowerSwitchEvent, utcnow
from ..services.energy_service import marginal_costs, latest_readings_by_source
from .base_agent import Action, BaseAgent

FACILITIES = ["Lagos Mill", "Kano Mill"]
MAINTENANCE_THRESHOLD_HOURS = 72


class EnergyAgent(BaseAgent):
    agent_type = "energy"
    description = "Real-time power-source optimiser (grid/gas/diesel/solar)"
    interval_seconds = 900

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._runtime_hours: dict[str, float] = {f: 0.0 for f in FACILITIES}
        self._last_source: dict[str, str] = {f: "grid" for f in FACILITIES}

    def observe(self, db: Session) -> dict:
        costs = marginal_costs(self.settings)
        readings = latest_readings_by_source(db)
        current: dict[str, dict] = {}
        for facility in FACILITIES:
            facility_readings = readings.get(facility, {})
            if facility_readings:
                latest = min(
                    facility_readings.values(),
                    key=lambda r: r.timestamp,
                    default=None,
                )
                if latest:
                    current[facility] = {
                        "source": latest.source,
                        "kwh": latest.kwh,
                        "cost_ngn": latest.cost_ngn,
                        "timestamp": latest.timestamp,
                    }
        return {
            "costs": costs,
            "current": current,
            "diesel_runtime": dict(self._runtime_hours),
        }

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []
        costs = observation["costs"]
        hour = utcnow().hour

        for facility in FACILITIES:
            cur = observation["current"].get(facility, {})
            current_source = cur.get("source", "grid")

            ranked = sorted(
                ((k, v) for k, v in costs.items() if k != "diesel"),
                key=lambda x: x[1],
            )
            best_source = ranked[0][0] if ranked else "grid"

            if hour in range(10, 16) and costs.get("solar", 999) < costs.get(current_source, 999):
                best_source = "solar"

            if current_source != best_source:
                saving = (costs.get(current_source, 65) - costs[best_source]) * 12000
                actions.append(
                    Action(
                        action_type="switch_source",
                        description=f"{facility}: {current_source} → {best_source} (save ₦{saving:,.0f}/day)",
                        params={
                            "facility": facility,
                            "from": current_source,
                            "to": best_source,
                            "projected_daily_saving_ngn": round(saving, 0),
                        },
                        estimated_impact_ngn=round(saving, 0),
                    )
                )

            if current_source == "diesel":
                self._runtime_hours[facility] += 4
                if self._runtime_hours[facility] >= MAINTENANCE_THRESHOLD_HOURS:
                    actions.append(
                        Action(
                            action_type="schedule_generator_maintenance",
                            description=f"{facility}: diesel runtime {self._runtime_hours[facility]:.0f}h — schedule maintenance",
                            params={
                                "facility": facility,
                                "hours_run": self._runtime_hours[facility],
                            },
                        )
                    )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        if action.action_type == "switch_source":
            facility = action.params.get("facility", "")
            from_src = action.params.get("from", "grid")
            to_src = action.params.get("to", "gas")
            saving = action.params.get("projected_daily_saving_ngn", 0)

            if from_src == "diesel":
                self._runtime_hours[facility] = 0

            event = PowerSwitchEvent(
                facility=facility,
                from_source=from_src,
                to_source=to_src,
                projected_daily_saving_ngn=saving,
                reason="cost-optimisation",
            )
            db.add(event)

            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "energy_switch",
                    {
                        "facility": facility,
                        "from": from_src,
                        "to": to_src,
                        "saving_ngn": saving,
                    },
                )

            self._last_source[facility] = to_src
            return {"switched": True, "facility": facility, "to": to_src}

        if action.action_type == "schedule_generator_maintenance":
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "maintenance",
                    action.params,
                )
            return {"scheduled": True, **action.params}

        return {"performed": False}
