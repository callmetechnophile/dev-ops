import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.intelligence import RiskAssessment, Recommendation
from app.models.model_registry import ModelVersion
from app.models.deployment import Deployment
from app.models.service import Service
from app.models.incident import Incident
from app.schemas.common import PaginatedResponse
from app.services.risk_assessment_service import risk_assessment_service, UnifiedRiskAssessmentResult
from app.services.impact_assessment import blast_radius_service, ImpactAssessment
from app.services.ml_pipeline import (
    ml_pipeline_service,
    ModelEligibilityStatus,
    ModelEvaluationMetrics,
    NUMERIC_FEATURE_KEYS,
)
from app.services.feature_engineering import FEATURE_SCHEMA_VERSION

router = APIRouter(prefix="/risk", tags=["Predictive Deployment Risk"])

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> uuid.UUID:
    if x_tenant_id:
        try:
            return uuid.UUID(x_tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


class CreateRiskAssessmentRequest(BaseModel):
    deployment_id: str


class RiskAssessmentSummary(BaseModel):
    id: str
    deployment_id: str
    service_id: str
    repository_id: Optional[str] = None
    environment: str
    overall_risk_score: float
    risk_level: str
    risk_category: str
    failure_probability: Optional[float] = None
    operational_impact_score: float
    impact_category: str
    rule_score: float
    ml_score: Optional[float] = None
    model_version: Optional[str] = None
    triggered_rules: List[Dict[str, Any]] = []
    affected_services: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    assessed_at: datetime


@router.post("/assessments", response_model=UnifiedRiskAssessmentResult)
async def create_risk_assessment(
    req: CreateRiskAssessmentRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Executes pre-deployment risk assessment evaluating code changes, rules, blast radius, and ML."""
    try:
        dep_uuid = uuid.UUID(req.deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID")

    try:
        result = await risk_assessment_service.assess_deployment(
            db=db,
            tenant_id=tenant_id,
            deployment_id=dep_uuid,
        )
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {str(e)}")


@router.get("/assessments", response_model=PaginatedResponse[RiskAssessmentSummary])
async def list_risk_assessments(
    service_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    environment: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RiskAssessment)
        .where(RiskAssessment.tenant_id == tenant_id)
        .options(selectinload(RiskAssessment.recommendations))
    )
    if service_id:
        stmt = stmt.where(RiskAssessment.service_id == uuid.UUID(service_id))
    if risk_level:
        stmt = stmt.where(RiskAssessment.risk_level == risk_level)
    if environment:
        stmt = stmt.where(RiskAssessment.environment == environment)

    stmt = stmt.order_by(desc(RiskAssessment.evaluated_at)).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    records = res.scalars().all()

    items = [
        RiskAssessmentSummary(
            id=str(r.id),
            deployment_id=str(r.deployment_id),
            service_id=str(r.service_id),
            repository_id=str(r.repository_id) if r.repository_id else None,
            environment=r.environment or "production",
            overall_risk_score=r.overall_risk_score,
            risk_level=r.risk_level,
            risk_category=r.risk_category or r.risk_level,
            failure_probability=r.failure_probability,
            operational_impact_score=r.operational_impact_score,
            impact_category=r.impact_category or "LOW",
            rule_score=r.rule_score,
            ml_score=r.ml_score,
            model_version=r.model_version,
            triggered_rules=r.triggered_rules or [],
            affected_services=r.affected_services or [],
            recommendations=[
                {
                    "recommendation_type": rec.recommendation_type,
                    "title": rec.title,
                    "rationale": rec.rationale,
                    "confidence_score": rec.confidence_score,
                    "requires_approval": rec.requires_approval,
                }
                for rec in r.recommendations
            ],
            assessed_at=r.assessed_at or r.evaluated_at,
        )
        for r in records
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size,
    )


@router.get("/assessments/{id}")
async def get_risk_assessment(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        ra_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid risk assessment UUID")

    stmt = (
        select(RiskAssessment)
        .where(and_(RiskAssessment.id == ra_uuid, RiskAssessment.tenant_id == tenant_id))
        .options(selectinload(RiskAssessment.recommendations))
    )
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Risk assessment not found")

    parsed_explanation = {}
    if r.explanation:
        try:
            parsed_explanation = json.loads(r.explanation)
        except Exception:
            parsed_explanation = {"raw": r.explanation}

    return {
        "id": str(r.id),
        "deployment_id": str(r.deployment_id),
        "service_id": str(r.service_id),
        "repository_id": str(r.repository_id) if r.repository_id else None,
        "environment": r.environment or "production",
        "overall_risk_score": r.overall_risk_score,
        "risk_level": r.risk_level,
        "risk_category": r.risk_category or r.risk_level,
        "failure_probability": r.failure_probability,
        "operational_impact_score": r.operational_impact_score,
        "impact_category": r.impact_category or "LOW",
        "affected_services": r.affected_services or [],
        "rule_score": r.rule_score,
        "ml_score": r.ml_score,
        "model_version": r.model_version,
        "model_status": "ACTIVE" if r.model_version else "INSUFFICIENT_DATA",
        "triggered_rules": r.triggered_rules or [],
        "supporting_incident_ids": r.supporting_incident_ids or [],
        "feature_snapshot": r.feature_snapshot or {},
        "explanation": parsed_explanation,
        "recommendations": [
            {
                "recommendation_type": rec.recommendation_type,
                "title": rec.title,
                "rationale": rec.rationale,
                "confidence_score": rec.confidence_score,
                "requires_approval": rec.requires_approval,
            }
            for rec in r.recommendations
        ],
        "assessed_at": r.assessed_at or r.evaluated_at,
    }


@router.get("/assessments/{id}/explanation")
async def get_assessment_explanation(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        ra_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid risk assessment UUID")

    stmt = select(RiskAssessment).where(and_(RiskAssessment.id == ra_uuid, RiskAssessment.tenant_id == tenant_id))
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Risk assessment not found")

    if r.explanation:
        try:
            return json.loads(r.explanation)
        except Exception:
            return {"explanation": r.explanation}

    return {
        "method": "DETERMINISTIC_RULE_ATTRIBUTION",
        "provenance": "Rule-based baseline",
        "top_risk_increasing_factors": [],
        "top_risk_mitigating_factors": [],
    }


@router.get("/assessments/{id}/similar-incidents")
async def get_assessment_similar_incidents(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        ra_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid risk assessment UUID")

    stmt = select(RiskAssessment).where(and_(RiskAssessment.id == ra_uuid, RiskAssessment.tenant_id == tenant_id))
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Risk assessment not found")

    supporting_ids = r.supporting_incident_ids or []
    if not supporting_ids:
        return []

    inc_stmt = select(Incident).where(
        and_(
            Incident.tenant_id == tenant_id,
            Incident.id.in_([uuid.UUID(i) for i in supporting_ids]),
        )
    )
    inc_res = await db.execute(inc_stmt)
    incidents = inc_res.scalars().all()

    return [
        {
            "id": str(inc.id),
            "incident_key": inc.incident_key,
            "title": inc.title,
            "severity": inc.severity,
            "status": inc.status,
            "incident_type": inc.incident_type,
            "detected_at": inc.detected_at,
        }
        for inc in incidents
    ]


@router.get("/impact/{deployment_id}", response_model=ImpactAssessment)
async def get_deployment_impact(
    deployment_id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        dep_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID")

    stmt = select(Deployment).where(and_(Deployment.id == dep_uuid, Deployment.tenant_id == tenant_id))
    res = await db.execute(stmt)
    dep = res.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")

    impact = await blast_radius_service.calculate_impact(
        db=db,
        tenant_id=tenant_id,
        target_service_id=dep.service_id,
        environment=dep.environment,
    )
    return impact


@router.get("/models/status", response_model=ModelEligibilityStatus)
async def get_model_status(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Returns active model availability, training eligibility, and labeled sample counts."""
    eligibility = await ml_pipeline_service.check_eligibility(db, tenant_id)
    return eligibility


@router.get("/models")
async def list_models(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ModelVersion)
        .where(ModelVersion.tenant_id == tenant_id)
        .order_by(desc(ModelVersion.trained_at))
    )
    res = await db.execute(stmt)
    models = res.scalars().all()

    return [
        {
            "id": str(m.id),
            "model_name": m.model_name,
            "version": m.version,
            "algorithm": m.algorithm,
            "status": m.status,
            "training_dataset_size": m.training_dataset_size,
            "evaluation_metrics": m.evaluation_metrics,
            "is_calibrated": m.is_calibrated,
            "trained_at": m.trained_at,
        }
        for m in models
    ]


@router.get("/models/{version}/evaluation")
async def get_model_evaluation(
    version: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ModelVersion).where(
        and_(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.version == version,
        )
    )
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail=f"Model version '{version}' not found")

    return {
        "version": m.version,
        "algorithm": m.algorithm,
        "status": m.status,
        "training_dataset_size": m.training_dataset_size,
        "evaluation_metrics": m.evaluation_metrics,
        "is_calibrated": m.is_calibrated,
        "trained_at": m.trained_at,
    }


@router.post("/models/train")
async def train_model_endpoint(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Triggers model training if dataset meets minimum quality and size thresholds."""
    mv, metrics, message = await ml_pipeline_service.train_model(db, tenant_id)
    if not mv:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": message,
        }

    await db.commit()
    return {
        "status": "TRAINED",
        "version": mv.version,
        "algorithm": mv.algorithm,
        "evaluation_metrics": metrics.model_dump(),
        "message": message,
    }


@router.get("/features/schema")
async def get_features_schema():
    return {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "features": [
            {"name": k, "type": "float", "description": f"Pre-deployment telemetry metric: {k}"}
            for k in NUMERIC_FEATURE_KEYS
        ],
        "target_leakage_policy": "Strictly excludes deployment completion status, finished_at, and post-deployment incident signals.",
    }
