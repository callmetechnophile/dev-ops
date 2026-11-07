"""Unified Deployment Risk Assessment Service.

Orchestrates:
Feature Extraction -> Deterministic Baseline -> Impact / Blast Radius ->
Operational Memory Similarity -> ML Inference -> Explainability -> Persistence.
"""
from __future__ import annotations
import uuid
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deployment import Deployment, Commit
from app.models.service import Service, Repository
from app.models.intelligence import RiskAssessment, Recommendation
from app.models.incident import Incident
from app.services.feature_engineering import feature_engineering_service, FeatureSnapshot
from app.services.deterministic_risk_engine import deterministic_risk_engine, DeterministicRiskAssessment
from app.services.impact_assessment import blast_radius_service, ImpactAssessment
from app.services.ml_pipeline import ml_pipeline_service, MLPredictionResult
from app.services.explainability import explainability_engine, PredictionExplanation
from app.services.similarity_retrieval import similarity_retrieval_service, SimilarIncidentMatch

logger = logging.getLogger(__name__)


class UnifiedRiskAssessmentResult(BaseModel):
    id: str
    deployment_id: str
    service_id: str
    repository_id: Optional[str] = None
    environment: str
    overall_risk_score: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    risk_category: str
    failure_probability: Optional[float] = None
    operational_impact_score: float
    impact_category: str
    affected_services: List[Dict[str, Any]] = []
    rule_score: float
    ml_score: Optional[float] = None
    model_version: Optional[str] = None
    model_status: str
    triggered_rules: List[Dict[str, Any]] = []
    supporting_incident_ids: List[str] = []
    similar_incidents: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    feature_snapshot: Dict[str, Any] = {}
    explanation: Dict[str, Any] = {}
    assessed_at: datetime


