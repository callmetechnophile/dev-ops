import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.types import JSON
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class Event(Base, TimestampMixin, TenantMixin):
    __tablename__ = "events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), nullable=False)
    source = Column(String(100), nullable=False, index=True)  # github, docker, kubernetes, prometheus
    event_type = Column(String(100), nullable=False, index=True)  # commit.created, build.failed, deployment.started, etc.
    schema_version = Column(String(20), default="1.0.0", nullable=False)
    repository_id = Column(GUID(), nullable=True, index=True)
    service_id = Column(GUID(), nullable=True, index=True)
    deployment_id = Column(GUID(), nullable=True, index=True)
    commit_sha = Column(String(64), nullable=True, index=True)
    environment = Column(String(100), nullable=True, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    correlation_id = Column(String(255), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    payload = Column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_event_tenant_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_event_tenant_type_occurred", "tenant_id", "event_type", "occurred_at"),
    )
