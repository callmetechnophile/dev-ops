from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class TriggeredRule(BaseModel):
    rule_id: str
    rule_name: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    supporting_evidence: Dict[str, Any] = {}


class RecommendationRead(BaseModel):
    id: str
    risk_assessment_id: str
    deployment_id: str
    recommendation_type: str
    title: str
    rationale: str
    mitigation_steps: List[str] = []
    confidence_score: float
    requires_approval: str

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentRead(BaseModel):
    id: str
    deployment_id: str
    service_id: str
    overall_risk_score: float
    risk_level: str
    failure_probability: Optional[float] = None
    operational_impact_score: float
    rule_score: float
    ml_score: Optional[float] = None
    triggered_rules: List[Dict[str, Any]] = []
    supporting_records: List[Dict[str, Any]] = []
    evaluated_at: datetime
    recommendations: List[RecommendationRead] = []

    model_config = ConfigDict(from_attributes=True)
