import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class NormalizedEventContract(BaseModel):
    """
    Unified, immutable event contract used across all integrations.
    Section 4 & Section 6 of Specification.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    source: str = Field(description="Integration source e.g. github, docker, kubernetes, prometheus")
    event_type: str = Field(
        description="Event category: push, pull_request, workflow_run, workflow_job, deployment, deployment_status"
    )
    schema_version: str = "1.0.0"
    repository_id: Optional[str] = None
    repository_name: Optional[str] = None
    commit_sha: Optional[str] = None
    workflow_run_id: Optional[str] = None
    deployment_id: Optional[str] = None
    environment: Optional[str] = "production"
    actor: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="allow")


class EventIngestResponse(BaseModel):
    accepted: bool
    event_id: str
    delivery_id: str
    idempotency_key: str
    status: str  # ingested, duplicate_ignored, queued, error
    message: str
