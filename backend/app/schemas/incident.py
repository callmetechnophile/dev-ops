from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class FailureRead(BaseModel):
    id: str
    service_id: str
    failure_type: str
    error_message: str
    stack_trace: Optional[str] = None
    container_name: Optional[str] = None
    pod_name: Optional[str] = None
    exit_code: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class FailureClassificationRead(BaseModel):
    id: str
    category: str
    subcategory: str
    classification_method: str = "DETERMINISTIC_RULE"
    evidence: Dict[str, Any] = {}
    classifier_version: str = "1.0.0"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RootCauseHypothesisRead(BaseModel):
    id: str
    incident_id: str
    hypothesis: str
    hypothesis_statement: str
    explanation: str = ""
    evidence_event_ids: List[str] = []
    confidence_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, INSUFFICIENT_EVIDENCE
    confidence_score: float = 0.5
    status: str = "SUSPECTED"  # SUSPECTED, PROBABLE, CONFIRMED, REJECTED, UNKNOWN
    generated_by: str = "DETERMINISTIC_STAGE_A"
    evidence_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConfirmedRootCauseRead(BaseModel):
    id: str
    incident_id: str
    hypothesis_id: Optional[str] = None
    confirmed_by: str = "authorized_engineer"
    confirmation_notes: str = ""
    root_cause_summary: str
    verified_engineering_lesson: str
    prevention_strategy: str
    confirmed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RemediationActionRead(BaseModel):
    id: str
    incident_id: str
    action_type: str
    description: str
    proposed_by: str = "SYSTEM"
    approved_by: Optional[str] = None
    execution_status: str = "RECORDED"
    outcome: Optional[str] = "UNKNOWN"
    effectiveness: Optional[str] = "MEDIUM"
    runbook_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationalLessonRead(BaseModel):
    id: str
    incident_id: str
    title: str
    lesson: str
    verified_root_cause_id: str
    remediation_action_id: Optional[str] = None
    applicability_conditions: Dict[str, Any] = {}
    verification_status: str = "VERIFIED"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentRead(BaseModel):
    id: str
    tenant_id: str
    incident_key: str = Field(default="")
    service_id: Optional[str] = None
    primary_service_id: Optional[str] = None
    repository_id: Optional[str] = None
    deployment_id: Optional[str] = None
    title: str
    summary: str
    description: Optional[str] = None
    incident_type: str = "UNKNOWN_FAILURE"
    severity: str
    status: str
    environment: str = "production"
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    blast_radius_score: float = 1.0
    classifications: List[FailureClassificationRead] = []
    failures: List[FailureRead] = []
    hypotheses: List[RootCauseHypothesisRead] = []
    confirmed_root_cause: Optional[ConfirmedRootCauseRead] = None
    remediations: List[RemediationActionRead] = []
    lessons: List[OperationalLessonRead] = []

    model_config = ConfigDict(from_attributes=True)


class IncidentAnalyticsResponse(BaseModel):
    total_incidents: int
    open_incidents: int
    resolved_incidents: int
    p1_count: int
    p2_count: int
    category_distribution: Dict[str, int]
    environment_distribution: Dict[str, int]
    recent_trend: List[Dict[str, Any]]
