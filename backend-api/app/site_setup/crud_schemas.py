from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ---- Sites ----

class SiteCreate(BaseModel):
    site_code: str
    site_name: str
    location: Optional[str] = None


class SiteUpdate(BaseModel):
    site_name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class SiteOut(BaseModel):
    id: UUID
    tenant_id: UUID
    site_code: str
    site_name: str
    location: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Gateways ----

class GatewayCreate(BaseModel):
    site_id: UUID
    gateway_code: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None


class GatewayUpdate(BaseModel):
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    is_active: Optional[bool] = None


class GatewayOut(BaseModel):
    id: UUID
    tenant_id: UUID
    site_id: UUID
    gateway_code: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    is_online: bool
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Assets ----

class AssetCreate(BaseModel):
    site_id: UUID
    gateway_id: Optional[UUID] = None
    asset_code: str
    asset_name: str
    asset_type: str


class AssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_type: Optional[str] = None
    gateway_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class AssetOut(BaseModel):
    id: UUID
    tenant_id: UUID
    site_id: UUID
    gateway_id: Optional[UUID] = None
    asset_code: str
    asset_name: str
    asset_type: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Sensors ----

class SensorCreate(BaseModel):
    asset_id: UUID
    gateway_id: Optional[UUID] = None
    sensor_code: str
    sensor_type: str
    mount_location: Optional[str] = None
    mqtt_topic: Optional[str] = None


class SensorUpdate(BaseModel):
    sensor_type: Optional[str] = None
    mount_location: Optional[str] = None
    mqtt_topic: Optional[str] = None
    gateway_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class SensorOut(BaseModel):
    id: UUID
    tenant_id: UUID
    asset_id: UUID
    gateway_id: Optional[UUID] = None
    sensor_code: str
    sensor_type: str
    mount_location: Optional[str] = None
    mqtt_topic: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
