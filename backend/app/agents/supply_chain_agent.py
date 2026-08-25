"""Supply Chain & Procurement Optimiser Agent.

Monitors FX volatility, wheat prices, and local substitute economics.
Triggers hedging, bidding, or local-sourcing actions when thresholds are breached.
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..config import Settings
from ..models.database import ActionLog, FXRate
from ..utils.helpers import new_id, utcnow
from ..utils.retry import retry
from .base_agent import Action, BaseAgent

SUPPLIERS = [
    {"name": "Olam Nigeria", "region": "Lagos", "price_index": 1.02},
    {"name": "Flour Mills Algeria", "region": "Import", "price_index": 0.97},
    {"name": "Honeywell Foods", "region": "Kano", "price_index": 1.05},
    {"name": "Dangote Flour", "region": "Lagos", "price_index": 1.00},
    {"name": "TGI Group", "region": "Abuja", "price_index": 1.03},
]

BASE_DEMAND_TONS_PER_MONTH = 18000


@retry(max_attempts=3, backoff_base=0.5, exceptions=(httpx.HTTPError,))
def _call_hedging_api(url: str, payload: dict) -> httpx.Response:
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        return client.post(url, json=payload)


class SupplyChainAgent(BaseAgent):
    agent_type = "supply_chain"
    description = "FX hedging, supplier bidding, and local-sourcing optimiser"
    interval_seconds = 86400

    def observe(self, db: Session) -> dict:
        rates = db.query(FXRate).order_by(FXRate.timestamp.desc()).limit(10).all()
        latest = rates[0] if rates else None
        previous = rates[1] if len(rates) > 1 else None
        fx_change_pct = 0.0
        if latest and previous:
            from ..utils.helpers import pct_change

            fx_change_pct = pct_change(latest.usd_ngn, previous.usd_ngn) or 0.0

        cassava_ratio = 1.0
        if latest and latest.wheat_usd_per_ton > 0:
            cassava_ratio = latest.cassava_usd_per_ton / latest.wheat_usd_per_ton

        last_bid = (
            db.query(ActionLog)
            .filter_by(action_type="initiate_supplier_bidding")
            .order_by(ActionLog.timestamp.desc())
            .first()
        )
        weeks_since_bid = 999
        if last_bid:
            delta = utcnow() - last_bid.timestamp
            weeks_since_bid = delta.days / 7

        return {
            "fx_now": latest.usd_ngn if latest else 1500.0,
            "fx_prev": previous.usd_ngn if previous else 1500.0,
            "fx_change_pct": fx_change_pct,
            "wheat_usd": latest.wheat_usd_per_ton if latest else 260.0,
            "cassava_ratio": cassava_ratio,
            "weeks_since_bid": weeks_since_bid,
        }

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []
        change = observation["fx_change_pct"]
        threshold = self.settings.fx_alert_threshold_pct
        fx_now = observation["fx_now"]
        wheat_usd = observation["wheat_usd"]

        if abs(change) >= threshold:
            volume = min(6000, int(BASE_DEMAND_TONS_PER_MONTH * 0.35))
            impact = abs(volume * wheat_usd * (change / 100) * fx_now)
            actions.append(
                Action(
                    action_type="hedge_fx_forward",
                    description=f"FX moved {change:+.1f}% — initiating forward cover for {volume}t",
                    params={
                        "volume_tons": volume,
                        "horizon_days": 90,
                        "reference_rate": fx_now,
                        "lock_premium": 0.01,
                    },
                    estimated_impact_ngn=impact,
                )
            )
            actions.append(
                Action(
                    action_type="initiate_supplier_bidding",
                    description="FX volatility detected — triggering competitive bidding round",
                    params={"lots": 3, "deadline_days": 14},
                )
            )

        if observation["weeks_since_bid"] > 7:
            actions.append(
                Action(
                    action_type="initiate_supplier_bidding",
                    description="Routine weekly supplier bidding cycle",
                    params={"lots": 2, "deadline_days": 7},
                )
            )

        if observation["cassava_ratio"] < 0.85:
            actions.append(
                Action(
                    action_type="propose_local_sourcing_contract",
                    description=f"Cassava ratio {observation['cassava_ratio']:.2f} — propose local sourcing",
                    params={
                        "substitute": "cassava",
                        "tonnage": 1500,
                        "max_price_ratio": 0.85,
                        "target_regions": ["Kano", "Enugu"],
                    },
                )
            )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        ref = new_id("HED")

        if action.action_type == "hedge_fx_forward":
            result = {
                "reference": ref,
                "mode": "simulated-bank-api",
                "volume_tons": action.params.get("volume_tons", 0),
                "horizon_days": action.params.get("horizon_days", 90),
                "rate": action.params.get("reference_rate", 0),
            }
            if self.settings.hedging_api_url:
                try:
                    _call_hedging_api(
                        self.settings.hedging_api_url,
                        {"contract_ref": ref, **action.params},
                    )
                    result["mode"] = "bank-api"
                except Exception:
                    result["mode"] = "bank-api-error"

            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "procurement",
                    {"action": "hedge", "reference": ref, **action.params},
                )
            return result

        if action.action_type == "initiate_supplier_bidding":
            winner = min(SUPPLIERS, key=lambda s: s["price_index"])
            result = {
                "winner": winner["name"],
                "price_index": winner["price_index"],
                "ref": ref,
            }
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "procurement",
                    {"action": "bidding", "winner": winner["name"], "ref": ref},
                )
            return result

        if action.action_type == "propose_local_sourcing_contract":
            terms = {
                "substitute": action.params.get("substitute"),
                "tonnage": action.params.get("tonnage", 1500),
                "max_price_ratio": action.params.get("max_price_ratio", 0.85),
                "contract_ref": ref,
            }
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "procurement",
                    {"action": "local_contract", **terms},
                )
            return terms

        return {"performed": False}
