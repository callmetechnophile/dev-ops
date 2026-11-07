import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.deployment import Deployment
from app.models.intelligence import RiskAssessment, Recommendation
from app.schemas.deployment import DeploymentRead, DeploymentCreate
from app.schemas.risk import RiskAssessmentRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.get("", response_model=PaginatedResponse[DeploymentRead])
async def list_deployments(
    service_id: Optional[str] = None,
    environment: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Deployment)
    if service_id:
        stmt = stmt.where(Deployment.service_id == uuid.UUID(service_id))
    if environment:
        stmt = stmt.where(Deployment.environment == environment)
    if status_filter:
        stmt = stmt.where(Deployment.status == status_filter)

    stmt = stmt.order_by(Deployment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    deployments = result.scalars().all()

    items = [
        DeploymentRead(
            id=str(d.id),
            tenant_id=str(d.tenant_id),
            service_id=str(d.service_id),
            build_id=str(d.build_id) if d.build_id else None,
            environment=d.environment,
            commit_sha=d.commit_sha,
            status=d.status,
            triggered_by=d.triggered_by,
            started_at=d.started_at,
            finished_at=d.finished_at,
            duration_seconds=d.duration_seconds,
            created_at=d.created_at,
            metadata_json=d.metadata_json or {}
        )
        for d in deployments
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size
    )


@router.get("/{id}", response_model=DeploymentRead)
async def get_deployment(id: str, db: AsyncSession = Depends(get_db)):
    try:
        dep_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID")

    stmt = select(Deployment).where(Deployment.id == dep_uuid)
    result = await db.execute(stmt)
    d = result.scalar_one_or_none()

    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return DeploymentRead(
        id=str(d.id),
        tenant_id=str(d.tenant_id),
        service_id=str(d.service_id),
        build_id=str(d.build_id) if d.build_id else None,
        environment=d.environment,
        commit_sha=d.commit_sha,
        status=d.status,
        triggered_by=d.triggered_by,
        started_at=d.started_at,
        finished_at=d.finished_at,
        duration_seconds=d.duration_seconds,
        created_at=d.created_at,
        metadata_json=d.metadata_json or {}
    )


@router.get("/{id}/risk", response_model=RiskAssessmentRead)
async def get_deployment_risk(id: str, db: AsyncSession = Depends(get_db)):
    try:
        dep_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID")

    stmt = (
        select(RiskAssessment)
        .where(RiskAssessment.deployment_id == dep_uuid)
        .options(selectinload(RiskAssessment.recommendations))
        .order_by(RiskAssessment.created_at.desc())
    )
    result = await db.execute(stmt)
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="No risk assessment generated for this deployment yet")

    return RiskAssessmentRead(
        id=str(assessment.id),
        deployment_id=str(assessment.deployment_id),
        service_id=str(assessment.service_id),
        overall_risk_score=assessment.overall_risk_score,
        risk_level=assessment.risk_level,
        failure_probability=assessment.failure_probability,
        operational_impact_score=assessment.operational_impact_score,
        rule_score=assessment.rule_score,
        ml_score=assessment.ml_score,
        triggered_rules=assessment.triggered_rules or [],
        supporting_records=assessment.supporting_records or [],
        evaluated_at=assessment.evaluated_at,
        recommendations=[
            {
                "id": str(r.id),
                "risk_assessment_id": str(r.risk_assessment_id),
                "deployment_id": str(r.deployment_id),
                "recommendation_type": r.recommendation_type,
                "title": r.title,
                "rationale": r.rationale,
                "mitigation_steps": r.mitigation_steps or [],
                "confidence_score": r.confidence_score,
                "requires_approval": r.requires_approval
            }
            for r in assessment.recommendations
        ]
    )
