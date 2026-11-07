"""Production Security and Observability Middleware for FastAPI.

Provides:
- Security HTTP headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options).
- Request ID & Correlation ID injection (X-Request-ID).
- In-memory rate limiting with sliding window on sensitive API routes.
- Request payload size protection.
- Automated Prometheus request latency and error counting.
"""

import time
import uuid
import logging
from typing import Dict, Tuple, List
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core import metrics

logger = logging.getLogger(__name__)

# Sensitive routes subject to strict rate limiting
RATE_LIMITED_PREFIXES = [
    "/api/v1/integrations/github/webhook",
    "/api/v1/webhooks",
    "/api/v1/approvals",
    "/api/v1/agent/executions",
]

# Simple in-memory sliding window rate limiter: (client_ip, endpoint) -> [timestamps]
_RATE_LIMIT_BUCKETS: Dict[Tuple[str, str], List[float]] = {}
RATE_LIMIT_MAX_REQUESTS = 120  # requests per minute per IP
RATE_LIMIT_WINDOW_SECONDS = 60.0
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB


class ProductionSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Enforce payload size limits
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_CONTENT_LENGTH:
            return JSONResponse(
                status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                content={"error": "Payload exceeds maximum allowed size (10MB)."},
            )

        # 2. Assign unique Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # 3. Rate limiting check on sensitive endpoints
        client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path

        if any(path.startswith(prefix) for prefix in RATE_LIMITED_PREFIXES):
            now = time.time()
            bucket_key = (client_ip, path)
            window_start = now - RATE_LIMIT_WINDOW_SECONDS

            timestamps = _RATE_LIMIT_BUCKETS.get(bucket_key, [])
            # Purge stale requests
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
                logger.warning(f"Rate limit exceeded for IP {client_ip} on {path}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Too many requests. Please slow down and retry in a minute."},
                    headers={"Retry-After": "60"},
                )

            valid_timestamps.append(now)
            _RATE_LIMIT_BUCKETS[bucket_key] = valid_timestamps

        # 4. Measure request duration and track active requests
        method = request.method
        handler = path
        metrics.http_requests_active.labels(method=method).inc()
        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
            duration = time.perf_counter() - start_time
            status_code = str(response.status_code)

            # Record metrics
            metrics.http_requests_total.labels(
                method=method,
                handler=handler,
                status_code=status_code,
            ).inc()
            metrics.http_request_duration_seconds.labels(
                method=method,
                handler=handler,
            ).observe(duration)

            if response.status_code >= 500:
                metrics.http_errors_total.labels(
                    method=method,
                    handler=handler,
                    status_code=status_code,
                ).inc()

        except Exception as exc:
            duration = time.perf_counter() - start_time
            metrics.http_errors_total.labels(
                method=method,
                handler=handler,
                status_code="500",
            ).inc()
            metrics.http_requests_total.labels(
                method=method,
                handler=handler,
                status_code="500",
            ).inc()
            raise exc
        finally:
            metrics.http_requests_active.labels(method=method).dec()

        # 5. Inject hardened HTTP security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"

        return response
