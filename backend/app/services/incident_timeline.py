"""Dedicated Incident Timeline Engine.

Reconstructs complete chronological operational timelines from:
- Commits & PRs
- Workflows & Builds
- Deployments & Status transitions
- Ingested Events (Triggering, Contributing, Correlated, Recovery)
- Failure Classifications
- Root-Cause Hypotheses & Human Verifications
- Remediation Actions & Outcomes

Preserves original occurred_at timestamps strictly.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.incident import (
    Incident,
    IncidentEvent,
    FailureClassification,
    RootCauseHypothesis,
    ConfirmedRootCause,
    OperationalLesson,
)
from app.models.intelligence import RemediationAction
from app.models.event import Event
from app.models.deployment import Commit, Build, Deployment
from app.models.github_entities import WorkflowRun, DeploymentEvent, PullRequest


def _to_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TimelineEntry(BaseModel):
    id: str
    record_id: str
    event_type: str
    title: str
    description: str
    occurred_at: datetime
    received_at: Optional[datetime] = None
    source: str
    relationship_type: str = "correlated"
    evidence_reference: Optional[Dict[str, Any]] = None


class IncidentTimelineResponse(BaseModel):
    incident_id: str
    incident_key: str
    title: str
    status: str
    severity: str
    environment: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    entry_count: int
    entries: List[TimelineEntry]


class IncidentTimelineService:
    """Constructs comprehensive chronological incident timelines."""

    async def get_incident_timeline(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
    ) -> Optional[IncidentTimelineResponse]:
        # 1. Fetch incident with relationships
        stmt = (
            select(Incident)
            .where(
                and_(
                    Incident.id == incident_id,
                    Incident.tenant_id == tenant_id,
                )
            )
            .options(
                selectinload(Incident.events).selectinload(IncidentEvent.event),
                selectinload(Incident.classifications),
                selectinload(Incident.hypotheses),
                selectinload(Incident.confirmed_root_cause),
                selectinload(Incident.remediations),
                selectinload(Incident.lessons),
            )
        )
        res = await db.execute(stmt)
        incident = res.scalar_one_or_none()
        if not incident:
            return None

        entries: List[TimelineEntry] = []

        # 2. Add linked incident events
        for inc_ev in incident.events:
            ev: Event = inc_ev.event
            if ev:
                entries.append(
                    TimelineEntry(
                        id=f"evt-{ev.id}",
                        record_id=str(ev.id),
                        event_type=ev.event_type,
                        title=f"Event: {ev.event_type}",
                        description=f"Source: {ev.source} | Event ID: {ev.event_id}",
                        occurred_at=ev.occurred_at,
                        received_at=ev.received_at,
                        source=ev.source,
                        relationship_type=inc_ev.relationship_type,
                        evidence_reference=ev.payload,
                    )
                )

        # 3. Add associated commits if repository / commit_sha is linked
        if incident.repository_id:
            c_stmt = (
                select(Commit)
                .where(
                    and_(
                        Commit.tenant_id == tenant_id,
                        Commit.repository_id == incident.repository_id,
                    )
                )
                .order_by(desc(Commit.committed_at))
                .limit(15)
            )
            c_res = await db.execute(c_stmt)
            for c in c_res.scalars().all():
                if incident.first_observed_at and c.committed_at <= incident.last_observed_at:
                    entries.append(
                        TimelineEntry(
                            id=f"commit-{c.id}",
                            record_id=str(c.id),
                            event_type="commit.pushed",
                            title=f"Commit: {c.commit_sha[:7]} by {c.author_name}",
                            description=c.message,
                            occurred_at=c.committed_at,
                            source="github",
                            relationship_type="contributing" if c.committed_at >= incident.first_observed_at else "correlated",
                            evidence_reference={"branch": c.branch, "sha": c.commit_sha},
                        )
                    )

        # 4. Add associated deployment & deployment events
        if incident.deployment_id:
            dep_stmt = select(Deployment).where(Deployment.id == incident.deployment_id)
            dep_res = await db.execute(dep_stmt)
            dep = dep_res.scalar_one_or_none()
            if dep:
                if dep.started_at:
                    entries.append(
                        TimelineEntry(
                            id=f"dep-start-{dep.id}",
                            record_id=str(dep.id),
                            event_type="deployment.started",
                            title=f"Deployment Started to {dep.environment}",
                            description=f"Status: {dep.status} | Triggered by: {dep.triggered_by}",
                            occurred_at=dep.started_at,
                            source="github",
                            relationship_type="correlated",
                            evidence_reference={"github_deployment_id": dep.github_deployment_id},
                        )
                    )
                if dep.finished_at:
                    entries.append(
                        TimelineEntry(
                            id=f"dep-finish-{dep.id}",
                            record_id=str(dep.id),
                            event_type=f"deployment.{dep.status.lower()}",
                            title=f"Deployment {dep.status} on {dep.environment}",
                            description=f"Finished in {dep.duration_seconds:.1f}s" if dep.duration_seconds else f"Finished with status {dep.status}",
                            occurred_at=dep.finished_at,
                            source="github",
                            relationship_type="triggering" if dep.status == "FAILED" else "recovery",
                            evidence_reference={"status": dep.status},
                        )
                    )

                # Fetch discrete deployment status events
                de_stmt = select(DeploymentEvent).where(DeploymentEvent.deployment_id == dep.id)
                de_res = await db.execute(de_stmt)
                for de in de_res.scalars().all():
                    entries.append(
                        TimelineEntry(
                            id=f"dep-status-{de.id}",
                            record_id=str(de.id),
                            event_type="deployment_status.transition",
                            title=f"Deployment Transition: {de.status}",
                            description=de.description or f"Status transitioned to {de.status}",
                            occurred_at=de.occurred_at,
                            source="github",
                            relationship_type="contributing" if de.status in ("failure", "error") else "monitoring",
                            evidence_reference=de.payload,
                        )
                    )

        # 5. Add failure classifications
        for fc in incident.classifications:
            entries.append(
                TimelineEntry(
                    id=f"fc-{fc.id}",
                    record_id=str(fc.id),
                    event_type="failure.classified",
                    title=f"Failure Classification: {fc.category}",
                    description=f"{fc.subcategory} (Method: {fc.classification_method})",
                    occurred_at=fc.created_at,
                    source="system",
                    relationship_type="triggering",
                    evidence_reference=fc.evidence,
                )
            )

        # 6. Add root cause hypotheses
        for hyp in incident.hypotheses:
            entries.append(
                TimelineEntry(
                    id=f"hyp-{hyp.id}",
                    record_id=str(hyp.id),
                    event_type="root_cause.hypothesized",
                    title=f"Hypothesis: {hyp.status} ({hyp.confidence_level})",
                    description=hyp.hypothesis,
                    occurred_at=hyp.created_at,
                    source=hyp.generated_by,
                    relationship_type="correlated",
                    evidence_reference={"evidence_event_ids": hyp.evidence_event_ids, "explanation": hyp.explanation},
                )
            )

        # 7. Add confirmed root cause
        if incident.confirmed_root_cause:
            crc = incident.confirmed_root_cause
            entries.append(
                TimelineEntry(
                    id=f"crc-{crc.id}",
                    record_id=str(crc.id),
                    event_type="root_cause.confirmed",
                    title=f"Root Cause Confirmed by {crc.confirmed_by}",
                    description=crc.root_cause_summary,
                    occurred_at=crc.confirmed_at,
                    source="engineer",
                    relationship_type="triggering",
                    evidence_reference={
                        "lesson": crc.verified_engineering_lesson,
                        "prevention": crc.prevention_strategy,
                        "notes": crc.confirmation_notes,
                    },
                )
            )

        # 8. Add remediation actions
        for rem in incident.remediations:
            entries.append(
                TimelineEntry(
                    id=f"rem-{rem.id}",
                    record_id=str(rem.id),
                    event_type="remediation.recorded",
                    title=f"Remediation: {rem.action_type} ({rem.execution_status})",
                    description=rem.description,
                    occurred_at=rem.created_at,
                    source=rem.proposed_by,
                    relationship_type="recovery" if rem.outcome == "SUCCESS" else "contributing",
                    evidence_reference={"outcome": rem.outcome, "effectiveness": rem.effectiveness},
                )
            )

        # 9. Add resolution event if resolved
        if incident.resolved_at:
            entries.append(
                TimelineEntry(
                    id=f"res-{incident.id}",
                    record_id=str(incident.id),
                    event_type="incident.resolved",
                    title="Incident Verified Resolved",
                    description=f"Incident '{incident.title}' status transitioned to RESOLVED.",
                    occurred_at=incident.resolved_at,
                    source="system",
                    relationship_type="recovery",
                )
            )

        # 10. Sort strictly by occurred_at ASC
        entries.sort(key=lambda x: _to_utc(x.occurred_at))

        return IncidentTimelineResponse(
            incident_id=str(incident.id),
            incident_key=incident.incident_key,
            title=incident.title,
            status=incident.status,
            severity=incident.severity,
            environment=incident.environment,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            entry_count=len(entries),
            entries=entries,
        )


incident_timeline_service = IncidentTimelineService()
