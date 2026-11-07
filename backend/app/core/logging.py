import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "access_token",
    "webhook_secret",
    "github_app_private_key",
    "private_key",
    "api_key",
}

BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE)
SECRET_PATTERN = re.compile(r"(ghp_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})")


def redact_sensitive_value(val: Any) -> Any:
    if isinstance(val, str):
        val = BEARER_PATTERN.sub(r"\1[REDACTED]", val)
        val = SECRET_PATTERN.sub("[REDACTED_GITHUB_TOKEN]", val)
        return val
    elif isinstance(val, dict):
        return {
            k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else redact_sensitive_value(v))
            for k, v in val.items()
        }
    elif isinstance(val, list):
        return [redact_sensitive_value(item) for item in val]
    return val


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter with automated credential redaction and environment context."""

    def __init__(self, service_name: str = "devops-intelligence-api", environment: str = "production"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        msg_redacted = redact_sensitive_value(msg)

        log_record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service_name", self.service_name),
            "environment": getattr(record, "environment", self.environment),
            "logger": record.name,
            "message": msg_redacted,
            "source": f"{record.filename}:{record.lineno}",
        }

        # Optional correlation metadata
        if hasattr(record, "tenant_id"):
            log_record["tenant_id"] = str(record.tenant_id)
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = str(record.correlation_id)
        if hasattr(record, "request_id"):
            log_record["request_id"] = str(record.request_id)
        if hasattr(record, "event_id"):
            log_record["event_id"] = str(record.event_id)
        if hasattr(record, "error_category"):
            log_record["error_category"] = str(record.error_category)

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging(level: str = "INFO", service_name: str = "devops-intelligence-api") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name=service_name))
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
