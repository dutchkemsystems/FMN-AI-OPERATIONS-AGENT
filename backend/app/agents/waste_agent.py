"""Waste & Production Analyser Agent.

Evaluates batch efficiency after each production run and recommends
process adjustments to reduce waste and improve output quality.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import BatchRecord, Report, WasteReport, utcnow
from .base_agent import Action, BaseAgent


class WasteAgent(BaseAgent):
    agent_type = "waste"
    description = "Batch efficiency analysis and waste-reduction recommender"
    interval_seconds = 3600

    def observe(self, db: Session) -> dict:
        batch = db.query(BatchRecord).order_by(BatchRecord.timestamp.desc()).first()
        if not batch:
            return {"has_batch": False}
        efficiency = batch.efficiency or (
            batch.output_tons / batch.input_tons if batch.input_tons > 0 else 0
        )
        waste_pct = batch.waste_tons / batch.input_tons * 100 if batch.input_tons > 0 else 0
        return {
            "has_batch": True,
            "batch_id": batch.id,
            "line": batch.line,
            "input_tons": batch.input_tons,
            "output_tons": batch.output_tons,
            "energy_kwh": batch.energy_kwh,
            "waste_tons": batch.waste_tons,
            "efficiency": round(efficiency, 4),
            "waste_pct": round(waste_pct, 2),
            "target_efficiency": self.settings.target_efficiency,
        }

    def think(self, observation: dict) -> list[Action]:
        if not observation.get("has_batch"):
            return []

        actions: list[Action] = []
        eff = observation["efficiency"]
        target = observation["target_efficiency"]

        if eff < target:
            gap = target - eff
            actions.append(
                Action(
                    action_type="recommend_process_adjustment",
                    description=f"Batch #{observation['batch_id']} efficiency {eff:.1%} below target {target:.1%}",
                    params={
                        "batch_id": observation["batch_id"],
                        "line": observation["line"],
                        "efficiency": eff,
                        "gap": round(gap, 4),
                        "adjustments": [
                            "Reduce grain moisture content by 0.5%",
                            "Recalibrate roller mills",
                            "Minimise idle time between batches",
                            "Inspect sieve condition",
                        ],
                        "expected_gain": round(gap, 4),
                    },
                    estimated_impact_ngn=round(observation["input_tons"] * gap * 45000, 0),
                )
            )

        actions.append(
            Action(
                action_type="file_efficiency_report",
                description=f"File efficiency report for batch #{observation['batch_id']}",
                params={"batch_id": observation["batch_id"], "efficiency": eff},
            )
        )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        if action.action_type == "recommend_process_adjustment":
            params = action.params
            report = WasteReport(
                batch_id=params.get("batch_id"),
                efficiency=params.get("efficiency", 0),
                findings={"adjustments": params.get("adjustments", []), "gap": params.get("gap", 0)},
                recommendation=action.description,
            )
            db.add(report)
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "waste_report",
                    {"batch_id": params.get("batch_id"), "efficiency": params.get("efficiency")},
                )
            return {"filed": True, "report_type": "waste"}

        if action.action_type == "file_efficiency_report":
            params = action.params
            report = Report(
                title=f"Efficiency Report — Batch #{params.get('batch_id')}",
                kind="efficiency",
                content={
                    "batch_id": params.get("batch_id"),
                    "efficiency": params.get("efficiency"),
                },
            )
            db.add(report)
            return {"filed": True, "report_type": "efficiency"}

        return {"performed": False}
