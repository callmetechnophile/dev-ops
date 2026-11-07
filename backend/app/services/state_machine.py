import enum
from typing import List, Dict, Set


class AgentDeploymentState(str, enum.Enum):
    DEPLOYMENT_DETECTED = "DEPLOYMENT_DETECTED"
    CONTEXT_COLLECTION = "CONTEXT_COLLECTION"
    HISTORICAL_RETRIEVAL = "HISTORICAL_RETRIEVAL"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    RECOMMENDATION_GENERATED = "RECOMMENDATION_GENERATED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POST_DEPLOYMENT_MONITORING = "POST_DEPLOYMENT_MONITORING"
    OUTCOME_VERIFICATION = "OUTCOME_VERIFICATION"
    MEMORY_UPDATED = "MEMORY_UPDATED"


class DeploymentStateMachine:
    """
    Enforces valid transitions and strict approval gate invariants.
    Rule: Operational interventions CANNOT transition past WAITING_FOR_APPROVAL
    without an explicit, cryptographically signed approval decision.
    """

    ALLOWED_TRANSITIONS: Dict[AgentDeploymentState, Set[AgentDeploymentState]] = {
        AgentDeploymentState.DEPLOYMENT_DETECTED: {AgentDeploymentState.CONTEXT_COLLECTION},
        AgentDeploymentState.CONTEXT_COLLECTION: {AgentDeploymentState.HISTORICAL_RETRIEVAL},
        AgentDeploymentState.HISTORICAL_RETRIEVAL: {AgentDeploymentState.RISK_ASSESSMENT},
        AgentDeploymentState.RISK_ASSESSMENT: {AgentDeploymentState.RECOMMENDATION_GENERATED},
        AgentDeploymentState.RECOMMENDATION_GENERATED: {AgentDeploymentState.WAITING_FOR_APPROVAL},
        AgentDeploymentState.WAITING_FOR_APPROVAL: {
            AgentDeploymentState.APPROVED,
            AgentDeploymentState.REJECTED,
        },
        AgentDeploymentState.APPROVED: {AgentDeploymentState.POST_DEPLOYMENT_MONITORING},
        AgentDeploymentState.REJECTED: {AgentDeploymentState.MEMORY_UPDATED},
        AgentDeploymentState.POST_DEPLOYMENT_MONITORING: {AgentDeploymentState.OUTCOME_VERIFICATION},
        AgentDeploymentState.OUTCOME_VERIFICATION: {AgentDeploymentState.MEMORY_UPDATED},
        AgentDeploymentState.MEMORY_UPDATED: set(),
    }

    @classmethod
    def can_transition(cls, current_state: AgentDeploymentState, next_state: AgentDeploymentState) -> bool:
        return next_state in cls.ALLOWED_TRANSITIONS.get(current_state, set())

    @classmethod
    def validate_transition(cls, current_state: AgentDeploymentState, next_state: AgentDeploymentState) -> None:
        if not cls.can_transition(current_state, next_state):
            raise ValueError(
                f"Illegal state transition from {current_state.value} to {next_state.value}. "
                f"Human approval gating invariant violated."
            )
