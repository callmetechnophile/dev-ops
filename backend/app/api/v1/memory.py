import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.incident import Incident, ConfirmedRootCause, Failure, OperationalLesson
from app.schemas.incident import ConfirmedRootCauseRead, OperationalLessonRead
from app.schemas.common import PaginatedResponse
from app.services.memory_service import operational_memory_service, MemorySearchResult
from app.core import metrics

router = APIRouter(prefix="/memory", tags=["Operational Memory"])

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> uuid.UUID:
    if x_tenant_id:
        try:
            return uuid.UUID(x_tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=2, description="Search query for failure memory or root causes"),
    category: Optional[str] = None,
    environment: Optional[str] = None,
    verified_only: bool = Query(True, description="Filter for human-verified lessons and confirmed causes only"),
    limit: int = Query(10, ge=1, le=50),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves historical operational memory: verified lessons, confirmed root causes,
    and matching failure patterns across previous deployment cycles.
    """
    metrics.semantic_search_requests_total.inc()
    results = await operational_memory_service.search_memory(
        db=db,
        tenant_id=tenant_id,
        query=q,
        category=category,
        environment=environment,
        verified_only=verified_only,
        limit=limit,
    )

    # Legacy compatibility fields for existing test assertions
    confirmed_records = [r for r in results if r.record_type in ("confirmed_root_cause", "operational_lesson")]
    failures_like = [r for r in results if r.record_type == "incident"]

    return {
        "query": q,
        "total_matches": len(results),
        "results": [r.model_dump() for r in results],
        "verified_lessons": [
            {
                "id": r.id,
                "incident_id": r.incident_id,
                "root_cause_summary": r.title,
                "verified_engineering_lesson": r.summary,
                "prevention_strategy": r.metadata.get("prevention_strategy", "Follow verified runbook"),
                "confirmed_at": r.created_at.isoformat(),
            }
            for r in confirmed_records
        ],
        "historical_failures": [
            {
                "id": r.id,
                "service_id": r.metadata.get("service_id", "default-service"),
                "failure_type": r.metadata.get("incident_type", "UNKNOWN"),
                "error_message": r.summary,
            }
            for r in failures_like
        ],
    }


@router.get("/lessons", response_model=PaginatedResponse[OperationalLessonRead])
async def list_operational_lessons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(OperationalLesson)
        .where(
            and_(
                OperationalLesson.tenant_id == tenant_id,
                OperationalLesson.verification_status == "VERIFIED",
            )
        )
        .order_by(desc(OperationalLesson.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    lessons = res.scalars().all()

    items = [
        OperationalLessonRead(
            id=str(l.id),
            incident_id=str(l.incident_id),
            title=l.title,
            lesson=l.lesson,
            verified_root_cause_id=str(l.verified_root_cause_id),
            remediation_action_id=str(l.remediation_action_id) if l.remediation_action_id else None,
            applicability_conditions=l.applicability_conditions or {},
            verification_status=l.verification_status,
            created_at=l.created_at,
        )
        for l in lessons
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size,
    )


@router.get("/lessons/{lesson_id}", response_model=OperationalLessonRead)
async def get_operational_lesson(
    lesson_id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        l_uuid = uuid.UUID(lesson_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lesson UUID")

    stmt = select(OperationalLesson).where(
        and_(
            OperationalLesson.id == l_uuid,
            OperationalLesson.tenant_id == tenant_id,
        )
    )
    res = await db.execute(stmt)
    lesson = res.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Operational lesson not found")

    return OperationalLessonRead(
        id=str(lesson.id),
        incident_id=str(lesson.incident_id),
        title=lesson.title,
        lesson=lesson.lesson,
        verified_root_cause_id=str(lesson.verified_root_cause_id),
        remediation_action_id=str(lesson.remediation_action_id) if lesson.remediation_action_id else None,
        applicability_conditions=lesson.applicability_conditions or {},
        verification_status=lesson.verification_status,
        created_at=lesson.created_at,
    )
