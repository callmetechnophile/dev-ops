import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.governance import ApprovalRequest, ApprovalDecision
from app.models.deployment import Deployment
from app.services.state_machine import DeploymentStateMachine, AgentDeploymentState
from app.schemas.approval import ApprovalRequestRead, ApprovalDecisionCreate, ApprovalDecisionRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/approvals", tags=["Approvals & Governance"])


@router.get("", response_model=PaginatedResponse[ApprovalRequestRead])
async def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.decisions))
        .order_by(ApprovalRequest.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    requests = result.scalars().all()

    items = [
        ApprovalRequestRead(
            id=str(r.id),
            tenant_id=str(r.tenant_id),
            deployment_id=str(r.deployment_id),
            recommendation_id=str(r.recommendation_id) if r.recommendation_id else None,
            requested_action=r.requested_action,
            status=r.status,
            expires_at=r.expires_at,
            context_data=r.context_data or {},
            created_at=r.created_at,
            decisions=[
                ApprovalDecisionRead(
                    id=str(d.id),
                    approval_request_id=str(d.approval_request_id),
                    decided_by_user_id=str(d.decided_by_user_id),
                    decision=d.decision,
                    justification=d.justification,
                    audit_signature=d.audit_signature,
                    decided_at=d.decided_at
                )
                for d in r.decisions
            ]
        )
        for r in requests
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size
    )


@router.post("/{id}", response_model=ApprovalDecisionRead)
async def submit_approval_decision(
    id: str,
    payload: ApprovalDecisionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits human approval decision (APPROVED / REJECTED) with cryptographic audit trail.
    Enforces that production deployment interventions cannot happen without signed human sign-off.
    """
    try:
        req_uuid = uuid.UUID(id)
        user_uuid = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID supplied for request or user")

    stmt = select(ApprovalRequest).where(ApprovalRequest.id == req_uuid)
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()

    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if req.status != "WAITING_FOR_APPROVAL":
        raise HTTPException(
            status_code=409,
            detail=f"Approval request is already resolved with status: {req.status}"
        )

    decision_clean = payload.decision.upper()
    if decision_clean not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="Decision must be either 'APPROVED' or 'REJECTED'")

    # Validate state transition
    target_state = AgentDeploymentState.APPROVED if decision_clean == "APPROVED" else AgentDeploymentState.REJECTED
    DeploymentStateMachine.validate_transition(AgentDeploymentState.WAITING_FOR_APPROVAL, target_state)

    # Compute audit signature
    now = datetime.now(timezone.utc)
    raw_signature_body = f"{req.id}:{user_uuid}:{decision_clean}:{payload.justification}:{now.isoformat()}"
    audit_signature = hashlib.sha256(raw_signature_body.encode("utf-8")).hexdigest()

    decision_record = ApprovalDecision(
        id=uuid.uuid4(),
        tenant_id=req.tenant_id,
        approval_request_id=req.id,
        decided_by_user_id=user_uuid,
        decision=decision_clean,
        justification=payload.justification,
        audit_signature=audit_signature,
        decided_at=now
    )
    db.add(decision_record)

    # Update request and deployment status
    req.status = decision_clean

    dep_stmt = select(Deployment).where(Deployment.id == req.deployment_id)
    dep_res = await db.execute(dep_stmt)
    deployment = dep_res.scalar_one_or_none()
    if deployment:
        deployment.status = decision_clean

    await db.flush()

    return ApprovalDecisionRead(
        id=str(decision_record.id),
        approval_request_id=str(decision_record.approval_request_id),
        decided_by_user_id=str(decision_record.decided_by_user_id),
        decision=decision_record.decision,
        justification=decision_record.justification,
        audit_signature=decision_record.audit_signature,
        decided_at=decision_record.decided_at
    )
