import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Index, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class PullRequest(Base, TimestampMixin, TenantMixin):
    """
    GitHub Pull Request operational record.
    Correlates branch updates, reviews, and merges with downstream deployments.
    """

    __tablename__ = "pull_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_pr_id = Column(String(100), nullable=False, index=True)
    number = Column(Integer, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    state = Column(String(50), default="open", nullable=False, index=True)  # open, closed
    is_merged = Column(Boolean, default=False, nullable=False)
    merged_at = Column(DateTime(timezone=True), nullable=True)
    head_sha = Column(String(64), nullable=False, index=True)
    base_branch = Column(String(255), default="main", nullable=False)
    head_branch = Column(String(255), nullable=False)
    author_login = Column(String(255), nullable=True)
    html_url = Column(String(512), nullable=True)
    changed_files_count = Column(Integer, default=0, nullable=False)
    additions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)

    repository = relationship("Repository", back_populates="pull_requests")

    __table_args__ = (
        Index("ix_pr_tenant_repo_number", "tenant_id", "repository_id", "number", unique=True),
        Index("ix_pr_head_sha", "tenant_id", "head_sha"),
    )


class WorkflowRun(Base, TimestampMixin, TenantMixin):
    """
    GitHub Actions Workflow Run record.
    Tracks execution status, conclusion, run attempt, duration, and commit SHA.
    """

    __tablename__ = "workflow_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    commit_id = Column(GUID(), ForeignKey("commits.id", ondelete="SET NULL"), nullable=True, index=True)
    github_run_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    head_sha = Column(String(64), nullable=False, index=True)
    head_branch = Column(String(255), default="main", nullable=False)
    event = Column(String(100), default="push", nullable=False)  # push, pull_request, workflow_dispatch
    status = Column(String(50), default="queued", nullable=False, index=True)  # queued, in_progress, completed
    conclusion = Column(String(50), nullable=True, index=True)  # success, failure, cancelled, timed_out
    run_number = Column(Integer, default=1, nullable=False)
    run_attempt = Column(Integer, default=1, nullable=False)
    actor_login = Column(String(255), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    html_url = Column(String(512), nullable=True)
    logs_url = Column(String(512), nullable=True)

    repository = relationship("Repository", back_populates="workflow_runs")
    commit = relationship("Commit", back_populates="workflow_runs")
    jobs = relationship("WorkflowJob", back_populates="workflow_run", cascade="all, delete-orphan")
    builds = relationship("Build", back_populates="workflow_run")
    deployments = relationship("Deployment", back_populates="workflow_run")

    __table_args__ = (
        Index("ix_run_tenant_github_id", "tenant_id", "github_run_id", unique=True),
        Index("ix_run_repo_head_sha", "repository_id", "head_sha"),
    )


class WorkflowJob(Base, TimestampMixin, TenantMixin):
    """
    Individual job within a GitHub Actions workflow run.
    """

    __tablename__ = "workflow_jobs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(GUID(), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    github_job_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="queued", nullable=False)  # queued, in_progress, completed
    conclusion = Column(String(50), nullable=True)  # success, failure, skipped, cancelled
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    runner_name = Column(String(255), nullable=True)
    steps_summary = Column(JSON, default=list, nullable=False)

    workflow_run = relationship("WorkflowRun", back_populates="jobs")

    __table_args__ = (Index("ix_job_tenant_github_id", "tenant_id", "github_job_id", unique=True),)


class DeploymentEvent(Base, TimestampMixin, TenantMixin):
    """
    Discrete deployment lifecycle events and status transitions.
    """

    __tablename__ = "deployment_events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    github_deployment_id = Column(String(100), nullable=True, index=True)
    github_deployment_status_id = Column(String(100), nullable=True, index=True)
    status = Column(String(50), nullable=False, index=True)  # pending, in_progress, success, failure, error, inactive
    environment = Column(String(100), default="production", nullable=False)
    creator_login = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)

    deployment = relationship("Deployment", back_populates="events")

    __table_args__ = (Index("ix_dep_event_time", "deployment_id", "occurred_at"),)
