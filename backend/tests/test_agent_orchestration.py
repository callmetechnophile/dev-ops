import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from app.services.agent_state_machine import (
    agent_state_machine,
    InvalidStateTransitionError,
    STATE_DEPLOYMENT_DETECTED,
    STATE_CONTEXT_COLLECTION,
    STATE_CONTEXT_VALIDATION,
    STATE_HISTORICAL_RETRIEVAL,
    STATE_RISK_ASSESSMENT,
    STATE_POLICY_EVALUATION,
    STATE_RECOMMENDATION_GENERATION,
    STATE_WAITING_FOR_APPROVAL,
    STATE_APPROVED,
    STATE_REJECTED,
    STATE_EXPIRED,
    STATE_POST_DEPLOYMENT_MONITORING,
    STATE_OUTCOME_VERIFICATION,
    STATE_MEMORY_UPDATE,
    STATE_COMPLETED,
    STATE_FAILED,
)
from app.services.agent_context_collector import agent_context_collector, CollectedContext
from app.services.agent_policy_engine import (
    agent_policy_engine,
    OUTCOME_ALLOW,
    OUTCOME_REQUIRE_APPROVAL,
    OUTCOME_REQUIRE_ADDITIONAL_REVIEW,
    OUTCOME_RECOMMEND_DELAY,
    OUTCOME_INSUFFICIENT_EVIDENCE,
)
from app.services.agent_recommendation_engine import agent_recommendation_engine
from app.services.agent_approval_manager import (
    agent_approval_manager,
    UnauthorizedReviewerError,
    ExpiredApprovalError,
    DuplicateDecisionError,
)
from app.services.agent_orchestrator import agent_orchestrator


@pytest.mark.asyncio
async def test_agent_state_machine_valid_transitions(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Create dummy deployment
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="staging",
        status="PENDING",
        commit_sha="a" * 40,
    )
    db_session.add(dep)
    await db_session.flush()

    # Create agent execution
    execution = models.AgentExecution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        current_state=STATE_DEPLOYMENT_DETECTED,
        trigger_type="TEST_TRIGGER",
        trigger_reference="test-ref",
    )
    db_session.add(execution)
    await db_session.commit()

    # Step through valid state transitions
    valid_path = [
        STATE_CONTEXT_COLLECTION,
        STATE_CONTEXT_VALIDATION,
        STATE_HISTORICAL_RETRIEVAL,
        STATE_RISK_ASSESSMENT,
        STATE_POLICY_EVALUATION,
        STATE_RECOMMENDATION_GENERATION,
        STATE_WAITING_FOR_APPROVAL,
        STATE_APPROVED,
        STATE_POST_DEPLOYMENT_MONITORING,
        STATE_OUTCOME_VERIFICATION,
        STATE_MEMORY_UPDATE,
        STATE_COMPLETED,
    ]

    for next_st in valid_path:
        await agent_state_machine.transition(
            db=db_session,
            execution=execution,
            next_state=next_st,
            reason=f"Advancing to {next_st}",
            triggered_by="test_runner",
            payload={"step": next_st},
        )
        assert execution.current_state == next_st

    # Verify audit transitions recorded in DB
    stmt = (
        select(models.AgentStateTransition)
        .where(models.AgentStateTransition.execution_id == execution.id)
        .order_by(models.AgentStateTransition.created_at.asc())
    )
    res = await db_session.execute(stmt)
    transitions = res.scalars().all()
    assert len(transitions) == len(valid_path)
    assert transitions[0].previous_state == STATE_DEPLOYMENT_DETECTED
    assert transitions[0].next_state == STATE_CONTEXT_COLLECTION
    assert transitions[-1].next_state == STATE_COMPLETED


@pytest.mark.asyncio
async def test_agent_state_machine_invalid_transition(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="staging",
        status="PENDING",
        commit_sha="b" * 40,
    )
    db_session.add(dep)
    await db_session.flush()

    execution = models.AgentExecution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        current_state=STATE_DEPLOYMENT_DETECTED,
        trigger_type="TEST_TRIGGER",
        trigger_reference="test-ref",
    )
    db_session.add(execution)
    await db_session.commit()

    # Attempt illegal jump: DEPLOYMENT_DETECTED -> COMPLETED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await agent_state_machine.transition(
            db=db_session,
            execution=execution,
            next_state=STATE_COMPLETED,
            reason="Illegal bypass",
        )
    assert "Invalid agent state transition" in str(exc_info.value)
    assert execution.current_state == STATE_DEPLOYMENT_DETECTED


