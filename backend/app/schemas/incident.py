from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


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


class RootCauseHypothesisRead(BaseModel):
    id: str
    incident_id: str
    hypothesis_statement: str
    confidence_score: float
    status: str
    evidence_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConfirmedRootCauseRead(BaseModel):
    id: str
    incident_id: str
    root_cause_summary: str
    verified_engineering_lesson: str
    prevention_strategy: str
    confirmed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentRead(BaseModel):
    id: str
    tenant_id: str
    service_id: str
    deployment_id: Optional[str] = None
    title: str
    summary: str
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    blast_radius_score: float = 1.0
    failures: List[FailureRead] = []
    hypotheses: List[RootCauseHypothesisRead] = []
    confirmed_root_cause: Optional[ConfirmedRootCauseRead] = None

    model_config = ConfigDict(from_attributes=True)
