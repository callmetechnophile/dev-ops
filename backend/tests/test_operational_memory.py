import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import (
    Incident,
    ConfirmedRootCause,
    OperationalLesson,
    FailureClassification,
)
from app.services.memory_service import operational_memory_service
from app.services.similarity_retrieval import similarity_retrieval_service


@pytest.mark.asyncio
async def test_memory_search_tenant_isolation(db_session: AsyncSession):
    tenant_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
    tenant_b = uuid.UUID("22222222-2222-2222-2222-222222222222")

    # Tenant A Incident & Lesson
    inc_a = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        incident_key="INC-A-01",
        title="Tenant A Private Security Incident",
        summary="Confidential architecture failure in auth gateway",
        incident_type="CONFIGURATION_FAILURE",
        severity="P1",
        status="RESOLVED",
        environment="production",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc_a)
    await db_session.flush()

    crc_a = ConfirmedRootCause(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        incident_id=inc_a.id,
        confirmed_by="security-lead@tenant-a.com",
        root_cause_summary="Tenant A proprietary OAuth token leakage",
        verified_engineering_lesson="Always encrypt token cache at rest using AES-256-GCM.",
        prevention_strategy="Automated key rotation.",
        confirmed_at=datetime.now(timezone.utc),
    )
    db_session.add(crc_a)

    lesson_a = OperationalLesson(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        incident_id=inc_a.id,
        title="OAuth Encryption Protocol",
        lesson="Always encrypt token cache at rest.",
        verified_root_cause_id=crc_a.id,
        verification_status="VERIFIED",
    )
    db_session.add(lesson_a)
    await db_session.commit()

    # Search as Tenant B: MUST NOT leak Tenant A's lesson
    results_b = await operational_memory_service.search_memory(
        db=db_session,
        tenant_id=tenant_b,
        query="OAuth token leakage",
    )
    assert len(results_b) == 0

    # Search as Tenant A: MUST find Tenant A's lesson
    results_a = await operational_memory_service.search_memory(
        db=db_session,
        tenant_id=tenant_a,
        query="OAuth token leakage",
    )
    assert len(results_a) >= 1
    assert "token" in results_a[0].summary.lower()


@pytest.mark.asyncio
async def test_historical_similarity_retrieval(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # 1. Historical Incident with confirmed lesson
    hist_inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-HIST-01",
        title="CrashLoopBackOff in Redis Worker",
        summary="Redis worker pod crashed repeatedly due to connection limit",
        incident_type="INFRASTRUCTURE_FAILURE",
        severity="P2",
        status="RESOLVED",
        environment="production",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(hist_inc)
    await db_session.flush()

    fc_hist = FailureClassification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=hist_inc.id,
        category="INFRASTRUCTURE_FAILURE",
        subcategory="Container crash",
        classification_method="DETERMINISTIC_RULE",
        evidence={"pattern": "CrashLoopBackOff"},
    )
    db_session.add(fc_hist)

    crc_hist = ConfirmedRootCause(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=hist_inc.id,
        confirmed_by="alice@example.com",
        root_cause_summary="Redis client connection pool reached maxclients limit.",
        verified_engineering_lesson="Increase redis maxclients to 10000 and enable client connection timeouts.",
        prevention_strategy="Added Prometheus alert on redis_connected_clients.",
        confirmed_at=datetime.now(timezone.utc),
    )
    db_session.add(crc_hist)
    await db_session.flush()

    # 2. New Active Incident with same category & subcategory
    new_inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-NEW-02",
        title="CrashLoopBackOff in Cache Proxy",
        summary="Container crash loop detected during release",
        incident_type="INFRASTRUCTURE_FAILURE",
        severity="P2",
        status="OPEN",
        environment="production",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(new_inc)
    await db_session.flush()

    fc_new = FailureClassification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=new_inc.id,
        category="INFRASTRUCTURE_FAILURE",
        subcategory="Container crash",
        classification_method="DETERMINISTIC_RULE",
        evidence={"pattern": "CrashLoopBackOff"},
    )
    db_session.add(fc_new)
    await db_session.commit()

    # Query similar incidents for new_inc
    matches = await similarity_retrieval_service.find_similar_incidents(
        db=db_session,
        tenant_id=tenant_id,
        incident_id=new_inc.id,
    )

    assert len(matches) >= 1
    best_match = matches[0]
    assert best_match.incident_id == str(hist_inc.id)
    assert best_match.similarity_score >= 0.70
    assert "INFRASTRUCTURE_FAILURE" in best_match.matching_categories
    assert best_match.confirmed_root_cause_summary is not None
    assert "Redis client connection pool" in best_match.confirmed_root_cause_summary


@pytest.mark.asyncio
async def test_incident_apis_e2e(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # 1. Test analytics endpoint
    res = await client.get("/api/v1/incidents/analytics")
    assert res.status_code == 200
    analytics = res.json()
    assert "total_incidents" in analytics
    assert "category_distribution" in analytics

    # 2. Create incident and test timeline & confirmation via API
    inc = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key="INC-API-TEST",
        title="API Integration Test Incident",
        summary="Testing API endpoints",
        incident_type="BUILD_FAILURE",
        severity="P2",
        status="OPEN",
        environment="staging",
        detected_at=datetime.now(timezone.utc),
    )
    db_session.add(inc)
    await db_session.commit()

    # Get incident
    get_res = await client.get(f"/api/v1/incidents/{inc.id}")
    assert get_res.status_code == 200
    assert get_res.json()["incident_key"] == "INC-API-TEST"

    # Get timeline
    tl_res = await client.get(f"/api/v1/incidents/{inc.id}/timeline")
    assert tl_res.status_code == 200
    assert tl_res.json()["incident_key"] == "INC-API-TEST"
