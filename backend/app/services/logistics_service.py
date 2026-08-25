"""Logistics service — route planning, shipment creation, cost estimation."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models.database import Order, Shipment, Truck, utcnow


# Approximate road distances between Nigerian hubs (km)
_DISTANCE_KM: dict[tuple[str, str], float] = {
    ("Lagos", "Ibadan"): 130,
    ("Lagos", "Abuja"): 600,
    ("Lagos", "Kano"): 1200,
    ("Lagos", "Enugu"): 530,
    ("Lagos", "Port Harcourt"): 630,
    ("Abuja", "Kano"): 530,
    ("Abuja", "Enugu"): 340,
    ("Kano", "Enugu"): 760,
    ("Enugu", "Port Harcourt"): 270,
    ("Ibadan", "Abuja"): 530,
    ("Ibadan", "Kano"): 1100,
}


def _lookup_distance(origin: str, destination: str) -> float:
    key = (origin, destination)
    rev = (destination, origin)
    if key in _DISTANCE_KM:
        return _DISTANCE_KM[key]
    if rev in _DISTANCE_KM:
        return _DISTANCE_KM[rev]
    return 350.0


def estimate_cost(distance_km: float, fuel_price: float, tons: float, cost_per_km: float) -> float:
    fuel_component = distance_km * 0.35 * fuel_price
    base_component = distance_km * cost_per_km
    handling = tons * 500
    return fuel_component + base_component + handling


def plan_route(
    order: Any,
    available_trucks: list[Any],
    fuel_price: float,
    traffic_factor: float = 1.0,
) -> dict[str, Any] | None:
    """Find the cheapest truck for a given order.

    Returns dict with keys: truck, distance_km, eta_hours, cost_ngn or None.
    """
    if not available_trucks:
        return None

    origin = "Lagos"
    destination = getattr(order, "region", "Lagos")
    tons = getattr(order, "tons", 1.0)
    distance = _lookup_distance(origin, destination) * traffic_factor

    best: dict[str, Any] | None = None
    for truck in available_trucks:
        cap = getattr(truck, "capacity_tons", 0)
        if cap < tons:
            continue
        cpk = getattr(truck, "cost_per_km", 250.0)
        cost = estimate_cost(distance, fuel_price, tons, cpk)
        speed = 45.0 / traffic_factor
        eta = distance / speed + 2.0
        candidate = {"truck": truck, "distance_km": distance, "eta_hours": eta, "cost_ngn": cost}
        if best is None or cost < best["cost_ngn"]:
            best = candidate
    return best


def create_shipment(
    db: Session,
    order: Any,
    plan: dict[str, Any],
) -> Shipment:
    """Create a shipment record and update the order status."""
    truck = plan.get("truck")
    truck_id = getattr(truck, "id", None) if truck else None
    shipment = Shipment(
        order_id=order.id,
        truck_id=truck_id,
        origin="Lagos",
        destination=getattr(order, "region", ""),
        distance_km=plan.get("distance_km", 0),
        eta_hours=plan.get("eta_hours", 0),
        cost_ngn=plan.get("cost_ngn", 0),
        status="dispatched",
        dispatched_at=utcnow(),
    )
    db.add(shipment)
    order.status = "dispatched"
    db.flush()
    return shipment
