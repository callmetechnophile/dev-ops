import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from app.services.outcome_labeler import LABEL_FAILED, LABEL_SUCCEEDED
from app.services.feature_engineering import FeatureSnapshot
from app.services.deterministic_risk_engine import deterministic_risk_engine
from app.services.ml_pipeline import (
    ml_pipeline_service,
    MIN_SAMPLES_THRESHOLD,
    MIN_MINORITY_CLASS_THRESHOLD,
)
from app.services.explainability import explainability_engine


@pytest.mark.asyncio
async def test_ml_pipeline_insufficient_data_governance(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Empty database -> check eligibility
    eligibility = await ml_pipeline_service.check_eligibility(db_session, tenant_id)
    assert not eligibility.is_eligible
    assert eligibility.status == "INSUFFICIENT_DATA"
    assert eligibility.total_labeled_samples == 0
    assert "Insufficient historical deployments" in eligibility.reason

    # Add 15 succeeded deployments (still < 30)
    for i in range(15):
        dep = models.Deployment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            service_id=service_id,
            environment="production",
            commit_sha=f"commit_{i:04d}",
            status="SUCCEEDED",
            triggered_by="github_action",
            started_at=datetime.now(timezone.utc) - timedelta(days=20 - i),
            finished_at=datetime.now(timezone.utc) - timedelta(days=20 - i) + timedelta(minutes=10),
        )
        db_session.add(dep)
        label = models.DeploymentOutcomeLabel(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            deployment_id=dep.id,
            observation_window_minutes=60,
            outcome_label=LABEL_SUCCEEDED,
            verification_status="VERIFIED",
            dataset_version="v1.0",
        )
        db_session.add(label)

    await db_session.commit()

    eligibility = await ml_pipeline_service.check_eligibility(db_session, tenant_id)
    assert not eligibility.is_eligible
    assert eligibility.status == "INSUFFICIENT_DATA"
    assert eligibility.total_labeled_samples == 15


@pytest.mark.asyncio
async def test_ml_training_evaluation_calibration_and_shap(db_session: AsyncSession):
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    service_id = uuid.UUID("00000000-0000-0000-0000-000000000004")

    # Generate 35 deployments chronologically:
    # 25 SUCCEEDED, 10 FAILED (minority class = 10 >= 5, total = 35 >= 30)
    base_time = datetime.now(timezone.utc) - timedelta(days=40)

    for i in range(35):
        is_failure = (i % 3 == 0) and (i < 30)  # 10 failures
        outcome = LABEL_FAILED if is_failure else LABEL_SUCCEEDED
        dep_time = base_time + timedelta(days=i)

        dep = models.Deployment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            service_id=service_id,
            environment="production",
            commit_sha=f"sha_{i:040d}",
            status="FAILED" if is_failure else "SUCCEEDED",
            triggered_by="github_action",
            started_at=dep_time,
            finished_at=dep_time + timedelta(minutes=5),
        )
        db_session.add(dep)

        label = models.DeploymentOutcomeLabel(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            deployment_id=dep.id,
            observation_window_minutes=60,
            outcome_label=outcome,
            failure_reason="Test failure" if is_failure else None,
            verification_status="VERIFIED",
            dataset_version="v1.0",
        )
        db_session.add(label)

    await db_session.commit()

    # Verify eligibility now passes
    eligibility = await ml_pipeline_service.check_eligibility(db_session, tenant_id)
    assert eligibility.is_eligible
    assert eligibility.status == "ELIGIBLE"
    assert eligibility.total_labeled_samples == 35
    assert eligibility.positive_samples == 10
    assert eligibility.negative_samples == 25

    # Train model pipeline
    mv, eval_metrics, msg = await ml_pipeline_service.train_model(db_session, tenant_id)
    assert mv is not None
    assert eval_metrics is not None
    assert "successfully" in msg
    version = mv.version
    assert version.startswith("v")

    # Check evaluation metrics
    assert eval_metrics.is_calibrated is True
    assert eval_metrics.calibration_method == "sigmoid"
    assert 0.0 <= eval_metrics.brier_score <= 1.0
    assert 0.0 <= eval_metrics.roc_auc <= 1.0

    # Test Prediction Inference
    sample_snapshot = FeatureSnapshot(
        extracted_at=datetime.now(timezone.utc),
        features={
            "files_changed_count": 8.0,
            "lines_added": 120.0,
            "lines_deleted": 30.0,
            "ci_test_passed": 1.0,
            "ci_failed_jobs_count": 0.0,
            "repo_unresolved_incidents": 0.0,
            "dependency_manifests_modified": 0.0,
            "infrastructure_config_modified": 0.0,
            "service_tier_criticality": 1.0,
            "downstream_dependency_count": 2.0,
            "similar_verified_incidents_count": 0.0,
            "repo_historical_deployment_failure_rate": 0.10,
        },
        categorical_features={"environment": "production", "service_tier": "tier-1"},
        missing_features=[],
    )

    pred = await ml_pipeline_service.predict_risk(db_session, tenant_id, sample_snapshot)
    assert pred.status == "ACTIVE"
    assert pred.model_version == version
    assert pred.calibrated_failure_probability is not None
    assert 0.0 <= pred.calibrated_failure_probability <= 1.0

    # Test Explainability: SHAP
    det_risk = deterministic_risk_engine.evaluate(sample_snapshot)
    explanation = explainability_engine.explain(
        snapshot=sample_snapshot,
        deterministic_risk=det_risk,
        model_version=version,
    )

    assert explanation.method in ("SHAP_TREE_EXPLAINER", "DETERMINISTIC_RULE_ATTRIBUTION")
    assert len(explanation.all_contributions) > 0


def test_explainability_fallback_when_no_model():
    sample_snapshot = FeatureSnapshot(
        extracted_at=datetime.now(timezone.utc),
        features={
            "files_changed_count": 12.0,
            "lines_added": 250.0,
            "lines_deleted": 80.0,
            "ci_test_passed": 0.0,
            "ci_failed_jobs_count": 1.0,
            "repo_unresolved_incidents": 1.0,
            "dependency_manifests_modified": 1.0,
            "infrastructure_config_modified": 0.0,
            "service_tier_criticality": 1.0,
            "downstream_dependency_count": 3.0,
            "similar_verified_incidents_count": 1.0,
            "repo_historical_deployment_failure_rate": 0.30,
        },
        categorical_features={"environment": "production", "service_tier": "tier-1"},
        missing_features=[],
    )

    det_risk = deterministic_risk_engine.evaluate(sample_snapshot)

    # Call with model_version=None (inactive ML)
    explanation = explainability_engine.explain(
        snapshot=sample_snapshot,
        deterministic_risk=det_risk,
        model_version=None,
    )

    assert explanation.method == "DETERMINISTIC_RULE_ATTRIBUTION"
    assert len(explanation.top_risk_increasing_factors) > 0
    assert any("R02_FAILED_CI_TESTS" in f.feature_name or "ci_failed_jobs_count" in f.feature_name for f in explanation.top_risk_increasing_factors)
