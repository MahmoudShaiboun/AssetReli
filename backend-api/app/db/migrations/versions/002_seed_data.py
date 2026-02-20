"""Seed default tenant, admin user, and initial ML model

Revision ID: 002_seed_data
Revises: 001_initial
Create Date: 2026-02-17

"""
from typing import Sequence, Union
from uuid import UUID as PyUUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "002_seed_data"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUIDs for reproducible seeding
DEFAULT_TENANT_ID = PyUUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = PyUUID("00000000-0000-0000-0000-000000000002")
DEFAULT_MODEL_ID = PyUUID("00000000-0000-0000-0000-000000000003")
DEFAULT_VERSION_ID = PyUUID("00000000-0000-0000-0000-000000000004")
DEFAULT_DEPLOYMENT_ID = PyUUID("00000000-0000-0000-0000-000000000005")
DEFAULT_SITE_ID = PyUUID("00000000-0000-0000-0000-000000000006")
DEFAULT_ASSET_ID = PyUUID("00000000-0000-0000-0000-000000000007")


def _uuid_param(name):
    """Create a bindparam with explicit UUID type for asyncpg compatibility."""
    return sa.bindparam(name, type_=UUID(as_uuid=True))


def upgrade() -> None:
    # Default tenant
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (id, tenant_code, tenant_name, plan, is_active, is_deleted)
            VALUES (:tid, 'default', 'Default Organization', 'free', true, false)
            ON CONFLICT (tenant_code) DO NOTHING
            """
        ).bindparams(sa.bindparam("tid", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)))
    )

    # Default admin user (password: admin123 — bcrypt hash)
    # This is for development only; production should change this immediately
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, tenant_id, username, email, full_name, password_hash, role, is_active, is_deleted)
            VALUES (
                :uid, :tenant_id, 'admin', 'admin@assetreli.com', 'System Administrator',
                '$2b$12$LJ3m4ys3uz5t5dMNmMHJJOYFzaNBm3MIE.JYfl8.JHmfFEXwNq3jq',
                'admin', true, false
            )
            ON CONFLICT ON CONSTRAINT uq_users_tenant_email DO NOTHING
            """
        ).bindparams(
            sa.bindparam("uid", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
        )
    )

    # Default site
    op.execute(
        sa.text(
            """
            INSERT INTO sites (id, tenant_id, site_code, site_name, location, is_active, is_deleted, created_by)
            VALUES (:sid, :tenant_id, 'main', 'Main Site', 'Building A', true, false, :user_id)
            ON CONFLICT ON CONSTRAINT uq_sites_tenant_code DO NOTHING
            """
        ).bindparams(
            sa.bindparam("sid", value=DEFAULT_SITE_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )

    # Default asset
    op.execute(
        sa.text(
            """
            INSERT INTO assets (id, tenant_id, site_id, asset_code, asset_name, asset_type, is_active, is_deleted, created_by)
            VALUES (:aid, :tenant_id, :site_id, 'pump_motor_01', 'Pump Motor Assembly 1', 'motor', true, false, :user_id)
            ON CONFLICT ON CONSTRAINT uq_assets_tenant_code DO NOTHING
            """
        ).bindparams(
            sa.bindparam("aid", value=DEFAULT_ASSET_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("site_id", value=DEFAULT_SITE_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )

    # ML model: fault_classifier
    op.execute(
        sa.text(
            """
            INSERT INTO ml_models (id, tenant_id, model_name, model_description, model_type, is_active, is_deleted, created_by)
            VALUES (
                :mid, :tenant_id, 'fault_classifier',
                'XGBoost-based industrial fault classifier (34 fault classes)',
                'Classification', true, false, :user_id
            )
            ON CONFLICT ON CONSTRAINT uq_ml_models_tenant_name DO NOTHING
            """
        ).bindparams(
            sa.bindparam("mid", value=DEFAULT_MODEL_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )

    # ML model version: v1 (production)
    op.execute(
        sa.text(
            """
            INSERT INTO ml_model_versions (
                id, tenant_id, model_id, semantic_version, full_version_label,
                stage, model_artifact_path, is_active, is_deleted, created_by
            ) VALUES (
                :vid, :tenant_id, :model_id, '1.0.0', 'fault_classifier:1.0.0',
                'production', 'models/current', true, false, :user_id
            )
            ON CONFLICT ON CONSTRAINT uq_ml_model_versions_tenant_label DO NOTHING
            """
        ).bindparams(
            sa.bindparam("vid", value=DEFAULT_VERSION_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("model_id", value=DEFAULT_MODEL_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )

    # ML model deployment: v1 is production
    op.execute(
        sa.text(
            """
            INSERT INTO ml_model_deployments (id, tenant_id, model_id, model_version_id, is_production, created_by)
            VALUES (:did, :tenant_id, :model_id, :version_id, true, :user_id)
            """
        ).bindparams(
            sa.bindparam("did", value=DEFAULT_DEPLOYMENT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("model_id", value=DEFAULT_MODEL_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("version_id", value=DEFAULT_VERSION_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )

    # Asset model version binding: default asset uses v1
    op.execute(
        sa.text(
            """
            INSERT INTO asset_model_versions (tenant_id, asset_id, model_id, model_version_id, stage, is_active, created_by)
            VALUES (:tenant_id, :asset_id, :model_id, :version_id, 'production', true, :user_id)
            """
        ).bindparams(
            sa.bindparam("tenant_id", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("asset_id", value=DEFAULT_ASSET_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("model_id", value=DEFAULT_MODEL_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("version_id", value=DEFAULT_VERSION_ID, type_=UUID(as_uuid=True)),
            sa.bindparam("user_id", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True)),
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM asset_model_versions WHERE tenant_id = :tid").bindparams(
        sa.bindparam("tid", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM ml_model_deployments WHERE id = :did").bindparams(
        sa.bindparam("did", value=DEFAULT_DEPLOYMENT_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM ml_model_versions WHERE id = :vid").bindparams(
        sa.bindparam("vid", value=DEFAULT_VERSION_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM ml_models WHERE id = :mid").bindparams(
        sa.bindparam("mid", value=DEFAULT_MODEL_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM assets WHERE id = :aid").bindparams(
        sa.bindparam("aid", value=DEFAULT_ASSET_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM sites WHERE id = :sid").bindparams(
        sa.bindparam("sid", value=DEFAULT_SITE_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM users WHERE id = :uid").bindparams(
        sa.bindparam("uid", value=DEFAULT_USER_ID, type_=UUID(as_uuid=True))))
    op.execute(sa.text("DELETE FROM tenants WHERE id = :tid").bindparams(
        sa.bindparam("tid", value=DEFAULT_TENANT_ID, type_=UUID(as_uuid=True))))
