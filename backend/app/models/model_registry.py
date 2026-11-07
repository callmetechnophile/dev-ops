import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index, DateTime
from sqlalchemy.types import JSON
from app.database import Base
from app.models.base import GUID, TimestampMixin, TenantMixin


class ModelVersion(Base, TimestampMixin, TenantMixin):
    __tablename__ = "model_versions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), default="deployment_risk_xgboost", nullable=False, index=True)
    version = Column(String(50), nullable=False)
    algorithm = Column(String(100), default="XGBoostClassifier", nullable=False)
    status = Column(String(50), default="CANDIDATE", nullable=False, index=True)  # CANDIDATE, ACTIVE, RETIRED, FAILED
    training_dataset_size = Column(Integer, default=0, nullable=False)
    features_list = Column(JSON, default=list, nullable=False)
    hyperparameters = Column(JSON, default=dict, nullable=False)
    evaluation_metrics = Column(JSON, default=dict, nullable=False)  # f1, roc_auc, brier_score, precision, recall
    is_calibrated = Column(String(10), default="false", nullable=False)
    artifact_path = Column(String(512), nullable=True)
    trained_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_model_version_tenant_name", "tenant_id", "model_name", "version", unique=True),
    )
