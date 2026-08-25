"""Pytest test suite for the FMN-AI Operations Agent backend."""
from __future__ import annotations

import os
os.environ["DATABASE_URL"] = "sqlite:///./fmn_test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_PASSWORD"] = "test123"
os.environ["ADMIN_USERNAME"] = "testadmin"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _init_db():
    from app.models.database import init_db, engine, Base
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ── Health / Root ─────────────────────────────────────────────────────────────


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "FMN-AI Operations Agent" in r.json()["app"]


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ── Metrics ───────────────────────────────────────────────────────────────────


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


# ── Dashboard ─────────────────────────────────────────────────────────────────


def test_dashboard(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "agents_running" in data
    assert "total_actions" in data


# ── Agents ────────────────────────────────────────────────────────────────────


def test_agents(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    assert "agents" in r.json()


def test_agent_runs(client):
    r = client.get("/api/agents/runs")
    assert r.status_code == 200
    assert "runs" in r.json()


# ── Energy ────────────────────────────────────────────────────────────────────


def test_energy_readings(client):
    r = client.get("/api/energy/readings")
    assert r.status_code == 200
    assert "readings" in r.json()


# ── Logistics ─────────────────────────────────────────────────────────────────


def test_trucks(client):
    r = client.get("/api/logistics/trucks")
    assert r.status_code == 200
    assert "trucks" in r.json()


def test_orders(client):
    r = client.get("/api/logistics/orders")
    assert r.status_code == 200
    assert "orders" in r.json()


def test_shipments(client):
    r = client.get("/api/logistics/shipments")
    assert r.status_code == 200
    assert "shipments" in r.json()


# ── Silos ─────────────────────────────────────────────────────────────────────


def test_silos(client):
    r = client.get("/api/silos")
    assert r.status_code == 200
    assert "readings" in r.json()


# ── Market ────────────────────────────────────────────────────────────────────


def test_fx_rates(client):
    r = client.get("/api/market/fx")
    assert r.status_code == 200
    assert "rates" in r.json()


# ── Production ────────────────────────────────────────────────────────────────


def test_batches(client):
    r = client.get("/api/production/batches")
    assert r.status_code == 200
    assert "batches" in r.json()


# ── Security ──────────────────────────────────────────────────────────────────


def test_security_alerts(client):
    r = client.get("/api/security/alerts")
    assert r.status_code == 200
    assert "alerts" in r.json()


# ── Vision ────────────────────────────────────────────────────────────────────


def test_vision_events(client):
    r = client.get("/api/vision/events")
    assert r.status_code == 200
    assert "events" in r.json()


# ── Blockchain ────────────────────────────────────────────────────────────────


def test_blockchain_records(client):
    r = client.get("/api/blockchain/records")
    assert r.status_code == 200
    assert "records" in r.json()


def test_blockchain_verify(client):
    r = client.get("/api/blockchain/verify")
    assert r.status_code == 200
    assert "valid" in r.json()


# ── Reports ───────────────────────────────────────────────────────────────────


def test_reports(client):
    r = client.get("/api/reports")
    assert r.status_code == 200
    assert "reports" in r.json()


def test_actions(client):
    r = client.get("/api/actions")
    assert r.status_code == 200
    assert "actions" in r.json()


def test_waste_reports(client):
    r = client.get("/api/waste/reports")
    assert r.status_code == 200
    assert "waste_reports" in r.json()


# ── Energy Service ────────────────────────────────────────────────────────────


def test_marginal_costs():
    from app.services.energy_service import marginal_costs
    from app.config import Settings
    s = Settings()
    costs = marginal_costs(s)
    assert "grid" in costs
    assert "gas" in costs
    assert "solar" in costs
    assert "diesel" in costs
    assert all(v > 0 for v in costs.values())


# ── Logistics Service ─────────────────────────────────────────────────────────


def test_estimate_cost():
    from app.services.logistics_service import estimate_cost
    cost = estimate_cost(100, 850, 10, 250)
    assert cost > 0


def test_plan_route_no_trucks():
    from app.services.logistics_service import plan_route
    result = plan_route(type("O", (), {"region": "Kano", "tons": 5})(), [], 850, 1.0)
    assert result is None


# ── Blockchain ────────────────────────────────────────────────────────────────


def test_local_hash_chain():
    from app.blockchain.fabric_client import LocalHashChainLedger
    from app.models.database import SessionLocal, Base, engine

    Base.metadata.create_all(engine)
    ledger = LocalHashChainLedger()
    db = SessionLocal()
    try:
        tx = ledger.append(db, "test_event", {"key": "value"})
        assert tx and len(tx) == 64
        result = ledger.verify(db, tx)
        assert result["valid"] is True
        chain = ledger.verify_chain(db)
        assert chain["valid"] is True
    finally:
        db.close()


# ── Digital Twin ──────────────────────────────────────────────────────────────


def test_simulate():
    from app.digital_twin.simulator import TwinParams, simulate
    result = simulate(TwinParams(days=7, seed=42))
    assert result.risk_score >= 0
    assert "total_procurement" in result.kpis
    assert len(result.series["procurement_cost"]) == 7


# ── Helpers ───────────────────────────────────────────────────────────────────


def test_helpers():
    from app.utils.helpers import sha256_of, new_id, pct_change, format_ngn
    assert len(sha256_of({"a": 1})) == 64
    assert new_id("T").startswith("T-")
    assert pct_change(110, 100) == 10.0
    assert "₦" in format_ngn(1000)


# ── Cache ─────────────────────────────────────────────────────────────────────


def test_cache():
    from app.utils.cache import Cache
    cache = Cache(redis_url=None)
    cache.set("test_key", {"data": 1}, ttl=60)
    assert cache.get("test_key") == {"data": 1}
    cache.delete("test_key")
    assert cache.get("test_key") is None


# ── Retry ─────────────────────────────────────────────────────────────────────


def test_retry_decorator():
    from app.utils.retry import retry

    call_count = 0

    @retry(max_attempts=3, backoff_base=0.01, exceptions=(ValueError,))
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "ok"

    assert flaky() == "ok"
    assert call_count == 3
