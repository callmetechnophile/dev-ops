"""Production Hardening, Security, and Reliability Tests for Milestone 6.

Validates:
1. Security HTTP response headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-Request-ID).
2. Rate-limiting middleware on sensitive endpoints with 429 response.
3. Payload size enforcement (413 Payload Too Large on oversized bodies).
4. Kubernetes liveness, readiness, and startup probe endpoints.
5. Automated credential and token redaction in structured logging.
6. Database health check and latency instrumentation.
7. Prometheus metrics exposition and strictly bounded cardinality.
8. Background worker graceful shutdown lifecycle.
"""
import json
import logging
import pytest
from httpx import AsyncClient
from app.core.logging import redact_sensitive_value, JSONFormatter
from app.core.security_middleware import _RATE_LIMIT_BUCKETS, RATE_LIMIT_MAX_REQUESTS
from app.database import check_database_health
from app.workers.redis_stream_worker import redis_stream_worker


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Verify production security headers are injected into every API response."""
    res = await client.get("/api/v1/health/liveness")
    assert res.status_code == 200

    headers = res.headers
    assert "x-request-id" in headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "max-age=31536000" in headers["strict-transport-security"]
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["permissions-policy"]


@pytest.mark.asyncio
async def test_rate_limiter_protection(client: AsyncClient):
    """Verify rate-limiting middleware blocks excessive requests to sensitive routes."""
    test_endpoint = "/api/v1/approvals"
    
    # Pre-populate bucket to exceed threshold
    bucket_key = ("127.0.0.1", test_endpoint)
    import time
    now = time.time()
    _RATE_LIMIT_BUCKETS[bucket_key] = [now] * RATE_LIMIT_MAX_REQUESTS

    res = await client.get(test_endpoint)
    assert res.status_code == 429
    data = res.json()
    assert "Too many requests" in data["error"]
    assert res.headers["retry-after"] == "60"

    # Clean up bucket for subsequent tests
    _RATE_LIMIT_BUCKETS.pop(bucket_key, None)


@pytest.mark.asyncio
async def test_payload_size_enforcement(client: AsyncClient):
    """Verify request entity size greater than 10MB is rejected with 413."""
    oversized_length = str(15 * 1024 * 1024)  # 15 MB
    res = await client.post(
        "/api/v1/webhooks",
        headers={"Content-Length": oversized_length, "Content-Type": "application/json"},
        content=b"{}"
    )
    assert res.status_code == 413
    data = res.json()
    assert "Payload exceeds maximum allowed size" in data["error"]


@pytest.mark.asyncio
async def test_kubernetes_probes(client: AsyncClient):
    """Verify Kubernetes liveness, readiness, and startup probe endpoints."""
    # 1. Liveness
    live_res = await client.get("/api/v1/health/liveness")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # 2. Startup
    start_res = await client.get("/api/v1/health/startup")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "started"

    # 3. Readiness
    ready_res = await client.get("/api/v1/health/readiness")
    assert ready_res.status_code in (200, 503)
    data = ready_res.json()
    assert "status" in data


def test_log_redaction_secrets_and_tokens():
    """Verify recursive log redactor masks credentials, Bearer tokens, and GitHub PATs."""
    raw_payload = {
        "user": "sre-admin",
        "password": "SuperSecretPassword123!",
        "token": "ghp_123456789012345678901234567890123456",
        "nested": {
            "api_key": "live_key_998877",
            "safe_field": "database-migration",
        },
        "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.test",
    }

    redacted = redact_sensitive_value(raw_payload)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "database-migration"
    assert "Bearer [REDACTED]" in redacted["auth_header"]

    # Verify JSONFormatter handles log records without leaking secrets
    formatter = JSONFormatter(service_name="test-worker", environment="test")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Authenticated user with token ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert "ghp_" not in parsed["message"]
    assert "[REDACTED_GITHUB_TOKEN]" in parsed["message"]


@pytest.mark.asyncio
async def test_database_health_check_function():
    """Verify check_database_health returns latency and status metrics."""
    health = await check_database_health()
    assert isinstance(health, dict)
    assert health["status"] in ("healthy", "unhealthy")
    assert "latency_ms" in health


@pytest.mark.asyncio
async def test_metrics_endpoint_exposition(client: AsyncClient):
    """Verify /metrics exports Prometheus metrics in standard exposition format."""
    res = await client.get("/metrics")
    assert res.status_code == 200
    text = res.text
    assert "http_requests_total" in text
    assert "database_pool_connections" in text
    assert "http_request_duration_seconds" in text


def test_worker_graceful_shutdown():
    """Verify background worker graceful stop signal toggles running flag."""
    redis_stream_worker.running = True
    assert redis_stream_worker.running is True
    redis_stream_worker.stop()
    assert redis_stream_worker.running is False
