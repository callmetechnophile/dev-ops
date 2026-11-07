import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from app.schemas.event import NormalizedEventContract
from app.schemas.github_events import (
    PushEvent,
    PullRequestEvent,
    WorkflowRunEvent,
    WorkflowJobEvent,
    DeploymentEvent,
    GitHubCommitInfo,
)


def parse_datetime(dt_str: Any) -> datetime:
    if isinstance(dt_str, datetime):
        return dt_str
    if not dt_str or not isinstance(dt_str, str):
        return datetime.now(timezone.utc)
    try:
        # Replace Z with +00:00 for ISO-8601 parsing
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def normalize_github_event(
    event_type: str, delivery_id: str, payload: Dict[str, Any], tenant_id: str = "00000000-0000-0000-0000-000000000001"
) -> Tuple[NormalizedEventContract, Any]:
    """
    Normalizes incoming GitHub webhook payload into typed event representation
    and common NormalizedEventContract.
    Preserves raw payload completely.
    """
    repo_data = payload.get("repository") or {}
    repo_name = repo_data.get("name") or "unknown-repo"
    repo_full_name = repo_data.get("full_name") or repo_name
    sender_data = payload.get("sender") or {}
    actor = sender_data.get("login") or payload.get("pusher", {}).get("name")

    # Common contract builder
    contract = NormalizedEventContract(
        event_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        source="github",
        event_type=f"github.{event_type}",
        schema_version="1.0.0",
        repository_name=repo_full_name,
        actor=actor,
        idempotency_key=f"github:{delivery_id}",
        correlation_id=str(uuid.uuid4()),
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        payload=payload,
    )

    specific_event = None

    if event_type == "push":
        commits_raw = payload.get("commits") or []
        parsed_commits = []
        for c in commits_raw:
            parsed_commits.append(
                GitHubCommitInfo(
                    id=c.get("id"),
                    message=c.get("message"),
                    timestamp=parse_datetime(c.get("timestamp")),
                    author_name=c.get("author", {}).get("name"),
                    author_email=c.get("author", {}).get("email"),
                    author_username=c.get("author", {}).get("username"),
                    added=c.get("added", []),
                    removed=c.get("removed", []),
                    modified=c.get("modified", []),
                )
            )

        head_commit_raw = payload.get("head_commit")
        head_commit = None
        if head_commit_raw:
            head_commit = GitHubCommitInfo(
                id=head_commit_raw.get("id"),
                message=head_commit_raw.get("message"),
                timestamp=parse_datetime(head_commit_raw.get("timestamp")),
                author_name=head_commit_raw.get("author", {}).get("name"),
                author_email=head_commit_raw.get("author", {}).get("email"),
                author_username=head_commit_raw.get("author", {}).get("username"),
                added=head_commit_raw.get("added", []),
                removed=head_commit_raw.get("removed", []),
                modified=head_commit_raw.get("modified", []),
            )

        head_sha = payload.get("after") or (head_commit.id if head_commit else None)
        contract.commit_sha = head_sha
        contract.occurred_at = (
            head_commit.timestamp if head_commit and head_commit.timestamp else datetime.now(timezone.utc)
        )

        specific_event = PushEvent(
            ref=payload.get("ref", "refs/heads/main"),
            before=payload.get("before"),
            after=head_sha or "0" * 40,
            repository_id=str(repo_data.get("id")),
            repository_name=repo_name,
            repository_full_name=repo_full_name,
            owner_login=repo_data.get("owner", {}).get("login"),
            pusher_name=payload.get("pusher", {}).get("name"),
            commits=parsed_commits,
            head_commit=head_commit,
            forced=payload.get("forced", False),
            created=payload.get("created", False),
            deleted=payload.get("deleted", False),
            raw_payload=payload,
        )

    elif event_type == "pull_request":
        pr_data = payload.get("pull_request") or {}
        head_sha = pr_data.get("head", {}).get("sha")
        merged_at = parse_datetime(pr_data.get("merged_at")) if pr_data.get("merged_at") else None

        contract.commit_sha = head_sha
        contract.occurred_at = parse_datetime(pr_data.get("updated_at") or pr_data.get("created_at"))

        specific_event = PullRequestEvent(
            action=payload.get("action", "opened"),
            number=pr_data.get("number", 0),
            pr_id=str(pr_data.get("id")),
            title=pr_data.get("title", ""),
            state=pr_data.get("state", "open"),
            is_merged=pr_data.get("merged", False),
            merged_at=merged_at,
            head_sha=head_sha or "",
            head_branch=pr_data.get("head", {}).get("ref", ""),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            author_login=pr_data.get("user", {}).get("login"),
            repository_name=repo_name,
            repository_full_name=repo_full_name,
            html_url=pr_data.get("html_url"),
            changed_files=pr_data.get("changed_files", 0),
            additions=pr_data.get("additions", 0),
            deletions=pr_data.get("deletions", 0),
            raw_payload=payload,
        )

    elif event_type == "workflow_run":
        run_data = payload.get("workflow_run") or {}
        head_sha = run_data.get("head_sha")
        started_at = parse_datetime(run_data.get("run_started_at") or run_data.get("created_at"))
        completed_at = parse_datetime(run_data.get("updated_at")) if run_data.get("status") == "completed" else None

        duration = None
        if completed_at and started_at:
            duration = max(0.0, (completed_at - started_at).total_seconds())

        contract.commit_sha = head_sha
        contract.workflow_run_id = str(run_data.get("id"))
        contract.occurred_at = completed_at or started_at

        specific_event = WorkflowRunEvent(
            action=payload.get("action", "completed"),
            run_id=str(run_data.get("id")),
            name=run_data.get("name", "workflow"),
            head_sha=head_sha or "",
            head_branch=run_data.get("head_branch", "main"),
            event=run_data.get("event", "push"),
            status=run_data.get("status", "queued"),
            conclusion=run_data.get("conclusion"),
            run_number=run_data.get("run_number", 1),
            run_attempt=run_data.get("run_attempt", 1),
            actor_login=run_data.get("actor", {}).get("login"),
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
            repository_name=repo_name,
            repository_full_name=repo_full_name,
            html_url=run_data.get("html_url"),
            raw_payload=payload,
        )

    elif event_type == "workflow_job":
        job_data = payload.get("workflow_job") or {}
        started_at = parse_datetime(job_data.get("started_at"))
        completed_at = parse_datetime(job_data.get("completed_at")) if job_data.get("completed_at") else None

        contract.commit_sha = job_data.get("head_sha")
        contract.workflow_run_id = str(job_data.get("run_id"))
        contract.occurred_at = completed_at or started_at

        specific_event = WorkflowJobEvent(
            action=payload.get("action", "completed"),
            job_id=str(job_data.get("id")),
            run_id=str(job_data.get("run_id")),
            name=job_data.get("name", "job"),
            status=job_data.get("status", "queued"),
            conclusion=job_data.get("conclusion"),
            started_at=started_at,
            completed_at=completed_at,
            runner_name=job_data.get("runner_name"),
            steps=job_data.get("steps", []),
            repository_full_name=repo_full_name,
            raw_payload=payload,
        )

    elif event_type in ("deployment", "deployment_status"):
        dep_data = payload.get("deployment") or {}
        status_data = payload.get("deployment_status") or {}
        commit_sha = dep_data.get("sha")
        environment = dep_data.get("environment") or "production"
        state = status_data.get("state") or (dep_data.get("task") or "pending")
        occurred = parse_datetime(status_data.get("created_at") or dep_data.get("created_at"))

        contract.commit_sha = commit_sha
        contract.deployment_id = str(dep_data.get("id"))
        contract.environment = environment
        contract.occurred_at = occurred

        specific_event = DeploymentEvent(
            action="updated" if event_type == "deployment_status" else "created",
            deployment_id=str(dep_data.get("id")),
            deployment_status_id=str(status_data.get("id")) if status_data else None,
            state=state,
            environment=environment,
            commit_sha=commit_sha or "",
            creator_login=dep_data.get("creator", {}).get("login"),
            description=status_data.get("description") or dep_data.get("description"),
            repository_name=repo_name,
            repository_full_name=repo_full_name,
            occurred_at=occurred,
            raw_payload=payload,
        )

    return contract, specific_event
