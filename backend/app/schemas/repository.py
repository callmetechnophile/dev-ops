from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class RepositoryRead(BaseModel):
    id: str
    tenant_id: str
    github_repo_id: Optional[str] = None
    name: str
    full_name: str
    owner_login: Optional[str] = None
    provider: str
    default_branch: str
    clone_url: Optional[str] = None
    html_url: Optional[str] = None
    is_private: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitRead(BaseModel):
    id: str
    repository_id: str
    commit_sha: str
    github_commit_id: Optional[str] = None
    branch: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    author_login: Optional[str] = None
    message: Optional[str] = None
    html_url: Optional[str] = None
    stats_additions: int = 0
    stats_deletions: int = 0
    committed_at: datetime

    model_config = ConfigDict(from_attributes=True)
