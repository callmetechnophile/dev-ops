import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.incident import (
    Incident,
    FailureClassification,
    RootCauseHypothesis,
    ConfirmedRootCause,
    OperationalLesson,
)
from app.models.intelligence import RemediationAction
from app.schemas.incident import (
    IncidentRead,
    FailureClassificationRead,
    RootCauseHypothesisRead,
    ConfirmedRootCauseRead,
    RemediationActionRead,
    IncidentAnalyticsResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.incident_timeline import incident_timeline_service, IncidentTimelineResponse
from app.services.root_cause_engine import root_cause_engine
from app.services.human_verification import (
    human_verification_service,
    ConfirmHypothesisRequest,
    RejectHypothesisRequest,
    InsufficientEvidenceRequest,
    RecordRemediationRequest,
)
from app.services.similarity_retrieval import similarity_retrieval_service, SimilarIncidentMatch
from app.core import metrics

router = APIRouter(prefix="/incidents", tags=["Incidents"])

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> uuid.UUID:
    if x_tenant_id:
        try:
            return uuid.UUID(x_tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


def _map_incident_to_read(inc: Incident) -> IncidentRead:
    return IncidentRead(
        id=str(inc.id),
        tenant_id=str(inc.tenant_id),
        incident_key=inc.incident_key or f"INC-{str(inc.id)[:8].upper()}",
        service_id=str(inc.service_id) if inc.service_id else None,
        primary_service_id=str(inc.primary_service_id) if inc.primary_service_id else None,
        repository_id=str(inc.repository_id) if inc.repository_id else None,
        deployment_id=str(inc.deployment_id) if inc.deployment_id else None,
        title=inc.title,
        summary=inc.summary,
        description=inc.description or inc.summary,
        incident_type=inc.incident_type or "UNKNOWN_FAILURE",
        severity=inc.severity,
        status=inc.status,
        environment=inc.environment or "production",
        first_observed_at=inc.first_observed_at,
        last_observed_at=inc.last_observed_at,
        detected_at=inc.detected_at,
        resolved_at=inc.resolved_at,
        blast_radius_score=inc.blast_radius_score,
        classifications=[
            FailureClassificationRead(
                id=str(fc.id),
                category=fc.category,
                subcategory=fc.subcategory,
                classification_method=fc.classification_method,
                evidence=fc.evidence,
                classifier_version=fc.classifier_version,
                created_at=fc.created_at,
            )
            for fc in (inc.classifications or [])
        ],
        failures=[
            {
                "id": str(f.id),
                "service_id": str(f.service_id),
                "failure_type": f.failure_type,
                "error_message": f.error_message,
                "stack_trace": f.stack_trace,
                "container_name": f.container_name,
                "pod_name": f.pod_name,
                "exit_code": f.exit_code,
            }
            for f in (inc.failures or [])
        ],
        hypotheses=[
            RootCauseHypothesisRead(
                id=str(h.id),
                incident_id=str(h.incident_id),
                hypothesis=h.hypothesis,
                hypothesis_statement=h.hypothesis,
                explanation=h.explanation or "",
                evidence_event_ids=h.evidence_event_ids or [],
                confidence_level=h.confidence_level or "MEDIUM",
                confidence_score=h.confidence_score,
                status=h.status,
                generated_by=h.generated_by or "DETERMINISTIC_STAGE_A",
                evidence_summary=h.evidence_summary,
            )
            for h in (inc.hypotheses or [])
        ],
        confirmed_root_cause=(
            ConfirmedRootCauseRead(
                id=str(inc.confirmed_root_cause.id),
                incident_id=str(inc.confirmed_root_cause.incident_id),
                hypothesis_id=(
                    str(inc.confirmed_root_cause.hypothesis_id) if inc.confirmed_root_cause.hypothesis_id else None
                ),
                confirmed_by=inc.confirmed_root_cause.confirmed_by or "authorized_engineer",
                confirmation_notes=inc.confirmed_root_cause.confirmation_notes or "",
                root_cause_summary=inc.confirmed_root_cause.root_cause_summary,
                verified_engineering_lesson=inc.confirmed_root_cause.verified_engineering_lesson,
                prevention_strategy=inc.confirmed_root_cause.prevention_strategy,
                confirmed_at=inc.confirmed_root_cause.confirmed_at,
            )
            if inc.confirmed_root_cause
            else None
        ),
        remediations=[
            RemediationActionRead(
                id=str(r.id),
                incident_id=str(r.incident_id),
                action_type=r.action_type,
                description=r.description,
                proposed_by=r.proposed_by or "SYSTEM",
                approved_by=r.approved_by,
                execution_status=r.execution_status or "RECORDED",
                outcome=r.outcome,
                effectiveness=r.effectiveness,
                runbook_url=r.runbook_url,
                created_at=r.created_at,
            )
            for r in (inc.remediations or [])
        ],
        lessons=[
            {
                "id": str(l.id),
                "incident_id": str(l.incident_id),
                "title": l.title,
                "lesson": l.lesson,
                "verified_root_cause_id": str(l.verified_root_cause_id),
                "remediation_action_id": str(l.remediation_action_id) if l.remediation_action_id else None,
                "applicability_conditions": l.applicability_conditions or {},
                "verification_status": l.verification_status,
                "created_at": l.created_at,
            }
            for l in (inc.lessons or [])
        ],
    )


@router.get("/analytics", response_model=IncidentAnalyticsResponse)
async def get_incident_analytics(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Calculates comprehensive failure and incident metrics from real stored records."""
    stmt = select(Incident).where(Incident.tenant_id == tenant_id).options(selectinload(Incident.classifications))
    res = await db.execute(stmt)
    incidents = res.scalars().all()

    total = len(incidents)
    open_count = sum(1 for i in incidents if i.status == "OPEN")
    resolved_count = sum(1 for i in incidents if i.status == "RESOLVED")
    p1_count = sum(1 for i in incidents if i.severity == "P1")
    p2_count = sum(1 for i in incidents if i.severity == "P2")

    cat_dist: Dict[str, int] = {}
    env_dist: Dict[str, int] = {}

    for inc in incidents:
        # Category
        cat = inc.incident_type or "UNKNOWN_FAILURE"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
        # Environment
        env = inc.environment or "production"
        env_dist[env] = env_dist.get(env, 0) + 1

    # Recent trend (last 7 days grouped)
    recent_trend = [
        {"day": inc.detected_at.strftime("%b %d"), "count": 1, "severity": inc.severity}
        for inc in sorted(incidents, key=lambda x: x.detected_at)[-10:]
    ]

    return IncidentAnalyticsResponse(
        total_incidents=total,
        open_incidents=open_count,
        resolved_incidents=resolved_count,
        p1_count=p1_count,
        p2_count=p2_count,
        category_distribution=cat_dist,
        environment_distribution=env_dist,
        recent_trend=recent_trend,
    )


@router.get("", response_model=PaginatedResponse[IncidentRead])
async def list_incidents(
    service_id: Optional[str] = None,
    repository_id: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    environment: Optional[str] = None,
    incident_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Incident)
        .where(Incident.tenant_id == tenant_id)
        .options(
            selectinload(Incident.failures),
            selectinload(Incident.classifications),
            selectinload(Incident.hypotheses),
            selectinload(Incident.confirmed_root_cause),
            selectinload(Incident.remediations),
            selectinload(Incident.lessons),
        )
    )
    if service_id:
        stmt = stmt.where(Incident.service_id == uuid.UUID(service_id))
    if repository_id:
        stmt = stmt.where(Incident.repository_id == uuid.UUID(repository_id))
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)
    if environment:
        stmt = stmt.where(Incident.environment == environment)
    if incident_type:
        stmt = stmt.where(Incident.incident_type == incident_type)

    stmt = stmt.order_by(Incident.detected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    incidents = result.scalars().all()

    items = [_map_incident_to_read(inc) for inc in incidents]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size,
    )


@router.get("/{id}", response_model=IncidentRead)
async def get_incident(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    stmt = (
        select(Incident)
        .where(and_(Incident.id == inc_uuid, Incident.tenant_id == tenant_id))
        .options(
            selectinload(Incident.failures),
            selectinload(Incident.classifications),
            selectinload(Incident.hypotheses),
            selectinload(Incident.confirmed_root_cause),
            selectinload(Incident.remediations),
            selectinload(Incident.lessons),
        )
    )
    result = await db.execute(stmt)
    inc = result.scalar_one_or_none()

    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    return _map_incident_to_read(inc)


@router.get("/{id}/timeline", response_model=IncidentTimelineResponse)
async def get_incident_timeline(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    timeline = await incident_timeline_service.get_incident_timeline(db, tenant_id, inc_uuid)
    if not timeline:
        raise HTTPException(status_code=404, detail="Incident not found")

    return timeline


@router.get("/{id}/classifications", response_model=List[FailureClassificationRead])
async def get_incident_classifications(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    stmt = select(FailureClassification).where(
        and_(
            FailureClassification.incident_id == inc_uuid,
            FailureClassification.tenant_id == tenant_id,
        )
    )
    res = await db.execute(stmt)
    classifications = res.scalars().all()
    return [
        FailureClassificationRead(
            id=str(fc.id),
            category=fc.category,
            subcategory=fc.subcategory,
            classification_method=fc.classification_method,
            evidence=fc.evidence,
            classifier_version=fc.classifier_version,
            created_at=fc.created_at,
        )
        for fc in classifications
    ]


@router.get("/{id}/hypotheses", response_model=List[RootCauseHypothesisRead])
async def get_or_generate_hypotheses(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    # Generate or retrieve
    hypotheses = await root_cause_engine.analyze_incident(db, tenant_id, inc_uuid)
    return [
        RootCauseHypothesisRead(
            id=str(h.id),
            incident_id=str(h.incident_id),
            hypothesis=h.hypothesis,
            hypothesis_statement=h.hypothesis,
            explanation=h.explanation or "",
            evidence_event_ids=h.evidence_event_ids or [],
            confidence_level=h.confidence_level or "MEDIUM",
            confidence_score=h.confidence_score,
            status=h.status,
            generated_by=h.generated_by or "DETERMINISTIC_STAGE_A",
            evidence_summary=h.evidence_summary,
        )
        for h in hypotheses
    ]


@router.post("/{id}/hypotheses/{hypothesis_id}/confirm", response_model=ConfirmedRootCauseRead)
async def confirm_hypothesis(
    id: str,
    hypothesis_id: str,
    req: ConfirmHypothesisRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
        hyp_uuid = uuid.UUID(hypothesis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    try:
        crc = await human_verification_service.confirm_hypothesis(
            db=db,
            tenant_id=tenant_id,
            incident_id=inc_uuid,
            hypothesis_id=hyp_uuid,
            req=req,
        )
        await db.commit()
        metrics.root_cause_hypotheses_confirmed_total.inc()
        return ConfirmedRootCauseRead(
            id=str(crc.id),
            incident_id=str(crc.incident_id),
            hypothesis_id=str(crc.hypothesis_id) if crc.hypothesis_id else None,
            confirmed_by=crc.confirmed_by,
            confirmation_notes=crc.confirmation_notes or "",
            root_cause_summary=crc.root_cause_summary,
            verified_engineering_lesson=crc.verified_engineering_lesson,
            prevention_strategy=crc.prevention_strategy,
            confirmed_at=crc.confirmed_at,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/hypotheses/{hypothesis_id}/reject", response_model=RootCauseHypothesisRead)
async def reject_hypothesis(
    id: str,
    hypothesis_id: str,
    req: RejectHypothesisRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
        hyp_uuid = uuid.UUID(hypothesis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    try:
        hyp = await human_verification_service.reject_hypothesis(
            db=db,
            tenant_id=tenant_id,
            incident_id=inc_uuid,
            hypothesis_id=hyp_uuid,
            req=req,
        )
        await db.commit()
        metrics.root_cause_hypotheses_rejected_total.inc()
        return RootCauseHypothesisRead(
            id=str(hyp.id),
            incident_id=str(hyp.incident_id),
            hypothesis=hyp.hypothesis,
            hypothesis_statement=hyp.hypothesis,
            explanation=hyp.explanation,
            evidence_event_ids=hyp.evidence_event_ids or [],
            confidence_level=hyp.confidence_level,
            confidence_score=hyp.confidence_score,
            status=hyp.status,
            generated_by=hyp.generated_by,
            evidence_summary=hyp.evidence_summary,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/hypotheses/{hypothesis_id}/insufficient-evidence", response_model=RootCauseHypothesisRead)
async def mark_insufficient_evidence(
    id: str,
    hypothesis_id: str,
    req: InsufficientEvidenceRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
        hyp_uuid = uuid.UUID(hypothesis_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    try:
        hyp = await human_verification_service.mark_insufficient_evidence(
            db=db,
            tenant_id=tenant_id,
            incident_id=inc_uuid,
            hypothesis_id=hyp_uuid,
            req=req,
        )
        await db.commit()
        return RootCauseHypothesisRead(
            id=str(hyp.id),
            incident_id=str(hyp.incident_id),
            hypothesis=hyp.hypothesis,
            hypothesis_statement=hyp.hypothesis,
            explanation=hyp.explanation,
            evidence_event_ids=hyp.evidence_event_ids or [],
            confidence_level=hyp.confidence_level,
            confidence_score=hyp.confidence_score,
            status=hyp.status,
            generated_by=hyp.generated_by,
            evidence_summary=hyp.evidence_summary,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}/remediations", response_model=List[RemediationActionRead])
async def list_incident_remediations(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    stmt = (
        select(RemediationAction)
        .where(
            and_(
                RemediationAction.incident_id == inc_uuid,
                RemediationAction.tenant_id == tenant_id,
            )
        )
        .order_by(RemediationAction.created_at.desc())
    )
    res = await db.execute(stmt)
    rems = res.scalars().all()
    return [
        RemediationActionRead(
            id=str(r.id),
            incident_id=str(r.incident_id),
            action_type=r.action_type,
            description=r.description,
            proposed_by=r.proposed_by or "SYSTEM",
            approved_by=r.approved_by,
            execution_status=r.execution_status or "RECORDED",
            outcome=r.outcome,
            effectiveness=r.effectiveness,
            runbook_url=r.runbook_url,
            created_at=r.created_at,
        )
        for r in rems
    ]


@router.post("/{id}/remediations", response_model=RemediationActionRead)
async def record_incident_remediation(
    id: str,
    req: RecordRemediationRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    try:
        action = await human_verification_service.record_remediation(
            db=db,
            tenant_id=tenant_id,
            incident_id=inc_uuid,
            req=req,
        )
        await db.commit()
        return RemediationActionRead(
            id=str(action.id),
            incident_id=str(action.incident_id),
            action_type=action.action_type,
            description=action.description,
            proposed_by=action.proposed_by,
            approved_by=action.approved_by,
            execution_status=action.execution_status,
            outcome=action.outcome,
            effectiveness=action.effectiveness,
            runbook_url=action.runbook_url,
            created_at=action.created_at,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{id}/similar", response_model=List[SimilarIncidentMatch])
async def get_similar_incidents(
    id: str,
    limit: int = Query(5, ge=1, le=20),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inc_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident UUID")

    matches = await similarity_retrieval_service.find_similar_incidents(
        db=db,
        tenant_id=tenant_id,
        incident_id=inc_uuid,
        limit=limit,
    )
    return matches
