import asyncio
import json
import logging
import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import AsyncSessionLocal
from app.integrations.github.normalizer import normalize_github_event
from app.services.correlation_engine import correlation_engine
from app.services.incident_reconstruction import incident_reconstruction_engine
from app.services.root_cause_engine import root_cause_engine
from app.models.event import Event
from app.models.webhook_delivery import WebhookDelivery
from app.core import metrics

logger = logging.getLogger(__name__)


class RedisStreamWorker:
    """
    Robust Redis Streams consumer worker with consumer groups, message acknowledgment,
    pending message recovery, retry handling, and dead-letter routing.
    Section 5 of Specification.
    """

    def __init__(self):
        self.stream_key = settings.REDIS_STREAM_EVENTS
        self.dead_letter_key = settings.REDIS_STREAM_DEAD_LETTER
        self.group_name = settings.REDIS_CONSUMER_GROUP
        self.consumer_name = settings.REDIS_CONSUMER_NAME
        self.max_retries = 3
        self._running = False
        self._client = None

    @property
    def running(self) -> bool:
        return self._running

    @running.setter
    def running(self, val: bool):
        self._running = val

    async def _init_redis(self):
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=5.0)
        # Ensure consumer group exists
        try:
            await self._client.xgroup_create(name=self.stream_key, groupname=self.group_name, id="0", mkstream=True)
            logger.info(f"Consumer group '{self.group_name}' created on stream '{self.stream_key}'.")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.warning(f"Error ensuring consumer group: {e}")

    async def start(self):
        self._running = True
        logger.info(f"Starting RedisStreamWorker '{self.consumer_name}' for stream '{self.stream_key}'...")
        await self._init_redis()

        while self._running:
            try:
                # 1. First recover any stale pending messages (> 30s)
                await self._recover_pending_messages()

                # 2. Read new messages from stream
                response = await self._client.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=10,
                    block=2000,
                )

                if response:
                    for stream, messages in response:
                        for message_id, data in messages:
                            await self._handle_message(message_id, data)

            except asyncio.CancelledError:
                logger.info("Worker task cancelled, stopping.")
                break
            except Exception as e:
                logger.error(f"Error in Redis Stream Worker loop: {e}", exc_info=True)
                await asyncio.sleep(2)

    def stop(self):
        self._running = False

    async def _recover_pending_messages(self):
        """Claims messages that have been pending/unacknowledged for > 30 seconds."""
        try:
            # xautoclaim: min_idle_time = 30000ms
            res = await self._client.xautoclaim(
                name=self.stream_key,
                groupname=self.group_name,
                consumername=self.consumer_name,
                min_idle_time=30000,
                start_id="0-0",
                count=5,
            )
            claimed_messages = res[1] if res and len(res) > 1 else []
            for message_id, data in claimed_messages:
                logger.info(f"Re-claimed pending message {message_id}")
                await self._handle_message(message_id, data)
        except Exception as e:
            logger.debug(f"Pending message check: {e}")

    async def _handle_message(self, message_id: str, data: Dict[str, Any]):
        delivery_id = data.get("delivery_id", "unknown")
        event_type = data.get("event_type", "unknown")
        tenant_id = data.get("tenant_id", "00000000-0000-0000-0000-000000000001")
        retry_count = int(data.get("retry_count", 0))

        start_time = time.perf_counter()

        try:
            payload_str = data.get("payload_json")
            payload = json.loads(payload_str) if payload_str else {}

            # Process event in database transaction
            async with AsyncSessionLocal() as session:
                await self.process_event(session, delivery_id, event_type, payload, tenant_id)
                await session.commit()

            # Acknowledge message in Redis stream
            await self._client.xack(self.stream_key, self.group_name, message_id)
            metrics.event_processing_duration_seconds.labels(event_type=event_type).observe(
                time.perf_counter() - start_time
            )
            logger.info(f"Processed and ACKed message {message_id} (delivery: {delivery_id}, event: {event_type})")

        except Exception as e:
            logger.error(f"Failed processing message {message_id}: {e}", exc_info=True)
            metrics.github_webhook_processing_errors_total.labels(
                event_type=event_type, error_type=type(e).__name__
            ).inc()

            if retry_count < self.max_retries:
                # Requeue with incremented retry count
                data["retry_count"] = retry_count + 1
                await self._client.xadd(self.stream_key, data)
                await self._client.xack(self.stream_key, self.group_name, message_id)
                logger.warning(f"Message {message_id} retry queued ({retry_count + 1}/{self.max_retries})")
            else:
                # Route poison pill to dead letter stream
                data["error_reason"] = str(e)
                data["failed_at"] = datetime.now(timezone.utc).isoformat()
                await self._client.xadd(self.dead_letter_key, data)
                await self._client.xack(self.stream_key, self.group_name, message_id)
                logger.critical(f"Message {message_id} routed to dead letter stream: {self.dead_letter_key}")

    async def process_event(
        self, db: AsyncSession, delivery_id: str, event_type: str, payload: Dict[str, Any], tenant_id: str
    ):
        """
        Executes normalization, persistence to events ledger, and deterministic correlation.
        """
        tenant_uuid = uuid.UUID(tenant_id)

        # 1. Normalize
        normalized_contract, specific_event = normalize_github_event(
            event_type=event_type, delivery_id=delivery_id, payload=payload, tenant_id=tenant_id
        )

        # 2. Persist to immutable normalized events ledger
        # Deduplication check for events table
        stmt = select(Event).where(
            and_(Event.tenant_id == tenant_uuid, Event.idempotency_key == normalized_contract.idempotency_key)
        )
        res = await db.execute(stmt)
        existing_event = res.scalar_one_or_none()

        if not existing_event:
            db_event = Event(
                id=uuid.UUID(normalized_contract.event_id),
                tenant_id=tenant_uuid,
                event_id=normalized_contract.event_id,
                source="github",
                event_type=normalized_contract.event_type,
                schema_version=normalized_contract.schema_version,
                repository_id=(
                    uuid.UUID(normalized_contract.repository_id) if normalized_contract.repository_id else None
                ),
                service_id=uuid.UUID(normalized_contract.service_id) if normalized_contract.service_id else None,
                deployment_id=(
                    uuid.UUID(normalized_contract.deployment_id) if normalized_contract.deployment_id else None
                ),
                commit_sha=normalized_contract.commit_sha,
                environment=normalized_contract.environment,
                occurred_at=normalized_contract.occurred_at,
                received_at=normalized_contract.received_at,
                correlation_id=normalized_contract.correlation_id,
                idempotency_key=normalized_contract.idempotency_key,
                payload=payload,
            )
            db.add(db_event)
            await db.flush()
            metrics.events_persisted_total.labels(event_type=event_type, tenant_id=tenant_id).inc()

        # 3. Deterministic Domain Correlations
        if event_type == "push" and specific_event:
            await correlation_engine.process_push_event(db, tenant_uuid, specific_event)
        elif event_type == "pull_request" and specific_event:
            await correlation_engine.process_pull_request_event(db, tenant_uuid, specific_event)
        elif event_type == "workflow_run" and specific_event:
            await correlation_engine.process_workflow_run_event(db, tenant_uuid, specific_event)
        elif event_type == "workflow_job" and specific_event:
            await correlation_engine.process_workflow_job_event(db, tenant_uuid, specific_event)
        elif event_type in ("deployment", "deployment_status") and specific_event:
            await correlation_engine.process_deployment_event(db, tenant_uuid, specific_event)

        # 4. Incident Reconstruction & Failure Intelligence (Milestone 3)
        target_event = db_event if not existing_event else existing_event
        if target_event:
            try:
                incident = await incident_reconstruction_engine.process_event_for_incidents(
                    db=db,
                    tenant_id=tenant_uuid,
                    event_model=target_event,
                )
                if incident:
                    await root_cause_engine.analyze_incident(db, tenant_uuid, incident.id)
            except Exception as e:
                logger.error(f"Error during incident reconstruction for event {target_event.id}: {e}", exc_info=True)

        # 5. Mark webhook delivery as PROCESSED
        w_stmt = select(WebhookDelivery).where(
            and_(WebhookDelivery.tenant_id == tenant_uuid, WebhookDelivery.delivery_id == delivery_id)
        )
        w_res = await db.execute(w_stmt)
        delivery = w_res.scalar_one_or_none()
        if delivery:
            delivery.status = "PROCESSED"
            delivery.processed_at = datetime.now(timezone.utc)
            await db.flush()


redis_stream_worker = RedisStreamWorker()
