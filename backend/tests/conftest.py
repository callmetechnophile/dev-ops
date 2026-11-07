import asyncio
import os
import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEBUG"] = "False"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"

from app.database import Base, get_db
from app.main import app as fastapi_application
import app.models as models

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Seed default tenant and user
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        tenant = models.Tenant(
            id=tenant_id,
            name="Acme Corp",
            slug="acme-corp",
            is_active=True
        )
        session.add(tenant)
        await session.flush()

        user = models.User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            tenant_id=tenant_id,
            email="lead-engineer@acme.corp",
            full_name="Lead DevOps Architect",
            hashed_password="hashed_pw_placeholder",
            role="approver",
            is_active=True
        )
        session.add(user)

        repo = models.Repository(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id=tenant_id,
            name="payment-gateway",
            full_name="acme/payment-gateway",
            provider="github",
            default_branch="main"
        )
        session.add(repo)

        service = models.Service(
            id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
            tenant_id=tenant_id,
            repository_id=repo.id,
            name="Payment Service",
            slug="payment-service",
            tier="tier-1",
            health_status="healthy",
            metadata_json={"framework": "fastapi", "runtime": "python3.13"}
        )
        session.add(service)

        await session.commit()
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    fastapi_application.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_application.dependency_overrides.clear()
