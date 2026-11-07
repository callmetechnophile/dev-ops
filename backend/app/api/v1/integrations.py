import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import verify_github_signature
from app.schemas.event import NormalizedEventContract, EventIngestResponse
from app.services.event_service import ingest_event

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.post("/github/webhook", response_model=EventIngestResponse)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header("push", alias="X-GitHub-Event"),
    x_github_delivery: str = Header(None, alias="X-GitHub-Delivery"),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests GitHub webhook events, verifies HMAC signature, normalizes to internal event contract.
    """
    body_bytes = await request.body()

    if not verify_github_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook HMAC signature"
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload"
        )

    # Resolve delivery id for idempotency
    delivery_id = x_github_delivery or str(uuid.uuid4())
    tenant_id = payload.get("tenant_id") or "00000000-0000-0000-0000-000000000001"
    commit_sha = payload.get("after") or (payload.get("head_commit") or {}).get("id")

    normalized = NormalizedEventContract(
        tenant_id=tenant_id,
        source="github",
        event_type=f"github.{x_github_event}",
        schema_version="1.0.0",
        commit_sha=commit_sha,
        idempotency_key=f"github:{delivery_id}",
        payload=payload
    )

    response, _ = await ingest_event(db, normalized)
    return response