@pytest.mark.asyncio
async def test_agent_context_collector_missing_telemetry(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Bare deployment with no linked commit or build
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        status="PENDING",
        commit_sha="c" * 40,
    )
    db_session.add(dep)
    await db_session.commit()

    context = await agent_context_collector.collect_context(db_session, tenant_id, dep)

    assert context.github_context.get("deployment_id") == str(dep.id)
    assert context.github_context.get("environment") == "production"
    assert "commit_details_and_diff" in context.missing_context
    assert "build_telemetry" in context.missing_context
    assert "deployment" in context.sources


@pytest.mark.asyncio
async def test_agent_policy_engine_evaluations(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Get default policy
    policy = await agent_policy_engine.get_or_create_default_policy(db_session, tenant_id)

    # 1. Staging deployment with low risk -> ALLOW_WITHOUT_ADDITIONAL_REVIEW
    ctx_clean = CollectedContext(
        collected_at=datetime.now(timezone.utc),
        sources={"deployment": "deployments.id:test"},
        github_context={"environment": "staging", "build": {"conclusion": "success"}},
        operational_memory={"active_p1_incidents": []},
        predictive_intelligence={},
        infrastructure_context={"target_service": {"tier": "tier-3"}, "downstream_dependencies": []},
        missing_context=[],
    )
    res_clean = agent_policy_engine._evaluate_single_policy(
        policy=policy,
        context=ctx_clean,
        risk_score=0.20,
        impact_score=0.15,
        risk_level="LOW",
    )
    assert res_clean.outcome == OUTCOME_ALLOW

    # 2. Production environment -> REQUIRE_APPROVAL
    ctx_prod = CollectedContext(
        collected_at=datetime.now(timezone.utc),
        sources={"deployment": "deployments.id:test"},
        github_context={"environment": "production", "build": {"conclusion": "success"}},
        operational_memory={"active_p1_incidents": []},
        predictive_intelligence={},
        infrastructure_context={"target_service": {"tier": "tier-2"}, "downstream_dependencies": []},
        missing_context=[],
    )
    res_prod = agent_policy_engine._evaluate_single_policy(
        policy=policy,
        context=ctx_prod,
        risk_score=0.30,
        impact_score=0.20,
        risk_level="MEDIUM",
    )
    assert res_prod.outcome == OUTCOME_REQUIRE_APPROVAL

    # 3. Active P1 incident -> RECOMMEND_DELAY
    ctx_p1 = CollectedContext(
        collected_at=datetime.now(timezone.utc),
        sources={"deployment": "deployments.id:test"},
        github_context={"environment": "production", "build": {"conclusion": "success"}},
        operational_memory={
            "similar_incidents": [{
                "id": str(uuid.uuid4()),
                "key": "INC-P1-001",
                "title": "P1 Outage",
                "status": "OPEN",
                "severity": "P1",
            }]
        },
        predictive_intelligence={},
        infrastructure_context={"target_service": {"tier": "tier-1"}, "downstream_dependencies": []},
        missing_context=[],
    )
    res_p1 = agent_policy_engine._evaluate_single_policy(
        policy=policy,
        context=ctx_p1,
        risk_score=0.40,
        impact_score=0.30,
        risk_level="HIGH",
    )
    assert res_p1.outcome == OUTCOME_RECOMMEND_DELAY

    # 4. Missing telemetry (>= 3 missing fields) -> INSUFFICIENT_EVIDENCE
    ctx_missing = CollectedContext(
        collected_at=datetime.now(timezone.utc),
        sources={"deployment": "deployments.id:test"},
        github_context={"environment": "staging"},
        operational_memory={"active_p1_incidents": []},
        predictive_intelligence={},
        infrastructure_context={"target_service": {"tier": "tier-2"}, "downstream_dependencies": []},
        missing_context=["commit_details_and_diff", "build_telemetry", "ci_tests"],
    )
    res_missing = agent_policy_engine._evaluate_single_policy(
        policy=policy,
        context=ctx_missing,
        risk_score=0.10,
        impact_score=0.10,
        risk_level="LOW",
    )
    assert res_missing.outcome == OUTCOME_INSUFFICIENT_EVIDENCE


@pytest.mark.asyncio
async def test_agent_approval_manager_rbac_and_fingerprint(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    approver_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    # Fetch approver user
    u_stmt = select(models.User).where(models.User.id == approver_id)
    u_res = await db_session.execute(u_stmt)
    approver_user = u_res.scalar_one()

    # Create viewer user
    viewer_id = uuid.uuid4()
    viewer_user = models.User(
        id=viewer_id,
        tenant_id=tenant_id,
        email="intern-viewer@acme.corp",
        full_name="Intern Viewer",
        hashed_password="pw",
        role="viewer",
        is_active=True,
    )
    db_session.add(viewer_user)

    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        status="PENDING",
        commit_sha="e" * 40,
    )
    db_session.add(dep)
    await db_session.flush()

    execution = models.AgentExecution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        current_state=STATE_WAITING_FOR_APPROVAL,
        trigger_type="TEST_TRIGGER",
        trigger_reference="test-ref",
    )
    db_session.add(execution)
    await db_session.flush()

    # Create approval request
    req = await agent_approval_manager.create_approval_request(
        db=db_session,
        execution=execution,
        recommendation=None,
        policy_version="v1.0.0",
        risk_assessment_version="1.0.0",
        ttl_hours=24,
    )
    await db_session.commit()

    # 1. Unauthorized reviewer (viewer) attempts to approve -> UnauthorizedReviewerError
    with pytest.raises(UnauthorizedReviewerError):
        await agent_approval_manager.record_decision(
            db=db_session,
            request_id=req.id,
            tenant_id=tenant_id,
            user=viewer_user,
            action="APPROVE",
            notes="Unauthorized attempt",
        )

    # 2. Authorized reviewer approves -> succeeds with SHA-256 fingerprint
    req_updated, decision = await agent_approval_manager.record_decision(
        db=db_session,
        request_id=req.id,
        tenant_id=tenant_id,
        user=approver_user,
        action="APPROVE",
        notes="Staging smoke tests passed and load capacity verified.",
    )

    assert decision.decision in ("APPROVED", "APPROVE")
    assert len(decision.audit_signature) == 64  # SHA-256 hex length
    assert req_updated.status == "APPROVED"


