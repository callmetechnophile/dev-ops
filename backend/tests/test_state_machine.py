import pytest
from app.services.state_machine import DeploymentStateMachine, AgentDeploymentState


def test_valid_state_machine_transitions():
    assert DeploymentStateMachine.can_transition(
        AgentDeploymentState.DEPLOYMENT_DETECTED,
        AgentDeploymentState.CONTEXT_COLLECTION
    )
    assert DeploymentStateMachine.can_transition(
        AgentDeploymentState.WAITING_FOR_APPROVAL,
        AgentDeploymentState.APPROVED
    )
    assert DeploymentStateMachine.can_transition(
        AgentDeploymentState.WAITING_FOR_APPROVAL,
        AgentDeploymentState.REJECTED
    )


def test_enforce_human_approval_invariant():
    # Agent cannot bypass approval straight from risk assessment to deployment execution
    assert not DeploymentStateMachine.can_transition(
        AgentDeploymentState.RISK_ASSESSMENT,
        AgentDeploymentState.APPROVED
    )
    assert not DeploymentStateMachine.can_transition(
        AgentDeploymentState.RECOMMENDATION_GENERATED,
        AgentDeploymentState.APPROVED
    )
    with pytest.raises(ValueError):
        DeploymentStateMachine.validate_transition(
            AgentDeploymentState.RECOMMENDATION_GENERATED,
            AgentDeploymentState.POST_DEPLOYMENT_MONITORING
        )
