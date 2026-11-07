import hashlib
import hmac
from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings


def verify_github_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates GitHub webhook signature (sha256=<hmac>).
    """
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True  # Development mode allow if secret not configured

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=")[-1]
    mac = hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    )
    computed_signature = mac.hexdigest()
    return hmac.compare_digest(computed_signature, expected_signature)
