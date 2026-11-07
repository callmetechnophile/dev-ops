from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.incident import Incident, ConfirmedRootCause, Failure
from app.schemas.incident import ConfirmedRootCauseRead

router = APIRouter(prefix="/memory", tags=["Operational Memory"])


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=2, description="Search query for failure memory or root causes"),
    service_id: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieves historical operational memory: verified lessons, confirmed root causes,
    and matching failure patterns across previous deployment cycles.
    """
    # 1. Search confirmed engineering lessons
    confirmed_stmt = (
        select(ConfirmedRootCause)
        .where(
            or_(
                ConfirmedRootCause.root_cause_summary.ilike(f"%{q}%"),
                ConfirmedRootCause.verified_engineering_lesson.ilike(f"%{q}%"),
                ConfirmedRootCause.prevention_strategy.ilike(f"%{q}%"),
            )
        )
        .limit(limit)
    )
    confirmed_res = await db.execute(confirmed_stmt)
    confirmed_records = confirmed_res.scalars().all()

    # 2. Search historical failure patterns
    failure_stmt = (
        select(Failure)
        .where(
            or_(
                Failure.failure_type.ilike(f"%{q}%"),
                Failure.error_message.ilike(f"%{q}%"),
            )
        )
        .limit(limit)
    )
    failure_res = await db.execute(failure_stmt)
    failures = failure_res.scalars().all()

    return {
        "query": q,
        "total_matches": len(confirmed_records) + len(failures),
        "verified_lessons": [
            {
                "id": str(c.id),
                "incident_id": str(c.incident_id),
                "root_cause_summary": c.root_cause_summary,
                "verified_engineering_lesson": c.verified_engineering_lesson,
                "prevention_strategy": c.prevention_strategy,
                "confirmed_at": c.confirmed_at.isoformat()
            }
            for c in confirmed_records
        ],
        "historical_failures": [
            {
                "id": str(f.id),
                "incident_id": str(f.incident_id),
                "service_id": str(f.service_id),
                "failure_type": f.failure_type,
                "error_message": f.error_message,
                "pod_name": f.pod_name,
                "exit_code": f.exit_code
            }
            for f in failures
        ]
    }
