import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, ForeignKey, Index, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class RemediationAction(Base, TimestampMixin, TenantMixin):
    __tablename__ = "remediation_actions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    failure_id = Column(GUID(), ForeignKey("failures.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(
        String(100), nullable=False
    )  # ROLLBACK, CONFIG_PATCH, RESOURCE_QUOTA_BUMP, RESTART, DEPENDENCY_PIN
    description = Column(Text, nullable=False)
    runbook_url = Column(String(512), nullable=True)
    estimated_recovery_time_sec = Column(Float, nullable=True)
    is_automated_executable = Column(String(10), default="false", nullable=False)
    proposed_by = Column(String(255), default="SYSTEM", nullable=False)
    approved_by = Column(String(255), nullable=True)
    execution_status = Column(
        String(50), default="RECORDED", nullable=False
    )  # RECORDED, PROPOSED, APPROVED, EXECUTED, FAILED
    outcome = Column(String(50), nullable=True)  # SUCCESS, PARTIAL_SUCCESS, FAILED, UNKNOWN
    effectiveness = Column(String(50), nullable=True)  # HIGH, MEDIUM, LOW, INEFFECTIVE

    incident = relationship("Incident", back_populates="remediations")
    lessons = relationship("OperationalLesson", back_populates="remediation_action")


class RiskAssessment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "risk_assessments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    environment = Column(String(100), default="production", nullable=False, index=True)

    overall_risk_score = Column(Float, nullable=False)  # 0.00 to 1.00
    risk_level = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    risk_category = Column(String(50), default="LOW", nullable=False, index=True)
    failure_probability = Column(Float, nullable=True)  # Calibrated ML probability or None if Stage A
    operational_impact_score = Column(Float, nullable=False)  # Downstream blast radius impact (0.0 to 1.0)
    impact_category = Column(String(50), default="LOW", nullable=False)
    affected_services = Column(JSON, default=list, nullable=False)

    rule_score = Column(Float, default=0.0, nullable=False)
    ml_score = Column(Float, nullable=True)
    feature_snapshot = Column(JSON, default=dict, nullable=False)
    triggered_rules = Column(JSON, default=list, nullable=False)
    supporting_records = Column(JSON, default=list, nullable=False)
    supporting_incident_ids = Column(JSON, default=list, nullable=False)
    model_version = Column(String(100), nullable=True)
    calibration_version = Column(String(100), nullable=True)
    explanation = Column(Text, nullable=True)
    assessment_status = Column(String(50), default="COMPLETED", nullable=False)

    assessed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    deployment = relationship("Deployment", back_populates="risk_assessments")
    recommendations = relationship("Recommendation", back_populates="risk_assessment", cascade="all, delete-orphan")


class Recommendation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "recommendations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    risk_assessment_id = Column(
        GUID(), ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id = Column(GUID(), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_type = Column(
        String(50), nullable=False
    )  # PROCEED_WITH_CANARY, BLOCK_DEPLOYMENT, ROLLBACK_PREPARATION, REQUIRE_CONFIG_REVIEW, SCALE_DOWN
    title = Column(String(255), nullable=False)
    rationale = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    evidence_references = Column(JSON, default=dict, nullable=False)
    confidence_level = Column(String(20), default="MEDIUM", nullable=False)
    status = Column(String(50), default="PROPOSED", nullable=False)  # PROPOSED, ACCEPTED, REJECTED, SUPERSEDED
    mitigation_steps = Column(JSON, default=list, nullable=False)
    confidence_score = Column(Float, default=0.8, nullable=False)
    requires_approval = Column(String(10), default="true", nullable=False)

    risk_assessment = relationship("RiskAssessment", back_populates="recommendations")
    approval_requests = relationship("ApprovalRequest", back_populates="recommendation")
    agent_execution = relationship("AgentExecution", back_populates="recommendations")