@pytest.mark.asyncio
async def test_agent_approval_manager_fail_closed_and_duplicate(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    approver_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    u_stmt = select(models.User).where(models.User.id == approver_id)
    u_res = await db_session.execute(u_stmt)
    approver_user = u_res.scalar_one()

    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        status="PENDING",
        commit_sha="f" * 40,
    )
    db_session.add(dep)
    await db_session.flush()

    execution = models.AgentExecution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        current_state=STATE_WAITING_FOR_APPROVAL,
        trigger_type="TEST_TRIGGER",
        trigger_reference="test-ref",
    )
    db_session.add(execution)
    await db_session.flush()

    # Create request with expired timestamp
    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        execution_id=execution.id,
        requested_action="Deploy to Staging",
        status="WAITING_FOR_APPROVAL",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db_session.add(req)
    await db_session.commit()

    # 1. Expired request fails closed
    with pytest.raises(ExpiredApprovalError):
        await agent_approval_manager.record_decision(
            db=db_session,
            request_id=req.id,
            tenant_id=tenant_id,
            user=approver_user,
            action="APPROVE",
            notes="Late approval",
        )
    assert req.status == "EXPIRED"

    # 2. Cannot decide on already finalized/expired request
    with pytest.raises(DuplicateDecisionError):
        await agent_approval_manager.record_decision(
            db=db_session,
            request_id=req.id,
            tenant_id=tenant_id,
            user=approver_user,
            action="REJECT",
            notes="Another try",
        )


