import hashlib
import hmac
import json
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_webhook_valid_signature_accepted(client: AsyncClient):
    webhook_secret = "test-secret"
    payload = {
        "repository": {"id": 12345, "name": "web-app", "full_name": "acme/web-app"},
        "ref": "refs/heads/main",
        "after": "d6a8f10239a58b23c914e6d420a7b52f90123456",
        "commits": []
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    mac = hmac.new(webhook_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    delivery_id = str(uuid.uuid4())
    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={mac}",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": delivery_id
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["delivery_id"] == delivery_id


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    raw_bytes = json.dumps({"test": 123}).encode("utf-8")
    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid0000000000000000000000000000000000000000000000000000000000",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": str(uuid.uuid4())
        }
    )
    assert res.status_code == 401
    assert "Invalid HMAC" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client: AsyncClient):
    raw_bytes = json.dumps({"test": 123}).encode("utf-8")
    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": str(uuid.uuid4())
        }
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_event_header_rejected(client: AsyncClient):
    raw_bytes = json.dumps({"test": 123}).encode("utf-8")
    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=123",
            "X-GitHub-Delivery": str(uuid.uuid4())
        }
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_webhook_malformed_json_rejected(client: AsyncClient):
    webhook_secret = "test-secret"
    raw_bytes = b"not-a-valid-json-payload-{"
    mac = hmac.new(webhook_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    res = await client.post(
        "/api/v1/integrations/github/webhook",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={mac}",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": str(uuid.uuid4())
        }
    )
    assert res.status_code == 400
    assert "Malformed JSON" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_duplicate_delivery_idempotent(client: AsyncClient):
    webhook_secret = "test-secret"
    payload = {"repository": {"name": "app", "full_name": "acme/app"}}
    raw_bytes = json.dumps(payload).encode("utf-8")
    mac = hmac.new(webhook_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    delivery_id = f"delivery-{uuid.uuid4()}"

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={mac}",
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": delivery_id
    }

    # Delivery 1
    res1 = await client.post("/api/v1/integrations/github/webhook", content=raw_bytes, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] in ("queued", "ingested_local", "processed_local")

    # Delivery 2 (Duplicate)
    res2 = await client.post("/api/v1/integrations/github/webhook", content=raw_bytes, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"
