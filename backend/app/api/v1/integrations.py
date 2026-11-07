import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import validate_webhook_request
from app.core import metrics
from app.schemas.event import EventIngestResponse
from app.services.webhook_service import handle_github_webhook_delivery
from app.integrations.github.client import github_client
from app.workers.redis_stream_worker import redis_stream_worker

router = APIRouter(prefix="/integrations", tags=["Integrations"])
logger = logging.getLogger(__name__)


@router.get("/github/status")
async def get_github_integration_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns live GitHub App integration status, connectivity details, and webhook metrics.
    Section 8 & Section 9 of Specification.
    """
    status_info = github_client.get_integration_status()
    return {
        "status": status_info["status"],
        "auth_type": status_info["auth_type"],
        "app_id": status_info["app_id"],
        "installation_id": status_info["installation_id"],
        "webhook_configured": status_info["webhook_configured"],
        "supported_events": ["push", "pull_request", "workflow_run", "workflow_job", "deployment", "deployment_status"],
    }


@router.post("/github/webhook", response_model=EventIngestResponse)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI webhook receiver for GitHub operational events.
    Verifies HMAC-SHA256 signature, validates delivery ID, persists delivery,
    and publishes to Redis Streams.
    Section 3 & 5 of Specification.
    """
    body_bytes = await request.body()

    # 1. Strict validation (size limit, headers, HMAC-SHA256 constant time verification)
    is_valid, error_msg = validate_webhook_request(
        payload_bytes=body_bytes,
        signature_header=x_hub_signature_256,
        event_header=x_github_event,
        delivery_id=x_github_delivery,
    )

    if not is_valid:
        metrics.github_webhook_invalid_signature_total.inc()
        logger.warning(
            f"Rejected GitHub webhook from {request.client.host if request.client else 'unknown'}: {error_msg}"
        )
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
                if "signature" in (error_msg or "").lower()
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=error_msg,
        )

    # 2. Parse payload safely
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception as e:
        logger.error(f"Failed parsing webhook JSON for delivery {x_github_delivery}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON body")

    # Resolve tenant
    tenant_id = payload.get("tenant_id") or "00000000-0000-0000-0000-000000000001"

    # 3. Process delivery
    response, is_new = await handle_github_webhook_delivery(
        db=db,
        delivery_id=x_github_delivery or "unknown",
        event_type=x_github_event or "unknown",
        signature=x_hub_signature_256,
        payload_dict=payload,
        tenant_id=tenant_id,
    )

    # If new and local processing mode (Redis offline or test mode), process synchronously
    if is_new and response.status == "ingested_local":
        try:
            await redis_stream_worker.process_event(
                db=db,
                delivery_id=x_github_delivery or "unknown",
                event_type=x_github_event or "unknown",
                payload=payload,
                tenant_id=tenant_id,
            )
            response.status = "processed_local"
        except Exception as e:
            logger.error(f"Error in fallback local event processing: {e}", exc_info=True)

    return response
