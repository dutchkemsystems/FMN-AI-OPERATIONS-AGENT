# FMN-AI Operations Agent

AI-powered multi-agent operations platform for **Flour Mills of Nigeria (FMN)**. Orchestrates autonomous agents managing energy, supply chain, logistics, silo monitoring, waste analysis, computer vision quality inspection, and security — backed by an immutable audit ledger and digital twin simulator.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│              Dashboard · Energy · Logistics · Silos         │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI Backend                         │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ Energy   │ Supply   │ Logistics│ Silo     │ Waste / Vision  │
│ Agent    │ Chain    │ Agent    │ Agent    │ Agent           │
│          │ Agent    │          │          │                 │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│              Orchestrator Agent (Master)                    │
├─────────────────────────────────────────────────────────────┤
│  Digital Twin │ MARL Core │ Scenario Generator │ LLM Client │
├─────────────────────────────────────────────────────────────┤
│       SQLAlchemy ORM │ TimescaleDB / SQLite │ Redis          │
├─────────────────────────────────────────────────────────────┤
│    Immutable Ledger (Local Hash-Chain / Fabric / Ethereum)  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Local Development

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./fmn.db` | PostgreSQL/SQLite connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Default admin username |
| `ADMIN_PASSWORD` | `admin123` | Default admin password |
| `AUTONOMY_LEVEL` | `1` | Agent autonomy: 0=observe, 1=simulate, 2=execute |
| `USE_VISION` | `false` | Enable camera/vision agent |
| `USE_BLOCKCHAIN` | `true` | Enable blockchain audit ledger |
| `OPENAI_API_KEY` | (none) | OpenAI API key for LLM features |
| `DIESEL_PRICE_PER_LITRE` | `850.0` | Default diesel price (₦/litre) |
| `FX_ALERT_THRESHOLD_PCT` | `2.0` | FX volatility alert threshold (%) |

See `.env.example` for the full list.

## Agents

| Agent | Interval | Description |
|---|---|---|
| **Energy** | 15 min | Switches between grid/gas/diesel/solar per facility |
| **Supply Chain** | 24 hrs | FX hedging, supplier bidding, local sourcing |
| **Logistics** | 30 min | Truck dispatch, route optimisation, rerouting |
| **Silo** | 1 hr | 17-silo temperature/humidity/fill monitor |
| **Waste** | 1 hr | Batch efficiency analysis and recommendations |
| **Vision** | 60 sec | Camera-based defect/intrusion detection |
| **Security** | 5 min | Intrusion escalation and audit logging |
| **Orchestrator** | 6 hrs | Master coordinator, conflict resolution, reports |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/dashboard` | GET | Dashboard summary |
| `/api/agents` | GET | Agent status overview |
| `/api/agents/runs` | GET | Recent agent runs |
| `/api/energy/readings` | GET | Energy consumption data |
| `/api/logistics/trucks` | GET | Fleet status |
| `/api/logistics/orders` | GET | Orders list |
| `/api/logistics/shipments` | GET | Shipments list |
| `/api/silos` | GET | Silo readings |
| `/api/market/fx` | GET | FX/commodity rates |
| `/api/production/batches` | GET | Batch records |
| `/api/security/alerts` | GET | Security alerts |
| `/api/vision/events` | GET | Vision detection events |
| `/api/blockchain/records` | GET | Blockchain audit records |
| `/api/blockchain/verify` | GET | Chain integrity verification |
| `/api/reports` | GET | Executive reports |
| `/api/actions` | GET | Action logs |
| `/api/waste/reports` | GET | Waste reports |

## Testing

```bash
pytest -v
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, APScheduler
- **Database:** TimescaleDB (PostgreSQL 16) or SQLite
- **Cache:** Redis 7
- **Frontend:** React 18, TypeScript, Vite, Recharts
- **AI/ML:** OpenAI GPT-4o, YOLOv8, Stable-Baselines3 (PPO)
- **Blockchain:** Local SHA-256 hash-chain (default), Hyperledger Fabric, Ethereum
- **Infrastructure:** Docker Compose 3.9, Nginx 1.27
