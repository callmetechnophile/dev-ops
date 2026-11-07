import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index, Text, DateTime, UniqueConstraint
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class EmbeddingVector(TypeDecorator):
    """Platform-independent embedding vector.
    Uses pgvector Vector in PostgreSQL if available, otherwise JSON.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dim=1536, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())


class Incident(Base, TimestampMixin, TenantMixin):
    __tablename__ = "incidents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_key = Column(
        String(100), nullable=False, default=lambda: f"INC-{uuid.uuid4().hex[:8].upper()}", index=True
    )
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    primary_service_id = Column(GUID(), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    incident_type = Column(String(100), default="UNKNOWN_FAILURE", nullable=False, index=True)
    severity = Column(String(20), default="P2", nullable=False)  # P1, P2, P3, P4
    status = Column(String(50), default="OPEN", nullable=False, index=True)  # OPEN, MITIGATING, RESOLVED, CLOSED
    environment = Column(String(100), default="production", nullable=False, index=True)

    first_observed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True, index=True
    )
    last_observed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True, index=True
    )
    detected_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    blast_radius_score = Column(Float, default=1.0, nullable=False)
    embedding = Column(EmbeddingVector(1536), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    deployment = relationship("Deployment", back_populates="incidents")
    failures = relationship("Failure", back_populates="incident", cascade="all, delete-orphan")
    hypotheses = relationship("RootCauseHypothesis", back_populates="incident", cascade="all, delete-orphan")
    confirmed_root_cause = relationship(
        "ConfirmedRootCause", back_populates="incident", uselist=False, cascade="all, delete-orphan"
    )
    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    classifications = relationship("FailureClassification", back_populates="incident", cascade="all, delete-orphan")
    remediations = relationship("RemediationAction", back_populates="incident", cascade="all, delete-orphan")
    lessons = relationship("OperationalLesson", back_populates="incident", cascade="all, delete-orphan")


class Failure(Base, TimestampMixin, TenantMixin):
    __tablename__ = "failures"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    failure_type = Column(
        String(100), nullable=False, index=True
    )  # CrashLoopBackOff, ImagePullBackOff, OOMKilled, DatabaseConnectionExhaustion, 5xxErrorSpike
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    container_name = Column(String(255), nullable=True)
    pod_name = Column(String(255), nullable=True)
    exit_code = Column(Integer, nullable=True)

    incident = relationship("Incident", back_populates="failures")


class IncidentEvent(Base, TimestampMixin, TenantMixin):
    __tablename__ = "incident_events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(
        String(50), default="correlated", nullable=False
    )  # triggering, contributing, correlated, recovery, monitoring
    relevance = Column(Float, default=1.0, nullable=False)

    incident = relationship("Incident", back_populates="events")
    event = relationship("Event")

    __table_args__ = (UniqueConstraint("incident_id", "event_id", name="uq_incident_event"),)


class FailureClassification(Base, TimestampMixin, TenantMixin):
    __tablename__ = "failure_classifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(
        String(100), nullable=False, index=True
    )  # BUILD_FAILURE, DEPLOYMENT_FAILURE, CONFIGURATION_FAILURE, INFRASTRUCTURE_FAILURE, UNKNOWN_FAILURE
    subcategory = Column(String(100), nullable=False, index=True)
    classification_method = Column(
        String(50), default="DETERMINISTIC_RULE", nullable=False
    )  # DETERMINISTIC_RULE, HEURISTIC, LLM_ASSISTED
    evidence = Column(JSON, default=dict, nullable=False)
    classifier_version = Column(String(50), default="1.0.0", nullable=False)

    incident = relationship("Incident", back_populates="classifications")


class RootCauseHypothesis(Base, TimestampMixin, TenantMixin):
    __tablename__ = "root_cause_hypotheses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    change_id = Column(GUID(), ForeignKey("changes.id", ondelete="SET NULL"), nullable=True)
    infrastructure_change_id = Column(
        GUID(), ForeignKey("infrastructure_changes.id", ondelete="SET NULL"), nullable=True
    )

    hypothesis = Column(Text, nullable=False)
    explanation = Column(Text, default="", nullable=False)
    evidence_event_ids = Column(JSON, default=list, nullable=False)
    confidence_level = Column(String(50), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, INSUFFICIENT_EVIDENCE
    confidence_score = Column(Float, default=0.5, nullable=False)  # 0.0 to 1.0 (legacy compatibility)
    status = Column(
        String(50), default="SUSPECTED", nullable=False
    )  # SUSPECTED, PROBABLE, CONFIRMED, REJECTED, UNKNOWN
    generated_by = Column(String(100), default="DETERMINISTIC_RULE_V1", nullable=False)
    evidence_summary = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="hypotheses")
    confirmed_root_cause = relationship("ConfirmedRootCause", back_populates="hypothesis", uselist=False)

    @property
    def hypothesis_statement(self):
        return self.hypothesis

    @hypothesis_statement.setter
    def hypothesis_statement(self, value):
        self.hypothesis = value


class ConfirmedRootCause(Base, TimestampMixin, TenantMixin):
    __tablename__ = "confirmed_root_causes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    hypothesis_id = Column(
        GUID(), ForeignKey("root_cause_hypotheses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confirmed_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by = Column(String(255), default="authorized_engineer", nullable=False)
    confirmation_notes = Column(Text, default="", nullable=False)

    root_cause_summary = Column(Text, nullable=False)
    verified_engineering_lesson = Column(Text, nullable=False)
    prevention_strategy = Column(Text, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    embedding = Column(EmbeddingVector(1536), nullable=True)

    incident = relationship("Incident", back_populates="confirmed_root_cause")
    hypothesis = relationship("RootCauseHypothesis", back_populates="confirmed_root_cause")
    lessons = relationship("OperationalLesson", back_populates="verified_root_cause", cascade="all, delete-orphan")


class OperationalLesson(Base, TimestampMixin, TenantMixin):
    __tablename__ = "operational_lessons"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    lesson = Column(Text, nullable=False)
    verified_root_cause_id = Column(
        GUID(), ForeignKey("confirmed_root_causes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_action_id = Column(
        GUID(), ForeignKey("remediation_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    applicability_conditions = Column(JSON, default=dict, nullable=False)
    verification_status = Column(String(50), default="VERIFIED", nullable=False)  # VERIFIED, ARCHIVED
    embedding = Column(EmbeddingVector(1536), nullable=True)

    incident = relationship("Incident", back_populates="lessons")
    verified_root_cause = relationship("ConfirmedRootCause", back_populates="lessons")
    remediation_action = relationship("RemediationAction", back_populates="lessons")
