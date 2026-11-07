from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str  # healthy, degraded, unhealthy
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    status: str  # healthy, degraded, unhealthy
    app_name: str
    version: str
    timestamp: datetime
    components: Dict[str, ComponentHealth]
