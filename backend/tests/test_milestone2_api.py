import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import app.models as models


@pytest.mark.asyncio
async def test_github_status_api(client: AsyncClient):
    res = await client.get("/api/v1/integrations/github/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "supported_events" in data
    assert "push" in data["supported_events"]


@pytest.mark.asyncio
async def test_repositories_and_commits_api(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    repo = models.Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="inventory-api",
        full_name="acme/inventory-api",
        provider="github",
        default_branch="main"
    )
    db_session.add(repo)

    commit = models.Commit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        commit_sha="1111222233334444555566667777888899990000",
        branch="main",
        author_name="Alice",
        message="Initial inventory schema",
        committed_at=datetime.now(timezone.utc)
    )
    db_session.add(commit)
    await db_session.commit()

    # List repositories
    repos_res = await client.get("/api/v1/repositories")
    assert repos_res.status_code == 200
    assert repos_res.json()["total"] >= 1

    # List repository commits
    commits_res = await client.get(f"/api/v1/repositories/{repo.id}/commits")
    assert commits_res.status_code == 200
    assert commits_res.json()["total"] == 1
    assert commits_res.json()["items"][0]["author_name"] == "Alice"


@pytest.mark.asyncio
async def test_deployment_timeline_api(client: AsyncClient, db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    repo_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    commit_sha = "99887766554433221100aabbccddeeff00112233"

    # 1. Commit
    commit = models.Commit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo_id,
        commit_sha=commit_sha,
        branch="main",
        author_login="octo-lead",
        message="Release v1.2.0 patch",
        committed_at=datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    )
    db_session.add(commit)

    # 2. PR
    pr = models.PullRequest(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo_id,
        github_pr_id="pr-77",
        number=77,
        title="Release v1.2.0",
        state="closed",
        is_merged=True,
        merged_at=datetime(2026, 11, 7, 10, 15, 0, tzinfo=timezone.utc),
        head_sha=commit_sha,
        base_branch="main",
        head_branch="release/v1.2.0",
        author_login="octo-lead"
    )
    db_session.add(pr)

    # 3. Workflow Run
    wf = models.WorkflowRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo_id,
        github_run_id="run-444",
        name="Production CI",
        head_sha=commit_sha,
        head_branch="main",
        event="push",
        status="completed",
        conclusion="success",
        run_number=44,
        run_attempt=1,
        started_at=datetime(2026, 11, 7, 10, 20, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 11, 7, 10, 25, 0, tzinfo=timezone.utc)
    )
    db_session.add(wf)

    # 4. Deployment
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        github_deployment_id="gh-dep-501",
        environment="production",
        commit_sha=commit_sha,
        status="SUCCEEDED",
        triggered_by="github_deployment:release-bot",
        creator_login="release-bot",
        started_at=datetime(2026, 11, 7, 10, 30, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 11, 7, 10, 34, 0, tzinfo=timezone.utc)
    )
    db_session.add(dep)

    # 5. Discrete Deployment Event
    de = models.DeploymentEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        deployment_id=dep.id,
        github_deployment_id="gh-dep-501",
        status="success",
        environment="production",
        creator_login="release-bot",
        description="Kubernetes rolling update completed",
        occurred_at=datetime(2026, 11, 7, 10, 34, 0, tzinfo=timezone.utc)
    )
    db_session.add(de)
    await db_session.commit()

    # Timeline verification
    res = await client.get(f"/api/v1/deployments/{dep.id}/timeline")
    assert res.status_code == 200
    timeline_data = res.json()
    assert timeline_data["deployment_id"] == str(dep.id)
    items = timeline_data["timeline"]
    assert len(items) >= 4

    # Verify chronological sequence: commit -> pr_merged -> workflow_run -> deployment_event
    types = [i["step_type"] for i in items]
    assert types == ["commit", "pr_merged", "workflow_run", "deployment_event"]


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    res = await client.get("/metrics")
    assert res.status_code == 200
    text = res.text
    assert "github_webhook_received_total" in text
    assert "event_processing_duration_seconds" in text
