"""Logistics Router Agent.

Assigns trucks to pending orders, computes optimal routes, and re-routes
shipments when disruptions are detected.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..blockchain.events import record_event
from ..models.database import Order, Shipment, Truck, utcnow
from ..services.logistics_service import plan_route, create_shipment
from .base_agent import Action, BaseAgent


class LogisticsAgent(BaseAgent):
    agent_type = "logistics"
    description = "Order dispatch, route optimisation and disruption re-routing"
    interval_seconds = 1800

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._traffic_factor: float = 1.0

    def set_traffic(self, factor: float) -> None:
        self._traffic_factor = max(1.0, min(3.0, factor))

    def observe(self, db: Session) -> dict:
        pending = db.query(Order).filter_by(status="pending").all()
        trucks = db.query(Truck).filter_by(available=True).all()
        active = db.query(Shipment).filter_by(status="dispatched").all()
        fuel = self.settings.diesel_price_per_litre
        return {
            "pending_orders": [
                {
                    "id": o.id,
                    "reference": o.reference,
                    "customer": o.customer,
                    "region": o.region,
                    "tons": o.tons,
                }
                for o in pending
            ],
            "available_trucks": [
                {
                    "id": t.id,
                    "plate": t.plate,
                    "region": t.region,
                    "capacity_tons": t.capacity_tons,
                    "cost_per_km": t.cost_per_km,
                }
                for t in trucks
            ],
            "fuel_price": fuel,
            "active_shipments": len(active),
            "traffic_factor": self._traffic_factor,
        }

    def think(self, observation: dict) -> list[Action]:
        actions: list[Action] = []
        orders = observation["pending_orders"]
        trucks = observation["available_trucks"]
        fuel = observation["fuel_price"]
        traffic = observation["traffic_factor"]

        used_trucks: set[int] = set()
        for order in orders:
            class _OrderProxy:
                def __init__(self, data: dict) -> None:
                    for k, v in data.items():
                        setattr(self, k, v)

            class _TruckProxy:
                def __init__(self, data: dict) -> None:
                    for k, v in data.items():
                        setattr(self, k, v)

            order_obj = _OrderProxy(order)
            avail = [t for t in trucks if t["id"] not in used_trucks]
            truck_objs = [_TruckProxy(t) for t in avail]
            plan = plan_route(order_obj, truck_objs, fuel, traffic)
            if plan:
                used_trucks.add(plan["truck"].id)
                actions.append(
                    Action(
                        action_type="dispatch_truck",
                        description=f"Assign {plan['truck'].plate} to {order['reference']} → {order['region']}",
                        params={
                            "order_ref": order["reference"],
                            "truck_plate": plan["truck"].plate,
                            "destination": order["region"],
                            "distance_km": plan["distance_km"],
                            "eta_hours": round(plan["eta_hours"], 1),
                            "cost_ngn": round(plan["cost_ngn"], 0),
                        },
                        estimated_impact_ngn=round(plan["cost_ngn"], 0),
                    )
                )

        if traffic > 1.4:
            active = observation.get("_active_shipment_ids", [])
            for sid in active[:3]:
                actions.append(
                    Action(
                        action_type="reroute_shipment",
                        description=f"Disruption detected — rerouting shipment #{sid}",
                        params={
                            "shipment_id": sid,
                            "reason": "traffic-disruption",
                            "alternate_via": "Abuja hub",
                            "eta_add_hours": 4,
                        },
                    )
                )

        return actions

    def perform_action(self, action: Action, db: Session) -> dict:
        if action.action_type == "dispatch_truck":
            order_ref = action.params.get("order_ref", "")
            truck_plate = action.params.get("truck_plate", "")
            order = db.query(Order).filter_by(reference=order_ref).first()
            truck = db.query(Truck).filter_by(plate=truck_plate).first()
            if not order or not truck:
                return {"error": "order or truck not found"}

            from ..services.logistics_service import estimate_cost

            distance = action.params.get("distance_km", 350)
            fuel = self.settings.diesel_price_per_litre
            cost = action.params.get(
                "cost_ngn",
                estimate_cost(distance, fuel, order.tons, truck.cost_per_km),
            )
            eta = action.params.get("eta_hours", distance / 45 * self._traffic_factor + 2)

            shipment = create_shipment(
                db, order, {"truck": truck, "distance_km": distance, "eta_hours": eta, "cost_ngn": cost}
            )
            if self.ledger:
                record_event(
                    self.ledger,
                    db,
                    "shipment",
                    {
                        "shipment_id": shipment.id,
                        "order_ref": order_ref,
                        "truck_plate": truck_plate,
                        "eta_hours": eta,
                    },
                )
            return {"shipment_id": shipment.id, "eta_hours": round(eta, 1)}

        if action.action_type == "reroute_shipment":
            sid = action.params.get("shipment_id")
            shipment = db.query(Shipment).filter_by(id=sid).first()
            if shipment:
                shipment.eta_hours += action.params.get("eta_add_hours", 4)
                shipment.cost_ngn += shipment.distance_km * 0.35 * self.settings.diesel_price_per_litre * 0.3
                shipment.route = shipment.route or {}
                shipment.route["rerouted"] = True
                shipment.route["via"] = action.params.get("alternate_via", "")
                if self.ledger:
                    record_event(self.ledger, db, "shipment", {"rerouted": True, "shipment_id": sid})
                return {"rerouted": True, "new_eta": shipment.eta_hours}
            return {"error": "shipment not found"}

        return {"performed": False}
