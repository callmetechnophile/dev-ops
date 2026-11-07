# Predictive DevOps Intelligence Platform
## Architecture Specification & System Design Contract — V1.0

### 1. Executive Summary & Core Differentiator
The **Predictive DevOps Intelligence Platform** is an independent, production-oriented operational memory and risk forecasting platform designed to sit between CI/CD triggers, container runtimes, and cluster orchestrators (GitHub Actions, Docker, Kubernetes).

> **Core Differentiator:**  
> *"An agent that remembers every deployment failure, understands what caused it, and predicts similar risks before they reach production."*

---

### 2. Architecture & Subsystem Boundaries

```
                                  [ Integrations ]
                      GitHub Actions | Docker | Kubernetes
                                        │
                                        ▼
                           [ Integration Gateway ]
                           HMAC Verification (SHA-256)
                           Idempotency & Deduplication
                                        │
                                        ▼
                            [ Redis Streams Bus ]
                           stream:devops:events
                                        │
                                        ▼
                           [ Operational Memory Core ]
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
       Episodic Memory          Relational Memory         Semantic Memory
     (Deployments/Builds)    (Topology & Dependencies)  (pgvector Embeddings)
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
                             [ Predictive Engine ]
                       Stage A: Deterministic Rules
                       Stage B: XGBoost + SHAP (when trained)
                                        │
                                        ▼
                           [ Agent State Machine ]
                       RECOMMENDATION_GENERATED
                                        │
                                        ▼
                          [ Mandatory Approval Gate ]
                         (Cryptographic Audit Signature)
                                        │
                                        ▼
                         [ Next.js Engineering UI ]
```

---

### 3. Database Architecture (23 Specified Entities)

All tables feature **UUID primary keys**, **tenant isolation (`tenant_id`)**, **UTC timestamps**, foreign key constraints, and dedicated indexes.

| Category | Entity / Table | Responsibilities |
|---|---|---|
| **Identity & Multi-Tenancy** | `tenants` | Multi-tenant isolation boundary. |
| | `organizations` | Workspace and repository groupings. |
| | `users` | Engineers, Approvers, and Admin accounts. |
| **Topology & Services** | `repositories` | Git source control repositories. |
| | `services` | Workloads, microservices, tiers, and health states. |
| | `environments` | Production, Staging, QA, Development. |
| | `service_dependencies` | Directed service graph edges with criticality and weights. |
| **Deployments & History** | `commits` | Git commit SHAs, authors, messages. |
| | `changes` | File paths, line additions/deletions, diff patches. |
| | `builds` | CI runs, test passes/failures, image tags. |
| | `deployments` | Lifecycle state transitions, durations, rollback references. |
| | `infrastructure_changes` | K8s manifests, Helm charts, Terraform, and Dockerfile diffs. |
| **Event Ledger** | `events` | Normalized, immutable event ledger with idempotency keys. |
| **Failure Memory** | `incidents` | Incident reports, blast radius, pgvector embeddings. |
| | `failures` | CrashLoopBackOff, OOMKilled, connection pool exhaustion. |
| | `root_cause_hypotheses` | Probabilistic and suspected causes. |
| | `confirmed_root_causes` | Verified engineering lessons and prevention strategies. |
| **Intelligence & Risk** | `remediation_actions` | Operational runbooks and rollback recommendations. |
| | `risk_assessments` | Multi-factor risk scores, failure probabilities, triggered rules. |
| | `recommendations` | Human-actionable mitigation steps and rationale. |
| **Governance & ML** | `approval_requests` | Gated operational approval requests. |
| | `approval_decisions` | Cryptographically signed human authorization decisions. |
| | `model_versions` | ML model lineage, metrics (F1, ROC-AUC, Brier score). |

---

### 4. Normalized Event Contract (Section 6)
Every event payload arriving from GitHub, Docker, Kubernetes, or Prometheus conforms to:
```json
{
  "event_id": "uuid-v4",
  "tenant_id": "uuid-v4",
  "source": "github | docker | kubernetes | prometheus",
  "event_type": "commit.created | build.failed | deployment.started | incident.detected",
  "schema_version": "1.0.0",
  "repository_id": "uuid-v4",
  "service_id": "uuid-v4",
  "deployment_id": "uuid-v4",
  "commit_sha": "40-char-hex",
  "environment": "production",
  "occurred_at": "2026-11-07T17:00:00Z",
  "received_at": "2026-11-07T17:00:01Z",
  "correlation_id": "uuid-v4",
  "idempotency_key": "github:delivery-id",
  "payload": {}
}
```

---

### 5. Agent State Machine & Invariants (Section 9)
States:
1. `DEPLOYMENT_DETECTED`
2. `CONTEXT_COLLECTION`
3. `HISTORICAL_RETRIEVAL`
4. `RISK_ASSESSMENT`
5. `RECOMMENDATION_GENERATED`
6. `WAITING_FOR_APPROVAL`
7. `APPROVED`
8. `REJECTED`
9. `POST_DEPLOYMENT_MONITORING`
10. `OUTCOME_VERIFICATION`
11. `MEMORY_UPDATED`

**Invariants Enforced by Backend:**
- The agent **cannot** execute production mutations autonomously.
- State machine transition past `WAITING_FOR_APPROVAL` is strictly blocked unless an explicit `approval_decision` is committed with a SHA-256 audit signature.
- No shell access or unrestricted Kubernetes cluster APIs.
