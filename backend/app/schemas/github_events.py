import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict


class GitHubCommitInfo(BaseModel):
    id: str
    message: Optional[str] = None
    timestamp: Optional[datetime] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    author_username: Optional[str] = None
    added: List[str] = []
    removed: List[str] = []
    modified: List[str] = []

    model_config = ConfigDict(extra="allow")


class PushEvent(BaseModel):
    """Normalized push event representation."""
    ref: str
    before: Optional[str] = None
    after: str  # Head commit SHA
    repository_id: Optional[str] = None
    repository_name: str
    repository_full_name: str
    owner_login: Optional[str] = None
    pusher_name: Optional[str] = None
    commits: List[GitHubCommitInfo] = []
    head_commit: Optional[GitHubCommitInfo] = None
    forced: bool = False
    created: bool = False
    deleted: bool = False
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class PullRequestEvent(BaseModel):
    """Normalized pull_request event representation."""
    action: str  # opened, closed, synchronize, reopened, etc.
    number: int
    pr_id: str
    title: str
    state: str  # open, closed
    is_merged: bool = False
    merged_at: Optional[datetime] = None
    head_sha: str
    head_branch: str
    base_branch: str
    author_login: Optional[str] = None
    repository_name: str
    repository_full_name: str
    html_url: Optional[str] = None
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class WorkflowRunEvent(BaseModel):
    """Normalized workflow_run event representation."""
    action: str  # requested, in_progress, completed
    run_id: str
    name: str
    head_sha: str
    head_branch: str
    event: str  # push, pull_request, etc.
    status: str  # queued, in_progress, completed
    conclusion: Optional[str] = None  # success, failure, cancelled, etc.
    run_number: int = 1
    run_attempt: int = 1
    actor_login: Optional[str] = None
    duration_seconds: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    repository_name: str
    repository_full_name: str
    html_url: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class WorkflowJobEvent(BaseModel):
    """Normalized workflow_job event representation."""
    action: str  # queued, in_progress, completed
    job_id: str
    run_id: str
    name: str
    status: str
    conclusion: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    runner_name: Optional[str] = None
    steps: List[Dict[str, Any]] = []
    repository_full_name: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class DeploymentEvent(BaseModel):
    """Normalized deployment and deployment_status event representation."""
    action: str  # created, updated
    deployment_id: str
    deployment_status_id: Optional[str] = None
    state: str  # pending, in_progress, success, failure, error
    environment: str = "production"
    commit_sha: str
    creator_login: Optional[str] = None
    description: Optional[str] = None
    repository_name: str
    repository_full_name: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
