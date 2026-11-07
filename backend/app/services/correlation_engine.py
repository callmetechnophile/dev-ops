import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.service import Repository, Service
from app.models.deployment import Commit, Change, Build, Deployment
from app.models.github_entities import PullRequest, WorkflowRun, WorkflowJob, DeploymentEvent
from app.models.event import Event
from app.schemas.event import NormalizedEventContract
from app.schemas.github_events import (
    PushEvent,
    PullRequestEvent,
    WorkflowRunEvent,
    WorkflowJobEvent,
    DeploymentEvent as DeploymentEventSchema,
)

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """
    Deterministic correlation engine linking repositories, commits, PRs,
    workflow runs, builds, and actual deployment events using stable external IDs.
    Section 7 of Specification.
    """

    async def get_or_create_repository(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        repo_full_name: str,
        repo_data: Optional[Dict[str, Any]] = None
    ) -> Repository:
        stmt = select(Repository).where(
            and_(
                Repository.tenant_id == tenant_id,
                Repository.full_name == repo_full_name
            )
        )
        result = await db.execute(stmt)
        repo = result.scalar_one_or_none()

        if not repo:
            parts = repo_full_name.split("/")
            repo_name = parts[-1] if parts else repo_full_name
            owner_login = parts[0] if len(parts) > 1 else None

            github_id = str(repo_data.get("id")) if repo_data and repo_data.get("id") else None
            html_url = repo_data.get("html_url") if repo_data else f"https://github.com/{repo_full_name}"

            repo = Repository(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=repo_name,
                full_name=repo_full_name,
                owner_login=owner_login,
                github_repo_id=github_id,
                provider="github",
                default_branch=(repo_data.get("default_branch") if repo_data else "main") or "main",
                html_url=html_url,
                is_private=(repo_data.get("private") if repo_data else False) or False
            )
            db.add(repo)
            await db.flush()

            # Ensure default service for repository
            svc_stmt = select(Service).where(
                and_(
                    Service.tenant_id == tenant_id,
                    Service.slug == repo_name.lower()
                )
            )
            svc_res = await db.execute(svc_stmt)
            service = svc_res.scalar_one_or_none()
            if not service:
                service = Service(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    repository_id=repo.id,
                    name=repo_name.replace("-", " ").title(),
                    slug=repo_name.lower(),
                    tier="tier-2",
                    health_status="healthy",
                    metadata_json={"source": "github_auto_discovered"}
                )
                db.add(service)
                await db.flush()

        return repo

    async def process_push_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event: PushEvent
    ) -> Tuple[Optional[Commit], int]:
        """Correlates commits and files modified from push event."""
        repo = await self.get_or_create_repository(
            db,
            tenant_id,
            event.repository_full_name,
            event.raw_payload.get("repository")
        )

        commits_added = 0
        head_commit_obj = None

        for c_info in event.commits:
            # Idempotent commit check
            stmt = select(Commit).where(
                and_(
                    Commit.tenant_id == tenant_id,
                    Commit.repository_id == repo.id,
                    Commit.commit_sha == c_info.id
                )
            )
            res = await db.execute(stmt)
            commit = res.scalar_one_or_none()

            if not commit:
                commit = Commit(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    repository_id=repo.id,
                    commit_sha=c_info.id,
                    github_commit_id=c_info.id,
                    branch=event.ref.replace("refs/heads/", ""),
                    author_name=c_info.author_name,
                    author_email=c_info.author_email,
                    author_login=c_info.author_username,
                    message=c_info.message or "",
                    html_url=f"{repo.html_url}/commit/{c_info.id}" if repo.html_url else None,
                    stats_additions=len(c_info.added),
                    stats_deletions=len(c_info.removed),
                    committed_at=c_info.timestamp or datetime.now(timezone.utc)
                )
                db.add(commit)
                await db.flush()
                commits_added += 1

                # Record file changes
                for fpath in c_info.added:
                    db.add(Change(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        commit_id=commit.id,
                        file_path=fpath,
                        change_type="added"
                    ))
                for fpath in c_info.modified:
                    db.add(Change(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        commit_id=commit.id,
                        file_path=fpath,
                        change_type="modified"
                    ))
                for fpath in c_info.removed:
                    db.add(Change(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        commit_id=commit.id,
                        file_path=fpath,
                        change_type="deleted"
                    ))

            if event.after and c_info.id == event.after:
                head_commit_obj = commit

        await db.flush()
        return head_commit_obj, commits_added

    async def process_pull_request_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event: PullRequestEvent
    ) -> PullRequest:
        """Correlates PR opened, closed, merged with repository and head commit."""
        repo = await self.get_or_create_repository(
            db,
            tenant_id,
            event.repository_full_name,
            event.raw_payload.get("repository")
        )

        stmt = select(PullRequest).where(
            and_(
                PullRequest.tenant_id == tenant_id,
                PullRequest.repository_id == repo.id,
                PullRequest.number == event.number
            )
        )
        res = await db.execute(stmt)
        pr = res.scalar_one_or_none()

        if not pr:
            pr = PullRequest(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                repository_id=repo.id,
                github_pr_id=event.pr_id,
                number=event.number,
                title=event.title,
                state=event.state,
                is_merged=event.is_merged,
                merged_at=event.merged_at,
                head_sha=event.head_sha,
                base_branch=event.base_branch,
                head_branch=event.head_branch,
                author_login=event.author_login,
                html_url=event.html_url,
                changed_files_count=event.changed_files,
                additions=event.additions,
                deletions=event.deletions
            )
            db.add(pr)
        else:
            # Update state, merge timestamp and head_sha
            pr.title = event.title
            pr.state = event.state
            pr.is_merged = event.is_merged
            pr.merged_at = event.merged_at or pr.merged_at
            pr.head_sha = event.head_sha or pr.head_sha
            pr.head_branch = event.head_branch
            pr.base_branch = event.base_branch

        await db.flush()
        return pr

    async def process_workflow_run_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event: WorkflowRunEvent
    ) -> WorkflowRun:
        """Correlates workflow execution to repository, commit, and build history."""
        repo = await self.get_or_create_repository(
            db,
            tenant_id,
            event.repository_full_name,
            event.raw_payload.get("repository")
        )

        # Correlate commit if exists
        commit_id = None
        if event.head_sha:
            c_stmt = select(Commit).where(
                and_(
                    Commit.tenant_id == tenant_id,
                    Commit.repository_id == repo.id,
                    Commit.commit_sha == event.head_sha
                )
            )
            c_res = await db.execute(c_stmt)
            commit = c_res.scalar_one_or_none()
            if commit:
                commit_id = commit.id

        # Idempotent lookup for workflow run
        stmt = select(WorkflowRun).where(
            and_(
                WorkflowRun.tenant_id == tenant_id,
                WorkflowRun.github_run_id == event.run_id
            )
        )
        res = await db.execute(stmt)
        run = res.scalar_one_or_none()

        if not run:
            run = WorkflowRun(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                repository_id=repo.id,
                commit_id=commit_id,
                github_run_id=event.run_id,
                name=event.name,
                head_sha=event.head_sha,
                head_branch=event.head_branch,
                event=event.event,
                status=event.status,
                conclusion=event.conclusion,
                run_number=event.run_number,
                run_attempt=event.run_attempt,
                actor_login=event.actor_login,
                duration_seconds=event.duration_seconds,
                started_at=event.started_at,
                completed_at=event.completed_at,
                html_url=event.html_url
            )
            db.add(run)
        else:
            run.status = event.status
            run.conclusion = event.conclusion
            run.run_attempt = event.run_attempt
            run.completed_at = event.completed_at or run.completed_at
            run.duration_seconds = event.duration_seconds or run.duration_seconds
            if commit_id and not run.commit_id:
                run.commit_id = commit_id

        await db.flush()

        # Correlate build history: if workflow is completed with conclusion, record build
        if event.status == "completed":
            b_stmt = select(Build).where(
                and_(
                    Build.tenant_id == tenant_id,
                    Build.repository_id == repo.id,
                    Build.commit_sha == event.head_sha,
                    Build.build_number == event.run_number
                )
            )
            b_res = await db.execute(b_stmt)
            build = b_res.scalar_one_or_none()

            build_status = "succeeded" if event.conclusion == "success" else "failed"
            if not build:
                build = Build(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    repository_id=repo.id,
                    commit_sha=event.head_sha,
                    workflow_run_id=run.id,
                    build_number=event.run_number,
                    status=build_status,
                    duration_seconds=event.duration_seconds,
                    logs_summary=f"GitHub Actions run '{event.name}' conclusion: {event.conclusion}",
                    metadata_json={"run_id": event.run_id, "attempt": event.run_attempt}
                )
                db.add(build)
            else:
                build.status = build_status
                build.duration_seconds = event.duration_seconds
                build.workflow_run_id = run.id

            await db.flush()

        return run

    async def process_workflow_job_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event: WorkflowJobEvent
    ) -> Optional[WorkflowJob]:
        """Correlates individual workflow job execution to parent workflow run."""
        r_stmt = select(WorkflowRun).where(
            and_(
                WorkflowRun.tenant_id == tenant_id,
                WorkflowRun.github_run_id == event.run_id
            )
        )
        r_res = await db.execute(r_stmt)
        run = r_res.scalar_one_or_none()
        if not run:
            logger.debug(f"WorkflowRun {event.run_id} not yet ingested, skipping job {event.job_id}")
            return None

        j_stmt = select(WorkflowJob).where(
            and_(
                WorkflowJob.tenant_id == tenant_id,
                WorkflowJob.github_job_id == event.job_id
            )
        )
        j_res = await db.execute(j_stmt)
        job = j_res.scalar_one_or_none()

        if not job:
            job = WorkflowJob(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                workflow_run_id=run.id,
                github_job_id=event.job_id,
                name=event.name,
                status=event.status,
                conclusion=event.conclusion,
                started_at=event.started_at,
                completed_at=event.completed_at,
                runner_name=event.runner_name,
                steps_summary=event.steps
            )
            db.add(job)
        else:
            job.status = event.status
            job.conclusion = event.conclusion
            job.completed_at = event.completed_at or job.completed_at
            job.steps_summary = event.steps

        await db.flush()
        return job

    async def process_deployment_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event: DeploymentEventSchema
    ) -> Deployment:
        """
        Correlates actual deployment lifecycle event to repository, service, and timeline.
        Mandate: Deployments are strictly created from verified deployment events.
        """
        repo = await self.get_or_create_repository(
            db,
            tenant_id,
            event.repository_full_name,
            event.raw_payload.get("repository")
        )

        # Find service associated with repository
        s_stmt = select(Service).where(
            and_(
                Service.tenant_id == tenant_id,
                Service.repository_id == repo.id
            )
        )
        s_res = await db.execute(s_stmt)
        service = s_res.scalar_one_or_none()
        if not service:
            # Fallback service
            service = Service(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                repository_id=repo.id,
                name=repo.name.replace("-", " ").title(),
                slug=repo.name.lower(),
                tier="tier-2",
                health_status="healthy",
                metadata_json={"source": "deployment_correlation"}
            )
            db.add(service)
            await db.flush()

        # Idempotent lookup by github_deployment_id
        d_stmt = select(Deployment).where(
            and_(
                Deployment.tenant_id == tenant_id,
                Deployment.github_deployment_id == event.deployment_id
            )
        )
        d_res = await db.execute(d_stmt)
        deployment = d_res.scalar_one_or_none()

        dep_status_map = {
            "success": "SUCCEEDED",
            "failure": "FAILED",
            "error": "FAILED",
            "in_progress": "IN_PROGRESS",
            "pending": "PENDING",
            "queued": "PENDING"
        }
        mapped_status = dep_status_map.get(event.state.lower(), "PENDING")

        if not deployment:
            deployment = Deployment(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                service_id=service.id,
                github_deployment_id=event.deployment_id,
                environment=event.environment,
                commit_sha=event.commit_sha,
                status=mapped_status,
                triggered_by=f"github_deployment:{event.creator_login or 'unknown'}",
                creator_login=event.creator_login,
                started_at=event.occurred_at,
                metadata_json=event.raw_payload
            )
            db.add(deployment)
            await db.flush()
        else:
            deployment.status = mapped_status
            if mapped_status in ("SUCCEEDED", "FAILED"):
                deployment.finished_at = event.occurred_at
                if deployment.started_at:
                    deployment.duration_seconds = max(0.0, (event.occurred_at - deployment.started_at).total_seconds())

        # Record discrete deployment event
        dep_event = DeploymentEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            deployment_id=deployment.id,
            github_deployment_id=event.deployment_id,
            github_deployment_status_id=event.deployment_status_id,
            status=event.state,
            environment=event.environment,
            creator_login=event.creator_login,
            description=event.description,
            occurred_at=event.occurred_at,
            payload=event.raw_payload
        )
        db.add(dep_event)
        await db.flush()

        return deployment


correlation_engine = CorrelationEngine()
