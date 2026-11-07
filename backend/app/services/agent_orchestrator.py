"""Master Agent Orchestrator.

Coordinates the end-to-end predictive DevOps agent lifecycle across 16 states:
1. DEPLOYMENT_DETECTED
2. CONTEXT_COLLECTION
3. CONTEXT_VALIDATION
4. HISTORICAL_RETRIEVAL
5. RISK_ASSESSMENT
6. POLICY_EVALUATION
7. RECOMMENDATION_GENERATION
8. WAITING_FOR_APPROVAL
9. APPROVED
10. REJECTED
11. EXPIRED
12. POST_DEPLOYMENT_MONITORING
13. OUTCOME_VERIFICATION
14. MEMORY_UPDATE
15. COMPLETED
16. FAILED

Invariants:
- Never executes production modifications autonomously.
- Idempotent trigger handling (prevents duplicate runs for same deployment).
- Strict transition validation enforced by `agent_state_machine`.
- Resilient retry handling and audit trails.
"""

from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import (
    AgentExecution,
    AgentStateTransition,
    DeploymentPolicy,
    PolicyEvaluation,
    OutcomeObservation,
)
from app.models.deployment import Deployment
from app.models.governance import ApprovalRequest, ApprovalDecision
from app.models.organization import User
from app.services.agent_state_machine import (
    agent_state_machine,
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
)
from app.services.agent_recommendation_engine import agent_recommendation_engine
from app.services.agent_approval_manager import agent_approval_manager
from app.services.agent_outcome_monitor import agent_outcome_monitor
from app.services.agent_memory_updater import agent_memory_updater
from app.services.risk_assessment_service import risk_assessment_service

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Master controller orchestrating agent executions through state transitions."""

    async def trigger_deployment_analysis(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deployment_id: uuid.UUID,
        trigger_type: str = "DEPLOYMENT_CREATED",
        trigger_reference: Optional[str] = None,
    ) -> AgentExecution:
        """Entrypoint for deployment events. Orchestrates pre-flight intelligence up to approval gate."""
        now = datetime.now(timezone.utc)

        # 1. Fetch deployment
        dep_stmt = (
            select(Deployment)
            .where(and_(Deployment.id == deployment_id, Deployment.tenant_id == tenant_id))
            .options(selectinload(Deployment.service))
        )
        dep_res = await db.execute(dep_stmt)
        dep = dep_res.scalar_one_or_none()
        if not dep:
            raise ValueError(f"Deployment {deployment_id} not found in tenant.")

        ref = trigger_reference or str(dep.commit_sha or dep.id)

        # 2. Idempotency Check: Look for existing active execution for this deployment
        existing_stmt = select(AgentExecution).where(
            and_(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.deployment_id == deployment_id,
                AgentExecution.execution_status.in_(["RUNNING", "WAITING_FOR_APPROVAL"]),
            )
        )
        existing_res = await db.execute(existing_stmt)
        existing_exec = existing_res.scalars().first()
        if existing_exec:
            logger.info(f"Returning existing active execution {existing_exec.id} for deployment {deployment_id}")
            return existing_exec

        # 3. Initialize AgentExecution: DEPLOYMENT_DETECTED
        execution = AgentExecution(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            trigger_type=trigger_type,
            trigger_reference=ref,
            deployment_id=dep.id,
            service_id=dep.service_id,
            environment=dep.environment,
            current_state=STATE_DEPLOYMENT_DETECTED,
            execution_status="RUNNING",
            context_snapshot={},
            missing_context=[],
            retry_count=0,
            started_at=now,
        )
        db.add(execution)
        await db.flush()

        # Record initial detected transition
        await agent_state_machine.transition(
            db=db,
            execution=execution,
            next_state=STATE_CONTEXT_COLLECTION,
            reason=f"Deployment {dep.id} detected in environment {dep.environment}. Initiating context collection.",
            triggered_by="SYSTEM_ORCHESTRATOR",
            payload={"deployment_id": str(dep.id), "commit_sha": dep.commit_sha},
        )

        try:
            # 4. CONTEXT_COLLECTION
            context = await agent_context_collector.collect_context(db, tenant_id, dep)
            execution.context_snapshot = context.model_dump(mode="json")
            execution.missing_context = context.missing_context

            # 5. Transition to CONTEXT_VALIDATION
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_CONTEXT_VALIDATION,
                reason=f"Collected context across GitHub, operational memory, and infrastructure. Missing: {len(context.missing_context)} fields.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )

            # 6. Transition to HISTORICAL_RETRIEVAL
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_HISTORICAL_RETRIEVAL,
                reason="Querying verified operational memory for incident patterns and confirmed root causes.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )

            # 7. Transition to RISK_ASSESSMENT
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_RISK_ASSESSMENT,
                reason="Synthesizing pre-deployment feature vectors, deterministic rules, and blast radius.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )

            # Run Risk Assessment Engine
            ra_res = await risk_assessment_service.assess_deployment(db, tenant_id, dep.id)

            # Fetch the persisted RiskAssessment model
            from app.models.intelligence import RiskAssessment

            ra_stmt = select(RiskAssessment).where(RiskAssessment.id == uuid.UUID(ra_res.id))
            ra_obj_res = await db.execute(ra_stmt)
            risk_record = ra_obj_res.scalar_one()

            # 8. Transition to POLICY_EVALUATION
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_POLICY_EVALUATION,
                reason=f"Risk assessed: {risk_record.risk_level} (Score: {risk_record.overall_risk_score:.2f}, Impact: {risk_record.operational_impact_score:.2f}). Evaluating enterprise policies.",
                triggered_by="SYSTEM_ORCHESTRATOR",
                payload={"risk_level": risk_record.risk_level, "score": risk_record.overall_risk_score},
            )

            policy_evals = await agent_policy_engine.evaluate_policies(
                db=db,
                execution=execution,
                context=context,
                risk_score=risk_record.overall_risk_score,
                impact_score=risk_record.operational_impact_score,
                risk_level=risk_record.risk_level,
            )

            # 9. Transition to RECOMMENDATION_GENERATION
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_RECOMMENDATION_GENERATION,
                reason="Synthesizing actionable recommendations and mitigation procedures.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )

            recommendations = await agent_recommendation_engine.generate_recommendations(
                db=db,
                execution=execution,
                risk_assessment=risk_record,
                policy_evaluations=policy_evals,
                context=context,
            )

            # 10. Determine Approval Gate
            # If any policy requires approval or additional review or recommendation requires approval
            requires_approval = any(
                pe.outcome in (OUTCOME_REQUIRE_APPROVAL, OUTCOME_REQUIRE_ADDITIONAL_REVIEW, OUTCOME_RECOMMEND_DELAY)
                for pe in policy_evals
            ) or any(r.requires_approval == "true" for r in recommendations)

            if requires_approval:
                # Create ApprovalRequest and wait
                primary_rec = recommendations[0] if recommendations else None
                app_req = await agent_approval_manager.create_approval_request(
                    db=db,
                    execution=execution,
                    recommendation=primary_rec,
                    policy_version=policy_evals[0].policy_version if policy_evals else "v1.0.0",
                    risk_assessment_version=risk_record.model_version or "1.0.0",
                )

                await agent_state_machine.transition(
                    db=db,
                    execution=execution,
                    next_state=STATE_WAITING_FOR_APPROVAL,
                    reason=f"Deployment policy or risk severity requires human authorization. Created ApprovalRequest #{str(app_req.id)[:8]}.",
                    triggered_by="SYSTEM_ORCHESTRATOR",
                    payload={"approval_request_id": str(app_req.id)},
                )
            else:
                # Allowed without manual review
                await agent_state_machine.transition(
                    db=db,
                    execution=execution,
                    next_state=STATE_APPROVED,
                    reason="Deployment policy evaluated: ALLOW_WITHOUT_ADDITIONAL_REVIEW. Auto-approved per organizational policy.",
                    triggered_by="POLICY_ENGINE",
                )
                await agent_state_machine.transition(
                    db=db,
                    execution=execution,
                    next_state=STATE_POST_DEPLOYMENT_MONITORING,
                    reason="Entering observation window for post-rollout outcome verification.",
                    triggered_by="SYSTEM_ORCHESTRATOR",
                )

            await db.commit()
            return execution

        except Exception as e:
            logger.error(f"Error during agent execution {execution.id}: {e}", exc_info=True)
            await db.rollback()
            # In a new sub-transaction, mark execution as failed
            try:
                execution.last_error = str(e)
                await agent_state_machine.transition(
                    db=db,
                    execution=execution,
                    next_state=STATE_FAILED,
                    reason=f"Execution halted due to error: {str(e)}",
                    triggered_by="SYSTEM_ORCHESTRATOR",
                )
                await db.commit()
            except Exception:
                pass
            raise

    async def handle_human_decision(
        self,
        db: AsyncSession,
        request_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user: User,
        action: str,  # APPROVE, REJECT, REQUEST_MORE_INFORMATION, ESCALATE
        notes: str,
    ) -> Tuple[AgentExecution, ApprovalRequest, ApprovalDecision]:
        """Processes an authenticated human approval decision and advances agent state accordingly."""
        req, decision = await agent_approval_manager.record_decision(
            db=db,
            request_id=request_id,
            tenant_id=tenant_id,
            user=user,
            action=action,
            notes=notes,
        )

        if not req.execution_id:
            raise ValueError(f"ApprovalRequest {request_id} is not linked to an AgentExecution.")

        exec_stmt = select(AgentExecution).where(AgentExecution.id == req.execution_id)
        exec_res = await db.execute(exec_stmt)
        execution = exec_res.scalar_one()

        if action == "APPROVE":
            # Transition WAITING_FOR_APPROVAL -> APPROVED
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_APPROVED,
                reason=f"Approved by authorized reviewer {user.email}: {notes}",
                triggered_by="HUMAN_APPROVER",
                payload={
                    "decision_id": str(decision.id),
                    "reviewer": user.email,
                    "signature": decision.audit_signature,
                },
            )
            # Advance APPROVED -> POST_DEPLOYMENT_MONITORING
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_POST_DEPLOYMENT_MONITORING,
                reason="Deployment authorized. Entering post-deployment outcome observation window.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )
        elif action == "REJECT":
            # Transition WAITING_FOR_APPROVAL -> REJECTED
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_REJECTED,
                reason=f"Rejected by reviewer {user.email}: {notes}",
                triggered_by="HUMAN_APPROVER",
                payload={"decision_id": str(decision.id), "reviewer": user.email},
            )
            # Advance REJECTED -> COMPLETED
            await agent_state_machine.transition(
                db=db,
                execution=execution,
                next_state=STATE_COMPLETED,
                reason="Execution closed following human rejection.",
                triggered_by="SYSTEM_ORCHESTRATOR",
            )

        await db.commit()
        return execution, req, decision

    async def advance_outcome_and_memory(
        self,
        db: AsyncSession,
        execution_id: uuid.UUID,
        tenant_id: uuid.UUID,
        observation_window_minutes: int = 60,
    ) -> AgentExecution:
        """Evaluates observed deployment outcomes and synthesizes memory lessons."""
        exec_stmt = select(AgentExecution).where(
            and_(AgentExecution.id == execution_id, AgentExecution.tenant_id == tenant_id)
        )
        exec_res = await db.execute(exec_stmt)
        execution = exec_res.scalar_one_or_none()
        if not execution:
            raise ValueError(f"AgentExecution {execution_id} not found.")

        # Ensure we are in POST_DEPLOYMENT_MONITORING
        if execution.current_state != STATE_POST_DEPLOYMENT_MONITORING:
            if execution.current_state == STATE_APPROVED:
                await agent_state_machine.transition(
                    db=db,
                    execution=execution,
                    next_state=STATE_POST_DEPLOYMENT_MONITORING,
                    reason="Advancing approved execution to post-deployment monitoring.",
                    triggered_by="SYSTEM_ORCHESTRATOR",
                )
            else:
                raise ValueError(f"Cannot advance outcome from current state '{execution.current_state}'.")

        # 1. Transition to OUTCOME_VERIFICATION
        await agent_state_machine.transition(
            db=db,
            execution=execution,
            next_state=STATE_OUTCOME_VERIFICATION,
            reason="Inspecting post-rollout deployment status, incidents, and telemetry.",
            triggered_by="SYSTEM_ORCHESTRATOR",
        )

        outcome_report = await agent_outcome_monitor.monitor_outcome(
            db=db,
            execution=execution,
            observation_window_minutes=observation_window_minutes,
        )

        # 2. Transition to MEMORY_UPDATE
        await agent_state_machine.transition(
            db=db,
            execution=execution,
            next_state=STATE_MEMORY_UPDATE,
            reason=f"Outcome observed: {outcome_report.overall_outcome}. Updating operational memory and lineage records.",
            triggered_by="SYSTEM_ORCHESTRATOR",
            payload={"outcome": outcome_report.overall_outcome, "verified": outcome_report.is_verified},
        )

        await agent_memory_updater.update_memory_with_outcome(
            db=db,
            execution=execution,
            outcome_value=outcome_report.overall_outcome,
            evidence={"summary": outcome_report.summary, "observations": outcome_report.observations},
        )

        # 3. Transition to COMPLETED
        await agent_state_machine.transition(
            db=db,
            execution=execution,
            next_state=STATE_COMPLETED,
            reason="Agent execution lifecycle completed successfully.",
            triggered_by="SYSTEM_ORCHESTRATOR",
        )

        await db.commit()
        return execution

    async def expire_pending_approvals(self, db: AsyncSession) -> int:
        """Watchdog cron/task to expire overdue approval requests and close executions."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ApprovalRequest)
            .where(
                and_(
                    ApprovalRequest.status == "WAITING_FOR_APPROVAL",
                    ApprovalRequest.expires_at < now,
                )
            )
            .options(selectinload(ApprovalRequest.agent_execution))
        )
        res = await db.execute(stmt)
        expired_reqs = res.scalars().all()
        count = 0

        for req in expired_reqs:
            req.status = "EXPIRED"
            if req.agent_execution and req.agent_execution.current_state == STATE_WAITING_FOR_APPROVAL:
                await agent_state_machine.transition(
                    db=db,
                    execution=req.agent_execution,
                    next_state=STATE_EXPIRED,
                    reason=f"Approval request expired at {req.expires_at.isoformat()}. Failing closed.",
                    triggered_by="TIMEOUT_WATCHDOG",
                )
                await agent_state_machine.transition(
                    db=db,
                    execution=req.agent_execution,
                    next_state=STATE_COMPLETED,
                    reason="Execution closed following approval expiration.",
                    triggered_by="TIMEOUT_WATCHDOG",
                )
            count += 1

        if count > 0:
            await db.commit()
        return count


agent_orchestrator = AgentOrchestrator()
