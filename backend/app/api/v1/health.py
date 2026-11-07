from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.health_service import check_system_health
from app.schemas.health import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Production health check verifying database connectivity, Redis connection,
    and agent orchestration subsystem availability.
    """
    return await check_system_health(db)
