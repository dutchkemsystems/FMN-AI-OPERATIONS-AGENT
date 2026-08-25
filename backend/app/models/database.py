"""SQLAlchemy models, engine/session management and schema initialisation."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from ..config import get_settings

logger = logging.getLogger("fmn.db")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)

_pool_kwargs: dict = {}
if not _settings.database_url.startswith("sqlite"):
    _pool_kwargs = {
        "pool_size": _settings.db_pool_size,
        "max_overflow": _settings.db_max_overflow,
        "pool_recycle": _settings.db_pool_recycle,
        "pool_pre_ping": True,
    }

engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    **_pool_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "checkout")
def _on_checkout(dbapi_conn, connection_rec, connection_proxy):
    """Log slow connection checkouts (> 1s)."""
    import time

    connection_proxy.info["checkout_time"] = time.monotonic()


@event.listens_for(engine, "checkin")
def _on_checkin(dbapi_conn, connection_rec):
    """Warn if connection was held for > 30s."""
    import time

    checkout_time = getattr(connection_rec.info, "get", lambda k, d: d)("checkout_time", None)
    if checkout_time:
        held = time.monotonic() - checkout_time
        if held > 30:
            logger.warning("Connection held for %.1fs (> 30s)", held)


class Base(DeclarativeBase):
    pass


# ── User ──────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")


# ── Market / FX ───────────────────────────────────────────────────────────────


class FXRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    usd_ngn: Mapped[float]
    wheat_usd_per_ton: Mapped[float] = mapped_column(Float, default=260.0)
    cassava_usd_per_ton: Mapped[float] = mapped_column(Float, default=150.0)


# ── Energy ────────────────────────────────────────────────────────────────────


class EnergyReading(Base):
    __tablename__ = "energy_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    facility: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    kwh: Mapped[float]
    cost_ngn: Mapped[float]


class PowerSwitchEvent(Base):
    __tablename__ = "power_switch_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    facility: Mapped[str] = mapped_column(String(64))
    from_source: Mapped[str] = mapped_column(String(32))
    to_source: Mapped[str] = mapped_column(String(32))
    projected_daily_saving_ngn: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")


# ── Logistics ─────────────────────────────────────────────────────────────────


class Truck(Base):
    __tablename__ = "trucks"
    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(32), unique=True)
    region: Mapped[str] = mapped_column(String(32))
    capacity_tons: Mapped[float]
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    cost_per_km: Mapped[float] = mapped_column(Float, default=250.0)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(32))
    tons: Mapped[float]
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    truck_id: Mapped[int | None] = mapped_column(ForeignKey("trucks.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(32))
    destination: Mapped[str] = mapped_column(String(32))
    distance_km: Mapped[float]
    eta_hours: Mapped[float]
    cost_ngn: Mapped[float]
    status: Mapped[str] = mapped_column(String(32), default="dispatched")
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    route: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ── Silo / Storage ────────────────────────────────────────────────────────────


class SiloReading(Base):
    __tablename__ = "silo_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    silo_id: Mapped[str] = mapped_column(String(16))
    temp_c: Mapped[float]
    humidity_pct: Mapped[float]
    fill_pct: Mapped[float]
    grain_type: Mapped[str] = mapped_column(String(32), default="wheat")
    quality_flag: Mapped[str] = mapped_column(String(32), default="ok")


# ── Production / Waste ────────────────────────────────────────────────────────


class BatchRecord(Base):
    __tablename__ = "batch_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    line: Mapped[str] = mapped_column(String(32))
    input_tons: Mapped[float]
    output_tons: Mapped[float]
    energy_kwh: Mapped[float]
    waste_tons: Mapped[float]
    efficiency: Mapped[float] = mapped_column(Float, default=0.0)


class WasteReport(Base):
    __tablename__ = "waste_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batch_records.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    efficiency: Mapped[float]
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, default="")


# ── Agent bookkeeping ─────────────────────────────────────────────────────────


class ActionLog(Base):
    __tablename__ = "action_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    agent_type: Mapped[str] = mapped_column(String(32))
    action_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="simulated")
    impact_ngn: Mapped[float | None] = mapped_column(Float, nullable=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    agent_type: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    observation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    num_actions: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── Blockchain / Audit ────────────────────────────────────────────────────────


class BlockchainRecord(Base):
    __tablename__ = "blockchain_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    block_number: Mapped[int] = mapped_column(Integer, unique=True)
    tx_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    prev_hash: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ── Vision / Security ─────────────────────────────────────────────────────────


class VisionEvent(Base):
    __tablename__ = "vision_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    camera_id: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(32))
    image_url: Mapped[str] = mapped_column(String(512), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bounding_boxes: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Scenarios / RL ────────────────────────────────────────────────────────────


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    predicted_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resilience_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class RLPolicy(Base):
    __tablename__ = "rl_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_type: Mapped[str] = mapped_column(String(32), default="global")
    version: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(512), default="")
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    performance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Conversational / Reports ──────────────────────────────────────────────────


class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    username: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    title: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ── Schema helpers ────────────────────────────────────────────────────────────


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(seed_admin: bool = True) -> None:
    """Create all tables and optionally seed an admin user."""
    Base.metadata.create_all(engine)
    if seed_admin:
        from passlib.context import CryptContext

        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        db = SessionLocal()
        try:
            settings = get_settings()
            existing = db.query(User).filter_by(username=settings.admin_username).first()
            if not existing:
                db.add(
                    User(
                        username=settings.admin_username,
                        hashed_password=pwd.hash(settings.admin_password),
                        role="admin",
                    )
                )
                db.commit()
                logger.info("Seeded admin user: %s", settings.admin_username)
        finally:
            db.close()
