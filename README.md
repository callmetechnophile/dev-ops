# Predictive DevOps Intelligence Platform

An independent, AI-powered predictive operational intelligence agent that maintains persistent memory of past build failures, deployments, infrastructure modifications, and downstream incident cascades to predict and mitigate deployment risks before reaching production.

> **Core Differentiator:**  
> *"An agent that remembers every deployment failure, understands what caused it, and predicts similar risks before they reach production."*

---

## Architecture & Subsystems

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui dark engineering dashboard, React Flow for microservice dependency topologies, interactive deployment timeline, build history.
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async/Sync), Alembic.
- **Data & Streaming**: PostgreSQL with pgvector semantic search, Redis Streams for consumer-group-based idempotent event processing with dead-letter queue.
- **GitHub Ingestion Engine**: GitHub App authentication, HMAC-SHA256 signature verification, typed normalizers (`PushEvent`, `PullRequestEvent`, `WorkflowRunEvent`, `WorkflowJobEvent`, `DeploymentEvent`), and deterministic correlation.
- **Governance & Approval Gate**: Mandatory human authorization gate with SHA-256 cryptographic audit trails.
- **Observability**: Prometheus metrics (`/metrics`) and structured JSON logging.

---

## Repository Structure

```
predictive-devops-intelligence/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Automated CI test workflow
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── router.py              # Central V1 API router
│   │   │   └── v1/
│   │   │       ├── health.py          # /api/v1/health
│   │   │       ├── integrations.py    # GitHub webhook receiver (HMAC SHA-256) & status
│   │   │       ├── repositories.py    # /api/v1/repositories & commits & workflows
│   │   │       ├── workflows.py       # /api/v1/workflows & /api/v1/builds
│   │   │       ├── deployments.py     # /api/v1/deployments & /api/v1/deployments/{id}/timeline
│   │   │       ├── incidents.py       # /api/v1/incidents
│   │   │       ├── services.py        # /api/v1/services & dependencies
│   │   │       ├── memory.py          # /api/v1/memory/search
│   │   │       ├── recommendations.py # /api/v1/recommendations
│   │   │       ├── approvals.py       # /api/v1/approvals
│   │   │       └── events.py          # /api/v1/events (immutable ledger)
│   │   ├── core/
│   │   │   ├── logging.py             # Structured JSON logger
│   │   │   ├── metrics.py             # Prometheus metrics
│   │   │   ├── security.py            # HMAC SHA-256 signature & size validator
│   │   │   └── exceptions.py          # Custom domain exceptions
│   │   ├── integrations/
│   │   │   └── github/
│   │   │       ├── client.py          # GitHub App JWT & API client
│   │   │       └── normalizer.py      # Event normalizer for all GitHub event types
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── webhook_delivery.py    # Raw immutable delivery ledger
│   │   │   ├── github_entities.py     # PullRequest, WorkflowRun, WorkflowJob, DeploymentEvent
│   │   │   ├── organization.py        # Tenant, Organization, User
│   │   │   ├── service.py             # Repository, Service, Environment, ServiceDependency
│   │   │   ├── deployment.py          # Commit, Change, Build, Deployment, InfrastructureChange
│   │   │   ├── event.py               # Normalized event ledger
│   │   │   ├── incident.py            # Incident, Failure, Hypotheses, ConfirmedRootCause
│   │   │   ├── intelligence.py        # RemediationAction, RiskAssessment, Recommendation
│   │   │   ├── governance.py          # ApprovalRequest, ApprovalDecision
│   │   │   └── model_registry.py      # ModelVersion
│   │   ├── schemas/                   # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── correlation_engine.py  # Deterministic event correlation graph
│   │   │   ├── webhook_service.py     # Webhook ingest & Redis dispatch
│   │   │   ├── health_service.py      # System health checks
│   │   │   └── state_machine.py       # Deployment state machine
│   │   ├── workers/
│   │   │   └── redis_stream_worker.py # Redis Streams consumer with ACK, retries & dead-letter
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis_client.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py
│   │   │   └── 0002_github_ingestion.py
│   │   └── env.py
│   ├── tests/
│   │   ├── test_webhook_security.py
│   │   ├── test_event_normalization.py
│   │   ├── test_correlation_engine.py
│   │   ├── test_milestone2_api.py
│   │   ├── test_api.py
│   │   ├── test_health.py
│   │   ├── test_event_contracts.py
│   │   └── test_state_machine.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx               # Overview Dashboard (Deployment stats, frequency, health)
│   │   │   ├── deployments/page.tsx   # Deployment History & Chronological Timeline
│   │   │   ├── builds/page.tsx        # Build History & CI Workflows
│   │   │   ├── risk/page.tsx          # Risk Assessment Center
│   │   │   ├── incidents/page.tsx     # Incident Intelligence
│   │   │   ├── dependencies/page.tsx  # React Flow Topology Explorer
│   │   │   ├── memory/page.tsx        # Operational Memory Search
│   │   │   ├── approvals/page.tsx     # Approval Gate & Audit Fingerprints
│   │   │   └── settings/page.tsx      # GitHub Integration & Webhook Health
│   │   ├── components/
│   │   └── lib/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
├── GITHUB_APP_SETUP.md                # Step-by-step GitHub App configuration guide
├── ARCHITECTURE.md
└── README.md
```

---

## Local Development & Quickstart

### Option 1: Running with Docker Compose (Recommended)

```bash
cd predictive-devops-intelligence
cp .env.example .env
docker compose up --build -d
```
- Web Dashboard: [http://localhost:3000](http://localhost:3000)
- Backend API Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- Prometheus Metrics: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- Health Status: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### Option 2: Running Locally (Native)

#### 1. Backend:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
pip install aiosqlite pytest pytest-asyncio httpx

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## Automated Verification & Tests

Run all automated test suites (30 tests across security, event processing, correlation, state machine, and APIs):
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

- [x] **Milestone 1 — Foundation**: Repository structure, FastAPI backend, Next.js dashboard, PostgreSQL schema, Redis streams, Alembic migrations, health checks, automated tests passing.
- [x] **Milestone 2 — GitHub Event Ingestion & Deployment Memory**: GitHub App integration, webhook receiver, constant-time HMAC-SHA256 verification, raw delivery ledger, Redis Streams consumer group with retry and dead-letter routing, event normalizers (`PushEvent`, `PullRequestEvent`, `WorkflowRunEvent`, `WorkflowJobEvent`, `DeploymentEvent`), deterministic correlation engine, deployment timeline API, build history UI, and 30 automated tests passing.
- [ ] **Milestone 3 — Failure Memory**: Incident records, CrashLoopBackOff/OOM classification, root-cause hypotheses.
- [ ] **Milestone 4 — Dependency Intelligence**: Service dependency graph traversal & blast radius calculator.
- [ ] **Milestone 5 — Predictive Intelligence**: Deterministic risk rules + XGBoost feature engineering.
- [ ] **Milestone 6 — Agent & Frontend**: Controlled state machine, recommendation generator, human approval gate.
- [ ] **Milestone 7 — Production Hardening**: Kubernetes manifests, Prometheus metrics, security verification.
