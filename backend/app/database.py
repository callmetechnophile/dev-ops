import time
import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

# Engine configuration with production connection pool tuning
is_sqlite = "sqlite" in settings.DATABASE_URL

engine_kwargs: Dict[str, Any] = {}
if not is_sqlite:
    engine_kwargs = {
        "pool_pre_ping": True,  # Validates connection liveness before checkout
        "pool_size": 15,  # Stable baseline connections
        "max_overflow": 25,  # Allowed burst connections
        "pool_timeout": 30.0,  # Wait up to 30s during traffic spikes
        "pool_recycle": 1800,  # Recycle connections every 30m to avoid stale firewall cuts
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """Evaluates database connectivity and checkout latency."""
    start_time = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "pool_size": getattr(engine.pool, "size", lambda: 0)(),
            "checked_out_connections": getattr(engine.pool, "checkedout", lambda: 0)(),
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
        }
