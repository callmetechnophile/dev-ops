from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class ServiceDependencyRead(BaseModel):
    id: str
    source_service_id: str
    target_service_id: str
    dependency_type: str
    criticality: str
    weight: float

    model_config = ConfigDict(from_attributes=True)


class ServiceRead(BaseModel):
    id: str
    tenant_id: str
    repository_id: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    tier: str
    health_status: str
    metadata_json: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
