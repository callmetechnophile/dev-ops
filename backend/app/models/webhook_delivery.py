import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index, Text
from sqlalchemy.types import JSON
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class WebhookDelivery(Base, TimestampMixin, TenantMixin):
    """
    Immutable ledger of all inbound webhook deliveries received from GitHub.
    Preserves raw payload and verification status for full traceability.
    """
    __tablename__ = "webhook_deliveries"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # push, workflow_run, pull_request, deployment, etc.
    signature = Column(String(255), nullable=True)
    status = Column(
        String(50),
        default="RECEIVED",
        nullable=False,
        index=True
    )  # RECEIVED, PUBLISHED, PROCESSED, DUPLICATE_IGNORED, FAILED
    payload = Column(JSON, default=dict, nullable=False)
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webhook_delivery_tenant_delivery", "tenant_id", "delivery_id", unique=True),
        Index("ix_webhook_delivery_status_time", "status", "received_at"),
    )
