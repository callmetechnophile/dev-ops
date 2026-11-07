"""Outcome Monitoring Engine.

Collects and verifies real deployment outcome signals post-rollout.

Outcome Categories:
- SUCCESS
- FAILURE
- ROLLBACK
- INCIDENT
- CENSORED
- UNKNOWN

Invariants:
- Never infers success from the mere absence of failure events.
- Never infers failure from incomplete telemetry.
- Persists verifiable observations in `outcome_observations`.
"""

from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentExecution, OutcomeObservation
from app.models.deployment import Deployment, DeploymentOutcomeLabel
from app.models.incident import Incident
from app.models.intelligence import RemediationAction
from app.services.outcome_labeler import outcome_labeling_service, LABEL_FAILED, LABEL_SUCCEEDED, LABEL_CENSORED

logger = logging.getLogger(__name__)

OBS_SUCCESS = "SUCCESS"
OBS_FAILURE = "FAILURE"
OBS_ROLLBACK = "ROLLBACK"
OBS_INCIDENT = "INCIDENT"
OBS_CENSORED = "CENSORED"
OBS_UNKNOWN = "UNKNOWN"


class DeploymentOutcomeReport(BaseModel):
    deployment_id: str
    overall_outcome: str  # SUCCESS, FAILURE, ROLLBACK, INCIDENT, CENSORED, UNKNOWN
    is_verified: bool
    summary: str
    observations: List[Dict[str, Any]]
    observation_window_minutes: int = 60


