"""Deterministic Risk Assessment Engine (Baseline).

Evaluates rule-based signals derived from pre-deployment features, operational memory,
and infrastructure topology.

Never represents uncalibrated rule scores as failure probabilities.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from app.services.feature_engineering import FeatureSnapshot

logger = logging.getLogger(__name__)

RULE_ENGINE_VERSION = "1.0.0"


class TriggeredRule(BaseModel):
    rule_id: str
    title: str
    weight: float
    rationale: str
    evidence: Dict[str, Any] = {}


class DeterministicRiskAssessment(BaseModel):
    rule_score: float  # 0.0 to 1.0
    risk_category: str  # LOW, MEDIUM, HIGH, CRITICAL
    triggered_rules: List[TriggeredRule]
    supporting_records: List[str]
    missing_evidence: List[str]
    rule_version: str = RULE_ENGINE_VERSION
    mitigation_recommendations: List[str] = []


class DeterministicRiskEngine:
    """Deterministic rule-based risk evaluation."""

    def evaluate(self, snapshot: FeatureSnapshot) -> DeterministicRiskAssessment:
        f = snapshot.features
        triggered: List[TriggeredRule] = []
        supporting_records: List[str] = []
        recommendations: List[str] = []

        total_weight = 0.0

        # R01: Unresolved Incidents
        if f.get("repo_unresolved_incidents", 0.0) > 0:
            count = int(f["repo_unresolved_incidents"])
            weight = min(0.40, 0.20 * count)
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R01_UNRESOLVED_INCIDENTS",
                    title="Active Unresolved Incidents on Target Repository",
                    weight=weight,
                    rationale=f"Found {count} unresolved active incident(s) in operational memory. Deploying over existing degradation creates compounding blast radius.",
                    evidence={"unresolved_count": count},
                )
            )
            recommendations.append("Require SRE review to verify existing incidents are mitigated before proceeding.")

        # R02: Failed CI Tests or Builds
        if f.get("ci_test_passed", 1.0) == 0.0 or f.get("ci_failed_jobs_count", 0.0) > 0:
            failed_jobs = int(f.get("ci_failed_jobs_count", 1.0))
            weight = 0.35
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R02_FAILED_CI_TESTS",
                    title="Automated CI Test Suite or Build Failed",
                    weight=weight,
                    rationale=f"CI workflow reported {failed_jobs} failed job(s). Promoting unverified code introduces high probability of regression.",
                    evidence={"failed_jobs_count": failed_jobs},
                )
            )
            recommendations.append("Block deployment until CI test suite passes successfully.")

        # R03: Dependency Installation Failure Signal
        if f.get("ci_dependency_install_failed", 0.0) > 0:
            weight = 0.25
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R03_DEPENDENCY_INSTALL_ERROR",
                    title="Package Dependency Resolution Failure",
                    weight=weight,
                    rationale="Package manager encountered 404 or unresolvable package version during build.",
                    evidence={"ci_dependency_install_failed": True},
                )
            )
            recommendations.append("Audit lockfile and verify upstream package registry accessibility.")

        # R04: Critical Dependency Manifest Modified
        if f.get("dependency_manifests_modified", 0.0) > 0:
            manifests = int(f["dependency_manifests_modified"])
            weight = 0.15
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R04_DEPENDENCY_MANIFEST_TOUCHED",
                    title="Third-Party Package Manifests Modified",
                    weight=weight,
                    rationale=f"Changes touch {manifests} package manifest file(s). Third-party upgrades carry supply-chain and runtime compatibility risk.",
                    evidence={"manifests_count": manifests},
                )
            )
            recommendations.append("Execute automated vulnerability scan and run canary rollout.")

        # R05: Infrastructure / Kubernetes Config Changed
        if f.get("infrastructure_config_modified", 0.0) > 0:
            infra_count = int(f["infrastructure_config_modified"])
            weight = 0.15
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R05_INFRASTRUCTURE_CONFIG_TOUCHED",
                    title="Container or Orchestration Manifest Modified",
                    weight=weight,
                    rationale=f"Commit modifies {infra_count} infrastructure configuration file(s) (e.g. Dockerfile, Helm, Kubernetes YAML).",
                    evidence={"infra_files_count": infra_count},
                )
            )
            recommendations.append("Verify resource requests and limits in Kubernetes deployment manifests.")

        # R06: Downstream Dependency Impact (Tier 1 or deep tree)
        if f.get("service_tier_criticality", 2.0) == 1.0 or f.get("downstream_dependency_count", 0.0) >= 2.0:
            downstream = int(f.get("downstream_dependency_count", 0.0))
            is_tier1 = f.get("service_tier_criticality", 2.0) == 1.0
            weight = 0.20
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R06_HIGH_DOWNSTREAM_BLAST_RADIUS",
                    title="High Downstream Blast Radius Exposure",
                    weight=weight,
                    rationale=f"Target service is {'Tier-1 Critical' if is_tier1 else 'Core Service'} with {downstream} downstream dependent service(s).",
                    evidence={"is_tier1": is_tier1, "downstream_services": downstream},
                )
            )
            recommendations.append("Prepare rollback runbook and enable progressive traffic routing.")

        # R07: Historical Operational Incidents on this Component
        if f.get("similar_verified_incidents_count", 0.0) > 0:
            count = int(f["similar_verified_incidents_count"])
            weight = min(0.25, 0.10 * count)
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R07_OPERATIONAL_MEMORY_MATCH",
                    title="Historical Incidents Recorded for Component",
                    weight=weight,
                    rationale=f"Operational memory contains {count} verified historical incident(s) on this repository.",
                    evidence={"historical_incidents_count": count},
                )
            )

        # R08: High Deployment Failure Rate on Environment
        if f.get("repo_historical_deployment_failure_rate", 0.0) > 0.25:
            rate = f["repo_historical_deployment_failure_rate"]
            weight = 0.20
            total_weight += weight
            triggered.append(
                TriggeredRule(
                    rule_id="R08_HIGH_HISTORICAL_FAILURE_RATE",
                    title="High Historical Deployment Failure Frequency",
                    weight=weight,
                    rationale=f"Historical deployment failure rate is {rate * 100:.1f}%, exceeding the 25% threshold.",
                    evidence={"historical_failure_rate": round(rate, 3)},
                )
            )

        # Normalize bounded score (0.00 to 1.00)
        rule_score = round(min(1.0, max(0.0, total_weight)), 2)

        # Categorize
        if rule_score >= 0.75:
            category = "CRITICAL"
        elif rule_score >= 0.50:
            category = "HIGH"
        elif rule_score >= 0.25:
            category = "MEDIUM"
        else:
            category = "LOW"

        if not recommendations:
            recommendations.append("Standard automated deployment pipeline can proceed.")

        return DeterministicRiskAssessment(
            rule_score=rule_score,
            risk_category=category,
            triggered_rules=triggered,
            supporting_records=supporting_records,
            missing_evidence=snapshot.missing_features,
            rule_version=RULE_ENGINE_VERSION,
            mitigation_recommendations=recommendations,
        )


deterministic_risk_engine = DeterministicRiskEngine()
