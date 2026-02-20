"""Security overhaul: platform/tenant scopes, super_admin role, audit logging

Revision ID: 003_security_overhaul
Revises: 002_seed_data
Create Date: 2026-02-18

Changes:
- users.tenant_id: nullable (platform-scoped super_admin has NULL)
- users.role: rename 'operator' → 'user'
- Partial unique indexes for NULL tenant_id
- Seed super_admin user
- Create audit_logs table
"""
from typing import Sequence, Union
from uuid import UUID as PyUUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "003_security_overhaul"
down_revision: Union[str, None] = "002_seed_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUPER_ADMIN_ID = PyUUID("00000000-0000-0000-0000-000000000099")


def upgrade() -> None:
    # 1. Make users.tenant_id nullable for platform-scoped users
    op.alter_column("users", "tenant_id", existing_type=sa.dialects.postgresql.UUID(),
                    nullable=True)

    # 2. Rename role 'operator' → 'user'
    op.execute(sa.text("UPDATE users SET role = 'user' WHERE role = 'operator'"))

    # 3. Partial unique indexes for super_admin users (tenant_id IS NULL)
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_users_null_tenant_username "
        "ON users (username) WHERE tenant_id IS NULL AND is_deleted = false"
    ))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_users_null_tenant_email "
        "ON users (email) WHERE tenant_id IS NULL AND is_deleted = false"
    ))

    # 4. Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_target_tenant", "audit_logs", ["target_tenant_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # 5. Seed super_admin user (no tenant, platform scope)
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, tenant_id, username, email, full_name, password_hash, role, is_active, is_deleted)
            VALUES (
                :uid, NULL, 'superadmin', 'superadmin@aastreli.local', 'Platform Administrator',
                '$2b$12$TR0RylmA4fhKc80qy/jthemdMKlskxLa09JtHvxO.LKmnTdFHZ952',
                'super_admin', true, false
            )
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            sa.bindparam("uid", value=SUPER_ADMIN_ID, type_=UUID(as_uuid=True)),
        )
    )


def downgrade() -> None:
    # Remove super_admin user
    op.execute(
        sa.text("DELETE FROM users WHERE id = :uid").bindparams(
            sa.bindparam("uid", value=SUPER_ADMIN_ID, type_=UUID(as_uuid=True))
        )
    )

    # Drop audit_logs
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target_tenant", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    # Drop partial indexes
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_null_tenant_email"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_null_tenant_username"))

    # Rename role 'user' → 'operator'
    op.execute(sa.text("UPDATE users SET role = 'operator' WHERE role = 'user'"))

    # Restore NOT NULL on tenant_id
    op.alter_column("users", "tenant_id", existing_type=sa.dialects.postgresql.UUID(),
                    nullable=False)
