import hashlib
import hmac
import json
import uuid
import pytest
from httpx import AsyncClient
from app.schemas.event import NormalizedEventContract


@pytest.mark.asyncio
async def test_event_schema_contract():
    event = NormalizedEventContract(
        tenant_id=str(uuid.uuid4()),
        source="github",
        event_type="build.failed",
        commit_sha="a" * 40,
        idempotency_key="build-101",
        payload={"exit_code": 1, "failed_step": "test_unit"}
    )
    assert event.schema_version == "1.0.0"
    assert event.source == "github"
    assert event.payload["exit_code"] == 1


@pytest.mark.asyncio
async def test_github_webhook_hmac_and_idempotency(client: AsyncClient):
    webhook_secret = "test-secret"
    payload_data = {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "action": "completed",
        "workflow_run": {
            "id": 123456,
            "conclusion": "failure",
            "head_sha": "abc1234567890abcdef1234567890abcdef1234"
        }
    }
    body_bytes = json.dumps(payload_data).encode("utf-8")
    mac = hmac.new(webhook_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    signature_header = f"sha256={mac}"
    delivery_id = f"delivery-{uuid.uuid4()}"

    # First delivery - should ingest
    res1 = await client.post(
        "/api/v1/integrations/github/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature_header,
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": delivery_id
        }
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["accepted"] is True
    assert data1["status"] in ("queued", "ingested_local", "processed_local")

    # Second delivery with identical delivery id - must safely deduplicate!
    res2 = await client.post(
        "/api/v1/integrations/github/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature_header,
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": delivery_id
        }
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["accepted"] is True
    assert data2["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature_rejected(client: AsyncClient):
    body_bytes = json.dumps({"test": "data"}).encode("utf-8")
    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid_hash_signature",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "delivery-invalid-sig-test"
        }
    )
    assert res.status_code == 401
    assert "Invalid HMAC SHA-256 signature" in res.json()["detail"]
