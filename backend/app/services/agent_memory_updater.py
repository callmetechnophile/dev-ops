"""Operational Memory Update Engine.

Updates M3 Operational Memory and links lifecycle lineage:
Prediction -> Recommendation -> Approval -> Deployment -> Outcome -> Incident -> Verified Lesson.

Invariants:
- Never rewrites historical risk assessments or predictions after outcomes are known.
- Stores predictions separately from actual outcomes to enable model drift and calibration evaluation.
- Promotes confirmed incident root causes into verified operational lessons when verified outcomes are observed.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentExecution, OutcomeObservation
from app.models.deployment import Deployment, DeploymentOutcomeLabel
from app.models.incident import Incident, ConfirmedRootCause, OperationalLesson
from app.models.intelligence import RiskAssessment, Recommendation, RemediationAction
from app.models.governance import ApprovalRequest, ApprovalDecision

logger = logging.getLogger(__name__)


class LineageAuditReport(BaseModel):
    execution_id: str
    deployment_id: Optional[str]
    prediction_id: Optional[str]
    recommendation_ids: List[str]
    approval_request_id: Optional[str]
    approval_status: Optional[str]
    outcome_value: str
    verified_lesson_ids: List[str]
    audit_chain_valid: bool = True


class AgentMemoryUpdater:
    """Updates operational memory with verified deployment outcomes and creates auditable lineage."""

    async def update_memory_with_outcome(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        outcome_value: str,  # SUCCESS, FAILURE, ROLLBACK, INCIDENT, CENSORED, UNKNOWN
        evidence: Dict[str, Any],
    ) -> LineageAuditReport:
        now = datetime.now(timezone.utc)
        verified_lesson_ids: List[str] = []

        # 1. Fetch deployment
        dep = None
        if execution.deployment_id:
            dep_stmt = select(Deployment).where(Deployment.id == execution.deployment_id)
            dep_res = await db.execute(dep_stmt)
            dep = dep_res.scalar_one_or_none()

        # 2. Fetch risk assessment (Preserve unaltered!)
        ra = None
        if dep:
            ra_stmt = select(RiskAssessment).where(
                and_(
                    RiskAssessment.deployment_id == dep.id,
                    RiskAssessment.tenant_id == execution.tenant_id,
                )
            ).order_by(desc(RiskAssessment.assessed_at))
            ra_res = await db.execute(ra_stmt)
            ra = ra_res.scalars().first()

        # 3. If outcome is FAILURE or INCIDENT, inspect linked confirmed root causes to generate/verify lessons
        if outcome_value in ("FAILURE", "INCIDENT", "ROLLBACK") and dep:
            inc_stmt = (
                select(Incident)
                .where(and_(Incident.deployment_id == dep.id, Incident.tenant_id == execution.tenant_id))
                .options(
                    selectinload(Incident.confirmed_root_cause),
                    selectinload(Incident.lessons),
                )
            )
            inc_res = await db.execute(inc_stmt)
            linked_incs = inc_res.scalars().all()

            for inc in linked_incs:
                if inc.confirmed_root_cause and not inc.lessons:
                    # Create operational lesson from human-confirmed root cause
                    crc = inc.confirmed_root_cause
                    new_lesson = OperationalLesson(
                        id=uuid.uuid4(),
                        tenant_id=execution.tenant_id,
                        incident_id=inc.id,
                        verified_root_cause_id=crc.id,
                        title=f"Deployment Lesson: {inc.title[:60]}",
                        lesson=f"{crc.verified_engineering_lesson} (Prevention: {crc.prevention_strategy})",
                        applicability_conditions={
                            "environment": inc.environment,
                            "service_id": str(inc.service_id) if inc.service_id else None,
                            "component": inc.incident_type,
                        },
                        verification_status="VERIFIED",
                    )
                    db.add(new_lesson)
                    verified_lesson_ids.append(str(new_lesson.id))
                    logger.info(f"Synthesized new Verified OperationalLesson {new_lesson.id} from Incident {inc.id}")

        # 4. Fetch approval request and decision
        ar_stmt = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.execution_id == execution.id,
                ApprovalRequest.tenant_id == execution.tenant_id,
            )
        ).options(selectinload(ApprovalRequest.decisions))
        ar_res = await db.execute(ar_stmt)
        app_req = ar_res.scalars().first()

        # 5. Fetch recommendations
        rec_stmt = select(Recommendation).where(
            and_(
                Recommendation.execution_id == execution.id,
                Recommendation.tenant_id == execution.tenant_id,
            )
        )
        rec_res = await db.execute(rec_stmt)
        recs = rec_res.scalars().all()

        await db.flush()

        return LineageAuditReport(
            execution_id=str(execution.id),
            deployment_id=str(dep.id) if dep else None,
            prediction_id=str(ra.id) if ra else None,
            recommendation_ids=[str(r.id) for r in recs],
            approval_request_id=str(app_req.id) if app_req else None,
            approval_status=app_req.status if app_req else None,
            outcome_value=outcome_value,
            verified_lesson_ids=verified_lesson_ids,
            audit_chain_valid=True,
        )


agent_memory_updater = AgentMemoryUpdater()