class AgentOutcomeMonitor:
    """Monitors, aggregates, and verifies post-deployment outcome telemetry."""

    async def monitor_outcome(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        observation_window_minutes: int = 60,
    ) -> DeploymentOutcomeReport:
        now = datetime.now(timezone.utc)
        observations: List[OutcomeObservation] = []

        if not execution.deployment_id:
            return DeploymentOutcomeReport(
                deployment_id="none",
                overall_outcome=OBS_UNKNOWN,
                is_verified=False,
                summary="Execution has no associated deployment record.",
                observations=[],
            )

        # 1. Fetch deployment record
        dep_stmt = select(Deployment).where(Deployment.id == execution.deployment_id)
        dep_res = await db.execute(dep_stmt)
        dep = dep_res.scalar_one_or_none()
        if not dep:
            return DeploymentOutcomeReport(
                deployment_id=str(execution.deployment_id),
                overall_outcome=OBS_UNKNOWN,
                is_verified=False,
                summary="Deployment record not found.",
                observations=[],
            )

        # 2. Check deployment status
        dep_status = dep.status or "PENDING"
        if dep_status in ("FAILED", "ROLLED_BACK"):
            obs = OutcomeObservation(
                id=uuid.uuid4(),
                tenant_id=execution.tenant_id,
                execution_id=execution.id,
                deployment_id=dep.id,
                observation_type="DEPLOYMENT_STATUS",
                observation_value=OBS_FAILURE if dep_status == "FAILED" else OBS_ROLLBACK,
                evidence_reference={
                    "status": dep_status,
                    "finished_at": dep.finished_at.isoformat() if dep.finished_at else None,
                },
                observed_at=now,
            )
            db.add(obs)
            observations.append(obs)

        # 3. Check for linked incidents
        inc_stmt = select(Incident).where(
            and_(
                Incident.deployment_id == dep.id,
                Incident.tenant_id == execution.tenant_id,
            )
        )
        inc_res = await db.execute(inc_stmt)
        linked_incs = inc_res.scalars().all()
        for inc in linked_incs:
            obs = OutcomeObservation(
                id=uuid.uuid4(),
                tenant_id=execution.tenant_id,
                execution_id=execution.id,
                deployment_id=dep.id,
                observation_type="INCIDENT_OCCURRENCE",
                observation_value=OBS_INCIDENT,
                evidence_reference={
                    "incident_key": inc.incident_key,
                    "title": inc.title,
                    "severity": inc.severity,
                    "status": inc.status,
                },
                observed_at=now,
            )
            db.add(obs)
            observations.append(obs)

        # 4. Check for remediation actions (Rollbacks)
        rem_stmt = select(RemediationAction).where(
            and_(
                RemediationAction.incident_id.in_([i.id for i in linked_incs]) if linked_incs else False,
                RemediationAction.tenant_id == execution.tenant_id,
                RemediationAction.action_type == "ROLLBACK",
            )
        )
        if linked_incs:
            rem_res = await db.execute(rem_stmt)
            for rem in rem_res.scalars().all():
                obs = OutcomeObservation(
                    id=uuid.uuid4(),
                    tenant_id=execution.tenant_id,
                    execution_id=execution.id,
                    deployment_id=dep.id,
                    observation_type="ROLLBACK_SIGNAL",
                    observation_value=OBS_ROLLBACK,
                    evidence_reference={"remediation_id": str(rem.id), "description": rem.description},
                    observed_at=now,
                )
                db.add(obs)
                observations.append(obs)

        # 5. Evaluate overall outcome with observation window
        overall_outcome = OBS_UNKNOWN
        is_verified = False
        summary = ""

        has_failure = any(o.observation_value in (OBS_FAILURE, OBS_INCIDENT, OBS_ROLLBACK) for o in observations)
        if has_failure:
            overall_outcome = OBS_FAILURE
            is_verified = True
            summary = f"Verified post-deployment failure: {len(observations)} failure/incident signal(s) recorded."
        else:
            # Check observation window
            if not dep.finished_at:
                overall_outcome = OBS_CENSORED
                is_verified = False
                summary = "Deployment execution has not yet finished; observation window pending."
            else:
                elapsed = now - dep.finished_at
                obs_window = timedelta(minutes=observation_window_minutes)
                if elapsed < obs_window:
                    overall_outcome = OBS_CENSORED
                    is_verified = False
                    summary = f"Observation window active ({elapsed.total_seconds() / 60:.1f}m / {observation_window_minutes}m elapsed). Inconclusive."
                elif dep_status == "SUCCEEDED":
                    overall_outcome = OBS_SUCCESS
                    is_verified = True
                    summary = (
                        f"Deployment verified successful after full {observation_window_minutes}m observation window."
                    )
                    obs = OutcomeObservation(
                        id=uuid.uuid4(),
                        tenant_id=execution.tenant_id,
                        execution_id=execution.id,
                        deployment_id=dep.id,
                        observation_type="DEPLOYMENT_STATUS",
                        observation_value=OBS_SUCCESS,
                        evidence_reference={
                            "observation_window_minutes": observation_window_minutes,
                            "status": dep_status,
                        },
                        observed_at=now,
                    )
                    db.add(obs)
                    observations.append(obs)
                else:
                    overall_outcome = OBS_UNKNOWN
                    summary = f"Inconclusive deployment status '{dep_status}' after observation window."

        # 6. Synchronize with ground truth outcome labeler (M4 dataset)
        try:
            await outcome_labeling_service.label_deployment(
                db=db,
                tenant_id=execution.tenant_id,
                deployment=dep,
                observation_window_minutes=observation_window_minutes,
                now=now,
            )
        except Exception as e:
            logger.warning(f"Could not update DeploymentOutcomeLabel: {e}")

        await db.flush()

        return DeploymentOutcomeReport(
            deployment_id=str(dep.id),
            overall_outcome=overall_outcome,
            is_verified=is_verified,
            summary=summary,
            observations=[
                {
                    "type": o.observation_type,
                    "value": o.observation_value,
                    "evidence": o.evidence_reference,
                    "observed_at": o.observed_at.isoformat(),
                }
                for o in observations
            ],
            observation_window_minutes=observation_window_minutes,
        )


agent_outcome_monitor = AgentOutcomeMonitor()
