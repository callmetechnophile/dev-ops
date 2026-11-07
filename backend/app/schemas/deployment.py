from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class BuildRead(BaseModel):
    id: str
    repository_id: str
    commit_sha: str
    build_number: Optional[int] = None
    status: str
    duration_seconds: Optional[float] = None
    docker_image_tag: Optional[str] = None
    tests_passed: int = 0
    tests_failed: int = 0

    model_config = ConfigDict(from_attributes=True)


class DeploymentCreate(BaseModel):
    service_id: str
    environment: str = "production"
    commit_sha: str
    triggered_by: str = "github_action"
    metadata_json: Dict[str, Any] = {}


class DeploymentRead(BaseModel):
    id: str
    tenant_id: str
    service_id: str
    build_id: Optional[str] = None
    environment: str
    commit_sha: str
    status: str
    triggered_by: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    metadata_json: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
