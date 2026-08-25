"""Digital Twin simulator for the FMN value chain."""
from __future__ import annotations
from dataclasses import dataclass, fields
import numpy as np

@dataclass
class TwinParams:
    days: int = 30
    seed: int = 7
    fx_usd_ngn: float = 1500.0
    wheat_usd_per_ton: float = 260.0
    cassava_substitution: float = 0.15
    diesel_price_per_litre: float = 850.0
    grid_tariff_per_kwh: float = 65.0
    gas_tariff_per_kwh: float = 45.0
    solar_capacity_kw: float = 1200.0
    mill_throughput_tph: float = 120.0
    fleet_size: int = 60
    demand_tons_per_day: float = 900.0
    demand_multiplier: float = 1.0
    fx_shock_pct: float = 0.0
    wheat_shock_pct: float = 0.0
    fuel_shock_pct: float = 0.0
    port_closure_days: int = 0
    disruption_probability: float = 0.08
    base_waste_pct: float = 6.0

@dataclass
class TwinResult:
    series: dict
    kpis: dict
    risk_score: float
    recommendations: list

    def to_dict(self) -> dict:
        return {"series": self.series, "kpis": self.kpis, "risk_score": self.risk_score, "recommendations": self.recommendations}

def simulate(p: TwinParams) -> TwinResult:
    rng = np.random.default_rng(p.seed)
    n = p.days
    ws = 1.0 - p.cassava_substitution
    fx = np.full(n, p.fx_usd_ngn * (1 + p.fx_shock_pct / 100)) * (1 + rng.normal(0, 0.005, n).cumsum() * 0.05)
    wh = np.full(n, p.wheat_usd_per_ton * (1 + p.wheat_shock_pct / 100)) * (1 + rng.normal(0, 0.004, n).cumsum() * 0.05)
    fl = np.full(n, p.diesel_price_per_litre * (1 + p.fuel_shock_pct / 100))
    demand = p.demand_tons_per_day * p.demand_multiplier
    throughput = p.mill_throughput_tph * 24.0
    port_start = n // 2
    port_end = min(n, port_start + p.port_closure_days)
    proc, ener, logi, prod, svc, wast = [], [], [], [], [], []
    for d in range(n):
        avail = demand * (0.3 if port_start <= d < port_end else 1.0)
        produced = min(avail, throughput) * (1 - rng.random() * 0.02)
        disrupt = rng.random() < p.disruption_probability
        served = produced * (0.72 if disrupt else 1.0)
        prod.append(round(float(produced), 1))
        svc.append(round(float(min(served / demand, 1.0)), 3))
        pc = float(produced * ws * wh[d] * fx[d] + produced * (1 - ws) * 260 * fx[d] * 0.55)
        proc.append(round(pc, 0))
        bl = 0.45 * p.grid_tariff_per_kwh + 0.35 * p.gas_tariff_per_kwh + 0.20 * (float(fl[d]) / 3.5)
        bl *= (1 - min(0.15, p.solar_capacity_kw / 8000))
        ec = float(produced * 55 * bl)
        ener.append(round(ec, 0))
        lc = float(served * 350 * 0.012 * fl[d] + served * 250 + 15000 * min(served / 30, 1.0))
        logi.append(round(lc, 0))
        wp = p.base_waste_pct + (2.0 if disrupt else 0) + (1.0 if port_start <= d < port_end else 0)
        wast.append(round(wp, 2))
    total_rev = sum(prod) * 45000
    total_proc = sum(proc)
    total_ener = sum(ener)
    total_logi = sum(logi)
    avg_svc = float(np.mean(svc))
    avg_waste = float(np.mean(wast))
    risk = (
        abs(p.fx_shock_pct) * 1.2 + abs(p.wheat_shock_pct) * 0.9
        + abs(p.fuel_shock_pct) * 0.8 + p.port_closure_days * 2.0
        + p.disruption_probability * 80 + avg_waste * 0.5
    )
    risk = float(np.clip(risk, 0, 100))
    recs = []
    if p.fx_shock_pct > 10:
        recs.append("Hedge FX exposure via forward contracts and increase local cassava sourcing")
    if p.fuel_shock_pct > 15:
        recs.append("Accelerate solar investment and negotiate gas-supply agreements")
    if p.port_closure_days > 3:
        recs.append("Build buffer wheat stocks for at least 14 days before anticipated closures")
    if avg_waste > 8:
        recs.append("Audit production lines and recalibrate milling equipment")
    if avg_svc < 0.85:
        recs.append("Review demand forecasting and increase distribution fleet capacity")
    series = {"procurement_cost": proc, "energy_cost": ener, "logistics_cost": logi, "production_tons": prod, "service_level": svc, "waste_pct": wast}
    kpis = {"total_procurement": total_proc, "total_energy": total_ener, "total_logistics": total_logi, "total_revenue": total_rev, "avg_service_level": avg_svc, "avg_waste_pct": avg_waste, "net_margin_ngn": total_rev - total_proc - total_ener - total_logi}
    return TwinResult(series=series, kpis=kpis, risk_score=risk, recommendations=recs)
