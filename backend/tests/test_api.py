import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import app.models


@pytest.mark.asyncio
async def test_services_and_dependencies_endpoints(client: AsyncClient):
    res = await client.get("/api/v1/services")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["slug"] == "payment-service"

    svc_id = data["items"][0]["id"]
    dep_res = await client.get(f"/api/v1/services/{svc_id}/dependencies")
    assert dep_res.status_code == 200
    assert isinstance(dep_res.json(), list)


@pytest.mark.asyncio
async def test_deployments_and_risk_lifecycle(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    deployment_id = uuid.uuid4()

    # Create deployment
    dep = app.models.Deployment(
        id=deployment_id,
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        commit_sha="e7a9b0c8d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6",
        status="WAITING_FOR_APPROVAL",
        triggered_by="github_action"
    )
    db_session.add(dep)

    # Attach risk assessment with supporting rules
    assessment = app.models.RiskAssessment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        service_id=service_id,
        overall_risk_score=0.82,
        risk_level="HIGH",
        failure_probability=0.74,
        operational_impact_score=0.90,
        rule_score=0.80,
        triggered_rules=[
            {
                "rule_id": "RULE-01-CRITICAL-DEPENDENCY",
                "severity": "HIGH",
                "description": "Modifies core schema affecting tier-1 downstream payment service"
            }
        ],
        supporting_records=[
            {
                "incident_id": "INC-2024-001",
                "similarity": 0.89,
                "reason": "Previous CrashLoopBackOff during DB migration mismatch"
            }
        ]
    )
    db_session.add(assessment)

    # Attach recommendation
    rec = app.models.Recommendation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        risk_assessment_id=assessment.id,
        deployment_id=deployment_id,
        recommendation_type="BLOCK_DEPLOYMENT",
        title="Require Database Migration Canary Verification",
        rationale="High probability of connection pool exhaustion based on historical incident INC-2024-001.",
        mitigation_steps=["Deploy canary pod", "Verify connection pool limits", "Require Lead SRE Approval"],
        confidence_score=0.88,
        requires_approval="true"
    )
    db_session.add(rec)

    # Attach approval request
    req = app.models.ApprovalRequest(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        recommendation_id=rec.id,
        requested_action="DEPLOY_TO_PRODUCTION",
        status="WAITING_FOR_APPROVAL",
        context_data={"risk_score": 0.82, "service": "payment-service"}
    )
    db_session.add(req)
    await db_session.commit()

    # 1. Fetch deployment
    res = await client.get(f"/api/v1/deployments/{deployment_id}")
    assert res.status_code == 200
    assert res.json()["id"] == str(deployment_id)

    # 2. Fetch risk assessment
    risk_res = await client.get(f"/api/v1/deployments/{deployment_id}/risk")
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["overall_risk_score"] == 0.82
    assert risk_data["risk_level"] == "HIGH"
    assert len(risk_data["triggered_rules"]) == 1
    assert len(risk_data["recommendations"]) == 1

    # 3. Test approval gate decision submission
    user_id = "00000000-0000-0000-0000-000000000002"
    appr_res = await client.post(
        f"/api/v1/approvals/{req.id}",
        json={
            "user_id": user_id,
            "decision": "APPROVED",
            "justification": "Canary verified on staging cluster with 500 RPS load. Confirmed safe."
        }
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["decision"] == "APPROVED"
    assert len(appr_data["audit_signature"]) == 64  # SHA-256 fingerprint


@pytest.mark.asyncio
async def test_operational_memory_search(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Create incident with confirmed root cause
    inc = app.models.Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        title="Payment Gateway Timeout Incident",
        summary="Downstream database connection pool starvation caused 504 timeouts.",
        severity="P1",
        status="RESOLVED",
        detected_at=datetime.now(timezone.utc),
        blast_radius_score=0.95
    )
    db_session.add(inc)

    cause = app.models.ConfirmedRootCause(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=inc.id,
        root_cause_summary="Connection pool max size of 20 exhausted under burst traffic.",
        verified_engineering_lesson="Connection pool size must be scaled with pod replica count.",
        prevention_strategy="Added connection pool alert metric and enforced min_pool=10, max_pool=100.",
        confirmed_at=datetime.now(timezone.utc)
    )
    db_session.add(cause)
    await db_session.commit()

    # Search memory
    mem_res = await client.get("/api/v1/memory/search?q=connection pool")
    assert mem_res.status_code == 200
    data = mem_res.json()
    assert data["total_matches"] >= 1
    assert "connection pool" in data["verified_lessons"][0]["root_cause_summary"].lower()
