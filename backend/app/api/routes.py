"""API routes for the FMN-AI Operations Agent."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.database import (
    ActionLog,
    AgentRun,
    BatchRecord,
    BlockchainRecord,
    EnergyReading,
    FXRate,
    Order,
    Report,
    SecurityAlert,
    Shipment,
    SiloReading,
    Truck,
    VisionEvent,
    WasteReport,
    get_db,
)
from ..utils.cache import get_cache

router = APIRouter(prefix="/api", tags=["api"])


def _cached(key: str, ttl: int, fn, *args, **kwargs):
    cache = get_cache()
    hit = cache.get(key)
    if hit is not None:
        return hit
    result = fn(*args, **kwargs)
    cache.set(key, result, ttl=ttl)
    return result


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    def _compute():
        return {
            "agents_running": db.query(AgentRun).filter_by(status="ok").count(),
            "total_actions": db.query(ActionLog).count(),
            "active_shipments": db.query(Shipment).filter_by(status="dispatched").count(),
            "pending_orders": db.query(Order).filter_by(status="pending").count(),
            "unresolved_alerts": db.query(SecurityAlert).filter_by(resolved=False).count(),
            "blockchain_records": db.query(BlockchainRecord).count(),
        }

    return _cached("dashboard", 10, _compute)


# ── Agents ────────────────────────────────────────────────────────────────────


@router.get("/agents")
def list_agents():
    from ..agents.registry import build_agents

    settings = get_settings()
    agents = build_agents(settings, None)
    return {"agents": {name: a.status_payload() for name, a in agents.items()}}


@router.get("/agents/runs")
def agent_runs(limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(AgentRun).order_by(AgentRun.timestamp.desc()).limit(limit).all()
    return {
        "runs": [
            {
                "id": r.id,
                "agent": r.agent_type,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "actions": r.num_actions,
                "error": r.error,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in runs
        ]
    }


# ── Energy ────────────────────────────────────────────────────────────────────


@router.get("/energy/readings")
def energy_readings(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(EnergyReading).order_by(EnergyReading.timestamp.desc()).limit(limit).all()
    return {
        "readings": [
            {
                "id": r.id,
                "facility": r.facility,
                "source": r.source,
                "kwh": r.kwh,
                "cost_ngn": r.cost_ngn,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ]
    }


# ── Logistics ─────────────────────────────────────────────────────────────────


@router.get("/logistics/trucks")
def list_trucks(db: Session = Depends(get_db)):
    def _compute():
        trucks = db.query(Truck).all()
        return {
            "trucks": [
                {
                    "id": t.id,
                    "plate": t.plate,
                    "region": t.region,
                    "capacity_tons": t.capacity_tons,
                    "available": t.available,
                    "cost_per_km": t.cost_per_km,
                }
                for t in trucks
            ]
        }

    return _cached("trucks", 30, _compute)


@router.get("/logistics/orders")
def list_orders(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Order)
    if status:
        q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).limit(50).all()
    return {
        "orders": [
            {
                "id": o.id,
                "reference": o.reference,
                "customer": o.customer,
                "region": o.region,
                "tons": o.tons,
                "status": o.status,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ]
    }


@router.get("/logistics/shipments")
def list_shipments(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Shipment)
    if status:
        q = q.filter_by(status=status)
    shipments = q.order_by(Shipment.id.desc()).limit(50).all()
    return {
        "shipments": [
            {
                "id": s.id,
                "order_id": s.order_id,
                "truck_id": s.truck_id,
                "origin": s.origin,
                "destination": s.destination,
                "distance_km": s.distance_km,
                "eta_hours": s.eta_hours,
                "cost_ngn": s.cost_ngn,
                "status": s.status,
                "dispatched_at": s.dispatched_at.isoformat() if s.dispatched_at else None,
            }
            for s in shipments
        ]
    }


# ── Silos ─────────────────────────────────────────────────────────────────────


@router.get("/silos")
def silo_readings(db: Session = Depends(get_db)):
    def _compute():
        rows = db.query(SiloReading).order_by(SiloReading.timestamp.desc()).limit(50).all()
        return {
            "readings": [
                {
                    "id": r.id,
                    "silo_id": r.silo_id,
                    "temp_c": r.temp_c,
                    "humidity_pct": r.humidity_pct,
                    "fill_pct": r.fill_pct,
                    "quality_flag": r.quality_flag,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in rows
            ]
        }

    return _cached("silos", 15, _compute)


# ── Market / FX ───────────────────────────────────────────────────────────────


@router.get("/market/fx")
def fx_rates(limit: int = 20, db: Session = Depends(get_db)):
    def _compute():
        rows = db.query(FXRate).order_by(FXRate.timestamp.desc()).limit(limit).all()
        return {
            "rates": [
                {
                    "id": r.id,
                    "usd_ngn": r.usd_ngn,
                    "wheat_usd_per_ton": r.wheat_usd_per_ton,
                    "cassava_usd_per_ton": r.cassava_usd_per_ton,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in rows
            ]
        }

    return _cached("fx_rates", 30, _compute)


# ── Production / Waste ────────────────────────────────────────────────────────


@router.get("/production/batches")
def batch_records(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(BatchRecord).order_by(BatchRecord.timestamp.desc()).limit(limit).all()
    return {
        "batches": [
            {
                "id": b.id,
                "line": b.line,
                "input_tons": b.input_tons,
                "output_tons": b.output_tons,
                "energy_kwh": b.energy_kwh,
                "waste_tons": b.waste_tons,
                "efficiency": b.efficiency,
                "timestamp": b.timestamp.isoformat(),
            }
            for b in rows
        ]
    }


# ── Security ──────────────────────────────────────────────────────────────────


@router.get("/security/alerts")
def security_alerts(resolved: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(SecurityAlert)
    if resolved is not None:
        q = q.filter_by(resolved=resolved)
    alerts = q.order_by(SecurityAlert.timestamp.desc()).limit(30).all()
    return {
        "alerts": [
            {
                "id": a.id,
                "source": a.source,
                "severity": a.severity,
                "message": a.message,
                "resolved": a.resolved,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in alerts
        ]
    }


# ── Vision ────────────────────────────────────────────────────────────────────


@router.get("/vision/events")
def vision_events(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.query(VisionEvent).order_by(VisionEvent.timestamp.desc()).limit(limit).all()
    return {
        "events": [
            {
                "id": v.id,
                "camera_id": v.camera_id,
                "event_type": v.event_type,
                "confidence": v.confidence,
                "timestamp": v.timestamp.isoformat(),
            }
            for v in rows
        ]
    }


# ── Blockchain / Audit ────────────────────────────────────────────────────────


@router.get("/blockchain/records")
def blockchain_records(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.query(BlockchainRecord).order_by(BlockchainRecord.block_number.desc()).limit(limit).all()
    return {
        "records": [
            {
                "id": r.id,
                "block_number": r.block_number,
                "tx_hash": r.tx_hash,
                "event_type": r.event_type,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/blockchain/verify")
def blockchain_verify(db: Session = Depends(get_db)):
    from ..blockchain.fabric_client import get_ledger

    ledger = get_ledger()
    result = ledger.verify_chain(db)
    return result


# ── Reports ───────────────────────────────────────────────────────────────────


@router.get("/reports")
def list_reports(kind: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if kind:
        q = q.filter_by(kind=kind)
    reports = q.order_by(Report.timestamp.desc()).limit(20).all()
    return {
        "reports": [
            {
                "id": r.id,
                "title": r.title,
                "kind": r.kind,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in reports
        ]
    }


# ── Actions (logs) ────────────────────────────────────────────────────────────


@router.get("/actions")
def action_logs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(ActionLog).order_by(ActionLog.timestamp.desc()).limit(limit).all()
    return {
        "actions": [
            {
                "id": a.id,
                "agent": a.agent_type,
                "action": a.action_type,
                "status": a.status,
                "impact": a.impact_ngn,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in rows
        ]
    }


# ── Reports (Waste) ───────────────────────────────────────────────────────────


@router.get("/waste/reports")
def waste_reports(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(WasteReport).order_by(WasteReport.timestamp.desc()).limit(limit).all()
    return {
        "waste_reports": [
            {
                "id": w.id,
                "batch_id": w.batch_id,
                "efficiency": w.efficiency,
                "recommendation": w.recommendation,
                "timestamp": w.timestamp.isoformat(),
            }
            for w in rows
        ]
    }