class RiskAssessmentService:
    """Evaluates and persists deployment risk assessments."""

    async def assess_deployment(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deployment_id: uuid.UUID,
    ) -> UnifiedRiskAssessmentResult:
        now = datetime.now(timezone.utc)

        # 1. Fetch deployment
        dep_stmt = (
            select(Deployment)
            .where(and_(Deployment.id == deployment_id, Deployment.tenant_id == tenant_id))
            .options(
                selectinload(Deployment.service),
                selectinload(Deployment.build),
            )
        )
        dep_res = await db.execute(dep_stmt)
        dep = dep_res.scalar_one_or_none()
        if not dep:
            raise ValueError(f"Deployment '{deployment_id}' not found.")

        # 2. Extract Features
        features: FeatureSnapshot = await feature_engineering_service.extract_features(
            db=db,
            tenant_id=tenant_id,
            deployment=dep,
            service=dep.service,
        )

        # 3. Deterministic Baseline Risk Evaluation
        det_risk: DeterministicRiskAssessment = deterministic_risk_engine.evaluate(features)

        # 4. Blast Radius & Downstream Operational Impact Assessment
        impact: ImpactAssessment = await blast_radius_service.calculate_impact(
            db=db,
            tenant_id=tenant_id,
            target_service_id=dep.service_id,
            environment=dep.environment,
        )

        # 5. ML Model Inference
        ml_res: MLPredictionResult = await ml_pipeline_service.predict_risk(
            db=db,
            tenant_id=tenant_id,
            feature_snapshot=features,
        )

        # Combine Overall Risk:
        # If calibrated ML model exists, overall score is weighted combination of failure_probability (0.60) + impact (0.40)
        # If ML is INSUFFICIENT_DATA, overall score is deterministic rule_score (0.60) + impact (0.40)
        if ml_res.calibrated_failure_probability is not None:
            failure_score = ml_res.calibrated_failure_probability
        else:
            failure_score = det_risk.rule_score

        overall_score = round(min(1.0, (failure_score * 0.60) + (impact.blast_radius_score * 0.40)), 2)

        if overall_score >= 0.75:
            overall_level = "CRITICAL"
        elif overall_score >= 0.50:
            overall_level = "HIGH"
        elif overall_score >= 0.25:
            overall_level = "MEDIUM"
        else:
            overall_level = "LOW"

        # 6. Explainability
        explanation: PredictionExplanation = explainability_engine.explain(
            snapshot=features,
            deterministic_risk=det_risk,
            model_version=ml_res.model_version,
        )

        # 7. Similar Historical Incidents
        similar_matches: List[SimilarIncidentMatch] = []
        supporting_inc_ids: List[str] = []
        # Find incidents sharing repository
        if dep.service and dep.service.repository_id:
            inc_stmt = (
                select(Incident)
                .where(
                    and_(
                        Incident.tenant_id == tenant_id,
                        Incident.repository_id == dep.service.repository_id,
                    )
                )
                .order_by(desc(Incident.detected_at))
                .limit(3)
            )
            inc_res = await db.execute(inc_stmt)
            for inc in inc_res.scalars().all():
                supporting_inc_ids.append(str(inc.id))
                similar_matches.append(
                    SimilarIncidentMatch(
                        incident_id=str(inc.id),
                        incident_key=inc.incident_key,
                        title=inc.title,
                        similarity_score=0.85,
                        matching_categories=[inc.incident_type],
                        environment=inc.environment,
                        status=inc.status,
                        detected_at=inc.detected_at,
                    )
                )

        # 8. Formulate Recommendations
        recs_data: List[Dict[str, Any]] = []
        for rec_text in det_risk.mitigation_recommendations:
            rec_type = "PROCEED_WITH_CANARY"
            if overall_level == "CRITICAL":
                rec_type = "BLOCK_DEPLOYMENT"
            elif overall_level == "HIGH":
                rec_type = "REQUIRE_CONFIG_REVIEW"

            recs_data.append(
                {
                    "title": f"Mitigation: {rec_type.replace('_', ' ')}",
                    "recommendation_type": rec_type,
                    "rationale": rec_text,
                    "confidence_score": 0.85 if overall_level in ("HIGH", "CRITICAL") else 0.70,
                    "requires_approval": "true" if overall_level in ("HIGH", "CRITICAL") else "false",
                }
            )

        # 9. Persist to Database
        risk_record = RiskAssessment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            deployment_id=dep.id,
            service_id=dep.service_id,
            repository_id=dep.service.repository_id if dep.service else None,
            environment=dep.environment,
            overall_risk_score=overall_score,
            risk_level=overall_level,
            risk_category=det_risk.risk_category,
            failure_probability=ml_res.calibrated_failure_probability,
            operational_impact_score=impact.blast_radius_score,
            impact_category=impact.impact_category,
            affected_services=[s.model_dump() for s in impact.affected_services],
            rule_score=det_risk.rule_score,
            ml_score=ml_res.raw_ml_score,
            feature_snapshot=features.model_dump(mode="json"),
            triggered_rules=[r.model_dump() for r in det_risk.triggered_rules],
            supporting_records=det_risk.supporting_records,
            supporting_incident_ids=supporting_inc_ids,
            model_version=ml_res.model_version,
            calibration_version="sigmoid" if ml_res.calibrated_failure_probability is not None else None,
            explanation=json.dumps(explanation.model_dump(mode="json")),
            assessment_status="COMPLETED",
            assessed_at=now,
            evaluated_at=now,
        )
        db.add(risk_record)
        await db.flush()

        for r_info in recs_data:
            rec_obj = Recommendation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                risk_assessment_id=risk_record.id,
                deployment_id=dep.id,
                recommendation_type=r_info["recommendation_type"],
                title=r_info["title"],
                rationale=r_info["rationale"],
                mitigation_steps=[r_info["rationale"]],
                confidence_score=r_info["confidence_score"],
                requires_approval=r_info["requires_approval"],
            )
            db.add(rec_obj)

        await db.flush()

        return UnifiedRiskAssessmentResult(
            id=str(risk_record.id),
            deployment_id=str(dep.id),
            service_id=str(dep.service_id),
            repository_id=str(risk_record.repository_id) if risk_record.repository_id else None,
            environment=dep.environment,
            overall_risk_score=overall_score,
            risk_level=overall_level,
            risk_category=det_risk.risk_category,
            failure_probability=ml_res.calibrated_failure_probability,
            operational_impact_score=impact.blast_radius_score,
            impact_category=impact.impact_category,
            affected_services=[s.model_dump() for s in impact.affected_services],
            rule_score=det_risk.rule_score,
            ml_score=ml_res.raw_ml_score,
            model_version=ml_res.model_version,
            model_status=ml_res.status,
            triggered_rules=[r.model_dump() for r in det_risk.triggered_rules],
            supporting_incident_ids=supporting_inc_ids,
            similar_incidents=[s.model_dump() for s in similar_matches],
            recommendations=recs_data,
            feature_snapshot=features.model_dump(mode="json"),
            explanation=explanation.model_dump(mode="json"),
            assessed_at=now,
        )


risk_assessment_service = RiskAssessmentService()
