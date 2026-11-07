"""Incident Reconstruction and Correlation Engine.

Reconstructs operational incidents from failure signals, correlates events via stable identifiers,
maintains incident lifecycle, and attaches chronological evidence.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import (
    Incident,
    IncidentEvent,
    FailureClassification,
    RootCauseHypothesis,
    ConfirmedRootCause,
)
from app.models.event import Event
from app.models.service import Repository, Service
from app.models.deployment import Deployment, Build, Commit
from app.models.github_entities import WorkflowRun, DeploymentEvent
from app.services.failure_classifier import (
    failure_classifier,
    ClassificationResult,
    CAT_UNKNOWN_FAILURE,
    SUB_CANCELLED_OR_SKIPPED,
)

logger = logging.getLogger(__name__)


class IncidentReconstructionEngine:
    """Deterministic incident reconstruction from real operational signals."""

    async def process_event_for_incidents(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event_model: Event,
        repository: Optional[Repository] = None,
        service: Optional[Service] = None,
        deployment: Optional[Deployment] = None,
        workflow_run: Optional[WorkflowRun] = None,
    ) -> Optional[Incident]:
        """Inspects an event, correlates with existing incidents, or reconstructs a new incident."""
        payload = event_model.payload or {}
        event_type = event_model.event_type

        # Check for recovery signal first
        recovery_incident = await self._check_and_apply_recovery(
            db, tenant_id, event_model, repository, service, deployment, workflow_run
        )
        if recovery_incident:
            return recovery_incident

        # Run deterministic failure classification
        classifications: List[ClassificationResult] = failure_classifier.classify_event(event_type, payload)

        # Filter out non-failures or purely cancelled/skipped workflows
        active_failures = [
            c for c in classifications
            if c.is_terminal_failure and c.subcategory != SUB_CANCELLED_OR_SKIPPED
        ]

        if not active_failures:
            return None

        primary_class = active_failures[0]
        repo_id = repository.id if repository else event_model.repository_id
        svc_id = service.id if service else event_model.service_id
        dep_id = deployment.id if deployment else event_model.deployment_id
        environment = event_model.environment or (deployment.environment if deployment else "production")

        # Find existing OPEN incident matching stable correlation keys
        existing_incident = await self._find_matching_open_incident(
            db=db,
            tenant_id=tenant_id,
            repository_id=repo_id,
            primary_service_id=svc_id,
            deployment_id=dep_id,
            environment=environment,
        )

        occurred_time = event_model.occurred_at or datetime.now(timezone.utc)

        if existing_incident:
            # Update existing incident observation bounds
            existing_incident.last_observed_at = occurred_time
            if not existing_incident.deployment_id and dep_id:
                existing_incident.deployment_id = dep_id

            # Attach event link if not already linked
            await self._link_incident_event(
                db=db,
                tenant_id=tenant_id,
                incident_id=existing_incident.id,
                event_id=event_model.id,
                relationship_type="contributing",
                relevance=1.0,
            )

            # Record classifications for this incident
            await self._persist_classifications(db, tenant_id, existing_incident.id, active_failures)
            await db.flush()
            return existing_incident

        # Reconstruct brand new Incident
        seq_code = uuid.uuid4().hex[:6].upper()
        date_str = occurred_time.strftime("%Y%m%d")
        incident_key = f"INC-{date_str}-{seq_code}"

        repo_name = repository.full_name if repository else "service"
        title = f"{primary_class.category}: {primary_class.subcategory} in {repo_name}"
        summary = (
            f"Detected {primary_class.subcategory} during {event_type} on environment '{environment}'. "
            f"Observed error: {primary_class.evidence.get('matched_text_snippet') or primary_class.evidence.get('conclusion') or 'Failure detected'}"
        )

        severity = "P1" if str(environment).lower() in ("prod", "production") else "P2"

        incident = Incident(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            incident_key=incident_key,
            title=title,
            summary=summary,
            description=summary,
            incident_type=primary_class.category,
            severity=severity,
            status="OPEN",
            environment=environment,
            repository_id=repo_id,
            primary_service_id=svc_id,
            service_id=svc_id,
            deployment_id=dep_id,
            first_observed_at=occurred_time,
            last_observed_at=occurred_time,
            detected_at=occurred_time,
            blast_radius_score=1.5 if severity == "P1" else 1.0,
            metadata_json={"initial_event_id": str(event_model.id), "event_type": event_type},
        )
        db.add(incident)
        await db.flush()

        # Link triggering event
        await self._link_incident_event(
            db=db,
            tenant_id=tenant_id,
            incident_id=incident.id,
            event_id=event_model.id,
            relationship_type="triggering",
            relevance=1.0,
        )

        # Record classifications
        await self._persist_classifications(db, tenant_id, incident.id, active_failures)

        await db.flush()
        return incident

    async def _find_matching_open_incident(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        repository_id: Optional[uuid.UUID],
        primary_service_id: Optional[uuid.UUID],
        deployment_id: Optional[uuid.UUID],
        environment: str,
    ) -> Optional[Incident]:
        """Finds active OPEN incident sharing stable identifiers."""
        conditions = [
            Incident.tenant_id == tenant_id,
            Incident.status == "OPEN",
            Incident.environment == environment,
        ]

        id_conditions = []
        if deployment_id:
            id_conditions.append(Incident.deployment_id == deployment_id)
        if repository_id:
            id_conditions.append(Incident.repository_id == repository_id)
        if primary_service_id:
            id_conditions.append(Incident.primary_service_id == primary_service_id)

        if not id_conditions:
            return None

        stmt = (
            select(Incident)
            .where(and_(*conditions, or_(*id_conditions)))
            .order_by(desc(Incident.detected_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _link_incident_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        event_id: uuid.UUID,
        relationship_type: str,
        relevance: float = 1.0,
    ) -> IncidentEvent:
        stmt = select(IncidentEvent).where(
            and_(
                IncidentEvent.incident_id == incident_id,
                IncidentEvent.event_id == event_id,
            )
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        inc_event = IncidentEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            incident_id=incident_id,
            event_id=event_id,
            relationship_type=relationship_type,
            relevance=relevance,
        )
        db.add(inc_event)
        return inc_event

    async def _persist_classifications(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        classifications: List[ClassificationResult],
    ):
        for c in classifications:
            # Check if this category/subcategory is already saved for this incident
            stmt = select(FailureClassification).where(
                and_(
                    FailureClassification.incident_id == incident_id,
                    FailureClassification.category == c.category,
                    FailureClassification.subcategory == c.subcategory,
                )
            )
            res = await db.execute(stmt)
            if not res.scalar_one_or_none():
                fc = FailureClassification(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    category=c.category,
                    subcategory=c.subcategory,
                    classification_method=c.classification_method,
                    evidence=c.evidence,
                    classifier_version=c.classifier_version,
                )
                db.add(fc)

    async def _check_and_apply_recovery(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event_model: Event,
        repository: Optional[Repository],
        service: Optional[Service],
        deployment: Optional[Deployment],
        workflow_run: Optional[WorkflowRun],
    ) -> Optional[Incident]:
        """Resolves an open incident if a verified recovery event arrives."""
        payload = event_model.payload or {}
        event_type = event_model.event_type

        is_success = False
        if event_type == "deployment_status" and payload.get("state") == "success":
            is_success = True
        elif event_type == "workflow_run" and payload.get("conclusion") == "success":
            is_success = True
        elif deployment and deployment.status == "SUCCEEDED":
            is_success = True

        if not is_success:
            return None

        repo_id = repository.id if repository else event_model.repository_id
        dep_id = deployment.id if deployment else event_model.deployment_id
        environment = event_model.environment or (deployment.environment if deployment else "production")

        matching_incident = await self._find_matching_open_incident(
            db=db,
            tenant_id=tenant_id,
            repository_id=repo_id,
            primary_service_id=service.id if service else None,
            deployment_id=dep_id,
            environment=environment,
        )

        if matching_incident:
            recovery_time = event_model.occurred_at or datetime.now(timezone.utc)
            matching_incident.status = "RESOLVED"
            matching_incident.resolved_at = recovery_time
            matching_incident.last_observed_at = recovery_time

            await self._link_incident_event(
                db=db,
                tenant_id=tenant_id,
                incident_id=matching_incident.id,
                event_id=event_model.id,
                relationship_type="recovery",
                relevance=1.0,
            )
            await db.flush()
            return matching_incident

        return None


incident_reconstruction_engine = IncidentReconstructionEngine()
