import pytest
from app.integrations.github.normalizer import normalize_github_event
from app.schemas.github_events import (
    PushEvent,
    PullRequestEvent,
    WorkflowRunEvent,
    WorkflowJobEvent,
    DeploymentEvent,
)


def test_push_event_normalization():
    payload = {
        "ref": "refs/heads/feature/auth",
        "before": "0" * 40,
        "after": "1" * 40,
        "repository": {"id": 999, "name": "auth-service", "full_name": "acme/auth-service"},
        "pusher": {"name": "octocat"},
        "commits": [
            {
                "id": "1" * 40,
                "message": "feat: add token rotation",
                "timestamp": "2026-11-07T12:00:00Z",
                "author": {"name": "Mona Lisa", "email": "mona@github.com", "username": "octocat"},
                "added": ["src/token.py"],
                "removed": [],
                "modified": ["src/auth.py"]
            }
        ]
    }
    contract, specific = normalize_github_event("push", "del-001", payload)
    assert contract.source == "github"
    assert contract.event_type == "github.push"
    assert contract.commit_sha == "1" * 40
    assert isinstance(specific, PushEvent)
    assert specific.ref == "refs/heads/feature/auth"
    assert len(specific.commits) == 1
    assert specific.commits[0].added == ["src/token.py"]


def test_pull_request_event_normalization():
    payload = {
        "action": "closed",
        "pull_request": {
            "id": 5555,
            "number": 42,
            "title": "Migrate database pool configuration",
            "state": "closed",
            "merged": True,
            "merged_at": "2026-11-07T13:30:00Z",
            "head": {"sha": "2" * 40, "ref": "feat/db-pool"},
            "base": {"ref": "main"},
            "user": {"login": "devops-engineer"},
            "changed_files": 4,
            "additions": 120,
            "deletions": 15
        },
        "repository": {"name": "core-api", "full_name": "acme/core-api"}
    }
    contract, specific = normalize_github_event("pull_request", "del-002", payload)
    assert contract.event_type == "github.pull_request"
    assert contract.commit_sha == "2" * 40
    assert isinstance(specific, PullRequestEvent)
    assert specific.is_merged is True
    assert specific.number == 42
    assert specific.author_login == "devops-engineer"


def test_workflow_run_event_normalization():
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 88889999,
            "name": "CI Pipeline",
            "head_sha": "3" * 40,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "run_number": 105,
            "run_attempt": 1,
            "run_started_at": "2026-11-07T14:00:00Z",
            "updated_at": "2026-11-07T14:05:00Z",
            "actor": {"login": "ci-bot"}
        },
        "repository": {"name": "billing", "full_name": "acme/billing"}
    }
    contract, specific = normalize_github_event("workflow_run", "del-003", payload)
    assert contract.workflow_run_id == "88889999"
    assert isinstance(specific, WorkflowRunEvent)
    assert specific.conclusion == "success"
    assert specific.duration_seconds == 300.0


def test_workflow_job_event_normalization():
    payload = {
        "action": "completed",
        "workflow_job": {
            "id": 7777,
            "run_id": 88889999,
            "name": "unit-tests",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2026-11-07T14:00:30Z",
            "completed_at": "2026-11-07T14:02:30Z",
            "runner_name": "ubuntu-latest-2core",
            "steps": [{"name": "Run Pytest", "status": "completed", "conclusion": "success"}]
        },
        "repository": {"full_name": "acme/billing"}
    }
    contract, specific = normalize_github_event("workflow_job", "del-004", payload)
    assert isinstance(specific, WorkflowJobEvent)
    assert specific.job_id == "7777"
    assert specific.runner_name == "ubuntu-latest-2core"


def test_deployment_event_normalization():
    payload = {
        "deployment": {
            "id": 112233,
            "sha": "4" * 40,
            "environment": "production",
            "creator": {"login": "release-manager"}
        },
        "deployment_status": {
            "id": 998877,
            "state": "success",
            "description": "Deployment deployed to k8s prod cluster successfully",
            "created_at": "2026-11-07T15:00:00Z"
        },
        "repository": {"name": "auth-service", "full_name": "acme/auth-service"}
    }
    contract, specific = normalize_github_event("deployment_status", "del-005", payload)
    assert contract.deployment_id == "112233"
    assert isinstance(specific, DeploymentEvent)
    assert specific.state == "success"
    assert specific.creator_login == "release-manager"


def test_unknown_event_preserves_full_payload():
    payload = {"custom_field": "val123", "sub": {"a": 1}}
    contract, specific = normalize_github_event("custom_unknown_ping", "del-006", payload)
    assert contract.event_type == "github.custom_unknown_ping"
    assert contract.payload["custom_field"] == "val123"
    assert specific is None
