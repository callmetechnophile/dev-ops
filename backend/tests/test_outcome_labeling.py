import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from app.services.outcome_labeler import (
    outcome_labeling_service,
    LABEL_FAILED,
    LABEL_SUCCEEDED,
    LABEL_CENSORED,
    DATASET_VERSION,
)


@pytest.mark.asyncio
async def test_label_failed_deployment_terminal_status(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Failed deployment
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="1111111111111111111111111111111111111111",
        status="FAILED",
        triggered_by="github_action",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        finished_at=datetime.now(timezone.utc) - timedelta(hours=2) + timedelta(minutes=10),
    )
    db_session.add(dep)
    await db_session.commit()

    label = await outcome_labeling_service.label_deployment(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
    )

    assert label.outcome_label == LABEL_FAILED
    assert label.verification_status == "VERIFIED"
    assert "FAILED" in label.failure_reason
    assert label.dataset_version == DATASET_VERSION


@pytest.mark.asyncio
async def test_label_failed_deployment_with_incident(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Deployment marked succeeded initially, but caused a downstream incident
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="2222222222222222222222222222222222222222",
        status="SUCCEEDED",
        triggered_by="github_action",
        started_at=datetime.now(timezone.utc) - timedelta(hours=3),
        finished_at=datetime.now(timezone.utc) - timedelta(hours=3) + timedelta(minutes=5),
    )
    db_session.add(dep)

    inc = models.Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        deployment_id=dep.id,
        title="OOM Killed after release 2.4",
        summary="Service pods ran out of memory after bad cache config",
        severity="P1",
        status="RESOLVED",
        incident_type="OOMKilled",
    )
    db_session.add(inc)
    await db_session.commit()

    label = await outcome_labeling_service.label_deployment(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
    )

    assert label.outcome_label == LABEL_FAILED
    assert label.verification_status == "VERIFIED"
    assert "OOM Killed" in label.failure_reason
    assert label.evidence_references["incident_key"] == inc.incident_key


@pytest.mark.asyncio
async def test_label_succeeded_deployment_after_observation_window(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Deployment finished 90 minutes ago (> 60m observation window) with no incidents
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="3333333333333333333333333333333333333333",
        status="SUCCEEDED",
        triggered_by="github_action",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=100),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    db_session.add(dep)
    await db_session.commit()

    label = await outcome_labeling_service.label_deployment(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
        observation_window_minutes=60,
    )

    assert label.outcome_label == LABEL_SUCCEEDED
    assert label.verification_status == "VERIFIED"
    assert label.failure_reason is None


@pytest.mark.asyncio
async def test_label_censored_deployment_within_observation_window(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Finished only 15 minutes ago (still in 60m observation window)
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="4444444444444444444444444444444444444444",
        status="SUCCEEDED",
        triggered_by="github_action",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=15),
    )
    db_session.add(dep)
    await db_session.commit()

    label = await outcome_labeling_service.label_deployment(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
        observation_window_minutes=60,
    )

    assert label.outcome_label == LABEL_CENSORED
    assert label.verification_status == "UNVERIFIED"
    assert "Observation window active" in label.failure_reason
