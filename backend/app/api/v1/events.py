import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.event import Event
from app.schemas.event import NormalizedEventContract
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/events", tags=["Events Ledger"])


@router.get("", response_model=PaginatedResponse[NormalizedEventContract])
async def list_events(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    repository_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Event).order_by(Event.occurred_at.desc())
    if source:
        stmt = stmt.where(Event.source == source)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    if repository_id:
        stmt = stmt.where(Event.repository_id == uuid.UUID(repository_id))

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    events = result.scalars().all()

    items = [
        NormalizedEventContract(
            event_id=e.event_id,
            tenant_id=str(e.tenant_id),
            source=e.source,
            event_type=e.event_type,
            schema_version=e.schema_version,
            repository_id=str(e.repository_id) if e.repository_id else None,
            service_id=str(e.service_id) if e.service_id else None,
            deployment_id=str(e.deployment_id) if e.deployment_id else None,
            commit_sha=e.commit_sha,
            environment=e.environment,
            occurred_at=e.occurred_at,
            received_at=e.received_at,
            correlation_id=e.correlation_id,
            idempotency_key=e.idempotency_key,
            payload=e.payload or {},
        )
        for e in events
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )
