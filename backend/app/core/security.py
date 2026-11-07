import hashlib
import hmac
import logging
from typing import Optional, Tuple
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)


def verify_github_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates GitHub webhook signature (sha256=<hmac_hex>) using constant-time comparison.
    Section 3 of Specification.
    """
    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET is empty. Webhook authentication cannot be verified.")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    expected_signature = signature_header.split("sha256=")[-1].strip()
    mac = hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    )
    computed_signature = mac.hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def validate_webhook_request(
    payload_bytes: bytes,
    signature_header: Optional[str],
    event_header: Optional[str],
    delivery_id: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive verification of incoming GitHub webhook request:
    - Size check
    - Event header presence
    - Delivery ID presence
    - HMAC SHA-256 signature match
    """
    if len(payload_bytes) > settings.MAX_WEBHOOK_PAYLOAD_BYTES:
        return False, f"Payload size {len(payload_bytes)} bytes exceeds maximum allowed limit {settings.MAX_WEBHOOK_PAYLOAD_BYTES}"

    if not event_header:
        return False, "Missing X-GitHub-Event header"

    if not delivery_id:
        return False, "Missing X-GitHub-Delivery header"

    if not verify_github_signature(payload_bytes, signature_header):
        return False, "Invalid HMAC SHA-256 signature"

    return True, None
