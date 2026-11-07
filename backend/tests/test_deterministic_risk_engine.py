from datetime import datetime, timezone
import pytest
from app.services.feature_engineering import FeatureSnapshot
from app.services.deterministic_risk_engine import (
    deterministic_risk_engine,
    RULE_ENGINE_VERSION,
)


def test_deterministic_risk_engine_clean_deployment():
    snapshot = FeatureSnapshot(
        extracted_at=datetime.now(timezone.utc),
        features={
            "files_changed_count": 2.0,
            "lines_added": 20.0,
            "lines_deleted": 5.0,
            "total_lines_changed": 25.0,
            "ci_test_passed": 1.0,
            "ci_failed_jobs_count": 0.0,
            "repo_unresolved_incidents": 0.0,
            "dependency_manifests_modified": 0.0,
            "infrastructure_config_modified": 0.0,
            "service_tier_criticality": 3.0,
            "downstream_dependency_count": 0.0,
            "similar_verified_incidents_count": 0.0,
            "repo_historical_deployment_failure_rate": 0.05,
        },
        categorical_features={"environment": "staging", "service_tier": "tier-3"},
        missing_features=[],
    )

    assessment = deterministic_risk_engine.evaluate(snapshot)

    assert assessment.rule_version == RULE_ENGINE_VERSION
    assert assessment.rule_score == 0.0
    assert assessment.risk_category == "LOW"
    assert len(assessment.triggered_rules) == 0


def test_deterministic_risk_engine_critical_deployment():
    snapshot = FeatureSnapshot(
        extracted_at=datetime.now(timezone.utc),
        features={
            "files_changed_count": 15.0,
            "lines_added": 450.0,
            "lines_deleted": 120.0,
            "total_lines_changed": 570.0,
            "ci_test_passed": 0.0,  # Failed CI -> triggers R02 (weight 0.35)
            "ci_failed_jobs_count": 2.0,
            "repo_unresolved_incidents": 2.0,  # Unresolved incidents -> triggers R01 (weight 0.40)
            "dependency_manifests_modified": 1.0,  # Triggers R04 (weight 0.15)
            "infrastructure_config_modified": 2.0,  # Triggers R05 (weight 0.15)
            "service_tier_criticality": 1.0,  # Tier 1 -> triggers R06 (weight 0.20)
            "downstream_dependency_count": 4.0,
            "similar_verified_incidents_count": 3.0,  # Triggers R07 (weight 0.25)
            "repo_historical_deployment_failure_rate": 0.45,  # Triggers R08 (weight 0.20)
        },
        categorical_features={"environment": "production", "service_tier": "tier-1"},
        missing_features=[],
    )

    assessment = deterministic_risk_engine.evaluate(snapshot)

    assert assessment.risk_category == "CRITICAL"
    assert assessment.rule_score >= 0.70
    assert assessment.rule_score <= 1.0  # Bounded to 1.0 max

    rule_ids = [r.rule_id for r in assessment.triggered_rules]
    assert "R01_UNRESOLVED_INCIDENTS" in rule_ids
    assert "R02_FAILED_CI_TESTS" in rule_ids
    assert "R04_DEPENDENCY_MANIFEST_TOUCHED" in rule_ids
    assert "R05_INFRASTRUCTURE_CONFIG_TOUCHED" in rule_ids
    assert "R06_HIGH_DOWNSTREAM_BLAST_RADIUS" in rule_ids
    assert "R07_OPERATIONAL_MEMORY_MATCH" in rule_ids
    assert "R08_HIGH_HISTORICAL_FAILURE_RATE" in rule_ids

    # Recommendations generated
    assert len(assessment.mitigation_recommendations) > 0
    assert any("CI test suite" in rec for rec in assessment.mitigation_recommendations)
