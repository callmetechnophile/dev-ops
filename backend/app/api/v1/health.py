from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.services.health_service import check_system_health
from app.schemas.health import HealthCheckResponse
from app.redis_client import redis_manager

router = APIRouter(tags=["Health & Probes"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check verifying PostgreSQL database, Redis event bus,
    and agent orchestration subsystem.
    """
    return await check_system_health(db)


@router.get("/health/liveness", tags=["Kubernetes Probes"])
async def liveness_probe():
    """Kubernetes liveness probe: verifies process execution and event loop responsiveness."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/readiness", tags=["Kubernetes Probes"])
async def readiness_probe():
    """Kubernetes readiness probe: verifies database connectivity before routing ingress traffic."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "redis": "connected" if redis_manager.is_connected else "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/health/startup", tags=["Kubernetes Probes"])
async def startup_probe():
    """Kubernetes startup probe: confirms application initialization."""
    return {"status": "started", "timestamp": datetime.now(timezone.utc).isoformat()}
