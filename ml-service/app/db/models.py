"""
SQLAlchemy ORM models for tables the ML service reads/writes.
Schema is owned by backend-api (Alembic migrations). These are read/write mirrors.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.postgres import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_code = Column(String(50), nullable=False, unique=True)
    tenant_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    model_name = Column(String(255), nullable=False)
    model_description = Column(Text, nullable=True)
    model_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "model_name", name="uq_ml_models_tenant_name"),
    )


class MLModelVersion(Base):
    __tablename__ = "ml_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False)
    semantic_version = Column(String(50), nullable=False)
    full_version_label = Column(String(255), nullable=False)
    stage = Column(String(50), nullable=False, default="staging")
    model_artifact_path = Column(Text, nullable=False)
    dataset_hash = Column(String(128), nullable=True)
    feature_schema_hash = Column(String(128), nullable=True)
    training_start = Column(DateTime(timezone=True), nullable=True)
    training_end = Column(DateTime(timezone=True), nullable=True)
    accuracy = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    false_alarm_rate = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "full_version_label", name="uq_ml_model_versions_tenant_label"),
    )


class MLModelDeployment(Base):
    __tablename__ = "ml_model_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False)
    model_version_id = Column(UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=False)
    is_production = Column(Boolean, nullable=False, default=False)
    deployment_start = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deployment_end = Column(DateTime(timezone=True), nullable=True)
    rollback_from_version_id = Column(UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=True)
    asset_id = Column(UUID(as_uuid=True), nullable=True)
    sensor_id = Column(UUID(as_uuid=True), nullable=True)
    prediction_id = Column(String(100), nullable=True)
    payload_normalized = Column(JSONB, nullable=True)
    validation_data = Column(JSONB, nullable=True)
    prediction_label = Column(String(255), nullable=False)
    probability = Column(Float, nullable=True)
    new_label = Column(String(255), nullable=False)
    correction = Column(Text, nullable=True)
    feedback_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=False)
