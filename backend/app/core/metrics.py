import time
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram

# Webhook Metrics
github_webhook_received_total = Counter(
    "github_webhook_received_total",
    "Total incoming GitHub webhooks received",
    ["event_type"]
)

github_webhook_invalid_signature_total = Counter(
    "github_webhook_invalid_signature_total",
    "Total GitHub webhooks rejected due to invalid HMAC signature"
)

github_webhook_processing_total = Counter(
    "github_webhook_processing_total",
    "Total GitHub webhooks submitted for processing",
    ["event_type", "status"]
)

github_webhook_processing_errors_total = Counter(
    "github_webhook_processing_errors_total",
    "Total errors during GitHub webhook processing",
    ["event_type", "error_type"]
)

# Stream & Processing Metrics
event_queue_pending_messages = Gauge(
    "event_queue_pending_messages",
    "Number of pending messages in the Redis event stream",
    ["stream"]
)

event_processing_duration_seconds = Histogram(
    "event_processing_duration_seconds",
    "Latency of event normalization and correlation processing in seconds",
    ["event_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

events_persisted_total = Counter(
    "events_persisted_total",
    "Total normalized events successfully persisted to PostgreSQL",
    ["event_type", "tenant_id"]
)

duplicate_events_total = Counter(
    "duplicate_events_total",
    "Total duplicate events detected and safely ignored",
    ["source"]
)

# Milestone 3 Incident & Memory Metrics
incidents_detected_total = Counter(
    "incidents_detected_total",
    "Total failure incidents detected from operational signals",
    ["category", "environment"]
)

incidents_created_total = Counter(
    "incidents_created_total",
    "Total new incident records created in PostgreSQL",
    ["severity", "environment"]
)

incidents_updated_total = Counter(
    "incidents_updated_total",
    "Total updates or status transitions applied to existing incidents",
    ["status"]
)

failure_classifications_total = Counter(
    "failure_classifications_total",
    "Total failure classifications executed by the deterministic engine",
    ["category", "subcategory"]
)

root_cause_hypotheses_generated_total = Counter(
    "root_cause_hypotheses_generated_total",
    "Total root-cause hypotheses generated",
    ["confidence_level"]
)

root_cause_hypotheses_confirmed_total = Counter(
    "root_cause_hypotheses_confirmed_total",
    "Total root-cause hypotheses confirmed by human engineers"
)

root_cause_hypotheses_rejected_total = Counter(
    "root_cause_hypotheses_rejected_total",
    "Total root-cause hypotheses rejected by human engineers"
)

incident_analysis_duration_seconds = Histogram(
    "incident_analysis_duration_seconds",
    "Latency of root-cause analysis pipeline in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

memory_retrieval_duration_seconds = Histogram(
    "memory_retrieval_duration_seconds",
    "Latency of operational memory searches in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
)

semantic_search_requests_total = Counter(
    "semantic_search_requests_total",
    "Total operational memory search queries executed"
)

semantic_search_errors_total = Counter(
    "semantic_search_errors_total",
    "Total failures encountered during operational memory searches"
)
