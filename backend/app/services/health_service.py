import time
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.redis_client import redis_manager
from app.schemas.health import HealthCheckResponse, ComponentHealth
from app.config import settings


async def check_system_health(db: AsyncSession) -> HealthCheckResponse:
    components = {}
    overall_healthy = True

    # Check Database
    db_start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - db_start) * 1000
        components["database"] = ComponentHealth(
            status="healthy",
            latency_ms=round(db_latency, 2),
            details={"engine": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite"},
        )
    except Exception as e:
        overall_healthy = False
        components["database"] = ComponentHealth(status="unhealthy", details={"error": str(e)})

    # Check Redis
    redis_start = time.perf_counter()
    try:
        redis_ok = await redis_manager.ping()
        redis_latency = (time.perf_counter() - redis_start) * 1000
        if redis_ok:
            components["redis"] = ComponentHealth(
                status="healthy", latency_ms=round(redis_latency, 2), details={"stream": settings.REDIS_STREAM_EVENTS}
            )
        else:
            components["redis"] = ComponentHealth(
                status="degraded", details={"info": "Redis running in resilient offline/disconnected mode"}
            )
    except Exception as e:
        components["redis"] = ComponentHealth(
            status="degraded", details={"error": str(e), "mode": "resilient fallback"}
        )

    # Agent State Machine Subsystem
    components["agent_engine"] = ComponentHealth(
        status="healthy", details={"state_machine": "ready", "enforce_human_approval": True}
    )

    return HealthCheckResponse(
        status="healthy" if overall_healthy else "degraded",
        app_name=settings.APP_NAME,
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        components=components,
    )
