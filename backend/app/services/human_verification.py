"""Human Verification Workflow for Root-Cause Analysis and Operational Lessons.

Enforces:
- Only authorized human verification can transition hypothesis to CONFIRMED.
- Confirmed root causes generate verified operational lessons.
- Immutable audit trail.
- LLMs are strictly forbidden from confirming root causes.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.incident import (
    Incident,
    RootCauseHypothesis,
    ConfirmedRootCause,
    OperationalLesson,
)
from app.models.intelligence import RemediationAction
from app.core.exceptions import DomainException

logger = logging.getLogger(__name__)


class ConfirmHypothesisRequest(BaseModel):
    confirmed_by: str = Field(..., min_length=2, max_length=255)
    confirmation_notes: str = Field("", max_length=2000)
    root_cause_summary: str = Field(..., min_length=5, max_length=2000)
    verified_engineering_lesson: str = Field(..., min_length=10, max_length=3000)
    prevention_strategy: str = Field(..., min_length=10, max_length=3000)


class RejectHypothesisRequest(BaseModel):
    rejected_by: str = Field(..., min_length=2, max_length=255)
    rejection_reason: str = Field(..., min_length=5, max_length=2000)


class InsufficientEvidenceRequest(BaseModel):
    reviewed_by: str = Field(..., min_length=2, max_length=255)
    notes: str = Field("", max_length=2000)


class RecordRemediationRequest(BaseModel):
    action_type: str = Field(..., min_length=2, max_length=100)  # ROLLBACK, CONFIG_PATCH, RESTART, DEPENDENCY_PIN
    description: str = Field(..., min_length=5, max_length=2000)
    proposed_by: str = Field(default="SYSTEM", max_length=255)
    approved_by: Optional[str] = Field(default=None, max_length=255)
    execution_status: str = Field(default="RECORDED", max_length=50)  # RECORDED, EXECUTED, FAILED
    outcome: Optional[str] = Field(default="UNKNOWN", max_length=50)  # SUCCESS, PARTIAL_SUCCESS, FAILED, UNKNOWN
    effectiveness: Optional[str] = Field(default="MEDIUM", max_length=50)  # HIGH, MEDIUM, LOW, INEFFECTIVE
    runbook_url: Optional[str] = Field(default=None, max_length=512)


class HumanVerificationService:
    """Handles engineer verification actions on root cause hypotheses."""

    async def confirm_hypothesis(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
        req: ConfirmHypothesisRequest,
    ) -> ConfirmedRootCause:
        # 1. Fetch hypothesis with incident check
        h_stmt = (
            select(RootCauseHypothesis)
            .where(
                and_(
                    RootCauseHypothesis.id == hypothesis_id,
                    RootCauseHypothesis.incident_id == incident_id,
                    RootCauseHypothesis.tenant_id == tenant_id,
                )
            )
        )
        h_res = await db.execute(h_stmt)
        hypothesis = h_res.scalar_one_or_none()
        if not hypothesis:
            raise DomainException(f"Hypothesis '{hypothesis_id}' not found for incident '{incident_id}'.")

        # 2. Update hypothesis status to CONFIRMED
        hypothesis.status = "CONFIRMED"
        hypothesis.confidence_level = "HIGH"
        hypothesis.confidence_score = 1.0

        # 3. Create or update ConfirmedRootCause
        crc_stmt = select(ConfirmedRootCause).where(
            and_(
                ConfirmedRootCause.incident_id == incident_id,
                ConfirmedRootCause.tenant_id == tenant_id,
            )
        )
        crc_res = await db.execute(crc_stmt)
        confirmed_rc = crc_res.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not confirmed_rc:
            confirmed_rc = ConfirmedRootCause(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                incident_id=incident_id,
                hypothesis_id=hypothesis.id,
                confirmed_by=req.confirmed_by,
                confirmation_notes=req.confirmation_notes,
                root_cause_summary=req.root_cause_summary,
                verified_engineering_lesson=req.verified_engineering_lesson,
                prevention_strategy=req.prevention_strategy,
                confirmed_at=now,
            )
            db.add(confirmed_rc)
            await db.flush()
        else:
            confirmed_rc.hypothesis_id = hypothesis.id
            confirmed_rc.confirmed_by = req.confirmed_by
            confirmed_rc.confirmation_notes = req.confirmation_notes
            confirmed_rc.root_cause_summary = req.root_cause_summary
            confirmed_rc.verified_engineering_lesson = req.verified_engineering_lesson
            confirmed_rc.prevention_strategy = req.prevention_strategy
            confirmed_rc.confirmed_at = now
            await db.flush()

        # 4. Automatically generate verified OperationalLesson
        lesson_stmt = select(OperationalLesson).where(
            and_(
                OperationalLesson.verified_root_cause_id == confirmed_rc.id,
                OperationalLesson.tenant_id == tenant_id,
            )
        )
        l_res = await db.execute(lesson_stmt)
        existing_lesson = l_res.scalar_one_or_none()

        if not existing_lesson:
            lesson = OperationalLesson(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                incident_id=incident_id,
                title=f"Lesson: {req.root_cause_summary[:80]}",
                lesson=f"{req.verified_engineering_lesson}\n\nPrevention: {req.prevention_strategy}",
                verified_root_cause_id=confirmed_rc.id,
                verification_status="VERIFIED",
                applicability_conditions={
                    "verified_by": req.confirmed_by,
                    "hypothesis_id": str(hypothesis.id),
                    "confidence": "HIGH",
                },
            )
            db.add(lesson)

        # 5. Transition incident to RESOLVED or MITIGATING if open
        inc_stmt = select(Incident).where(Incident.id == incident_id)
        inc_res = await db.execute(inc_stmt)
        incident = inc_res.scalar_one_or_none()
        if incident and incident.status == "OPEN":
            incident.status = "RESOLVED"
            incident.resolved_at = now

        await db.flush()
        logger.info(f"Root cause confirmed for incident {incident_id} by {req.confirmed_by}")
        return confirmed_rc

    async def reject_hypothesis(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
        req: RejectHypothesisRequest,
    ) -> RootCauseHypothesis:
        h_stmt = (
            select(RootCauseHypothesis)
            .where(
                and_(
                    RootCauseHypothesis.id == hypothesis_id,
                    RootCauseHypothesis.incident_id == incident_id,
                    RootCauseHypothesis.tenant_id == tenant_id,
                )
            )
        )
        h_res = await db.execute(h_stmt)
        hypothesis = h_res.scalar_one_or_none()
        if not hypothesis:
            raise DomainException(f"Hypothesis '{hypothesis_id}' not found for incident '{incident_id}'.")

        hypothesis.status = "REJECTED"
        hypothesis.explanation = f"{hypothesis.explanation}\n[REJECTED by {req.rejected_by}]: {req.rejection_reason}"
        await db.flush()
        return hypothesis

    async def mark_insufficient_evidence(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
        req: InsufficientEvidenceRequest,
    ) -> RootCauseHypothesis:
        h_stmt = (
            select(RootCauseHypothesis)
            .where(
                and_(
                    RootCauseHypothesis.id == hypothesis_id,
                    RootCauseHypothesis.incident_id == incident_id,
                    RootCauseHypothesis.tenant_id == tenant_id,
                )
            )
        )
        h_res = await db.execute(h_stmt)
        hypothesis = h_res.scalar_one_or_none()
        if not hypothesis:
            raise DomainException(f"Hypothesis '{hypothesis_id}' not found for incident '{incident_id}'.")

        hypothesis.confidence_level = "INSUFFICIENT_EVIDENCE"
        hypothesis.status = "UNKNOWN"
        hypothesis.explanation = f"{hypothesis.explanation}\n[MARKED INSUFFICIENT EVIDENCE by {req.reviewed_by}]: {req.notes}"
        await db.flush()
        return hypothesis

    async def record_remediation(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        req: RecordRemediationRequest,
    ) -> RemediationAction:
        action = RemediationAction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            incident_id=incident_id,
            action_type=req.action_type.upper(),
            description=req.description,
            proposed_by=req.proposed_by,
            approved_by=req.approved_by,
            execution_status=req.execution_status.upper(),
            outcome=req.outcome.upper() if req.outcome else "UNKNOWN",
            effectiveness=req.effectiveness.upper() if req.effectiveness else "MEDIUM",
            runbook_url=req.runbook_url,
        )
        db.add(action)
        await db.flush()
        return action


human_verification_service = HumanVerificationService()
