import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserOut
from app.db.models import AuditLog

audit_logger = logging.getLogger("aastreli.audit")


async def log_platform_action(
    session: AsyncSession,
    user: UserOut,
    action: str,
    target_tenant_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Log a platform-scoped (super_admin) action for audit trail.

    Always logs to structured logger. Persists to audit_logs table if session provided.
    """
    audit_logger.warning(
        "PLATFORM_ACTION | user=%s | action=%s | target_tenant=%s | "
        "resource=%s:%s | details=%s",
        user.email, action, target_tenant_id,
        resource_type, resource_id, details,
    )

    entry = AuditLog(
        user_id=user.id,
        scope=user.scope,
        action=action,
        target_tenant_id=target_tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    session.add(entry)
