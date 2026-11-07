# Final Product Architecture Specification (V1.0)

**Platform:** Predictive DevOps Intelligence Platform  
**Status:** Release Ready  
**Execution Paradigm:** Controlled Operational Intelligence (Recommendation-Only; Zero Autonomous Production Modifications)  

---

## 1. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Ingestion ["Stage 1: Ingestion & Verification"]
        GH["GitHub App Webhooks"]
        AUTH["HMAC-SHA256 Verification & Replay Protection"]
        DEDUP["Redis Deduplication & Webhook Deliveries Ledger"]
        NORM["Event Normalizer (Push, PR, Workflow, Build, Deploy)"]
        STREAM[("Redis Streams (stream:devops:events)")]
    end

    subgraph Correlation ["Stage 2: Persistent Correlation Engine"]
        WORKER["Decoupled Stream Worker (SIGTERM Handling)"]
        REL["Relational Memory Graph (Repo ➔ Commit ➔ PR ➔ Workflow ➔ Build ➔ Deploy)"]
        DLQ[("Dead Letter Stream (stream:devops:deadletter)")]
    end

    subgraph FailureIntelligence ["Stage 3: Failure Intelligence & Operational Memory"]
        CLASSIFY["Deterministic Failure Classifier"]
        RECON["Incident Reconstruction Engine (5-Min Window)"]
        RCA["Root-Cause Engine (Evidence Citing)"]
        HV["Human Verification Service (Reviewer Confirmation)"]
        MEMORY[("PostgreSQL 16 + pgvector (Episodic, Relational, Semantic)")]
    end

    subgraph DependencyRisk ["Stage 4 & 5: Blast Radius & Predictive Risk"]
        GRAPH["Service Dependency Traversal (Cycle Detection, Depth <= 5)"]
        FEAT["Zero-Leakage Pre-Deployment Feature Extractor"]
        MODEL_REG["Model Registry (Chronological Splits, Brier Calibration)"]
        DET_RULES["Deterministic Risk Rules Fallback (Active when N < 50)"]
    end

    subgraph Orchestration ["Stage 6: Controlled Agent Orchestration"]
        FSM["8-Stage Finite State Machine"]
        CTX["Context Collector"]
        POLICY["Server-Side Declarative Policy Engine"]
        GATEWAY["Cryptographic Approval Gateway (RBAC, SHA-256 Signatures)"]
        MONITOR["Post-Rollout Outcome Monitor (Observation Window)"]
    end

    GH --> AUTH --> DEDUP --> NORM --> STREAM
    STREAM --> WORKER
    WORKER --> REL --> MEMORY
    WORKER -.->|Poison Pill (>3 retries)| DLQ

    REL --> CLASSIFY --> RECON --> RCA --> HV --> MEMORY
    REL --> GRAPH --> FEAT
    FEAT --> MODEL_REG
    FEAT --> DET_RULES

    REL --> FSM
    FSM --> CTX
    CTX --> POLICY
    MODEL_REG --> POLICY
    DET_RULES --> POLICY
    POLICY --> GATEWAY
    GATEWAY -->|Human Approval Required| MONITOR
    MONITOR -->|Verified Ground Truth Outcome| MEMORY
```

---

## 2. Subsystem Invariants & Guarantees

1. **Autonomy Guardrails:** The platform never executes autonomous production mutations, deployments, or rollbacks. It is strictly human-in-the-loop.
2. **Zero Post-Deployment Data Leakage:** Pre-deployment risk assessments evaluate exclusively features that were observable prior to release execution.
3. **Calibrated Provenance:** When operational records are fewer than 50 verified samples, the ML pipeline reports as "INSUFFICIENT_DATA" and the platform operates exclusively on deterministic baseline rules.
4. **Cryptographic Approval Audit Trail:** Every approval decision generates an immutable SHA-256 hash digest over the reviewer ID, role, deployment ID, recommendation summary, and timestamp.
5. **Decoupled Scale:** Ingestion webhooks, API requests, and stream consumer workers run as separate container workloads with independent autoscaling policies.
