"""Agent State Machine & State Transition Engine.

Enforces:
- Strict 16-state lifecycle.
- Deterministic transition validation matrix.
- Immutable transition persistence in `agent_state_transitions`.
- LLM response transition containment (LLMs cannot bypass validation).
- Safe timeout and expiration handling.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentExecution, AgentStateTransition

logger = logging.getLogger(__name__)

# The 16 required states
STATE_DEPLOYMENT_DETECTED = "DEPLOYMENT_DETECTED"
STATE_CONTEXT_COLLECTION = "CONTEXT_COLLECTION"
STATE_CONTEXT_VALIDATION = "CONTEXT_VALIDATION"
STATE_HISTORICAL_RETRIEVAL = "HISTORICAL_RETRIEVAL"
STATE_RISK_ASSESSMENT = "RISK_ASSESSMENT"
STATE_POLICY_EVALUATION = "POLICY_EVALUATION"
STATE_RECOMMENDATION_GENERATION = "RECOMMENDATION_GENERATION"
STATE_WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
STATE_APPROVED = "APPROVED"
STATE_REJECTED = "REJECTED"
STATE_EXPIRED = "EXPIRED"
STATE_POST_DEPLOYMENT_MONITORING = "POST_DEPLOYMENT_MONITORING"
STATE_OUTCOME_VERIFICATION = "OUTCOME_VERIFICATION"
STATE_MEMORY_UPDATE = "MEMORY_UPDATE"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"

ALL_STATES = {
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
}

# Strict Transition Validation Matrix
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    STATE_DEPLOYMENT_DETECTED: {STATE_CONTEXT_COLLECTION, STATE_FAILED},
    STATE_CONTEXT_COLLECTION: {STATE_CONTEXT_VALIDATION, STATE_FAILED},
    STATE_CONTEXT_VALIDATION: {STATE_HISTORICAL_RETRIEVAL, STATE_FAILED},
    STATE_HISTORICAL_RETRIEVAL: {STATE_RISK_ASSESSMENT, STATE_FAILED},
    STATE_RISK_ASSESSMENT: {STATE_POLICY_EVALUATION, STATE_FAILED},
    STATE_POLICY_EVALUATION: {STATE_RECOMMENDATION_GENERATION, STATE_FAILED},
    STATE_RECOMMENDATION_GENERATION: {STATE_WAITING_FOR_APPROVAL, STATE_APPROVED, STATE_REJECTED, STATE_FAILED},
    STATE_WAITING_FOR_APPROVAL: {STATE_APPROVED, STATE_REJECTED, STATE_EXPIRED, STATE_FAILED},
    STATE_APPROVED: {STATE_POST_DEPLOYMENT_MONITORING, STATE_COMPLETED, STATE_FAILED},
    STATE_REJECTED: {STATE_COMPLETED, STATE_FAILED},
    STATE_EXPIRED: {STATE_COMPLETED, STATE_FAILED},
    STATE_POST_DEPLOYMENT_MONITORING: {STATE_OUTCOME_VERIFICATION, STATE_FAILED},
    STATE_OUTCOME_VERIFICATION: {STATE_MEMORY_UPDATE, STATE_COMPLETED, STATE_FAILED},
    STATE_MEMORY_UPDATE: {STATE_COMPLETED, STATE_FAILED},
    STATE_COMPLETED: set(),  # Terminal
    STATE_FAILED: {STATE_CONTEXT_COLLECTION},  # Only retry transitions from FAILED back to initial collection
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, current_state: str, target_state: str, reason: str = ""):
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        super().__init__(f"Invalid agent state transition: '{current_state}' -> '{target_state}'. {reason}")


class AgentStateMachine:
    """State machine controller for predictive DevOps agent executions."""

    def can_transition(self, current_state: str, target_state: str) -> bool:
        if current_state not in VALID_TRANSITIONS:
            return False
        return target_state in VALID_TRANSITIONS[current_state]

    async def transition(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        next_state: str,
        reason: str,
        triggered_by: str = "SYSTEM_ORCHESTRATOR",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentStateTransition:
        """Validates and applies a state transition, persisting the audit transition record."""
        current_state = execution.current_state

        if next_state not in ALL_STATES:
            raise InvalidStateTransitionError(current_state, next_state, "Target state is unknown.")

        if not self.can_transition(current_state, next_state):
            raise InvalidStateTransitionError(
                current_state,
                next_state,
                f"Valid next states from '{current_state}' are: {list(VALID_TRANSITIONS.get(current_state, set()))}"
            )

        now = datetime.now(timezone.utc)

        # Create state transition audit record
        transition_record = AgentStateTransition(
            id=uuid.uuid4(),
            tenant_id=execution.tenant_id,
            execution_id=execution.id,
            previous_state=current_state,
            next_state=next_state,
            transition_reason=reason,
            triggered_by=triggered_by,
            payload=payload or {},
            created_at=now,
        )
        db.add(transition_record)

        # Update execution current state
        execution.current_state = next_state
        if next_state == STATE_WAITING_FOR_APPROVAL:
            execution.execution_status = "WAITING_FOR_APPROVAL"
        elif next_state == STATE_COMPLETED:
            execution.execution_status = "COMPLETED"
            execution.completed_at = now
        elif next_state == STATE_FAILED:
            execution.execution_status = "FAILED"
            execution.last_error = reason
            execution.completed_at = now
        elif next_state in (STATE_APPROVED, STATE_POST_DEPLOYMENT_MONITORING, STATE_OUTCOME_VERIFICATION, STATE_MEMORY_UPDATE):
            execution.execution_status = "RUNNING"

        await db.flush()
        logger.info(f"AgentExecution {execution.id} transitioned: {current_state} -> {next_state} ({reason})")
        return transition_record


agent_state_machine = AgentStateMachine()
