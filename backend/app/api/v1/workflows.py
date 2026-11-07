import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.github_entities import WorkflowRun, WorkflowJob
from app.models.deployment import Build
from app.schemas.workflow import WorkflowRunRead, WorkflowJobRead, BuildDetailRead
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["Workflows & Builds"])


@router.get("/workflows", response_model=PaginatedResponse[WorkflowRunRead])
async def list_workflows(
    repository_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    conclusion: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WorkflowRun).options(selectinload(WorkflowRun.jobs)).order_by(WorkflowRun.started_at.desc())
    if repository_id:
        stmt = stmt.where(WorkflowRun.repository_id == uuid.UUID(repository_id))
    if status_filter:
        stmt = stmt.where(WorkflowRun.status == status_filter)
    if conclusion:
        stmt = stmt.where(WorkflowRun.conclusion == conclusion)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
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
            jobs=[
                WorkflowJobRead(
                    id=str(j.id),
                    workflow_run_id=str(j.workflow_run_id),
                    github_job_id=j.github_job_id,
                    name=j.name,
                    status=j.status,
                    conclusion=j.conclusion,
                    started_at=j.started_at,
                    completed_at=j.completed_at,
                    runner_name=j.runner_name,
                )
                for j in w.jobs
            ],
        )
        for w in runs
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )


@router.get("/workflows/{id}", response_model=WorkflowRunRead)
async def get_workflow(id: str, db: AsyncSession = Depends(get_db)):
    try:
        run_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow UUID")

    stmt = select(WorkflowRun).where(WorkflowRun.id == run_uuid).options(selectinload(WorkflowRun.jobs))
    result = await db.execute(stmt)
    w = result.scalar_one_or_none()

    if not w:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    return WorkflowRunRead(
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
        jobs=[
            WorkflowJobRead(
                id=str(j.id),
                workflow_run_id=str(j.workflow_run_id),
                github_job_id=j.github_job_id,
                name=j.name,
                status=j.status,
                conclusion=j.conclusion,
                started_at=j.started_at,
                completed_at=j.completed_at,
                runner_name=j.runner_name,
            )
            for j in w.jobs
        ],
    )


@router.get("/builds", response_model=PaginatedResponse[BuildDetailRead])
async def list_builds(
    repository_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Build).order_by(Build.created_at.desc())
    if repository_id:
        stmt = stmt.where(Build.repository_id == uuid.UUID(repository_id))
    if status_filter:
        stmt = stmt.where(Build.status == status_filter)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    builds = result.scalars().all()

    items = [
        BuildDetailRead(
            id=str(b.id),
            repository_id=str(b.repository_id),
            commit_sha=b.commit_sha,
            workflow_run_id=str(b.workflow_run_id) if b.workflow_run_id else None,
            build_number=b.build_number,
            status=b.status,
            duration_seconds=b.duration_seconds,
            docker_image_tag=b.docker_image_tag,
            tests_passed=b.tests_passed,
            tests_failed=b.tests_failed,
            logs_summary=b.logs_summary,
            created_at=b.created_at,
        )
        for b in builds
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )


@router.get("/builds/{id}", response_model=BuildDetailRead)
async def get_build(id: str, db: AsyncSession = Depends(get_db)):
    try:
        b_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid build UUID")

    stmt = select(Build).where(Build.id == b_uuid)
    result = await db.execute(stmt)
    b = result.scalar_one_or_none()

    if not b:
        raise HTTPException(status_code=404, detail="Build not found")

    return BuildDetailRead(
        id=str(b.id),
        repository_id=str(b.repository_id),
        commit_sha=b.commit_sha,
        workflow_run_id=str(b.workflow_run_id) if b.workflow_run_id else None,
        build_number=b.build_number,
        status=b.status,
        duration_seconds=b.duration_seconds,
        docker_image_tag=b.docker_image_tag,
        tests_passed=b.tests_passed,
        tests_failed=b.tests_failed,
        logs_summary=b.logs_summary,
        created_at=b.created_at,
    )
