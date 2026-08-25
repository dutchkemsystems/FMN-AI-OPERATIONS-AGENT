"""Scenario Generator (Generative AI for stress-testing).

Creates plausible adverse scenarios ("black swan" events) and evaluates
their impact via the digital twin.
"""
from __future__ import annotations

import random
from dataclasses import fields
from typing import Any

from ..config import get_settings
from ..digital_twin.simulator import TwinParams, simulate
from ..models.database import Scenario, SessionLocal, utcnow
from ..utils.helpers import new_id

SCENARIO_TEMPLATES = [
    {"name": "Naira Devaluation Shock", "parameters": {"fx_shock_pct": 20}},
    {"name": "Global Wheat Shortage", "parameters": {"wheat_shock_pct": 35}},
    {"name": "Port Congestion / Blockage", "parameters": {"port_closure_days": 7}},
    {"name": "Diesel Price Spike", "parameters": {"fuel_shock_pct": 40}},
    {"name": "Fuel Subsidy Removal Aftershock", "parameters": {"fuel_shock_pct": 25, "fx_shock_pct": 8}},
    {"name": "Protest Route Closures", "parameters": {"disruption_probability": 0.35}},
    {"name": "Silo Failure (Kano)", "parameters": {"base_waste_pct": 12.0}},
    {"name": "Demand Surge (Festive)", "parameters": {"demand_multiplier": 1.3}},
    {"name": "Cyber-Physical Outage", "parameters": {"mill_throughput_tph": 90.0}},
    {"name": "Import Tariff Increase", "parameters": {"wheat_shock_pct": 15, "fx_shock_pct": 5}},
]

TWIN_FIELD_NAMES = {f.name for f in fields(TwinParams)}

SCENARIO_SYSTEM_PROMPT = """You are an operations risk analyst for a Nigerian flour milling company.
Generate plausible adverse scenarios as a JSON array under the key "scenarios".
Each scenario must have "name" (string) and "parameters" (dict with optional keys:
fx_shock_pct, wheat_shock_pct, fuel_shock_pct, port_closure_days,
disruption_probability, demand_multiplier, base_waste_pct, mill_throughput_tph).
Return at most 12 scenarios.  Output JSON only."""


class ScenarioGenerator:
    def __init__(self, settings: Any | None = None, llm: Any = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm

    def generate(
        self,
        count: int = 5,
        use_llm: bool = False,
        persist: bool = True,
        session_factory: Any | None = None,
    ) -> list[Scenario]:
        raw_scenarios: list[dict] = []

        if use_llm and self.llm and self.llm.available:
            try:
                result = self.llm.chat_json(
                    SCENARIO_SYSTEM_PROMPT,
                    f"Generate {count} adverse scenarios for a Nigerian flour-milling supply chain.",
                )
                raw = result.get("scenarios", result if isinstance(result, list) else [])
                raw_scenarios = raw[:count]
            except Exception:
                pass

        while len(raw_scenarios) < count:
            tpl = random.choice(SCENARIO_TEMPLATES)
            jittered = {
                k: round(v * random.uniform(0.7, 1.3), 2) if isinstance(v, float) else
                   int(v * random.uniform(0.7, 1.3)) if isinstance(v, int) else v
                for k, v in tpl["parameters"].items()
            }
            raw_scenarios.append({"name": tpl["name"], "parameters": jittered})

        rows: list[Scenario] = []
        for s in raw_scenarios[:count]:
            params = {k: v for k, v in s.get("parameters", {}).items() if k in TWIN_FIELD_NAMES}
            row = Scenario(id=new_id("SCN"), name=s.get("name", "Unnamed"), parameters=params)
            if persist:
                sf = session_factory or SessionLocal
                db = sf()
                try:
                    db.add(row)
                    db.commit()
                finally:
                    db.close()
            rows.append(row)

        return rows

    def stress_test(self, scenario: Scenario, session_factory: Any | None = None) -> Scenario:
        sf = session_factory or SessionLocal
        db = sf()
        try:
            params_dict = scenario.parameters or {}

            baseline_params = TwinParams(days=30, seed=hash(scenario.name or "") % 9999)
            shocked_values = {k: v for k, v in params_dict.items() if k in TWIN_FIELD_NAMES}
            shocked_params = replace(baseline_params, **shocked_values)

            baseline = simulate(baseline_params)
            shocked = simulate(shocked_params)

            cost_increase = 0.0
            base_cost = (
                baseline.kpis.get("total_procurement", 0)
                + baseline.kpis.get("total_energy", 0)
                + baseline.kpis.get("total_logistics", 0)
            )
            shock_cost = (
                shocked.kpis.get("total_procurement", 0)
                + shocked.kpis.get("total_energy", 0)
                + shocked.kpis.get("total_logistics", 0)
            )
            if base_cost > 0:
                cost_increase = round((shock_cost - base_cost) / base_cost * 100, 1)

            impact = {
                "cost_increase_pct": cost_increase,
                "service_level_drop_pp": round(
                    (baseline.kpis.get("avg_service_level", 1) - shocked.kpis.get("avg_service_level", 1)) * 100, 1
                ),
                "peak_risk": shocked.risk_score,
                "waste_pct_change": round(
                    shocked.kpis.get("avg_waste_pct", 6) - baseline.kpis.get("avg_waste_pct", 6), 2
                ),
            }
            resilience = max(0.0, 100.0 - shocked.risk_score)

            scenario.predicted_impact = impact
            scenario.resilience_score = round(resilience, 1)
            db.add(scenario)
            db.commit()
        finally:
            db.close()

        return scenario
