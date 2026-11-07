"""Prometheus Metrics Instrumentation for Predictive DevOps Intelligence Platform.

Strict Invariant:
- All labels are strictly bounded (categorical/enumerated).
- Unbounded identifiers (commit SHAs, user IDs, deployment IDs, exception strings)
  must NEVER be used as Prometheus labels to avoid cardinality explosion.
"""

from prometheus_client import Counter, Gauge, Histogram

# -------------------------------------------------------------------
# 1. HTTP & API Application Metrics
# -------------------------------------------------------------------
http_requests_total = Counter(
    "http_requests_total",
    "Total incoming HTTP requests processed",
    ["method", "handler", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latency of HTTP requests in seconds",
    ["method", "handler"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_active = Gauge(
    "http_requests_active",
    "Number of concurrently active HTTP requests",
    ["method"],
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP server errors (5xx responses)",
    ["method", "handler", "status_code"],
)

database_pool_connections = Gauge(
    "database_pool_connections",
    "Status of PostgreSQL async connection pool",
    ["state"],  # total, checked_out, overflow
)

# -------------------------------------------------------------------
# 2. Event Ingestion & Redis Streams Processing Metrics
# -------------------------------------------------------------------
github_webhook_received_total = Counter(
    "github_webhook_received_total",
    "Total incoming GitHub webhooks received",
    ["event_type"],
)

github_webhook_invalid_signature_total = Counter(
    "github_webhook_invalid_signature_total",
    "Total GitHub webhooks rejected due to invalid HMAC signature",
)

github_webhook_processing_total = Counter(
    "github_webhook_processing_total",
    "Total GitHub webhooks submitted for processing",
    ["event_type", "status"],
)

github_webhook_processing_errors_total = Counter(
    "github_webhook_processing_errors_total",
    "Total errors during GitHub webhook processing",
    ["event_type", "error_type"],
)

event_queue_pending_messages = Gauge(
    "event_queue_pending_messages",
    "Number of pending messages in the Redis event stream",
    ["stream"],
)

event_processing_duration_seconds = Histogram(
    "event_processing_duration_seconds",
    "Latency of event normalization and correlation processing in seconds",
    ["event_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

events_persisted_total = Counter(
    "events_persisted_total",
    "Total normalized events successfully persisted to PostgreSQL",
    ["event_type", "tenant_id"],
)

duplicate_events_total = Counter(
    "duplicate_events_total",
    "Total duplicate events detected and safely ignored",
    ["source"],
)

dead_letter_messages_total = Counter(
    "dead_letter_messages_total",
    "Total poison-pill messages routed to the dead-letter stream",
    ["stream"],
)

# -------------------------------------------------------------------
# 3. Incident Intelligence & Operational Memory Metrics
# -------------------------------------------------------------------
incidents_detected_total = Counter(
    "incidents_detected_total",
    "Total failure incidents detected from operational signals",
    ["category", "environment"],
)

incidents_created_total = Counter(
    "incidents_created_total",
    "Total new incident records created in PostgreSQL",
    ["severity", "environment"],
)

incidents_updated_total = Counter(
    "incidents_updated_total",
    "Total updates or status transitions applied to existing incidents",
    ["status"],
)

failure_classifications_total = Counter(
    "failure_classifications_total",
    "Total failure classifications executed by the deterministic engine",
    ["category", "subcategory"],
)

root_cause_hypotheses_generated_total = Counter(
    "root_cause_hypotheses_generated_total",
    "Total root-cause hypotheses generated",
    ["confidence_level"],
)

root_cause_hypotheses_confirmed_total = Counter(
    "root_cause_hypotheses_confirmed_total",
    "Total root-cause hypotheses confirmed by human engineers",
)

root_cause_hypotheses_rejected_total = Counter(
    "root_cause_hypotheses_rejected_total",
    "Total root-cause hypotheses rejected by human engineers",
)

incident_analysis_duration_seconds = Histogram(
    "incident_analysis_duration_seconds",
    "Latency of root-cause analysis pipeline in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

memory_retrieval_duration_seconds = Histogram(
    "memory_retrieval_duration_seconds",
    "Latency of operational memory searches in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

semantic_search_requests_total = Counter(
    "semantic_search_requests_total",
    "Total operational memory search queries executed",
)

semantic_search_errors_total = Counter(
    "semantic_search_errors_total",
    "Total failures encountered during operational memory searches",
)

# -------------------------------------------------------------------
# 4. Predictive Risk Intelligence Metrics
# -------------------------------------------------------------------
risk_assessments_generated_total = Counter(
    "risk_assessments_generated_total",
    "Total deployment risk assessments produced",
    ["risk_category", "environment"],
)

risk_assessment_failures_total = Counter(
    "risk_assessment_failures_total",
    "Total failures during predictive risk evaluation",
    ["error_type"],
)

ml_model_available = Gauge(
    "ml_model_available",
    "Binary indicator of whether a calibrated ML model is active in registry",
    ["model_name"],
)

prediction_latency_seconds = Histogram(
    "prediction_latency_seconds",
    "Latency of predictive scoring execution in seconds",
    ["engine_type"],  # ml_model, deterministic_fallback
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

missing_features_total = Counter(
    "missing_features_total",
    "Frequency of missing features during deployment feature extraction",
    ["feature_name"],
)

# -------------------------------------------------------------------
# 5. Agent Orchestration & Human Approval Gateway Metrics
# -------------------------------------------------------------------
agent_executions_total = Counter(
    "agent_executions_total",
    "Total agent lifecycle executions triggered",
    ["trigger_type", "status"],
)

agent_state_transitions_total = Counter(
    "agent_state_transitions_total",
    "Total successful state machine transitions",
    ["from_state", "to_state"],
)

agent_state_transition_failures_total = Counter(
    "agent_state_transition_failures_total",
    "Total rejected or invalid state machine transitions",
    ["from_state", "to_state"],
)

pending_approval_requests = Gauge(
    "pending_approval_requests",
    "Current count of approval requests waiting for human signature",
    ["environment"],
)

expired_approval_requests_total = Counter(
    "expired_approval_requests_total",
    "Total approval requests that reached expiration timeout and failed closed",
    ["environment"],
)

outcome_verifications_total = Counter(
    "outcome_verifications_total",
    "Total deployment outcomes verified by the post-rollout monitor",
    ["outcome_verdict"],  # SUCCESS, FAILURE, ROLLBACK, INCIDENT, CENSORED, UNKNOWN
)
