import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserCreate, UserOut, LoginRequest, Token
from app.auth.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.db.postgres import get_pg_session
from app.db.models import Tenant, User
from app.common.dependencies import get_current_user
from app.common.exceptions import UnauthorizedError, ConflictError, ForbiddenError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_pg_session),
):
    # Check if email or username already exists
    result = await session.execute(
        select(User).where(
            (User.email == user_create.email) | (User.username == user_create.username),
            User.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail="Email or username already registered")

    # Resolve or create tenant
    if user_create.tenant_code:
        result = await session.execute(
            select(Tenant).where(
                Tenant.tenant_code == user_create.tenant_code,
                Tenant.is_active == True,
                Tenant.is_deleted == False,
            )
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ConflictError(detail=f"Tenant '{user_create.tenant_code}' not found")
    else:
        # Create a personal tenant from the username
        tenant_code = user_create.username.lower().replace(" ", "_")
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_code == tenant_code)
        )
        existing_tenant = result.scalar_one_or_none()
        if existing_tenant:
            tenant = existing_tenant
        else:
            tenant = Tenant(
                tenant_code=tenant_code,
                tenant_name=f"{user_create.username}'s Organization",
            )
            session.add(tenant)
            await session.flush()

    # Registration always creates tenant-scoped users (admin for new tenant, user for existing)
    user = User(
        tenant_id=tenant.id,
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        password_hash=get_password_hash(user_create.password),
        role="admin" if not user_create.tenant_code else "user",
    )
    session.add(user)
    await session.flush()

    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "tenant_code": tenant.tenant_code,
            "role": user.role,
            "scope": "tenant",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    logger.info(f"New user registered: {user.email} (tenant: {tenant.tenant_code})")
    return Token(access_token=access_token, token_type="bearer")


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(User).where(
            User.email == login_data.email,
            User.is_deleted == False,
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise UnauthorizedError(detail="Incorrect email or password")

    if not user.is_active:
        raise ForbiddenError(detail="User account is disabled")

    # Determine scope and load tenant info
    if user.role == "super_admin" and user.tenant_id is None:
        # Platform-scoped user
        scope = "platform"
        tenant_id_str = None
        tenant_code = None
    else:
        # Tenant-scoped user
        scope = "tenant"
        tenant_id_str = str(user.tenant_id)
        tenant_result = await session.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        tenant_code = tenant.tenant_code if tenant else None

    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": str(user.id),
            "tenant_id": tenant_id_str,
            "tenant_code": tenant_code,
            "role": user.role,
            "scope": scope,
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    logger.info(f"User logged in: {login_data.email} (scope: {scope})")
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserOut)
async def get_current_user_info(current_user: UserOut = Depends(get_current_user)):
    return current_user
