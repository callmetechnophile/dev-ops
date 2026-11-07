import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.service import Service, ServiceDependency
from app.schemas.service import ServiceRead, ServiceDependencyRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=PaginatedResponse[ServiceRead])
async def list_services(
    tier: Optional[str] = None,
    health_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Service)
    if tier:
        stmt = stmt.where(Service.tier == tier)
    if health_status:
        stmt = stmt.where(Service.health_status == health_status)

    stmt = stmt.order_by(Service.name.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    services = result.scalars().all()

    items = [
        ServiceRead(
            id=str(s.id),
            tenant_id=str(s.tenant_id),
            repository_id=str(s.repository_id) if s.repository_id else None,
            name=s.name,
            slug=s.slug,
            description=s.description,
            tier=s.tier,
            health_status=s.health_status,
            metadata_json=s.metadata_json or {}
        )
        for s in services
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size
    )


@router.get("/{id}/dependencies", response_model=List[ServiceDependencyRead])
async def get_service_dependencies(id: str, db: AsyncSession = Depends(get_db)):
    try:
        svc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid service UUID")

    stmt = select(ServiceDependency).where(
        (ServiceDependency.source_service_id == svc_uuid) | (ServiceDependency.target_service_id == svc_uuid)
    )
    result = await db.execute(stmt)
    dependencies = result.scalars().all()

    return [
        ServiceDependencyRead(
            id=str(dep.id),
            source_service_id=str(dep.source_service_id),
            target_service_id=str(dep.target_service_id),
            dependency_type=dep.dependency_type,
            criticality=dep.criticality,
            weight=dep.weight
        )
        for dep in dependencies
    ]
