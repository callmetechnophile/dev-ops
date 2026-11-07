import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.correlation_engine import correlation_engine
from app.integrations.github.normalizer import normalize_github_event
from app.models.service import Repository, Service
from app.models.deployment import Commit, Build, Deployment
from app.models.github_entities import PullRequest, WorkflowRun, DeploymentEvent


@pytest.mark.asyncio
async def test_push_and_commit_correlation(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    commit_sha = "a" * 40

    push_payload = {
        "ref": "refs/heads/main",
        "after": commit_sha,
        "repository": {"id": 1001, "name": "user-service", "full_name": "acme/user-service"},
        "commits": [
            {
                "id": commit_sha,
                "message": "fix: update db timeout",
                "timestamp": "2026-11-07T10:00:00Z",
                "author": {"name": "Dev", "email": "dev@acme.corp", "username": "dev1"},
                "added": ["config.py"],
                "removed": [],
                "modified": ["main.py"]
            }
        ]
    }
    _, push_evt = normalize_github_event("push", "del-101", push_payload, str(tenant_id))
    commit, count = await correlation_engine.process_push_event(db_session, tenant_id, push_evt)

    assert count == 1
    assert commit is not None
    assert commit.commit_sha == commit_sha
    assert commit.stats_additions == 1

    # Verify repository was created and auto-discovered
    repo_stmt = select(Repository).where(Repository.full_name == "acme/user-service")
    repo = (await db_session.execute(repo_stmt)).scalar_one_or_none()
    assert repo is not None


@pytest.mark.asyncio
async def test_pull_request_correlation(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    head_sha = "b" * 40

    pr_payload = {
        "action": "closed",
        "pull_request": {
            "id": 901,
            "number": 15,
            "title": "Add redis caching layer",
            "state": "closed",
            "merged": True,
            "merged_at": "2026-11-07T11:00:00Z",
            "head": {"sha": head_sha, "ref": "feat/redis"},
            "base": {"ref": "main"},
            "user": {"login": "octo"},
            "changed_files": 2,
            "additions": 45,
            "deletions": 5
        },
        "repository": {"name": "user-service", "full_name": "acme/user-service"}
    }
    _, pr_evt = normalize_github_event("pull_request", "del-102", pr_payload, str(tenant_id))
    pr = await correlation_engine.process_pull_request_event(db_session, tenant_id, pr_evt)

    assert pr.number == 15
    assert pr.is_merged is True
    assert pr.head_sha == head_sha


@pytest.mark.asyncio
async def test_workflow_run_correlates_build_history(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    commit_sha = "c" * 40

    wf_payload = {
        "action": "completed",
        "workflow_run": {
            "id": 654321,
            "name": "Integration Tests",
            "head_sha": commit_sha,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "run_number": 88,
            "run_attempt": 1,
            "run_started_at": "2026-11-07T11:10:00Z",
            "updated_at": "2026-11-07T11:14:00Z",
            "actor": {"login": "runner-bot"}
        },
        "repository": {"name": "user-service", "full_name": "acme/user-service"}
    }
    _, wf_evt = normalize_github_event("workflow_run", "del-103", wf_payload, str(tenant_id))
    run = await correlation_engine.process_workflow_run_event(db_session, tenant_id, wf_evt)

    assert run.github_run_id == "654321"
    assert run.conclusion == "success"

    # Verify correlated build record was created
    b_stmt = select(Build).where(Build.commit_sha == commit_sha)
    build = (await db_session.execute(b_stmt)).scalar_one_or_none()
    assert build is not None
    assert build.status == "succeeded"
    assert build.workflow_run_id == run.id


@pytest.mark.asyncio
async def test_deployment_event_independence(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    commit_sha = "d" * 40
    dep_github_id = "dep-9988"

    dep_payload = {
        "deployment": {
            "id": dep_github_id,
            "sha": commit_sha,
            "environment": "staging",
            "creator": {"login": "sre-engineer"}
        },
        "deployment_status": {
            "id": "status-111",
            "state": "success",
            "description": "Deployed to staging namespace",
            "created_at": "2026-11-07T11:30:00Z"
        },
        "repository": {"name": "user-service", "full_name": "acme/user-service"}
    }
    _, dep_evt = normalize_github_event("deployment_status", "del-104", dep_payload, str(tenant_id))
    dep = await correlation_engine.process_deployment_event(db_session, tenant_id, dep_evt)

    assert dep.environment == "staging"
    assert dep.status == "SUCCEEDED"
    assert dep.creator_login == "sre-engineer"

    # Verify discrete DeploymentEvent was stored
    de_stmt = select(DeploymentEvent).where(DeploymentEvent.deployment_id == dep.id)
    de = (await db_session.execute(de_stmt)).scalar_one_or_none()
    assert de is not None
    assert de.status == "success"
