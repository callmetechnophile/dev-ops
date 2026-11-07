import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from app.services.feature_engineering import (
    feature_engineering_service,
    FEATURE_SCHEMA_VERSION,
)


@pytest.mark.asyncio
async def test_feature_extraction_zero_leakage_and_metrics(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # 1. Create Repository
    repo = models.Repository(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="billing-service",
        full_name="acme/billing-service",
        provider="github",
        default_branch="main",
    )
    db_session.add(repo)

    # 2. Create Service
    service = models.Service(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        name="Billing Engine",
        slug="billing-engine",
        tier="tier-1",
        health_status="healthy",
    )
    db_session.add(service)

    # 3. Create Commit with changes
    commit_sha = "abc1234567890abcdef1234567890abcdef12345"
    commit = models.Commit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        commit_sha=commit_sha,
        message="feat: update payment gateway client and docker config",
        author_name="Alice Developer",
        author_email="alice@acme.corp",
        stats_additions=62,
        stats_deletions=16,
        committed_at=datetime.now(timezone.utc) - timedelta(minutes=15),
    )
    db_session.add(commit)

    # Add change records across all categories
    change1 = models.Change(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        commit_id=commit.id,
        change_type="modified",
        file_path="src/billing/client.py",
        additions=45,
        deletions=10,
    )
    change2 = models.Change(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        commit_id=commit.id,
        change_type="modified",
        file_path="Dockerfile",
        additions=5,
        deletions=2,
    )
    change3 = models.Change(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        commit_id=commit.id,
        change_type="modified",
        file_path="requirements.txt",
        additions=2,
        deletions=1,
    )
    change4 = models.Change(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        commit_id=commit.id,
        change_type="modified",
        file_path="config.yaml",
        additions=10,
        deletions=3,
    )
    db_session.add_all([change1, change2, change3, change4])

    # 4. Create Build
    build = models.Build(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        repository_id=repo.id,
        commit_sha=commit_sha,
        status="succeeded",
        duration_seconds=120,
    )
    db_session.add(build)

    # 5. Create Deployment (Pre-deployment state WAITING_FOR_APPROVAL)
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service.id,
        build_id=build.id,
        environment="production",
        commit_sha=commit_sha,
        status="WAITING_FOR_APPROVAL",
        triggered_by="github_action",
    )
    db_session.add(dep)
    await db_session.commit()

    # Extract features
    snapshot = await feature_engineering_service.extract_features(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
        service=service,
        repository=repo,
        target_commit_sha=commit_sha,
    )

    # Verify schema version
    assert snapshot.schema_version == FEATURE_SCHEMA_VERSION

    # Verify change features
    assert snapshot.features["files_changed_count"] == 4.0
    assert snapshot.features["lines_added"] == 62.0
    assert snapshot.features["lines_deleted"] == 16.0
    assert snapshot.features["config_files_modified"] == 1.0  # config.yaml
    assert snapshot.features["dependency_manifests_modified"] == 1.0  # requirements.txt
    assert snapshot.features["infrastructure_config_modified"] == 1.0  # Dockerfile

    # Verify build telemetry
    assert snapshot.features["ci_build_duration_seconds"] == 120.0
    assert snapshot.features["ci_test_passed"] == 1.0
    assert snapshot.features["ci_failed_jobs_count"] == 0.0

    # Verify service attributes & categorical features
    assert snapshot.categorical_features["service_tier"] == "tier-1"
    assert snapshot.categorical_features["environment"] == "production"

    # Verify Zero Target Leakage:
    # None of the features should reference deployment.finished_at, post-deployment status, or incident outcomes
    assert "deployment_finished_at" not in snapshot.features
    assert "post_deploy_incident" not in snapshot.features
    assert "rollback_triggered" not in snapshot.features


@pytest.mark.asyncio
async def test_feature_extraction_graceful_missing_data(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Create minimal deployment without existing commit changes or build
    dep = models.Deployment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_id=service_id,
        environment="staging",
        commit_sha="0000000000000000000000000000000000000000",
        status="WAITING_FOR_APPROVAL",
        triggered_by="manual",
    )
    db_session.add(dep)
    await db_session.commit()

    snapshot = await feature_engineering_service.extract_features(
        db=db_session,
        tenant_id=tenant_id,
        deployment=dep,
    )

    assert snapshot.schema_version == FEATURE_SCHEMA_VERSION
    # Handled missing commit gracefully with default 0s
    assert snapshot.features["files_changed_count"] == 0.0
    assert snapshot.features["lines_added"] == 0.0
    # Missing tracking recorded
    assert "commit_diff_details" in snapshot.missing_features
    assert "ci_build_telemetry" in snapshot.missing_features
