from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

VALID_ROLES = ("super_admin", "admin", "user")


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    tenant_code: Optional[str] = None  # join existing tenant or create new


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminUserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    role: str = "user"
    tenant_id: Optional[UUID] = None  # super_admin can specify target tenant

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v


class UserOut(BaseModel):
    id: UUID
    tenant_id: Optional[UUID] = None  # None for super_admin (platform scope)
    email: Optional[EmailStr] = None
    username: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    created_at: Optional[datetime] = None
    # Populated by get_current_user() dependency — not from DB
    scope: str = "tenant"  # "platform" | "tenant"
    effective_tenant_id: Optional[UUID] = None

    model_config = {"from_attributes": True}
