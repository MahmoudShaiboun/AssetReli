import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserOut
from app.auth.tenant_schemas import TenantCreate, TenantUpdate, TenantOut
from app.common.dependencies import require_role
from app.common.exceptions import NotFoundError, ConflictError
from app.common.audit import log_platform_action
from app.db.postgres import get_pg_session
from app.db.models import Tenant

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(
    skip: int = 0,
    limit: int = 50,
    current_user: UserOut = Depends(require_role("super_admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Tenant)
        .where(Tenant.is_deleted == False)
        .order_by(Tenant.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    tenants = result.scalars().all()
    return [TenantOut.model_validate(t) for t in tenants]


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    current_user: UserOut = Depends(require_role("super_admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Tenant).where(Tenant.tenant_code == data.tenant_code)
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail=f"Tenant code '{data.tenant_code}' already exists")

    tenant = Tenant(
        tenant_code=data.tenant_code,
        tenant_name=data.tenant_name,
        plan=data.plan,
        created_by=current_user.id,
    )
    session.add(tenant)
    await session.flush()

    await log_platform_action(
        session, current_user, "create_tenant",
        target_tenant_id=tenant.id, resource_type="tenant",
        resource_id=str(tenant.id), details={"tenant_code": data.tenant_code},
    )

    return TenantOut.model_validate(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: UUID,
    current_user: UserOut = Depends(require_role("super_admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError(detail="Tenant not found")
    return TenantOut.model_validate(tenant)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    current_user: UserOut = Depends(require_role("super_admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError(detail="Tenant not found")

    changes = {}
    if data.tenant_name is not None:
        tenant.tenant_name = data.tenant_name
        changes["tenant_name"] = data.tenant_name
    if data.plan is not None:
        tenant.plan = data.plan
        changes["plan"] = data.plan
    if data.is_active is not None:
        tenant.is_active = data.is_active
        changes["is_active"] = data.is_active

    await log_platform_action(
        session, current_user, "update_tenant",
        target_tenant_id=tenant_id, resource_type="tenant",
        resource_id=str(tenant_id), details=changes,
    )

    return TenantOut.model_validate(tenant)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    current_user: UserOut = Depends(require_role("super_admin")),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError(detail="Tenant not found")

    tenant.is_deleted = True
    tenant.deleted_by = current_user.id
    tenant.deleted_at = datetime.utcnow()

    await log_platform_action(
        session, current_user, "delete_tenant",
        target_tenant_id=tenant_id, resource_type="tenant",
        resource_id=str(tenant_id), details={"tenant_code": tenant.tenant_code},
    )
