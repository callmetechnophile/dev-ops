from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class BuildRead(BaseModel):
    id: str
    repository_id: str
    commit_sha: str
    workflow_run_id: Optional[str] = None
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


class DeploymentEventRead(BaseModel):
    id: str
    deployment_id: str
    github_deployment_id: Optional[str] = None
    github_deployment_status_id: Optional[str] = None
    status: str
    environment: str
    creator_login: Optional[str] = None
    description: Optional[str] = None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeploymentRead(BaseModel):
    id: str
    tenant_id: str
    service_id: str
    build_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    github_deployment_id: Optional[str] = None
    environment: str
    commit_sha: str
    status: str
    triggered_by: str
    creator_login: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    metadata_json: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class DeploymentTimelineItem(BaseModel):
    step_type: str  # commit, pr_merged, build_started, build_finished, deployment_started, deployment_status, approval
    title: str
    description: Optional[str] = None
    status: str
    timestamp: datetime
    actor: Optional[str] = None
    reference_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class DeploymentTimelineRead(BaseModel):
    deployment_id: str
    environment: str
    commit_sha: str
    current_status: str
    timeline: List[DeploymentTimelineItem]
