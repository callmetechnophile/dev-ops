import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.incident import Incident, IncidentEvent, FailureClassification
from app.models.event import Event
from app.models.service import Repository, Service
from app.services.incident_reconstruction import incident_reconstruction_engine
from app.services.incident_timeline import incident_timeline_service


@pytest.mark.asyncio
async def test_reconstruct_incident_from_failed_event(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo = Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="payment-gateway",
        full_name="org/payment-gateway",
    )
    db_session.add(repo)
    await db_session.flush()

    event_time = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    ev = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-wf-001",
        source="github",
        event_type="workflow_run",
        repository_id=repo.id,
        environment="production",
        occurred_at=event_time,
        correlation_id="corr-1",
        idempotency_key="idem-1",
        payload={
            "workflow_name": "production-deploy",
            "conclusion": "failure",
            "error_message": "CrashLoopBackOff: segmentation fault in main application container",
        },
    )
    db_session.add(ev)
    await db_session.flush()

    incident = await incident_reconstruction_engine.process_event_for_incidents(
        db=db_session,
        tenant_id=tenant_id,
        event_model=ev,
        repository=repo,
    )

    assert incident is not None
    assert incident.status == "OPEN"
    assert incident.severity == "P1"
    assert incident.incident_type == "INFRASTRUCTURE_FAILURE"
    assert incident.environment == "production"
    assert incident.first_observed_at == event_time
    assert incident.detected_at == event_time

    # Verify triggering incident_event link
    stmt = select(IncidentEvent).where(IncidentEvent.incident_id == incident.id)
    res = await db_session.execute(stmt)
    links = res.scalars().all()
    assert len(links) == 1
    assert links[0].relationship_type == "triggering"
    assert links[0].event_id == ev.id

    # Verify classification
    c_stmt = select(FailureClassification).where(FailureClassification.incident_id == incident.id)
    c_res = await db_session.execute(c_stmt)
    classes = c_res.scalars().all()
    assert len(classes) >= 1
    assert classes[0].category == "INFRASTRUCTURE_FAILURE"


@pytest.mark.asyncio
async def test_correlate_subsequent_event_into_open_incident(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo = Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="billing-service",
        full_name="org/billing-service",
    )
    db_session.add(repo)
    await db_session.flush()

    t1 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
    ev1 = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-01",
        source="github",
        event_type="workflow_run",
        repository_id=repo.id,
        environment="production",
        occurred_at=t1,
        correlation_id="c1",
        idempotency_key="i1",
        payload={"workflow_name": "release", "conclusion": "failure", "error_message": "Exit code 137 OOMKilled"},
    )
    db_session.add(ev1)
    await db_session.flush()

    inc1 = await incident_reconstruction_engine.process_event_for_incidents(
        db=db_session, tenant_id=tenant_id, event_model=ev1, repository=repo
    )
    assert inc1 is not None

    # Subsequent contributing failure 5 minutes later
    t2 = t1 + timedelta(minutes=5)
    ev2 = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-02",
        source="github",
        event_type="deployment_status",
        repository_id=repo.id,
        environment="production",
        occurred_at=t2,
        correlation_id="c1",
        idempotency_key="i2",
        payload={"state": "failure", "description": "CrashLoopBackOff after restart"},
    )
    db_session.add(ev2)
    await db_session.flush()

    inc2 = await incident_reconstruction_engine.process_event_for_incidents(
        db=db_session, tenant_id=tenant_id, event_model=ev2, repository=repo
    )

    # Should update the existing incident, NOT create a new duplicate
    assert inc2.id == inc1.id
    assert inc2.last_observed_at == t2

    stmt = select(IncidentEvent).where(IncidentEvent.incident_id == inc1.id)
    res = await db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) == 2
    types = {e.relationship_type for e in events}
    assert "triggering" in types
    assert "contributing" in types


@pytest.mark.asyncio
async def test_recovery_signal_resolves_open_incident(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo = Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="auth-api",
        full_name="org/auth-api",
    )
    db_session.add(repo)
    await db_session.flush()

    # Create failure
    t_fail = datetime(2026, 11, 7, 14, 0, 0, tzinfo=timezone.utc)
    ev_fail = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-fail-1",
        source="github",
        event_type="workflow_run",
        repository_id=repo.id,
        environment="production",
        occurred_at=t_fail,
        correlation_id="c-auth",
        idempotency_key="i-auth-fail",
        payload={"workflow_name": "deploy", "conclusion": "failure", "error_message": "CrashLoopBackOff"},
    )
    db_session.add(ev_fail)
    await db_session.flush()

    inc = await incident_reconstruction_engine.process_event_for_incidents(
        db=db_session, tenant_id=tenant_id, event_model=ev_fail, repository=repo
    )
    assert inc.status == "OPEN"

    # Send recovery signal: deployment succeeded
    t_rec = t_fail + timedelta(minutes=15)
    ev_rec = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-rec-1",
        source="github",
        event_type="deployment_status",
        repository_id=repo.id,
        environment="production",
        occurred_at=t_rec,
        correlation_id="c-auth",
        idempotency_key="i-auth-rec",
        payload={"state": "success", "description": "Rollback deployment active and healthy"},
    )
    db_session.add(ev_rec)
    await db_session.flush()

    resolved_inc = await incident_reconstruction_engine.process_event_for_incidents(
        db=db_session, tenant_id=tenant_id, event_model=ev_rec, repository=repo
    )

    assert resolved_inc is not None
    assert resolved_inc.id == inc.id
    assert resolved_inc.status == "RESOLVED"
    assert resolved_inc.resolved_at == t_rec

    # Verify timeline reflects resolution
    timeline = await incident_timeline_service.get_incident_timeline(db_session, tenant_id, inc.id)
    assert timeline is not None
    assert timeline.status == "RESOLVED"
    entry_types = [e.event_type for e in timeline.entries]
    assert "incident.resolved" in entry_types