@pytest.mark.asyncio
async def test_agent_outcome_monitoring_and_memory_update(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Create deployment that experienced a failure
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        status="FAILED",
        commit_sha="1" * 40,
    )
    db_session.add(dep)
    await db_session.flush()

    # Create linked incident
    incident = models.Incident(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="High latency after deployment",
        summary="Database connection pool exhausted due to unindexed query",
        severity="P2",
        status="RESOLVED",
        environment="production",
        deployment_id=dep.id,
    )
    db_session.add(incident)
    await db_session.flush()

    # Create confirmed root cause
    crc = models.ConfirmedRootCause(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_id=incident.id,
        root_cause_summary="Unindexed query on orders table causing DB connection pool exhaustion",
        verified_engineering_lesson="Ensure composite indexes are present on filtered columns before deploying new queries.",
        prevention_strategy="Enforce query explain plan CI checks on migration PRs.",
    )
    db_session.add(crc)
    await db_session.flush()

    execution = models.AgentExecution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        current_state=STATE_POST_DEPLOYMENT_MONITORING,
        trigger_type="TEST_TRIGGER",
        trigger_reference="test-ref",
    )
    db_session.add(execution)
    await db_session.commit()

    # Advance through outcome verification and memory update
    updated_exec = await agent_orchestrator.advance_outcome_and_memory(
        db=db_session,
        execution_id=execution.id,
        tenant_id=tenant_id,
        observation_window_minutes=60,
    )

    assert updated_exec.current_state == STATE_COMPLETED
    assert updated_exec.execution_status == "COMPLETED"

    # Verify outcome observations were persisted
    stmt = select(models.OutcomeObservation).where(models.OutcomeObservation.execution_id == execution.id)
    obs_res = await db_session.execute(stmt)
    observations = obs_res.scalars().all()
    assert len(observations) >= 2

    # Verify verified lesson was created in operational memory
    lesson_stmt = select(models.OperationalLesson).where(models.OperationalLesson.tenant_id == tenant_id)
    lesson_res = await db_session.execute(lesson_stmt)
    lessons = lesson_res.scalars().all()
    assert len(lessons) >= 1
    assert any("High latency" in l.title or "composite indexes" in l.lesson for l in lessons)


@pytest.mark.asyncio
async def test_agent_orchestration_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    approver_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    # 1. Create a deployment
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="production",
        status="PENDING",
        commit_sha="2" * 40,
    )
    db_session.add(dep)
    await db_session.commit()

    # 2. Trigger agent execution via API
    resp = await client.post(
        "/api/v1/agent/executions",
        json={"deployment_id": str(dep.id), "trigger_type": "API_TEST"},
    )
    assert resp.status_code == 201
    data = resp.json()
    exec_id = data["id"]
    assert data["current_state"] == STATE_WAITING_FOR_APPROVAL

    # 3. Fetch execution details
    resp_get = await client.get(f"/api/v1/agent/executions/{exec_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == exec_id

    # 4. Fetch execution timeline
    resp_timeline = await client.get(f"/api/v1/agent/executions/{exec_id}/timeline")
    assert resp_timeline.status_code == 200
    timeline = resp_timeline.json()
    assert len(timeline) >= 6

    # 5. List executions
    resp_list = await client.get("/api/v1/agent/executions")
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] >= 1

    # 6. Fetch recommendations
    resp_recs = await client.get(f"/api/v1/agent/executions/{exec_id}/recommendations")
    assert resp_recs.status_code == 200
    assert len(resp_recs.json()) >= 1

    # 7. Policies API: List & Create
    resp_policies = await client.get("/api/v1/agent/policies")
    assert resp_policies.status_code == 200

    resp_create_policy = await client.post(
        "/api/v1/agent/policies",
        json={
            "name": "Strict Zero Trust Policy",
            "policy_version": "2.0.0",
            "enabled": True,
            "policy_definition": {
                "max_risk_score": 0.50,
                "require_approval_environments": ["production", "staging"],
            },
        },
    )
    assert resp_create_policy.status_code == 201

    # 8. Submit human approval decision via Approvals API
    approvals_resp = await client.get("/api/v1/approvals")
    assert approvals_resp.status_code == 200
    approval_items = approvals_resp.json()["items"]
    assert len(approval_items) >= 1

    req_id = approval_items[0]["id"]
    resp_decision = await client.post(
        f"/api/v1/approvals/{req_id}/decision",
        json={
            "user_id": str(approver_id),
            "action": "APPROVE",
            "notes": "Verified telemetry and approved for canary deployment.",
        },
    )
    assert resp_decision.status_code == 200
    decision_data = resp_decision.json()
    assert decision_data["decision"] in ("APPROVED", "APPROVE")
    assert len(decision_data["audit_signature"]) == 64
