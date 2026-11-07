import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Index, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class Commit(Base, TimestampMixin, TenantMixin):
    __tablename__ = "commits"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_sha = Column(String(64), nullable=False, index=True)
    branch = Column(String(255), default="main", nullable=False)
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    committed_at = Column(DateTime(timezone=True), nullable=False)

    changes = relationship("Change", back_populates="commit", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_commit_tenant_repo_sha", "tenant_id", "repository_id", "commit_sha", unique=True),
    )


class Change(Base, TimestampMixin, TenantMixin):
    __tablename__ = "changes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    commit_id = Column(GUID(), ForeignKey("commits.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False, index=True)
    change_type = Column(String(50), default="modified", nullable=False)  # added, modified, deleted, renamed
    additions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)
    patch_summary = Column(Text, nullable=True)

    commit = relationship("Commit", back_populates="changes")


class Build(Base, TimestampMixin, TenantMixin):
    __tablename__ = "builds"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_sha = Column(String(64), nullable=False, index=True)
    build_number = Column(Integer, nullable=True)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, running, succeeded, failed
    duration_seconds = Column(Float, nullable=True)
    docker_image_tag = Column(String(255), nullable=True)
    tests_passed = Column(Integer, default=0, nullable=False)
    tests_failed = Column(Integer, default=0, nullable=False)
    logs_summary = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    deployments = relationship("Deployment", back_populates="build")


class Deployment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "deployments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    build_id = Column(GUID(), ForeignKey("builds.id", ondelete="SET NULL"), nullable=True, index=True)
    environment = Column(String(100), default="production", nullable=False, index=True)
    commit_sha = Column(String(64), nullable=False, index=True)
    status = Column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True
    )  # DEPLOYMENT_DETECTED, CONTEXT_COLLECTION, HISTORICAL_RETRIEVAL, RISK_ASSESSMENT,
       # RECOMMENDATION_GENERATED, WAITING_FOR_APPROVAL, APPROVED, REJECTED,
       # IN_PROGRESS, SUCCEEDED, FAILED, ROLLED_BACK
    triggered_by = Column(String(255), default="github_action", nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    rollback_from_id = Column(GUID(), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    service = relationship("Service", back_populates="deployments")
    build = relationship("Build", back_populates="deployments")
    infrastructure_changes = relationship("InfrastructureChange", back_populates="deployment")
    risk_assessments = relationship("RiskAssessment", back_populates="deployment")
    incidents = relationship("Incident", back_populates="deployment")


class InfrastructureChange(Base, TimestampMixin, TenantMixin):
    __tablename__ = "infrastructure_changes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    change_category = Column(String(50), nullable=False)  # k8s_manifest, helm_chart, dockerfile, terraform, env_vars
    file_path = Column(String(512), nullable=False)
    diff_content = Column(Text, nullable=True)
    risk_level = Column(String(50), default="low", nullable=False)  # low, medium, high, critical

    deployment = relationship("Deployment", back_populates="infrastructure_changes")
