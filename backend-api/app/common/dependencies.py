from uuid import UUID
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import verify_token
from app.auth.schemas import UserOut
from app.db.postgres import get_pg_session
from app.db.models import User, Tenant
from app.common.exceptions import UnauthorizedError, ForbiddenError

security = HTTPBearer()


class TenantContext(BaseModel):
    """Lightweight tenant info extracted from JWT — no DB user lookup needed."""
    tenant_id: UUID
    tenant_code: str


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_pg_session),
) -> UserOut:
    """Get current authenticated user from JWT token (PostgreSQL).

    Populates effective_tenant_id based on scope:
    - Platform (super_admin): reads X-Tenant-Id header, validates tenant exists
    - Tenant (admin/user): uses DB tenant_id, rejects override attempts
    """
    token = credentials.credentials
    token_data = verify_token(token)

    if token_data is None or token_data.user_id is None:
        raise UnauthorizedError()

    try:
        user_id = UUID(token_data.user_id)
    except (ValueError, TypeError):
        raise UnauthorizedError()

    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.is_deleted == False,
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError(detail="User not found")

    user_out = UserOut.model_validate(user)

    # --- Tenant resolution ---
    if user.role == "super_admin" and user.tenant_id is None:
        # PLATFORM SCOPE
        user_out.scope = "platform"
        header_tenant = request.headers.get("x-tenant-id")
        if header_tenant:
            try:
                target_id = UUID(header_tenant)
            except (ValueError, TypeError):
                raise ForbiddenError(detail="Invalid X-Tenant-Id header")
            # Verify target tenant exists and is active
            tenant_result = await session.execute(
                select(Tenant).where(
                    Tenant.id == target_id,
                    Tenant.is_active == True,
                    Tenant.is_deleted == False,
                )
            )
            if tenant_result.scalar_one_or_none() is None:
                raise ForbiddenError(detail="Target tenant not found or inactive")
            user_out.effective_tenant_id = target_id
        # If no header, effective_tenant_id stays None
        # Endpoints requiring tenant context will fail-safe via get_current_user_with_tenant
    else:
        # TENANT SCOPE
        user_out.scope = "tenant"
        user_out.effective_tenant_id = user.tenant_id
        # Deny X-Tenant-Id override for non-super_admin
        header_tenant = request.headers.get("x-tenant-id")
        if header_tenant:
            try:
                if UUID(header_tenant) != user.tenant_id:
                    raise ForbiddenError(detail="Cross-tenant access denied")
            except (ValueError, TypeError):
                pass  # Ignore malformed header for tenant-scoped users

    return user_out


async def get_current_user_with_tenant(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """Wraps get_current_user and ensures effective_tenant_id is set.

    Use this for all endpoints that operate on tenant-scoped data.
    Super_admin must provide X-Tenant-Id header to access these endpoints.
    """
    if current_user.effective_tenant_id is None:
        raise ForbiddenError(
            detail="X-Tenant-Id header required for platform-scoped users"
        )
    return current_user


async def get_current_tenant(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_pg_session),
) -> TenantContext:
    """Extract tenant from JWT and verify it is active.

    Lighter than get_current_user() — suitable for service-to-service
    calls where only tenant context is needed.
    """
    token = credentials.credentials
    token_data = verify_token(token)

    if token_data is None:
        raise UnauthorizedError()

    # Platform-scoped: read X-Tenant-Id header
    if token_data.scope == "platform":
        header_tenant = request.headers.get("x-tenant-id")
        if not header_tenant:
            raise ForbiddenError(detail="X-Tenant-Id header required for platform-scoped users")
        try:
            tenant_id = UUID(header_tenant)
        except (ValueError, TypeError):
            raise ForbiddenError(detail="Invalid X-Tenant-Id header")
        # Verify tenant
        result = await session.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.is_active == True,
                Tenant.is_deleted == False,
            )
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            raise ForbiddenError(detail="Target tenant not found or inactive")
        return TenantContext(tenant_id=tenant.id, tenant_code=tenant.tenant_code)

    # Tenant-scoped: use JWT tenant_id
    if token_data.tenant_id is None:
        raise UnauthorizedError()

    try:
        tenant_id = UUID(token_data.tenant_id)
    except (ValueError, TypeError):
        raise UnauthorizedError()

    # If JWT already carries tenant_code, skip the DB lookup
    if token_data.tenant_code:
        return TenantContext(tenant_id=tenant_id, tenant_code=token_data.tenant_code)

    # Fallback: look up tenant in PG
    result = await session.execute(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_active == True,
            Tenant.is_deleted == False,
        )
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise UnauthorizedError(detail="Tenant not found or inactive")

    return TenantContext(tenant_id=tenant.id, tenant_code=tenant.tenant_code)


async def verify_api_key(x_api_key: str = Header(default="")) -> str:
    """Validate X-API-Key header for service-to-service requests.

    Enforcement is skipped when INTERNAL_API_KEY is unset or equals 'dev_key'
    (development mode — matches the pattern in ml-service/app/common/auth.py).
    """
    from app.config import settings
    key = settings.INTERNAL_API_KEY
    if key and key != "dev_key":
        if x_api_key != key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
    return x_api_key


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory: raises 403 if user's role is not in allowed_roles.

    super_admin implicitly passes any role check (platform scope has full access).
    """
    async def _check(current_user: UserOut = Depends(get_current_user)):
        if current_user.role == "super_admin":
            return current_user
        if current_user.role not in allowed_roles:
            raise ForbiddenError(detail=f"Role '{current_user.role}' not permitted")
        return current_user
    return _check
