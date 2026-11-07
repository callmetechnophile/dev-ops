import logging
import uuid
from typing import Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import Event
from app.schemas.event import NormalizedEventContract, EventIngestResponse
from app.redis_client import redis_manager
from app.config import settings

logger = logging.getLogger(__name__)


async def ingest_event(db: AsyncSession, contract: NormalizedEventContract) -> Tuple[EventIngestResponse, bool]:
    """
    Ingests an incoming event with strict idempotency and persistence.
    Returns (Response, is_new_event).
    """
    # 1. Deduplication check via tenant_id + idempotency_key
    stmt = select(Event).where(
        Event.tenant_id == uuid.UUID(contract.tenant_id), Event.idempotency_key == contract.idempotency_key
    )
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()

    if existing_event:
        logger.info(f"Duplicate event detected for key: {contract.idempotency_key}. Safely skipping.")
        return (
            EventIngestResponse(
                accepted=True,
                event_id=str(existing_event.id),
                idempotency_key=contract.idempotency_key,
                status="duplicate_ignored",
                message="Event already ingested. Idempotency guaranteed.",
            ),
            False,
        )

    # 2. Persist new event to relational store
    db_event = Event(
        id=uuid.UUID(contract.event_id) if contract.event_id else uuid.uuid4(),
        event_id=contract.event_id,
        tenant_id=uuid.UUID(contract.tenant_id),
        source=contract.source,
        event_type=contract.event_type,
        schema_version=contract.schema_version,
        repository_id=uuid.UUID(contract.repository_id) if contract.repository_id else None,
        service_id=uuid.UUID(contract.service_id) if contract.service_id else None,
        deployment_id=uuid.UUID(contract.deployment_id) if contract.deployment_id else None,
        commit_sha=contract.commit_sha,
        environment=contract.environment,
        occurred_at=contract.occurred_at,
        received_at=contract.received_at,
        correlation_id=contract.correlation_id,
        idempotency_key=contract.idempotency_key,
        payload=contract.payload,
    )

    db.add(db_event)
    await db.flush()

    # 3. Publish to Redis Stream for asynchronous correlation workers
    stream_payload = {
        "event_id": str(db_event.id),
        "tenant_id": str(db_event.tenant_id),
        "event_type": db_event.event_type,
        "source": db_event.source,
        "correlation_id": db_event.correlation_id,
        "occurred_at": db_event.occurred_at.isoformat(),
    }
    await redis_manager.publish_event(settings.REDIS_STREAM_EVENTS, stream_payload)

    return (
        EventIngestResponse(
            accepted=True,
            event_id=str(db_event.id),
            idempotency_key=contract.idempotency_key,
            status="ingested",
            message="Event validated, persisted, and queued.",
        ),
        True,
    )
