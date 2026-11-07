from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class ApprovalDecisionCreate(BaseModel):
    decision: str  # APPROVED, REJECTED
    justification: str
    user_id: str


class ApprovalDecisionRead(BaseModel):
    id: str
    approval_request_id: str
    decided_by_user_id: str
    decision: str
    justification: str
    audit_signature: str
    decided_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestRead(BaseModel):
    id: str
    tenant_id: str
    deployment_id: str
    recommendation_id: Optional[str] = None
    requested_action: str
    status: str
    expires_at: Optional[datetime] = None
    context_data: Dict[str, Any] = {}
    created_at: datetime
    decisions: List[ApprovalDecisionRead] = []

    model_config = ConfigDict(from_attributes=True)
