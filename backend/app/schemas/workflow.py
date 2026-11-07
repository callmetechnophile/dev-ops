from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class WorkflowJobRead(BaseModel):
    id: str
    workflow_run_id: str
    github_job_id: str
    name: str
    status: str
    conclusion: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    runner_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowRunRead(BaseModel):
    id: str
    repository_id: str
    commit_id: Optional[str] = None
    github_run_id: str
    name: str
    head_sha: str
    head_branch: str
    event: str
    status: str
    conclusion: Optional[str] = None
    run_number: int
    run_attempt: int
    actor_login: Optional[str] = None
    duration_seconds: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    html_url: Optional[str] = None
    jobs: List[WorkflowJobRead] = []

    model_config = ConfigDict(from_attributes=True)


class BuildDetailRead(BaseModel):
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
    logs_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
