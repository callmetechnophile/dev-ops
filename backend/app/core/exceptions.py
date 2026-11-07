from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class DevOpsIntelligenceError(Exception):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DomainException(DevOpsIntelligenceError):
    pass


class EntityNotFoundError(DevOpsIntelligenceError):
    pass


class InvalidEventError(DevOpsIntelligenceError):
    pass


class DuplicateEventError(DevOpsIntelligenceError):
    pass


class ApprovalError(DevOpsIntelligenceError):
    pass


class SecurityVerificationError(DevOpsIntelligenceError):
    pass
