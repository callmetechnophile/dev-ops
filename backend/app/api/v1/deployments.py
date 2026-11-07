import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.deployment import Deployment, Commit
from app.models.github_entities import WorkflowRun, DeploymentEvent, PullRequest
from app.models.governance import ApprovalRequest, ApprovalDecision
from app.models.intelligence import RiskAssessment, Recommendation
from app.schemas.deployment import (
    DeploymentRead,
    DeploymentCreate,
    DeploymentTimelineRead,
    DeploymentTimelineItem,
)
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
            workflow_run_id=str(d.workflow_run_id) if d.workflow_run_id else None,
            github_deployment_id=d.github_deployment_id,
            environment=d.environment,
            commit_sha=d.commit_sha,
            status=d.status,
            triggered_by=d.triggered_by,
            creator_login=d.creator_login,
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
        workflow_run_id=str(d.workflow_run_id) if d.workflow_run_id else None,
        github_deployment_id=d.github_deployment_id,
        environment=d.environment,
        commit_sha=d.commit_sha,
        status=d.status,
        triggered_by=d.triggered_by,
        creator_login=d.creator_login,
        started_at=d.started_at,
        finished_at=d.finished_at,
        duration_seconds=d.duration_seconds,
        created_at=d.created_at,
        metadata_json=d.metadata_json or {}
    )


@router.get("/{id}/timeline", response_model=DeploymentTimelineRead)
async def get_deployment_timeline(id: str, db: AsyncSession = Depends(get_db)):
    """
    Constructs a deterministic chronological timeline for a deployment:
    Commit -> Pull Request -> CI Workflow Runs -> Approvals -> Deployment Events.
    Section 8 of Specification.
    """
    try:
        dep_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID")

    stmt = select(Deployment).where(Deployment.id == dep_uuid).options(selectinload(Deployment.events))
    result = await db.execute(stmt)
    d = result.scalar_one_or_none()

    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")

    timeline_items: List[DeploymentTimelineItem] = []

    # 1. Correlated Commit
    c_stmt = select(Commit).where(
        and_(
            Commit.tenant_id == d.tenant_id,
            Commit.commit_sha == d.commit_sha
        )
    )
    c_res = await db.execute(c_stmt)
    commit = c_res.scalar_one_or_none()
    if commit:
        timeline_items.append(
            DeploymentTimelineItem(
                step_type="commit",
                title=f"Commit created: {commit.commit_sha[:7]}",
                description=commit.message,
                status="committed",
                timestamp=commit.committed_at,
                actor=commit.author_login or commit.author_name,
                reference_id=commit.commit_sha,
                metadata={"additions": commit.stats_additions, "deletions": commit.stats_deletions}
            )
        )

        # 2. Correlated Pull Request
        pr_stmt = select(PullRequest).where(
            and_(
                PullRequest.tenant_id == d.tenant_id,
                PullRequest.head_sha == commit.commit_sha
            )
        )
        pr_res = await db.execute(pr_stmt)
        pr = pr_res.scalar_one_or_none()
        if pr and pr.is_merged and pr.merged_at:
            timeline_items.append(
                DeploymentTimelineItem(
                    step_type="pr_merged",
                    title=f"Pull Request #{pr.number} Merged: {pr.title}",
                    description=f"Merged {pr.head_branch} into {pr.base_branch}",
                    status="merged",
                    timestamp=pr.merged_at,
                    actor=pr.author_login,
                    reference_id=str(pr.number)
                )
            )

    # 3. Correlated Workflow Runs
    w_stmt = select(WorkflowRun).where(
        and_(
            WorkflowRun.tenant_id == d.tenant_id,
            WorkflowRun.head_sha == d.commit_sha
        )
    ).order_by(WorkflowRun.started_at.asc())
    w_res = await db.execute(w_stmt)
    workflows = w_res.scalars().all()
    for w in workflows:
        timeline_items.append(
            DeploymentTimelineItem(
                step_type="workflow_run",
                title=f"GitHub Actions: {w.name} (#{w.run_number})",
                description=f"Event: {w.event} &middot; Conclusion: {w.conclusion or 'running'}",
                status=w.conclusion or w.status,
                timestamp=w.started_at,
                actor=w.actor_login,
                reference_id=w.github_run_id,
                metadata={"duration_seconds": w.duration_seconds}
            )
        )

    # 4. Approvals
    app_stmt = select(ApprovalRequest).where(
        ApprovalRequest.deployment_id == d.id
    ).options(selectinload(ApprovalRequest.decisions))
    app_res = await db.execute(app_stmt)
    app_requests = app_res.scalars().all()
    for ar in app_requests:
        for dec in ar.decisions:
            timeline_items.append(
                DeploymentTimelineItem(
                    step_type="approval",
                    title=f"Human Gate Decision: {dec.decision}",
                    description=dec.justification,
                    status=dec.decision,
                    timestamp=dec.decided_at,
                    reference_id=str(dec.id),
                    metadata={"audit_signature": dec.audit_signature}
                )
            )

    # 5. Discrete Deployment Events
    for de in d.events:
        timeline_items.append(
            DeploymentTimelineItem(
                step_type="deployment_event",
                title=f"Deployment state changed to {de.status.upper()}",
                description=de.description or f"Target environment: {de.environment}",
                status=de.status,
                timestamp=de.occurred_at,
                actor=de.creator_login,
                reference_id=de.github_deployment_status_id or de.github_deployment_id
            )
        )

    # Sort chronological
    timeline_items.sort(key=lambda x: x.timestamp)

    return DeploymentTimelineRead(
        deployment_id=str(d.id),
        environment=d.environment,
        commit_sha=d.commit_sha,
        current_status=d.status,
        timeline=timeline_items
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
