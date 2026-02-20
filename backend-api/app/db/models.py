"""
SQLAlchemy ORM models for all PostgreSQL tables.
Aligned with the reference ERD (Section 3.5.3 of the architecture plan).
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

from app.db.postgres import Base


# ============================================================
# TENANTS
# ============================================================
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_code = Column(String(50), nullable=False, unique=True)
    tenant_name = Column(String(255), nullable=False)
    plan = Column(String(50), nullable=False, default="free")
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), nullable=True)


# ============================================================
# USERS
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,  # None for platform-scoped super_admin users
    )
    username = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )


# ============================================================
# USER SETTINGS
# ============================================================
class UserSetting(Base):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    auto_refresh = Column(Boolean, nullable=False, default=True)
    refresh_interval_sec = Column(Integer, nullable=False, default=5)
    anomaly_threshold = Column(Float, nullable=False, default=0.7)
    enable_notifications = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================
# FAULT ACTIONS
# ============================================================
class FaultAction(Base):
    __tablename__ = "fault_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    config = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================
# SITES
# ============================================================
class Site(Base):
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_code = Column(String(100), nullable=False)
    site_name = Column(String(255), nullable=False)
    location = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "site_code", name="uq_sites_tenant_code"),
    )


# ============================================================
# GATEWAYS
# ============================================================
class Gateway(Base):
    __tablename__ = "gateways"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    gateway_code = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    firmware_version = Column(String(100), nullable=True)
    is_online = Column(Boolean, nullable=False, default=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "gateway_code", name="uq_gateways_tenant_code"
        ),
    )


# ============================================================
# ASSETS
# ============================================================
class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    gateway_id = Column(
        UUID(as_uuid=True), ForeignKey("gateways.id"), nullable=True
    )
    asset_code = Column(String(100), nullable=False)
    asset_name = Column(String(255), nullable=False)
    asset_type = Column(String(100), nullable=False)
    image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_code", name="uq_assets_tenant_code"),
    )


# ============================================================
# SENSORS
# ============================================================
class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    gateway_id = Column(
        UUID(as_uuid=True), ForeignKey("gateways.id"), nullable=True
    )
    sensor_code = Column(String(100), nullable=False)
    sensor_type = Column(String(100), nullable=False)
    mount_location = Column(String(100), nullable=True)
    mqtt_topic = Column(String(255), nullable=True)
    validation_data = Column(JSONB, nullable=True)
    installation_date = Column(Date, nullable=True)
    position_x = Column(Numeric(5, 2), nullable=False, server_default="0")
    position_y = Column(Numeric(5, 2), nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sensor_code", name="uq_sensors_tenant_code"),
    )


# ============================================================
# ASSET HEALTH
# ============================================================
class AssetHealth(Base):
    __tablename__ = "asset_health"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    health_score = Column(
        Float,
        nullable=False,
    )
    health_status = Column(String(50), nullable=False)
    calculation_method = Column(String(100), nullable=True)
    health_calc_date = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "health_score >= 0 AND health_score <= 100",
            name="ck_asset_health_score_range",
        ),
        Index(
            "idx_asset_health_latest", "asset_id", health_calc_date.desc()
        ),
    )


# ============================================================
# ML MODELS
# ============================================================
class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    model_name = Column(String(255), nullable=False)
    model_description = Column(Text, nullable=True)
    model_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "model_name", name="uq_ml_models_tenant_name"
        ),
    )


# ============================================================
# ML MODEL VERSIONS
# ============================================================
class MLModelVersion(Base):
    __tablename__ = "ml_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ml_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    semantic_version = Column(String(50), nullable=False)
    full_version_label = Column(String(255), nullable=False)
    stage = Column(String(50), nullable=False, default="staging")
    model_artifact_path = Column(Text, nullable=False)
    docker_image_tag = Column(String(255), nullable=True)
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
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "full_version_label",
            name="uq_ml_model_versions_tenant_label",
        ),
    )


# ============================================================
# ML MODEL DEPLOYMENTS
# ============================================================
class MLModelDeployment(Base):
    __tablename__ = "ml_model_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    model_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False
    )
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=False
    )
    is_production = Column(Boolean, nullable=False, default=False)
    deployment_start = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deployment_end = Column(DateTime(timezone=True), nullable=True)
    rollback_from_version_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


# ============================================================
# ASSET MODEL VERSIONS
# ============================================================
class AssetModelVersion(Base):
    __tablename__ = "asset_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    asset_id = Column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    model_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_models.id"), nullable=False
    )
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=False
    )
    stage = Column(String(50), nullable=False, default="production")
    deployment_start = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deployment_end = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


# ============================================================
# FEEDBACK
# ============================================================
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    sensor_id = Column(
        UUID(as_uuid=True), ForeignKey("sensors.id"), nullable=True
    )
    prediction_id = Column(String(100), nullable=True)
    payload_normalized = Column(JSONB, nullable=True)
    validation_data = Column(JSONB, nullable=True)
    prediction_label = Column(String(255), nullable=False)
    probability = Column(Float, nullable=True)
    new_label = Column(String(255), nullable=False)
    correction = Column(Text, nullable=True)
    feedback_type = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


# ============================================================
# NOTIFICATION TYPES
# ============================================================
class NotificationType(Base):
    __tablename__ = "notification_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    notify_type_name = Column(String(100), nullable=False)
    notify_type_data = Column(JSONB, nullable=False, server_default="{}")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "notify_type_name",
            name="uq_notification_types_tenant_name",
        ),
    )


# ============================================================
# ALARM RULES
# ============================================================
class AlarmRule(Base):
    __tablename__ = "alarm_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    sensor_id = Column(
        UUID(as_uuid=True), ForeignKey("sensors.id"), nullable=True
    )
    rule_name = Column(String(255), nullable=False)
    parameter_name = Column(String(100), nullable=False)
    threshold_value = Column(Float, nullable=False)
    comparison_operator = Column(String(10), nullable=False)
    severity_level = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


# ============================================================
# ALARM NOTIFICATION TYPES (M:N join)
# ============================================================
class AlarmNotificationType(Base):
    __tablename__ = "alarm_notification_types"

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    alarm_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alarm_rules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    notification_type_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_types.id", ondelete="CASCADE"),
        primary_key=True,
    )


# ============================================================
# ALARM EVENTS
# ============================================================
class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    sensor_id = Column(
        UUID(as_uuid=True), ForeignKey("sensors.id"), nullable=True
    )
    alarm_rule_id = Column(
        UUID(as_uuid=True), ForeignKey("alarm_rules.id"), nullable=True
    )
    prediction_id = Column(String(100), nullable=True)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("ml_model_versions.id"), nullable=True
    )
    triggered_value = Column(Float, nullable=True)
    triggered_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    correction_plan = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="open")
    acknowledged_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_alarm_events_tenant_status",
            "tenant_id",
            "status",
            triggered_at.desc(),
        ),
    )


# ============================================================
# NOTIFICATION LOG
# ============================================================
class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    alarm_event_id = Column(
        UUID(as_uuid=True), ForeignKey("alarm_events.id"), nullable=False
    )
    notification_type_id = Column(
        UUID(as_uuid=True), ForeignKey("notification_types.id"), nullable=True
    )
    channel = Column(String(50), nullable=False)
    recipient = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================
# MAINTENANCE WORK ORDERS
# ============================================================
class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    asset_id = Column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    alarm_event_id = Column(
        UUID(as_uuid=True), ForeignKey("alarm_events.id"), nullable=True
    )
    work_number = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    priority_level = Column(String(50), nullable=False, default="medium")
    status = Column(String(50), nullable=False, default="open")
    assigned_to = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


# ============================================================
# API KEYS (service-to-service auth)
# ============================================================
# ============================================================
# AUDIT LOGS
# ============================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    scope = Column(String(20), nullable=False)
    action = Column(String(100), nullable=False)
    target_tenant_id = Column(UUID(as_uuid=True), nullable=True)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    key_hash = Column(Text, nullable=False)
    scopes = Column(ARRAY(Text), nullable=False, server_default="{}")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
