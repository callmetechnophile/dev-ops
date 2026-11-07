import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from app.services.impact_assessment import blast_radius_service


@pytest.mark.asyncio
async def test_blast_radius_graph_traversal(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Create Repo
    repo = models.Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="platform-mesh",
        full_name="acme/platform-mesh",
        provider="github",
    )
    db_session.add(repo)

    # Create 3 Services:
    # Service A (target) -> Service B (direct dependent) -> Service C (downstream, Tier-1)
    svcA = models.Service(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        name="Auth Service",
        slug="auth-service",
        tier="tier-2",
        health_status="healthy",
    )
    svcB = models.Service(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        name="API Gateway",
        slug="api-gateway",
        tier="tier-2",
        health_status="healthy",
    )
    svcC = models.Service(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        name="Order Processing Service",
        slug="order-processing",
        tier="tier-1",
        health_status="healthy",
    )
    db_session.add_all([svcA, svcB, svcC])

    # Add Dependencies:
    # Service B depends on Service A (source=B, target=A)
    dep_b_to_a = models.ServiceDependency(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_service_id=svcB.id,
        target_service_id=svcA.id,
        dependency_type="sync_http",
        criticality="high",
    )
    # Service C depends on Service B (source=C, target=B)
    dep_c_to_b = models.ServiceDependency(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_service_id=svcC.id,
        target_service_id=svcB.id,
        dependency_type="grpc",
        criticality="high",
    )
    db_session.add_all([dep_b_to_a, dep_c_to_b])
    await db_session.commit()

    # Calculate impact of deployment on Service A
    impact = await blast_radius_service.calculate_impact(
        db=db_session,
        tenant_id=tenant_id,
        target_service_id=svcA.id,
        environment="production",
    )

    assert impact.target_service_id == str(svcA.id)
    assert impact.direct_services_count >= 1
    assert impact.downstream_services_count >= 1
    assert impact.critical_tier1_exposed is True
    assert impact.blast_radius_score > 0.0
    assert impact.impact_category in ("HIGH", "CRITICAL")


@pytest.mark.asyncio
async def test_risk_assessment_api_lifecycle(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # 1. Create Deployment in waiting state
    dep_id = uuid.uuid4()
    dep = models.Deployment(
        id=dep_id,
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="abcdef1234567890abcdef1234567890abcdef12",
        status="WAITING_FOR_APPROVAL",
        triggered_by="github_action",
    )
    db_session.add(dep)
    await db_session.commit()

    # 2. Test GET /api/v1/risk/models/status
    model_status_res = await client.get("/api/v1/risk/models/status")
    assert model_status_res.status_code == 200
    status_data = model_status_res.json()
    assert "status" in status_data
    assert "minimum_required_samples" in status_data

    # 3. Test GET /api/v1/risk/features/schema
    schema_res = await client.get("/api/v1/risk/features/schema")
    assert schema_res.status_code == 200
    schema_data = schema_res.json()
    assert "schema_version" in schema_data
    assert "features" in schema_data

    # 4. Trigger Pre-deployment Risk Assessment: POST /api/v1/risk/assessments
    create_res = await client.post(
        "/api/v1/risk/assessments",
        json={"deployment_id": str(dep_id)},
    )
    assert create_res.status_code == 200
    assessment_data = create_res.json()
    assessment_id = assessment_data["id"]

    assert assessment_data["deployment_id"] == str(dep_id)
    assert assessment_data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "overall_risk_score" in assessment_data
    assert "operational_impact_score" in assessment_data

    # 5. Test GET /api/v1/risk/assessments
    list_res = await client.get("/api/v1/risk/assessments")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == assessment_id for a in list_data["items"])

    # 6. Test GET /api/v1/risk/assessments/{id}
    detail_res = await client.get(f"/api/v1/risk/assessments/{assessment_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == assessment_id

    # 7. Test GET /api/v1/risk/assessments/{id}/explanation
    expl_res = await client.get(f"/api/v1/risk/assessments/{assessment_id}/explanation")
    assert expl_res.status_code == 200
    expl_data = expl_res.json()
    assert "method" in expl_data

    # 8. Test GET /api/v1/risk/impact/{deployment_id}
    impact_res = await client.get(f"/api/v1/risk/impact/{dep_id}")
    assert impact_res.status_code == 200
    impact_data = impact_res.json()
    assert "blast_radius_score" in impact_data
    assert "impact_category" in impact_data
