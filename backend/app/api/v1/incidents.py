import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=PaginatedResponse[IncidentRead])
async def list_incidents(
    service_id: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Incident)
        .options(
            selectinload(Incident.failures),
            selectinload(Incident.hypotheses),
            selectinload(Incident.confirmed_root_cause)
        )
    )
    if service_id:
        stmt = stmt.where(Incident.service_id == uuid.UUID(service_id))
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)

    stmt = stmt.order_by(Incident.detected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    incidents = result.scalars().all()

    items = []
    for inc in incidents:
        items.append(
            IncidentRead(
                id=str(inc.id),
                tenant_id=str(inc.tenant_id),
                service_id=str(inc.service_id),
                deployment_id=str(inc.deployment_id) if inc.deployment_id else None,
                title=inc.title,
                summary=inc.summary,
                severity=inc.severity,
                status=inc.status,
                detected_at=inc.detected_at,
                resolved_at=inc.resolved_at,
                blast_radius_score=inc.blast_radius_score,
                failures=[
                    {
                        "id": str(f.id),
                        "service_id": str(f.service_id),
                        "failure_type": f.failure_type,
                        "error_message": f.error_message,
                        "stack_trace": f.stack_trace,
                        "container_name": f.container_name,
                        "pod_name": f.pod_name,
                        "exit_code": f.exit_code
                    }
                    for f in inc.failures
                ],
                hypotheses=[
                    {
                        "id": str(h.id),
                        "incident_id": str(h.incident_id),
                        "hypothesis_statement": h.hypothesis_statement,
                        "confidence_score": h.confidence_score,
                        "status": h.status,
                        "evidence_summary": h.evidence_summary
                    }
                    for h in inc.hypotheses
                ],
                confirmed_root_cause={
                    "id": str(inc.confirmed_root_cause.id),
                    "incident_id": str(inc.confirmed_root_cause.incident_id),
                    "root_cause_summary": inc.confirmed_root_cause.root_cause_summary,
                    "verified_engineering_lesson": inc.confirmed_root_cause.verified_engineering_lesson,
                    "prevention_strategy": inc.confirmed_root_cause.prevention_strategy,
                    "confirmed_at": inc.confirmed_root_cause.confirmed_at
                } if inc.confirmed_root_cause else None
            )
        )

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size
    )


@router.get("/{id}", response_model=IncidentRead)
async def get_incident(id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    stmt = (
        select(Incident)
        .where(Incident.id == inc_uuid)
        .options(
            selectinload(Incident.failures),
            selectinload(Incident.hypotheses),
            selectinload(Incident.confirmed_root_cause)
        )
    )
    result = await db.execute(stmt)
    inc = result.scalar_one_or_none()

    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    return IncidentRead(
        id=str(inc.id),
        tenant_id=str(inc.tenant_id),
        service_id=str(inc.service_id),
        deployment_id=str(inc.deployment_id) if inc.deployment_id else None,
        title=inc.title,
        summary=inc.summary,
        severity=inc.severity,
        status=inc.status,
        detected_at=inc.detected_at,
        resolved_at=inc.resolved_at,
        blast_radius_score=inc.blast_radius_score,
        failures=[
            {
                "id": str(f.id),
                "service_id": str(f.service_id),
                "failure_type": f.failure_type,
                "error_message": f.error_message,
                "stack_trace": f.stack_trace,
                "container_name": f.container_name,
                "pod_name": f.pod_name,
                "exit_code": f.exit_code
            }
            for f in inc.failures
        ],
        hypotheses=[
            {
                "id": str(h.id),
                "incident_id": str(h.incident_id),
                "hypothesis_statement": h.hypothesis_statement,
                "confidence_score": h.confidence_score,
                "status": h.status,
                "evidence_summary": h.evidence_summary
            }
            for h in inc.hypotheses
        ],
        confirmed_root_cause={
            "id": str(inc.confirmed_root_cause.id),
            "incident_id": str(inc.confirmed_root_cause.incident_id),
            "root_cause_summary": inc.confirmed_root_cause.root_cause_summary,
            "verified_engineering_lesson": inc.confirmed_root_cause.verified_engineering_lesson,
            "prevention_strategy": inc.confirmed_root_cause.prevention_strategy,
            "confirmed_at": inc.confirmed_root_cause.confirmed_at
        } if inc.confirmed_root_cause else None
    )
