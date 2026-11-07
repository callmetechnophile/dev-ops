"""Predictive DevOps Intelligence Agent API Endpoints.

Provides REST interfaces for:
- Agent Executions Lifecycle (/executions)
- State Transitions & Timeline (/executions/{id}/timeline)
- Policy Management & Evaluations (/policies, /executions/{id}/policy-evaluations)
- Recommendations (/executions/{id}/recommendations)
- Post-Deployment Outcome Monitoring (/executions/{id}/outcomes, /executions/{id}/advance-outcome)
"""
from __future__ import annotations
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.agent import AgentExecution, AgentStateTransition, DeploymentPolicy, PolicyEvaluation, OutcomeObservation
from app.models.deployment import Deployment
from app.models.governance import ApprovalRequest
from app.models.intelligence import Recommendation
from app.schemas.common import PaginatedResponse
from app.services.agent_orchestrator import agent_orchestrator
from app.services.agent_policy_engine import agent_policy_engine

router = APIRouter(prefix="/agent", tags=["Agent Orchestration"])

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> uuid.UUID:
    if x_tenant_id:
        try:
            return uuid.UUID(x_tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


class TriggerAgentExecutionRequest(BaseModel):
    deployment_id: str
    trigger_type: Optional[str] = "MANUAL_DISPATCH"
    trigger_reference: Optional[str] = None


class CreateDeploymentPolicyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    policy_version: Optional[str] = "v1.0.0"
    enabled: bool = True
    policy_definition: Dict[str, Any]


class UpdateDeploymentPolicyRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    policy_version: Optional[str] = None
    enabled: Optional[bool] = None
    policy_definition: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------
# Agent Executions
# --------------------------------------------------------------------------

@router.get("/executions")
async def list_agent_executions(
    status: Optional[str] = Query(None, description="Filter by status (RUNNING, WAITING_FOR_APPROVAL, COMPLETED, FAILED)"),
    state: Optional[str] = Query(None, description="Filter by current state"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AgentExecution)
        .where(AgentExecution.tenant_id == tenant_id)
        .options(
            selectinload(AgentExecution.approval_requests),
            selectinload(AgentExecution.recommendations),
        )
        .order_by(desc(AgentExecution.started_at))
    )
    if status:
        stmt = stmt.where(AgentExecution.execution_status == status)
    if state:
        stmt = stmt.where(AgentExecution.current_state == state)
    if environment:
        stmt = stmt.where(AgentExecution.environment == environment)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    records = res.scalars().all()

    items = [
        {
            "id": str(e.id),
            "trigger_type": e.trigger_type,
            "trigger_reference": e.trigger_reference,
            "deployment_id": str(e.deployment_id) if e.deployment_id else None,
            "service_id": str(e.service_id) if e.service_id else None,
            "environment": e.environment,
            "current_state": e.current_state,
            "execution_status": e.execution_status,
            "missing_context_count": len(e.missing_context or []),
            "recommendations_count": len(e.recommendations or []),
            "waiting_approval": any(r.status == "WAITING_FOR_APPROVAL" for r in (e.approval_requests or [])),
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "last_error": e.last_error,
        }
        for e in records
    ]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
        has_more=len(items) == page_size,
    )


