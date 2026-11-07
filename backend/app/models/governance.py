import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, Index, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class ApprovalRequest(Base, TimestampMixin, TenantMixin):
    __tablename__ = "approval_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(GUID(), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id = Column(GUID(), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_action = Column(String(100), nullable=False)  # DEPLOY_TO_PRODUCTION, PROCEED_CANARY_ROLLOUT, ABORT_DEPLOYMENT
    status = Column(String(50), default="WAITING_FOR_APPROVAL", nullable=False, index=True)  # WAITING_FOR_APPROVAL, APPROVED, REJECTED, EXPIRED
    expires_at = Column(DateTime(timezone=True), nullable=True)
    context_data = Column(JSON, default=dict, nullable=False)

    recommendation = relationship("Recommendation", back_populates="approval_requests")
    decisions = relationship("ApprovalDecision", back_populates="approval_request", cascade="all, delete-orphan")


class ApprovalDecision(Base, TimestampMixin, TenantMixin):
    __tablename__ = "approval_decisions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    approval_request_id = Column(GUID(), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    decided_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision = Column(String(20), nullable=False)  # APPROVED, REJECTED
    justification = Column(Text, nullable=False)
    audit_signature = Column(String(255), nullable=False)  # Cryptographic SHA-256 audit fingerprint
    decided_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    approval_request = relationship("ApprovalRequest", back_populates="decisions")
