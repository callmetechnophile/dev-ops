"""Historical Outcome Dataset Builder & Labeling Engine.

Extracts trustworthy ground-truth outcomes from real historical deployment records:
- Explicit observation windows (default 60 minutes)
- Distinguishes verified failures (rollbacks, failure status, incidents) from verified successes
- Explicitly flags unobserved / recent deployments as CENSORED (excluded from training)
- Never fabricates outcomes or assumes unobserved deployments succeeded.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deployment import Deployment, DeploymentOutcomeLabel
from app.models.incident import Incident
from app.models.intelligence import RemediationAction

logger = logging.getLogger(__name__)

DATASET_VERSION = "v1.0"
DEFAULT_OBSERVATION_WINDOW_MINUTES = 60

LABEL_FAILED = "FAILED"
LABEL_SUCCEEDED = "SUCCEEDED"
LABEL_CENSORED = "CENSORED"


class LabeledDeploymentOutcome(BaseModel):
    deployment_id: str
    observation_window_minutes: int
    outcome_label: str  # FAILED, SUCCEEDED, CENSORED
    failure_reason: Optional[str] = None
    evidence_references: Dict[str, Any] = {}
    verification_status: str = "VERIFIED"
    dataset_version: str = DATASET_VERSION
    finished_at: Optional[datetime] = None


class OutcomeLabelingService:
    """Labels deployment records into verified training outcomes."""

    async def label_deployment(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deployment: Deployment,
        observation_window_minutes: int = DEFAULT_OBSERVATION_WINDOW_MINUTES,
        now: Optional[datetime] = None,
    ) -> DeploymentOutcomeLabel:
        current_time = now or datetime.now(timezone.utc)
        obs_window = timedelta(minutes=observation_window_minutes)

        # 1. Check for existing label
        stmt = select(DeploymentOutcomeLabel).where(
            and_(
                DeploymentOutcomeLabel.tenant_id == tenant_id,
                DeploymentOutcomeLabel.deployment_id == deployment.id,
            )
        )
        res = await db.execute(stmt)
        existing_label = res.scalar_one_or_none()

        # 2. Check for explicit failure signals
        failure_reason = None
        evidence = {}

        # Signal A: Deployment status is explicitly FAILED or ROLLED_BACK
        if deployment.status in ("FAILED", "ROLLED_BACK"):
            failure_reason = f"Deployment marked with terminal status '{deployment.status}'"
            evidence["deployment_status"] = deployment.status
            evidence["finished_at"] = deployment.finished_at.isoformat() if deployment.finished_at else None

        # Signal B: Verified incident linked to deployment
        inc_stmt = select(Incident).where(
            and_(
                Incident.deployment_id == deployment.id,
                Incident.tenant_id == tenant_id,
            )
        )
        inc_res = await db.execute(inc_stmt)
        linked_incidents = inc_res.scalars().all()
        if linked_incidents:
            primary_inc = linked_incidents[0]
            failure_reason = f"Verified incident {primary_inc.incident_key}: {primary_inc.title}"
            evidence["incident_key"] = primary_inc.incident_key
            evidence["severity"] = primary_inc.severity
            evidence["incident_type"] = primary_inc.incident_type

        # Signal C: Remediation record of rollback
        rem_stmt = select(RemediationAction).where(
            and_(
                RemediationAction.incident_id.in_([i.id for i in linked_incidents]) if linked_incidents else False,
                RemediationAction.tenant_id == tenant_id,
                RemediationAction.action_type == "ROLLBACK",
            )
        )
        if linked_incidents:
            rem_res = await db.execute(rem_stmt)
            if rem_res.scalars().first():
                evidence["rollback_action_executed"] = True

        # Determine label
        if failure_reason:
            outcome_label = LABEL_FAILED
            verification_status = "VERIFIED"
        else:
            # Check observation window
            if not deployment.finished_at:
                outcome_label = LABEL_CENSORED
                failure_reason = "Deployment has not finished execution."
                verification_status = "UNVERIFIED"
            else:
                elapsed = current_time - deployment.finished_at
                if elapsed < obs_window:
                    outcome_label = LABEL_CENSORED
                    failure_reason = f"Observation window active ({elapsed.total_seconds() / 60:.1f}m / {observation_window_minutes}m elapsed)."
                    verification_status = "UNVERIFIED"
                elif deployment.status == "SUCCEEDED":
                    outcome_label = LABEL_SUCCEEDED
                    verification_status = "VERIFIED"
                else:
                    outcome_label = LABEL_CENSORED
                    failure_reason = f"Ambiguous deployment state '{deployment.status}' without explicit failure or success."
                    verification_status = "UNVERIFIED"

        if existing_label:
            existing_label.observation_window_minutes = observation_window_minutes
            existing_label.outcome_label = outcome_label
            existing_label.failure_reason = failure_reason
            existing_label.evidence_references = evidence
            existing_label.verification_status = verification_status
            existing_label.dataset_version = DATASET_VERSION
            return existing_label

        new_label = DeploymentOutcomeLabel(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            deployment_id=deployment.id,
            observation_window_minutes=observation_window_minutes,
            outcome_label=outcome_label,
            failure_reason=failure_reason,
            evidence_references=evidence,
            verification_status=verification_status,
            dataset_version=DATASET_VERSION,
        )
        db.add(new_label)
        return new_label

    async def build_dataset(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        observation_window_minutes: int = DEFAULT_OBSERVATION_WINDOW_MINUTES,
    ) -> List[LabeledDeploymentOutcome]:
        """Labels all historical deployments and returns the clean verified training corpus."""
        stmt = (
            select(Deployment)
            .where(Deployment.tenant_id == tenant_id)
            .order_by(Deployment.created_at.asc())
        )
        res = await db.execute(stmt)
        deployments = res.scalars().all()

        labeled_corpus: List[LabeledDeploymentOutcome] = []
        for dep in deployments:
            lbl = await self.label_deployment(
                db=db,
                tenant_id=tenant_id,
                deployment=dep,
                observation_window_minutes=observation_window_minutes,
            )
            labeled_corpus.append(
                LabeledDeploymentOutcome(
                    deployment_id=str(dep.id),
                    observation_window_minutes=lbl.observation_window_minutes,
                    outcome_label=lbl.outcome_label,
                    failure_reason=lbl.failure_reason,
                    evidence_references=lbl.evidence_references,
                    verification_status=lbl.verification_status,
                    dataset_version=lbl.dataset_version,
                    finished_at=dep.finished_at,
                )
            )

        await db.flush()
        return labeled_corpus


outcome_labeling_service = OutcomeLabelingService()