@router.post("/executions", status_code=status.HTTP_201_CREATED)
async def create_agent_execution(
    req: TriggerAgentExecutionRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        dep_uuid = uuid.UUID(req.deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment UUID.")

    try:
        execution = await agent_orchestrator.trigger_deployment_analysis(
            db=db,
            tenant_id=tenant_id,
            deployment_id=dep_uuid,
            trigger_type=req.trigger_type or "MANUAL_DISPATCH",
            trigger_reference=req.trigger_reference,
        )
        return {
            "id": str(execution.id),
            "deployment_id": str(execution.deployment_id),
            "current_state": execution.current_state,
            "execution_status": execution.execution_status,
            "started_at": execution.started_at,
            "message": f"Agent execution initialized in state '{execution.current_state}'.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{id}")
async def get_agent_execution(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    stmt = (
        select(AgentExecution)
        .where(and_(AgentExecution.id == exec_uuid, AgentExecution.tenant_id == tenant_id))
        .options(
            selectinload(AgentExecution.transitions),
            selectinload(AgentExecution.policy_evaluations),
            selectinload(AgentExecution.recommendations),
            selectinload(AgentExecution.approval_requests),
            selectinload(AgentExecution.outcome_observations),
        )
    )
    res = await db.execute(stmt)
    e = res.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Agent execution not found.")

    return {
        "id": str(e.id),
        "trigger_type": e.trigger_type,
        "trigger_reference": e.trigger_reference,
        "deployment_id": str(e.deployment_id) if e.deployment_id else None,
        "service_id": str(e.service_id) if e.service_id else None,
        "environment": e.environment,
        "current_state": e.current_state,
        "execution_status": e.execution_status,
        "context_snapshot": e.context_snapshot or {},
        "missing_context": e.missing_context or [],
        "retry_count": e.retry_count,
        "started_at": e.started_at,
        "completed_at": e.completed_at,
        "last_error": e.last_error,
        "transitions_count": len(e.transitions),
        "policy_evaluations_count": len(e.policy_evaluations),
        "recommendations_count": len(e.recommendations),
        "approval_requests": [
            {
                "id": str(ar.id),
                "status": ar.status,
                "requested_action": ar.requested_action,
                "expires_at": ar.expires_at,
            }
            for ar in e.approval_requests
        ],
    }


@router.get("/executions/{id}/timeline")
async def get_execution_timeline(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    stmt = (
        select(AgentStateTransition)
        .where(and_(AgentStateTransition.execution_id == exec_uuid, AgentStateTransition.tenant_id == tenant_id))
        .order_by(AgentStateTransition.created_at.asc())
    )
    res = await db.execute(stmt)
    transitions = res.scalars().all()

    return [
        {
            "id": str(t.id),
            "previous_state": t.previous_state,
            "next_state": t.next_state,
            "transition_reason": t.transition_reason,
            "triggered_by": t.triggered_by,
            "payload": t.payload or {},
            "created_at": t.created_at,
        }
        for t in transitions
    ]


@router.get("/executions/{id}/recommendations")
async def get_execution_recommendations(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    stmt = (
        select(Recommendation)
        .where(and_(Recommendation.execution_id == exec_uuid, Recommendation.tenant_id == tenant_id))
        .order_by(Recommendation.created_at.asc())
    )
    res = await db.execute(stmt)
    recs = res.scalars().all()

    return [
        {
            "id": str(r.id),
            "recommendation_type": r.recommendation_type,
            "title": r.title,
            "rationale": r.rationale,
            "explanation": r.explanation,
            "mitigation_steps": r.mitigation_steps or [],
            "evidence_references": r.evidence_references or {},
            "confidence_level": r.confidence_level,
            "confidence_score": r.confidence_score,
            "status": r.status,
            "requires_approval": r.requires_approval == "true",
            "created_at": r.created_at,
        }
        for r in recs
    ]


@router.get("/executions/{id}/policy-evaluations")
async def get_execution_policy_evaluations(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    stmt = (
        select(PolicyEvaluation)
        .where(and_(PolicyEvaluation.execution_id == exec_uuid, PolicyEvaluation.tenant_id == tenant_id))
        .options(selectinload(PolicyEvaluation.policy))
        .order_by(PolicyEvaluation.evaluated_at.asc())
    )
    res = await db.execute(stmt)
    evals = res.scalars().all()

    return [
        {
            "id": str(pe.id),
            "policy_id": str(pe.policy_id),
            "policy_name": pe.policy.name if pe.policy else "Default Policy",
            "policy_version": pe.policy_version,
            "outcome": pe.outcome,
            "evidence": pe.evidence or {},
            "evaluated_at": pe.evaluated_at,
        }
        for pe in evals
    ]


@router.get("/executions/{id}/outcomes")
async def get_execution_outcomes(
    id: str,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    stmt = (
        select(OutcomeObservation)
        .where(and_(OutcomeObservation.execution_id == exec_uuid, OutcomeObservation.tenant_id == tenant_id))
        .order_by(OutcomeObservation.observed_at.desc())
    )
    res = await db.execute(stmt)
    observations = res.scalars().all()

    return [
        {
            "id": str(o.id),
            "deployment_id": str(o.deployment_id),
            "observation_type": o.observation_type,
            "observation_value": o.observation_value,
            "evidence_reference": o.evidence_reference or {},
            "observed_at": o.observed_at,
        }
        for o in observations
    ]


@router.post("/executions/{id}/advance-outcome")
async def advance_execution_outcome(
    id: str,
    observation_window_minutes: int = Query(60, ge=1, le=1440),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        exec_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution UUID.")

    try:
        execution = await agent_orchestrator.advance_outcome_and_memory(
            db=db,
            execution_id=exec_uuid,
            tenant_id=tenant_id,
            observation_window_minutes=observation_window_minutes,
        )
        return {
            "id": str(execution.id),
            "current_state": execution.current_state,
            "execution_status": execution.execution_status,
            "message": f"Execution outcome verified and operational memory updated. Current state is '{execution.current_state}'.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------------
# Deployment Policies
# --------------------------------------------------------------------------

@router.get("/policies")
async def list_deployment_policies(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(DeploymentPolicy)
        .where(DeploymentPolicy.tenant_id == tenant_id)
        .order_by(desc(DeploymentPolicy.created_at))
    )
    res = await db.execute(stmt)
    policies = res.scalars().all()

    if not policies:
        default_p = await agent_policy_engine.get_or_create_default_policy(db, tenant_id)
        await db.commit()
        policies = [default_p]

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "policy_version": p.policy_version,
            "enabled": p.enabled,
            "policy_definition": p.policy_definition or {},
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in policies
    ]


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_deployment_policy(
    req: CreateDeploymentPolicyRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    policy = DeploymentPolicy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=req.name,
        description=req.description,
        policy_version=req.policy_version or "v1.0.0",
        enabled=req.enabled,
        policy_definition=req.policy_definition,
        created_at=now,
        updated_at=now,
    )
    db.add(policy)
    await db.commit()
    return {
        "id": str(policy.id),
        "name": policy.name,
        "policy_version": policy.policy_version,
        "enabled": policy.enabled,
    }


@router.patch("/policies/{id}")
async def update_deployment_policy(
    id: str,
    req: UpdateDeploymentPolicyRequest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        policy_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid policy UUID.")

    stmt = select(DeploymentPolicy).where(
        and_(DeploymentPolicy.id == policy_uuid, DeploymentPolicy.tenant_id == tenant_id)
    )
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Deployment policy not found.")

    if req.name is not None:
        policy.name = req.name
    if req.description is not None:
        policy.description = req.description
    if req.policy_version is not None:
        policy.policy_version = req.policy_version
    if req.enabled is not None:
        policy.enabled = req.enabled
    if req.policy_definition is not None:
        policy.policy_definition = req.policy_definition

    policy.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "id": str(policy.id),
        "name": policy.name,
        "policy_version": policy.policy_version,
        "enabled": policy.enabled,
        "updated_at": policy.updated_at,
    }
