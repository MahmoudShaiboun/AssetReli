import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import AdminUserCreate, UserUpdate, UserOut
from app.auth.security import get_password_hash
from app.common.dependencies import require_role
from app.common.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.db.postgres import get_pg_session
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_target_tenant(current_user: UserOut, explicit_tenant_id: Optional[UUID] = None) -> UUID:
    """Resolve the target tenant_id for user operations.

    - super_admin: uses explicit_tenant_id or effective_tenant_id (from X-Tenant-Id header)
    - admin: always uses own effective_tenant_id, rejects explicit overrides
    """
    if current_user.scope == "platform":
        tid = explicit_tenant_id or current_user.effective_tenant_id
        if tid is None:
            raise ForbiddenError(detail="X-Tenant-Id header or tenant_id field required")
        return tid
    else:
        if explicit_tenant_id and explicit_tenant_id != current_user.effective_tenant_id:
            raise ForbiddenError(detail="Cross-tenant access denied")
        return current_user.effective_tenant_id


@router.get("/users", response_model=list[UserOut])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant (super_admin only)"),
    current_user: UserOut = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    target_tid = _resolve_target_tenant(current_user, tenant_id)
    result = await session.execute(
        select(User)
        .where(User.tenant_id == target_tid, User.is_deleted == False)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    current_user: UserOut = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    target_tid = _resolve_target_tenant(current_user, data.tenant_id)

    # Only super_admin can create super_admin users
    if data.role == "super_admin" and current_user.role != "super_admin":
        raise ForbiddenError(detail="Only super_admin can create super_admin users")

    result = await session.execute(
        select(User).where(
            User.tenant_id == target_tid,
            (User.email == data.email) | (User.username == data.username),
            User.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail="Email or username already exists in this tenant")

    user = User(
        tenant_id=target_tid,
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        role=data.role,
        created_by=current_user.id,
    )
    session.add(user)
    await session.flush()

    logger.info(f"User created: {user.email} in tenant {target_tid} by {current_user.email}")
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: UserOut = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    # Build query — super_admin can update users in any tenant via X-Tenant-Id
    filters = [User.id == user_id, User.is_deleted == False]
    if current_user.scope != "platform":
        filters.append(User.tenant_id == current_user.effective_tenant_id)

    result = await session.execute(select(User).where(*filters))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(detail="User not found")

    # Only super_admin can assign super_admin role
    if data.role == "super_admin" and current_user.role != "super_admin":
        raise ForbiddenError(detail="Only super_admin can assign super_admin role")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    user.updated_at = datetime.utcnow()
    user.updated_by = current_user.id

    logger.info(f"User updated: {user.email} by {current_user.email}")
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: UserOut = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    if user_id == current_user.id:
        raise ConflictError(detail="Cannot delete your own account")

    # Build query — super_admin can delete users in any tenant via X-Tenant-Id
    filters = [User.id == user_id, User.is_deleted == False]
    if current_user.scope != "platform":
        filters.append(User.tenant_id == current_user.effective_tenant_id)

    result = await session.execute(select(User).where(*filters))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError(detail="User not found")

    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.deleted_by = current_user.id

    logger.info(f"User soft-deleted: {user.email} by {current_user.email}")
