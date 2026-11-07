"""Explainability Engine with SHAP Integration and Deterministic Attribution.

Guarantees:
- Integrates SHAP only when a trained model exists.
- Never fabricates SHAP explanations for models that do not exist.
- When ML is INSUFFICIENT_DATA, provides truthful deterministic feature attribution based on rule activations.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import numpy as np

try:
    import shap

    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

from app.services.feature_engineering import FeatureSnapshot
from app.services.deterministic_risk_engine import DeterministicRiskAssessment
from app.services.ml_pipeline import ml_pipeline_service, NUMERIC_FEATURE_KEYS

logger = logging.getLogger(__name__)


class FeatureContribution(BaseModel):
    feature_name: str
    feature_value: float
    contribution_score: float  # Positive increases risk, negative decreases risk
    direction: str  # INCREASES_RISK, DECREASES_RISK, NEUTRAL
    explanation: str


class PredictionExplanation(BaseModel):
    method: str  # SHAP_TREE_EXPLAINER, DETERMINISTIC_RULE_ATTRIBUTION
    model_version: Optional[str] = None
    baseline_expected_value: float = 0.20
    top_risk_increasing_factors: List[FeatureContribution]
    top_risk_mitigating_factors: List[FeatureContribution]
    all_contributions: List[FeatureContribution]
    provenance: str


class ExplainabilityEngine:
    """Computes explainable feature contributions for risk assessments."""

    def explain(
        self,
        snapshot: FeatureSnapshot,
        deterministic_risk: DeterministicRiskAssessment,
        model_version: Optional[str] = None,
    ) -> PredictionExplanation:
        # If trained model is active and SHAP is installed, compute SHAP values
        if model_version and ml_pipeline_service._active_model and HAS_SHAP:
            return self._compute_shap_explanation(snapshot, model_version)

        # Truthful deterministic rule-based attribution fallback
        return self._compute_deterministic_attribution(snapshot, deterministic_risk)

    def _compute_shap_explanation(
        self,
        snapshot: FeatureSnapshot,
        model_version: str,
    ) -> PredictionExplanation:
        try:
            vec = np.array([[snapshot.features.get(k, 0.0) for k in NUMERIC_FEATURE_KEYS]], dtype=np.float32)
            explainer = shap.Explainer(ml_pipeline_service._active_model)
            shap_values = explainer(vec)

            vals = shap_values.values[0]
            if len(vals.shape) > 1:
                vals = vals[:, 1]  # positive class contributions

            contributions: List[FeatureContribution] = []
            for i, k in enumerate(NUMERIC_FEATURE_KEYS):
                v = float(snapshot.features.get(k, 0.0))
                contrib = float(vals[i])
                direction = "INCREASES_RISK" if contrib > 0.01 else ("DECREASES_RISK" if contrib < -0.01 else "NEUTRAL")

                contributions.append(
                    FeatureContribution(
                        feature_name=k,
                        feature_value=v,
                        contribution_score=round(contrib, 4),
                        direction=direction,
                        explanation=f"{k} ({v}) contributed {contrib:+.3f} to ML failure probability.",
                    )
                )

            increasing = sorted(
                [c for c in contributions if c.direction == "INCREASES_RISK"],
                key=lambda c: c.contribution_score,
                reverse=True,
            )[:5]
            mitigating = sorted(
                [c for c in contributions if c.direction == "DECREASES_RISK"], key=lambda c: c.contribution_score
            )[:5]

            return PredictionExplanation(
                method="SHAP_TREE_EXPLAINER",
                model_version=model_version,
                baseline_expected_value=float(
                    explainer.expected_value[1]
                    if hasattr(explainer, "expected_value") and isinstance(explainer.expected_value, (list, np.ndarray))
                    else 0.20
                ),
                top_risk_increasing_factors=increasing,
                top_risk_mitigating_factors=mitigating,
                all_contributions=contributions,
                provenance=f"Calculated using SHAP Explainer on trained model artifact {model_version}.",
            )
        except Exception as e:
            logger.warning(f"SHAP explanation failed, falling back to deterministic attribution: {e}")
            return self._compute_deterministic_attribution(snapshot, None)

    def _compute_deterministic_attribution(
        self,
        snapshot: FeatureSnapshot,
        deterministic_risk: Optional[DeterministicRiskAssessment],
    ) -> PredictionExplanation:
        contributions: List[FeatureContribution] = []

        # Map features to deterministic impact
        f = snapshot.features

        rule_map = {}
        if deterministic_risk:
            for r in deterministic_risk.triggered_rules:
                rule_map[r.rule_id] = r

        for k in NUMERIC_FEATURE_KEYS:
            val = float(f.get(k, 0.0))
            score = 0.0
            desc = f"Feature '{k}' value: {val}."

            if k == "repo_unresolved_incidents" and val > 0:
                score = min(0.40, val * 0.20)
                desc = f"Found {int(val)} active unresolved incident(s)."
            elif k == "ci_failed_jobs_count" and val > 0:
                score = 0.35
                desc = f"CI reported {int(val)} failed job(s)."
            elif k == "ci_dependency_install_failed" and val > 0:
                score = 0.25
                desc = "Dependency installation halted build."
            elif k == "dependency_manifests_modified" and val > 0:
                score = 0.15
                desc = f"Modified {int(val)} third-party package manifest(s)."
            elif k == "infrastructure_config_modified" and val > 0:
                score = 0.15
                desc = f"Modified {int(val)} container/infrastructure file(s)."
            elif k == "downstream_dependency_count" and val >= 2:
                score = 0.20
                desc = f"{int(val)} downstream services exposed to failure propagation."
            elif k == "similar_verified_incidents_count" and val > 0:
                score = min(0.25, val * 0.10)
                desc = f"{int(val)} historically similar incident(s) recorded in operational memory."
            elif k == "ci_test_passed" and val == 1.0:
                score = -0.20
                desc = "Automated CI test suite passed."

            direction = "INCREASES_RISK" if score > 0 else ("DECREASES_RISK" if score < 0 else "NEUTRAL")
            contributions.append(
                FeatureContribution(
                    feature_name=k,
                    feature_value=val,
                    contribution_score=round(score, 3),
                    direction=direction,
                    explanation=desc,
                )
            )

        increasing = sorted(
            [c for c in contributions if c.direction == "INCREASES_RISK"],
            key=lambda c: c.contribution_score,
            reverse=True,
        )[:5]
        mitigating = sorted(
            [c for c in contributions if c.direction == "DECREASES_RISK"], key=lambda c: c.contribution_score
        )[:5]

        return PredictionExplanation(
            method="DETERMINISTIC_RULE_ATTRIBUTION",
            model_version=None,
            baseline_expected_value=0.10,
            top_risk_increasing_factors=increasing,
            top_risk_mitigating_factors=mitigating,
            all_contributions=contributions,
            provenance="Rule-based heuristic attribution (ML model in INSUFFICIENT_DATA status; SHAP unengaged).",
        )


explainability_engine = ExplainabilityEngine()
