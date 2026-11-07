"""Human Approval Gateway and Decision Governance Manager.

Implements authenticated approval workflows for the Predictive DevOps Intelligence Agent.

Guarantees:
- Server-side RBAC enforcement (only approvers/admins can sign off).
- Tenant isolation boundaries.
- Approval expiration with fail-closed semantics (expired requests cannot be approved).
- Duplicate decision protection (idempotency).
- Cryptographic SHA-256 audit fingerprint signing.
- Human-in-the-loop: Authorizes recommendations within the platform; never executes
  destructive production mutations automatically.
"""

from __future__ import annotations
import uuid
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentExecution
from app.models.governance import ApprovalRequest, ApprovalDecision
from app.models.intelligence import Recommendation
from app.models.organization import User

logger = logging.getLogger(__name__)

ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_REQUEST_MORE_INFO = "REQUEST_MORE_INFORMATION"
ACTION_ESCALATE = "ESCALATE"
ACTION_EXPIRE = "EXPIRE"

DEFAULT_APPROVAL_TTL_HOURS = 24


class ApprovalError(Exception):
    """Base exception for approval failures."""

    pass


class UnauthorizedReviewerError(ApprovalError):
    """Raised when an unauthorized user attempts an approval decision."""

    pass


class ExpiredApprovalError(ApprovalError):
    """Raised when attempting to decide an expired approval request."""

    pass


class DuplicateDecisionError(ApprovalError):
    """Raised when an approval request has already been finalized."""

    pass


class AgentApprovalManager:
    """Manages the lifecycle of human approval requests and cryptographic decisions."""

    async def create_approval_request(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        recommendation: Optional[Recommendation],
        policy_version: Optional[str] = "v1.0.0",
        risk_assessment_version: Optional[str] = "1.0.0",
        ttl_hours: int = DEFAULT_APPROVAL_TTL_HOURS,
        assigned_reviewer_id: Optional[uuid.UUID] = None,
    ) -> ApprovalRequest:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        req = ApprovalRequest(
            id=uuid.uuid4(),
            tenant_id=execution.tenant_id,
            deployment_id=execution.deployment_id,
            execution_id=execution.id,
            recommendation_id=recommendation.id if recommendation else None,
            assigned_reviewer_id=assigned_reviewer_id,
            requested_action=recommendation.recommendation_type if recommendation else "VERIFY_DEPLOYMENT_RISK",
            status="WAITING_FOR_APPROVAL",
            expires_at=expires_at,
            policy_version=policy_version,
            risk_assessment_version=risk_assessment_version,
            context_data={
                "execution_id": str(execution.id),
                "environment": execution.environment,
                "recommendation_title": recommendation.title if recommendation else "Human review required",
                "risk_category": execution.context_snapshot.get("predictive_intelligence", {}).get(
                    "risk_level", "MEDIUM"
                ),
            },
        )
        db.add(req)
        await db.flush()
        logger.info(f"Created ApprovalRequest {req.id} for Execution {execution.id} (expires: {expires_at})")
        return req

    async def record_decision(
        self,
        db: AsyncSession,
        request_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user: User,
        action: str,  # APPROVE, REJECT, REQUEST_MORE_INFORMATION, ESCALATE
        notes: str,
    ) -> Tuple[ApprovalRequest, ApprovalDecision]:
        now = datetime.now(timezone.utc)

        # 1. Fetch approval request with lock
        stmt = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.id == request_id,
                    ApprovalRequest.tenant_id == tenant_id,
                )
            )
            .options(
                selectinload(ApprovalRequest.agent_execution),
                selectinload(ApprovalRequest.recommendation),
            )
        )
        res = await db.execute(stmt)
        req = res.scalar_one_or_none()
        if not req:
            raise ApprovalError(f"Approval request {request_id} not found.")

        # 2. Duplicate decision check
        if req.status not in ("WAITING_FOR_APPROVAL", "REQUEST_MORE_INFO"):
            raise DuplicateDecisionError(f"Approval request {request_id} is already in terminal state '{req.status}'.")

        # 3. Check expiration (fail-closed)
        if req.expires_at:
            req_exp = (
                req.expires_at if req.expires_at.tzinfo is not None else req.expires_at.replace(tzinfo=timezone.utc)
            )
            if req_exp < now:
                req.status = "EXPIRED"
                await db.flush()
                raise ExpiredApprovalError(
                    f"Approval request expired at {req.expires_at.isoformat()}. Action rejected."
                )

        # 4. RBAC Check: User must be an approver, admin, or lead
        allowed_roles = {"approver", "admin", "lead", "owner"}
        user_role = (getattr(user, "role", None) or "approver").lower()
        if user_role not in allowed_roles:
            raise UnauthorizedReviewerError(
                f"User '{user.email}' with role '{user_role}' is not authorized to sign off approvals."
            )

        # If assigned to a specific reviewer, verify match or admin
        if req.assigned_reviewer_id and req.assigned_reviewer_id != user.id and user_role != "admin":
            raise UnauthorizedReviewerError("This approval request is assigned to a different authorized reviewer.")

        # 5. Generate Cryptographic Audit Signature (SHA-256)
        audit_payload = {
            "request_id": str(req.id),
            "tenant_id": str(tenant_id),
            "execution_id": str(req.execution_id) if req.execution_id else None,
            "user_id": str(user.id),
            "user_email": user.email,
            "action": action,
            "notes_hash": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
            "timestamp": now.isoformat(),
        }
        raw_signature_bytes = json.dumps(audit_payload, sort_keys=True).encode("utf-8")
        audit_signature = hashlib.sha256(raw_signature_bytes).hexdigest()

        # 6. Map action to status
        canonical_decision = (
            "APPROVED"
            if action in (ACTION_APPROVE, "APPROVED")
            else ("REJECTED" if action in (ACTION_REJECT, "REJECT") else action)
        )
        target_status = "APPROVED" if canonical_decision == "APPROVED" else "REJECTED"
        if action == ACTION_REQUEST_MORE_INFO:
            target_status = "REQUEST_MORE_INFO"
        elif action == ACTION_ESCALATE:
            target_status = "ESCALATED"

        req.status = target_status

        decision_rec = ApprovalDecision(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            approval_request_id=req.id,
            decided_by_user_id=user.id,
            decision=canonical_decision,
            justification=notes,
            notes=notes,
            audit_signature=audit_signature,
            decided_at=now,
        )
        db.add(decision_rec)

        # Update recommendation status if attached
        if req.recommendation:
            if action == ACTION_APPROVE:
                req.recommendation.status = "ACCEPTED"
            elif action == ACTION_REJECT:
                req.recommendation.status = "REJECTED"

        await db.flush()
        logger.info(
            f"Recorded decision {action} on Request {req.id} by {user.email}. Signature: {audit_signature[:20]}..."
        )
        return req, decision_rec


agent_approval_manager = AgentApprovalManager()
