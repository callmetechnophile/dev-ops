import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.incident import (
    Incident,
    IncidentEvent,
    FailureClassification,
    RootCauseHypothesis,
    ConfirmedRootCause,
    OperationalLesson,
)
from app.models.event import Event
from app.models.service import Repository
from app.services.root_cause_engine import root_cause_engine
from app.services.human_verification import (
    human_verification_service,
    ConfirmHypothesisRequest,
    RejectHypothesisRequest,
    InsufficientEvidenceRequest,
    RecordRemediationRequest,
)


@pytest.mark.asyncio
async def test_root_cause_hypothesis_generation_with_evidence(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo = Repository(id=uuid.uuid4(), tenant_id=tenant_id, name="order-svc", full_name="org/order-svc")
    db_session.add(repo)
    await db_session.flush()

    inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-2026-TEST01",
        title="OOMKilled in order-svc",
        summary="Pod terminated by Linux OOM killer",
        incident_type="INFRASTRUCTURE_FAILURE",
        severity="P1",
        status="OPEN",
        environment="production",
        repository_id=repo.id,
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc)
    await db_session.flush()

    # Add failure classification
    fc = FailureClassification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=inc.id,
        category="INFRASTRUCTURE_FAILURE",
        subcategory="Resource exhaustion",
        classification_method="DETERMINISTIC_RULE",
        evidence={"matched_text_snippet": "command killed due to out of memory (exit code 137)", "exit_code": 137},
    )
    db_session.add(fc)

    # Add supporting operational event
    ev = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        event_id="evt-oom-001",
        source="kubernetes",
        event_type="container.terminated",
        repository_id=repo.id,
        environment="production",
        occurred_at=datetime.now(timezone.utc),
        correlation_id="corr-oom",
        idempotency_key="idem-oom",
        payload={"exit_code": 137, "reason": "OOMKilled"},
    )
    db_session.add(ev)
    await db_session.flush()

    inc_ev = IncidentEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=inc.id,
        event_id=ev.id,
        relationship_type="triggering",
        relevance=1.0,
    )
    db_session.add(inc_ev)
    await db_session.flush()

    hypotheses = await root_cause_engine.analyze_incident(db_session, tenant_id, inc.id)
    assert len(hypotheses) >= 1
    h = hypotheses[0]
    assert h.confidence_level == "HIGH"
    assert "OOMKilled" in h.hypothesis or "memory" in h.hypothesis.lower()
    assert h.status in ("SUSPECTED", "PROBABLE")
    assert h.generated_by.startswith("DETERMINISTIC")


@pytest.mark.asyncio
async def test_human_confirmation_creates_verified_lesson(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-2026-CONFIRM",
        title="Database Timeout",
        summary="Pool exhaustion",
        incident_type="DEPLOYMENT_FAILURE",
        severity="P2",
        status="OPEN",
        environment="staging",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc)
    await db_session.flush()

    hyp = RootCauseHypothesis(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=inc.id,
        hypothesis="Connection pool size inadequate for batch processing job",
        explanation="Default pool size 5 was overwhelmed by concurrent requests.",
        evidence_event_ids=["evt-mock-123"],
        confidence_level="MEDIUM",
        status="SUSPECTED",
        generated_by="DETERMINISTIC_STAGE_A",
    )
    db_session.add(hyp)
    await db_session.flush()

    # Engineer confirms hypothesis
    req = ConfirmHypothesisRequest(
        confirmed_by="alice@example.com",
        confirmation_notes="Verified via Prometheus postgres connection graph.",
        root_cause_summary="Default connection pool size of 5 exhausted under batch load.",
        verified_engineering_lesson="Worker pods must allocate dedicated connection pool of at least 25 connections.",
        prevention_strategy="Added connection pool quota validation to Helm values template.",
    )

    crc = await human_verification_service.confirm_hypothesis(
        db=db_session,
        tenant_id=tenant_id,
        incident_id=inc.id,
        hypothesis_id=hyp.id,
        req=req,
    )

    assert crc is not None
    assert crc.confirmed_by == "alice@example.com"
    assert hyp.status == "CONFIRMED"
    assert hyp.confidence_level == "HIGH"

    # Verify that an OperationalLesson was automatically created
    l_stmt = select(OperationalLesson).where(OperationalLesson.verified_root_cause_id == crc.id)
    l_res = await db_session.execute(l_stmt)
    lesson = l_res.scalar_one_or_none()
    assert lesson is not None
    assert lesson.verification_status == "VERIFIED"
    assert "Worker pods must allocate" in lesson.lesson


@pytest.mark.asyncio
async def test_human_rejection_of_hypothesis(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-2026-REJECT",
        title="Spurious hypothesis test",
        summary="Test incident",
        incident_type="UNKNOWN_FAILURE",
        severity="P3",
        status="OPEN",
        environment="dev",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc)
    await db_session.flush()

    hyp = RootCauseHypothesis(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=inc.id,
        hypothesis="Suspected network partition between AZs",
        explanation="Temporary latency spike noticed.",
        confidence_level="LOW",
        status="SUSPECTED",
        generated_by="STAGE_A",
    )
    db_session.add(hyp)
    await db_session.flush()

    req = RejectHypothesisRequest(
        rejected_by="bob@example.com",
        rejection_reason="Cloud provider verified no network partition occurred.",
    )
    rejected_hyp = await human_verification_service.reject_hypothesis(
        db=db_session,
        tenant_id=tenant_id,
        incident_id=inc.id,
        hypothesis_id=hyp.id,
        req=req,
    )

    assert rejected_hyp.status == "REJECTED"
    assert "Cloud provider verified" in rejected_hyp.explanation


@pytest.mark.asyncio
async def test_record_remediation_action(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-2026-REM",
        title="Remediation action test",
        summary="Rollback test",
        incident_type="DEPLOYMENT_FAILURE",
        severity="P1",
        status="OPEN",
        environment="production",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc)
    await db_session.flush()

    req = RecordRemediationRequest(
        action_type="ROLLBACK",
        description="Triggered rollback to stable release tag v2.4.1",
        proposed_by="sre_oncall",
        approved_by="tech_lead",
        execution_status="EXECUTED",
        outcome="SUCCESS",
        effectiveness="HIGH",
    )

    action = await human_verification_service.record_remediation(
        db=db_session,
        tenant_id=tenant_id,
        incident_id=inc.id,
        req=req,
    )

    assert action.action_type == "ROLLBACK"
    assert action.execution_status == "EXECUTED"
    assert action.outcome == "SUCCESS"
    assert action.effectiveness == "HIGH"
