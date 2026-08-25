"""Energy service — cost calculations and reading aggregation."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models.database import EnergyReading


def marginal_costs(settings: Any) -> dict[str, float]:
    """Return marginal cost per kWh for each power source."""
    return {
        "grid": settings.grid_tariff_per_kwh,
        "gas": settings.gas_tariff_per_kwh,
        "solar": settings.solar_tariff_per_kwh,
        "diesel": settings.diesel_price_per_litre / 3.5,
    }


def latest_readings_by_source(db: Session) -> dict[str, dict[str, EnergyReading]]:
    """Return latest reading per source for each facility.

    Structure: {facility: {source: EnergyReading}}
    """
    facilities: dict[str, dict[str, EnergyReading]] = {}
    rows = (
        db.query(EnergyReading)
        .order_by(EnergyReading.timestamp.desc())
        .limit(200)
        .all()
    )
    for row in rows:
        fac = row.facility
        src = row.source
        if fac not in facilities:
            facilities[fac] = {}
        if src not in facilities[fac]:
            facilities[fac][src] = row
    return facilities
