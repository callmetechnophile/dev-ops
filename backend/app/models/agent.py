import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Index, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class AgentExecution(Base, TimestampMixin, TenantMixin):
    __tablename__ = "agent_executions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    trigger_type = Column(String(100), nullable=False, index=True)  # DEPLOYMENT_CREATED, WEBHOOK_PUSH, MANUAL_DISPATCH, API_TRIGGER
    trigger_reference = Column(String(255), nullable=False, index=True)  # commit sha, deployment id, pr number
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True, index=True)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    environment = Column(String(100), default="production", nullable=False, index=True)

    current_state = Column(String(50), default="DEPLOYMENT_DETECTED", nullable=False, index=True)
    execution_status = Column(String(50), default="RUNNING", nullable=False, index=True)  # RUNNING, WAITING_FOR_APPROVAL, COMPLETED, FAILED, CANCELLED
    context_snapshot = Column(JSON, default=dict, nullable=False)
    missing_context = Column(JSON, default=list, nullable=False)
    
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    # Relationships
    deployment = relationship("Deployment", backref="agent_executions")
    transitions = relationship("AgentStateTransition", back_populates="execution", cascade="all, delete-orphan", order_by="AgentStateTransition.created_at")
    policy_evaluations = relationship("PolicyEvaluation", back_populates="execution", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="agent_execution", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="agent_execution", cascade="all, delete-orphan")
    outcome_observations = relationship("OutcomeObservation", back_populates="execution", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agent_exec_tenant_status", "tenant_id", "execution_status"),
        Index("ix_agent_exec_tenant_state", "tenant_id", "current_state"),
        Index("ix_agent_exec_trigger", "tenant_id", "trigger_type", "trigger_reference"),
    )


class AgentStateTransition(Base, TimestampMixin, TenantMixin):
    __tablename__ = "agent_state_transitions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    execution_id = Column(GUID(), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_state = Column(String(50), nullable=False)
    next_state = Column(String(50), nullable=False, index=True)
    transition_reason = Column(Text, nullable=False)
    triggered_by = Column(String(100), default="SYSTEM_ORCHESTRATOR", nullable=False)  # SYSTEM_ORCHESTRATOR, HUMAN_APPROVER, TIMEOUT_WATCHDOG, POLICY_ENGINE
    payload = Column(JSON, default=dict, nullable=False)

    execution = relationship("AgentExecution", back_populates="transitions")

    __table_args__ = (
        Index("ix_agent_trans_exec_order", "execution_id", "created_at"),
    )


class DeploymentPolicy(Base, TimestampMixin, TenantMixin):
    __tablename__ = "deployment_policies"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    policy_version = Column(String(50), default="v1.0.0", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    policy_definition = Column(JSON, default=dict, nullable=False)
    # policy_definition schema:
    # {
    #   "max_risk_score": 0.65,
    #   "max_impact_score": 0.80,
    #   "block_on_critical_incident": true,
    #   "require_approval_environments": ["production", "prod"],
    #   "require_additional_review_tier1": true,
    #   "require_ci_pass": true,
    #   "require_evidence_threshold": 0.50
    # }

    evaluations = relationship("PolicyEvaluation", back_populates="policy", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_dep_policy_tenant_name", "tenant_id", "name", unique=True),
    )


class PolicyEvaluation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "policy_evaluations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    execution_id = Column(GUID(), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(GUID(), ForeignKey("deployment_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_version = Column(String(50), default="v1.0.0", nullable=False)
    outcome = Column(String(50), nullable=False, index=True)  # ALLOW_WITHOUT_ADDITIONAL_REVIEW, REQUIRE_APPROVAL, REQUIRE_ADDITIONAL_REVIEW, RECOMMEND_DELAY, INSUFFICIENT_EVIDENCE
    evidence = Column(JSON, default=dict, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    execution = relationship("AgentExecution", back_populates="policy_evaluations")
    policy = relationship("DeploymentPolicy", back_populates="evaluations")


class OutcomeObservation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "outcome_observations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    execution_id = Column(GUID(), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_type = Column(String(100), nullable=False, index=True)  # DEPLOYMENT_STATUS, WORKFLOW_STATUS, BUILD_RESULT, INCIDENT_OCCURRENCE, ROLLBACK_SIGNAL, SLO_BREACH
    observation_value = Column(String(100), nullable=False, index=True)  # SUCCESS, FAILURE, ROLLBACK, INCIDENT, UNKNOWN, CENSORED
    evidence_reference = Column(JSON, default=dict, nullable=False)
    observed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    execution = relationship("AgentExecution", back_populates="outcome_observations")
    deployment = relationship("Deployment", backref="outcome_observations")
