"""Initial schema - all PostgreSQL tables from reference ERD

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- TENANTS --
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_code", sa.String(50), nullable=False, unique=True),
        sa.Column("tenant_name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
    )

    # -- USERS --
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # -- USER SETTINGS --
    op.create_table(
        "user_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("auto_refresh", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("refresh_interval_sec", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("anomaly_threshold", sa.Float, nullable=False, server_default=sa.text("0.7")),
        sa.Column("enable_notifications", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- FAULT ACTIONS --
    op.create_table(
        "fault_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- SITES --
    op.create_table(
        "sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_code", sa.String(100), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=False),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "site_code", name="uq_sites_tenant_code"),
    )

    # -- GATEWAYS --
    op.create_table(
        "gateways",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gateway_code", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("firmware_version", sa.String(100), nullable=True),
        sa.Column("is_online", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "gateway_code", name="uq_gateways_tenant_code"),
    )

    # -- ASSETS --
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gateway_id", UUID(as_uuid=True), sa.ForeignKey("gateways.id"), nullable=True),
        sa.Column("asset_code", sa.String(100), nullable=False),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "asset_code", name="uq_assets_tenant_code"),
    )

    # -- SENSORS --
    op.create_table(
        "sensors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gateway_id", UUID(as_uuid=True), sa.ForeignKey("gateways.id"), nullable=True),
        sa.Column("sensor_code", sa.String(100), nullable=False),
        sa.Column("sensor_type", sa.String(100), nullable=False),
        sa.Column("mount_location", sa.String(100), nullable=True),
        sa.Column("mqtt_topic", sa.String(255), nullable=True),
        sa.Column("validation_data", JSONB, nullable=True),
        sa.Column("installation_date", sa.Date, nullable=True),
        sa.Column("position_x", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("position_y", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "sensor_code", name="uq_sensors_tenant_code"),
    )

    # -- ASSET HEALTH --
    op.create_table(
        "asset_health",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("health_score", sa.Float, nullable=False),
        sa.Column("health_status", sa.String(50), nullable=False),
        sa.Column("calculation_method", sa.String(100), nullable=True),
        sa.Column("health_calc_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("health_score >= 0 AND health_score <= 100", name="ck_asset_health_score_range"),
    )
    op.create_index("idx_asset_health_latest", "asset_health", ["asset_id", sa.text("health_calc_date DESC")])

    # -- ML MODELS --
    op.create_table(
        "ml_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("model_description", sa.Text, nullable=True),
        sa.Column("model_type", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "model_name", name="uq_ml_models_tenant_name"),
    )

    # -- ML MODEL VERSIONS --
    op.create_table(
        "ml_model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semantic_version", sa.String(50), nullable=False),
        sa.Column("full_version_label", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False, server_default="staging"),
        sa.Column("model_artifact_path", sa.Text, nullable=False),
        sa.Column("docker_image_tag", sa.String(255), nullable=True),
        sa.Column("dataset_hash", sa.String(128), nullable=True),
        sa.Column("feature_schema_hash", sa.String(128), nullable=True),
        sa.Column("training_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("precision_score", sa.Float, nullable=True),
        sa.Column("recall_score", sa.Float, nullable=True),
        sa.Column("f1_score", sa.Float, nullable=True),
        sa.Column("false_alarm_rate", sa.Float, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "full_version_label", name="uq_ml_model_versions_tenant_label"),
    )

    # -- ML MODEL DEPLOYMENTS --
    op.create_table(
        "ml_model_deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("model_version_id", UUID(as_uuid=True), sa.ForeignKey("ml_model_versions.id"), nullable=False),
        sa.Column("is_production", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deployment_start", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deployment_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_from_version_id", UUID(as_uuid=True), sa.ForeignKey("ml_model_versions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # -- ASSET MODEL VERSIONS --
    op.create_table(
        "asset_model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("model_version_id", UUID(as_uuid=True), sa.ForeignKey("ml_model_versions.id"), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False, server_default="production"),
        sa.Column("deployment_start", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deployment_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # -- FEEDBACK --
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("sensor_id", UUID(as_uuid=True), sa.ForeignKey("sensors.id"), nullable=True),
        sa.Column("prediction_id", sa.String(100), nullable=True),
        sa.Column("payload_normalized", JSONB, nullable=True),
        sa.Column("validation_data", JSONB, nullable=True),
        sa.Column("prediction_label", sa.String(255), nullable=False),
        sa.Column("probability", sa.Float, nullable=True),
        sa.Column("new_label", sa.String(255), nullable=False),
        sa.Column("correction", sa.Text, nullable=True),
        sa.Column("feedback_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )

    # -- NOTIFICATION TYPES --
    op.create_table(
        "notification_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("notify_type_name", sa.String(100), nullable=False),
        sa.Column("notify_type_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "notify_type_name", name="uq_notification_types_tenant_name"),
    )

    # -- ALARM RULES --
    op.create_table(
        "alarm_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("sensor_id", UUID(as_uuid=True), sa.ForeignKey("sensors.id"), nullable=True),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("parameter_name", sa.String(100), nullable=False),
        sa.Column("threshold_value", sa.Float, nullable=False),
        sa.Column("comparison_operator", sa.String(10), nullable=False),
        sa.Column("severity_level", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # -- ALARM NOTIFICATION TYPES (M:N join) --
    op.create_table(
        "alarm_notification_types",
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("alarm_rule_id", UUID(as_uuid=True), sa.ForeignKey("alarm_rules.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("notification_type_id", UUID(as_uuid=True), sa.ForeignKey("notification_types.id", ondelete="CASCADE"), primary_key=True),
    )

    # -- ALARM EVENTS --
    op.create_table(
        "alarm_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("sensor_id", UUID(as_uuid=True), sa.ForeignKey("sensors.id"), nullable=True),
        sa.Column("alarm_rule_id", UUID(as_uuid=True), sa.ForeignKey("alarm_rules.id"), nullable=True),
        sa.Column("prediction_id", sa.String(100), nullable=True),
        sa.Column("model_version_id", UUID(as_uuid=True), sa.ForeignKey("ml_model_versions.id"), nullable=True),
        sa.Column("triggered_value", sa.Float, nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correction_plan", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("acknowledged_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_alarm_events_tenant_status",
        "alarm_events",
        ["tenant_id", "status", sa.text("triggered_at DESC")],
    )

    # -- NOTIFICATION LOG --
    op.create_table(
        "notification_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("alarm_event_id", UUID(as_uuid=True), sa.ForeignKey("alarm_events.id"), nullable=False),
        sa.Column("notification_type_id", UUID(as_uuid=True), sa.ForeignKey("notification_types.id"), nullable=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- MAINTENANCE WORK ORDERS --
    op.create_table(
        "maintenance_work_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("alarm_event_id", UUID(as_uuid=True), sa.ForeignKey("alarm_events.id"), nullable=True),
        sa.Column("work_number", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority_level", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # -- API KEYS --
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("scopes", ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("maintenance_work_orders")
    op.drop_table("notification_logs")
    op.drop_index("idx_alarm_events_tenant_status", table_name="alarm_events")
    op.drop_table("alarm_events")
    op.drop_table("alarm_notification_types")
    op.drop_table("alarm_rules")
    op.drop_table("notification_types")
    op.drop_table("feedback")
    op.drop_table("asset_model_versions")
    op.drop_table("ml_model_deployments")
    op.drop_table("ml_model_versions")
    op.drop_table("ml_models")
    op.drop_index("idx_asset_health_latest", table_name="asset_health")
    op.drop_table("asset_health")
    op.drop_table("sensors")
    op.drop_table("assets")
    op.drop_table("gateways")
    op.drop_table("sites")
    op.drop_table("fault_actions")
    op.drop_table("user_settings")
    op.drop_table("users")
    op.drop_table("tenants")
