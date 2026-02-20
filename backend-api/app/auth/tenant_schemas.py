from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TenantCreate(BaseModel):
    tenant_code: str
    tenant_name: str
    plan: str = "free"


class TenantUpdate(BaseModel):
    tenant_name: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None


class TenantOut(BaseModel):
    id: UUID
    tenant_code: str
    tenant_name: str
    plan: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
