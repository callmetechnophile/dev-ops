import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index, Text, DateTime
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
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    severity = Column(String(20), default="P2", nullable=False)  # P1, P2, P3, P4
    status = Column(String(50), default="OPEN", nullable=False, index=True)  # OPEN, MITIGATING, RESOLVED, CLOSED
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    blast_radius_score = Column(Float, default=1.0, nullable=False)
    embedding = Column(EmbeddingVector(1536), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    deployment = relationship("Deployment", back_populates="incidents")
    failures = relationship("Failure", back_populates="incident", cascade="all, delete-orphan")
    hypotheses = relationship("RootCauseHypothesis", back_populates="incident", cascade="all, delete-orphan")
    confirmed_root_cause = relationship("ConfirmedRootCause", back_populates="incident", uselist=False)


class Failure(Base, TimestampMixin, TenantMixin):
    __tablename__ = "failures"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    failure_type = Column(
        String(100),
        nullable=False,
        index=True
    )  # CrashLoopBackOff, ImagePullBackOff, OOMKilled, DatabaseConnectionExhaustion, 5xxErrorSpike
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    container_name = Column(String(255), nullable=True)
    pod_name = Column(String(255), nullable=True)
    exit_code = Column(Integer, nullable=True)

    incident = relationship("Incident", back_populates="failures")


class RootCauseHypothesis(Base, TimestampMixin, TenantMixin):
    __tablename__ = "root_cause_hypotheses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    change_id = Column(GUID(), ForeignKey("changes.id", ondelete="SET NULL"), nullable=True)
    infrastructure_change_id = Column(GUID(), ForeignKey("infrastructure_changes.id", ondelete="SET NULL"), nullable=True)
    hypothesis_statement = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.5, nullable=False)  # 0.0 to 1.0
    status = Column(String(50), default="SUSPECTED_CAUSE", nullable=False)  # SUSPECTED_CAUSE, PROBABLE_CAUSE, DISPROVEN
    evidence_summary = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="hypotheses")


class ConfirmedRootCause(Base, TimestampMixin, TenantMixin):
    __tablename__ = "confirmed_root_causes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    incident_id = Column(GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    confirmed_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    root_cause_summary = Column(Text, nullable=False)
    verified_engineering_lesson = Column(Text, nullable=False)
    prevention_strategy = Column(Text, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=False)
    embedding = Column(EmbeddingVector(1536), nullable=True)

    incident = relationship("Incident", back_populates="confirmed_root_cause")
