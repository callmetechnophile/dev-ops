import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Float, Index, Text
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class Repository(Base, TimestampMixin, TenantMixin):
    __tablename__ = "repositories"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False, index=True)  # e.g., org/repo
    provider = Column(String(50), default="github", nullable=False)
    default_branch = Column(String(100), default="main", nullable=False)
    clone_url = Column(String(512), nullable=True)

    organization = relationship("Organization", back_populates="repositories")
    services = relationship("Service", back_populates="repository")


class Service(Base, TimestampMixin, TenantMixin):
    __tablename__ = "services"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    repository_id = Column(GUID(), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    tier = Column(String(50), default="tier-2", nullable=False)  # tier-1 (critical), tier-2, tier-3
    health_status = Column(String(50), default="healthy", nullable=False)  # healthy, degraded, failing, unknown
    metadata_json = Column(JSON, default=dict, nullable=False)

    repository = relationship("Repository", back_populates="services")
    deployments = relationship("Deployment", back_populates="service")

    __table_args__ = (
        Index("ix_service_tenant_slug", "tenant_id", "slug", unique=True),
    )


class Environment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "environments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # production, staging, development
    slug = Column(String(100), nullable=False)
    is_production = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_env_tenant_slug", "tenant_id", "slug", unique=True),
    )


class ServiceDependency(Base, TimestampMixin, TenantMixin):
    __tablename__ = "service_dependencies"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    source_service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    target_service_id = Column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(50), default="sync_http", nullable=False)  # sync_http, grpc, async_queue, database
    criticality = Column(String(50), default="high", nullable=False)  # high, medium, low
    weight = Column(Float, default=1.0, nullable=False)

    __table_args__ = (
        Index("ix_svc_dep_unique", "tenant_id", "source_service_id", "target_service_id", unique=True),
    )
