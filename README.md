# Predictive DevOps Intelligence Platform

An independent, AI-powered predictive operational intelligence agent that maintains persistent memory of past build failures, deployments, infrastructure modifications, and downstream incident cascades to predict and mitigate deployment risks before reaching production.

> **Core Differentiator:**  
> *"An agent that remembers every deployment failure, understands what caused it, and predicts similar risks before they reach production."*

---

## Architecture & Subsystems

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui dark engineering dashboard, React Flow for microservice dependency topologies.
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async/Sync), Alembic.
- **Data & Streaming**: PostgreSQL with pgvector semantic search, Redis Streams for idempotent event ingestion.
- **Predictive Engine**: Stage A deterministic rule heuristics + Stage B XGBoost feature pipeline and SHAP explainability interface.
- **Governance & Approval Gate**: Mandatory human authorization gate with SHA-256 cryptographic audit trails.

---

## Repository Structure

```
predictive-devops-intelligence/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI test workflow
├── backend/
│   ├── app/
│   │   ├── api/                 # Versioned REST APIs (/api/v1/...)
│   │   ├── core/                # Logging, security (HMAC), custom exceptions
│   │   ├── models/              # 23 SQLAlchemy 2.0 models with pgvector & UUIDs
│   │   ├── schemas/             # Pydantic v2 contracts (Section 6 Event Contract)
│   │   ├── services/            # Health, Event Ingest, Agent State Machine
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # Async & Sync database engine
│   │   ├── redis_client.py      # Redis Streams connection manager
│   │   └── main.py              # FastAPI application entrypoint
│   ├── alembic/                 # Database migrations (0001_initial_schema.py)
│   ├── tests/                   # Automated unit & integration tests (Pytest)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages (Overview, Deployments, Risk, etc.)
│   │   ├── components/          # Dark engineering UI components & React Flow graph
│   │   └── lib/                 # Typed API client and utilities
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml           # Multi-container orchestration (PostgreSQL, Redis, Backend, Frontend)
├── .env.example                 # Environment variables template
├── ARCHITECTURE.md              # Master architecture specification
└── README.md
```

---

## Local Development & Quickstart

### Option 1: Running with Docker Compose (Recommended)

1. **Clone and enter repository**:
   ```bash
   cd predictive-devops-intelligence
   cp .env.example .env
   ```

2. **Start all services**:
   ```bash
   docker compose up --build -d
   ```

3. **Access Services**:
   - Web Dashboard: [http://localhost:3000](http://localhost:3000)
   - Backend API Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
   - Health Status: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### Option 2: Running Locally (Native)

#### 1. Backend Setup:
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
pip install aiosqlite pytest pytest-asyncio httpx

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```

---

## Automated Verification & Tests

Run the backend test suite:
```bash
cd backend
python -m pytest tests -v
```

Build the production frontend:
```bash
cd frontend
npm run build
```

---

## Status & Roadmap

- [x] **Milestone 1 — Foundation**: Repository structure, FastAPI backend, Next.js dashboard, PostgreSQL 23 entity models, Redis streams, Alembic migrations, CI workflow, automated tests passing.
- [ ] **Milestone 2 — Event Ingestion**: Inbound GitHub webhook ingestion, signature verification, event normalizer.
- [ ] **Milestone 3 — Failure Memory**: Incident records, CrashLoopBackOff/OOM classification, root-cause hypotheses.
- [ ] **Milestone 4 — Dependency Intelligence**: Service dependency graph traversal & blast radius calculator.
- [ ] **Milestone 5 — Predictive Intelligence**: Deterministic risk rules + XGBoost feature engineering.
- [ ] **Milestone 6 — Agent & Frontend**: Controlled state machine, recommendation generator, human approval gate.
- [ ] **Milestone 7 — Production Hardening**: Kubernetes manifests, Prometheus metrics, security verification.
