"""Convert TwinResult to chart payloads for the frontend."""
from __future__ import annotations
from .simulator import TwinResult

HUB_GEO = {
    "Lagos": [6.4550, 3.3841],
    "Ibadan": [7.3775, 3.9470],
    "Abuja": [9.0765, 7.3986],
    "Kano": [12.0022, 8.5920],
    "Enugu": [6.5244, 7.4951],
    "Port Harcourt": [4.8156, 7.0498],
}

def to_chart_payload(result: TwinResult) -> dict:
    n = len(next(iter(result.series.values())))
    return {
        "labels": [f"D{i+1}" for i in range(n)],
        "series": [
            {"name": k.replace("_", " ").title(), "data": v}
            for k, v in result.series.items()
        ],
        "kpis": result.kpis,
        "risk_score": result.risk_score,
        "recommendations": result.recommendations,
    }

def network_geo() -> dict:
    nodes = [{"id": k, "lat": v[0], "lon": v[1]} for k, v in HUB_GEO.items()]
    edges = [
        {"from": "Lagos", "to": "Ibadan"},
        {"from": "Lagos", "to": "Abuja"},
        {"from": "Abuja", "to": "Kano"},
        {"from": "Abuja", "to": "Enugu"},
        {"from": "Enugu", "to": "Port Harcourt"},
    ]
    return {"nodes": nodes, "edges": edges}
