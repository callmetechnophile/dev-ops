import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.service import Repository
from app.models.deployment import Commit
from app.models.github_entities import WorkflowRun
from app.schemas.repository import RepositoryRead, CommitRead
from app.schemas.workflow import WorkflowRunRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=PaginatedResponse[RepositoryRead])
async def list_repositories(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)
):
    stmt = select(Repository).order_by(Repository.full_name.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    repos = result.scalars().all()

    items = [
        RepositoryRead(
            id=str(r.id),
            tenant_id=str(r.tenant_id),
            github_repo_id=r.github_repo_id,
            name=r.name,
            full_name=r.full_name,
            owner_login=r.owner_login,
            provider=r.provider,
            default_branch=r.default_branch,
            clone_url=r.clone_url,
            html_url=r.html_url,
            is_private=r.is_private,
            created_at=r.created_at,
        )
        for r in repos
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )


@router.get("/{id}", response_model=RepositoryRead)
async def get_repository(id: str, db: AsyncSession = Depends(get_db)):
    try:
        repo_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository UUID")

    stmt = select(Repository).where(Repository.id == repo_uuid)
    result = await db.execute(stmt)
    r = result.scalar_one_or_none()

    if not r:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepositoryRead(
        id=str(r.id),
        tenant_id=str(r.tenant_id),
        github_repo_id=r.github_repo_id,
        name=r.name,
        full_name=r.full_name,
        owner_login=r.owner_login,
        provider=r.provider,
        default_branch=r.default_branch,
        clone_url=r.clone_url,
        html_url=r.html_url,
        is_private=r.is_private,
        created_at=r.created_at,
    )


@router.get("/{id}/commits", response_model=PaginatedResponse[CommitRead])
async def list_repository_commits(
    id: str,
    branch: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        repo_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository UUID")

    stmt = select(Commit).where(Commit.repository_id == repo_uuid)
    if branch:
        stmt = stmt.where(Commit.branch == branch)

    stmt = stmt.order_by(Commit.committed_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    commits = result.scalars().all()

    items = [
        CommitRead(
            id=str(c.id),
            repository_id=str(c.repository_id),
            commit_sha=c.commit_sha,
            github_commit_id=c.github_commit_id,
            branch=c.branch,
            author_name=c.author_name,
            author_email=c.author_email,
            author_login=c.author_login,
            message=c.message,
            html_url=c.html_url,
            stats_additions=c.stats_additions,
            stats_deletions=c.stats_deletions,
            committed_at=c.committed_at,
        )
        for c in commits
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )


@router.get("/{id}/workflows", response_model=PaginatedResponse[WorkflowRunRead])
async def list_repository_workflows(
    id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)
):
    try:
        repo_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository UUID")

    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.repository_id == repo_uuid)
        .order_by(WorkflowRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()

    items = [
        WorkflowRunRead(
            id=str(w.id),
            repository_id=str(w.repository_id),
            commit_id=str(w.commit_id) if w.commit_id else None,
            github_run_id=w.github_run_id,
            name=w.name,
            head_sha=w.head_sha,
            head_branch=w.head_branch,
            event=w.event,
            status=w.status,
            conclusion=w.conclusion,
            run_number=w.run_number,
            run_attempt=w.run_attempt,
            actor_login=w.actor_login,
            duration_seconds=w.duration_seconds,
            started_at=w.started_at,
            completed_at=w.completed_at,
            html_url=w.html_url,
            jobs=[],
        )
        for w in runs
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )
