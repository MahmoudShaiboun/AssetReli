import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserOut
from app.common.database import get_mongo_db
from app.common.dependencies import get_current_user_with_tenant
from app.common.exceptions import NotFoundError, ConflictError
from app.db.postgres import get_pg_session
from app.db.models import UserSetting, FaultAction, Site, Gateway, Asset, Sensor
from app.site_setup.crud_schemas import (
    SiteCreate, SiteUpdate, SiteOut,
    GatewayCreate, GatewayUpdate, GatewayOut,
    AssetCreate, AssetUpdate, AssetOut,
    SensorCreate, SensorUpdate, SensorOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Sensors (PostgreSQL CRUD) ----


@router.get("/sensors", response_model=list[SensorOut])
async def list_sensors(
    asset_id: Optional[UUID] = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    query = select(Sensor).where(
        Sensor.tenant_id == current_user.effective_tenant_id,
        Sensor.is_deleted == False,
    )
    if asset_id:
        query = query.where(Sensor.asset_id == asset_id)
    result = await session.execute(query.order_by(Sensor.created_at.desc()))
    return [SensorOut.model_validate(s) for s in result.scalars().all()]


@router.post("/sensors", response_model=SensorOut, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    data: SensorCreate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Sensor).where(
            Sensor.tenant_id == current_user.effective_tenant_id,
            Sensor.sensor_code == data.sensor_code,
            Sensor.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail=f"Sensor code '{data.sensor_code}' already exists")

    sensor = Sensor(
        tenant_id=current_user.effective_tenant_id,
        asset_id=data.asset_id,
        gateway_id=data.gateway_id,
        sensor_code=data.sensor_code,
        sensor_type=data.sensor_type,
        mount_location=data.mount_location,
        mqtt_topic=data.mqtt_topic,
        created_by=current_user.id,
    )
    session.add(sensor)
    await session.flush()
    return SensorOut.model_validate(sensor)


@router.get("/sensors/{sensor_id}", response_model=SensorOut)
async def get_sensor(
    sensor_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Sensor).where(
            Sensor.id == sensor_id,
            Sensor.tenant_id == current_user.effective_tenant_id,
            Sensor.is_deleted == False,
        )
    )
    sensor = result.scalar_one_or_none()
    if not sensor:
        raise NotFoundError(detail="Sensor not found")
    return SensorOut.model_validate(sensor)


@router.patch("/sensors/{sensor_id}", response_model=SensorOut)
async def update_sensor(
    sensor_id: UUID,
    data: SensorUpdate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Sensor).where(
            Sensor.id == sensor_id,
            Sensor.tenant_id == current_user.effective_tenant_id,
            Sensor.is_deleted == False,
        )
    )
    sensor = result.scalar_one_or_none()
    if not sensor:
        raise NotFoundError(detail="Sensor not found")

    if data.sensor_type is not None:
        sensor.sensor_type = data.sensor_type
    if data.mount_location is not None:
        sensor.mount_location = data.mount_location
    if data.mqtt_topic is not None:
        sensor.mqtt_topic = data.mqtt_topic
    if data.gateway_id is not None:
        sensor.gateway_id = data.gateway_id
    if data.is_active is not None:
        sensor.is_active = data.is_active
    sensor.updated_by = current_user.id

    return SensorOut.model_validate(sensor)


@router.delete("/sensors/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sensor(
    sensor_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Sensor).where(
            Sensor.id == sensor_id,
            Sensor.tenant_id == current_user.effective_tenant_id,
            Sensor.is_deleted == False,
        )
    )
    sensor = result.scalar_one_or_none()
    if not sensor:
        raise NotFoundError(detail="Sensor not found")

    sensor.is_deleted = True
    sensor.deleted_by = current_user.id
    sensor.deleted_at = datetime.utcnow()


# ---- Sensor Telemetry (MongoDB reads) ----


@router.get("/sensor-readings")
async def get_sensor_readings(
    skip: int = 0,
    limit: int = 100,
    sensor_id: str = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    query = {"tenant_id": str(current_user.effective_tenant_id)}
    if sensor_id:
        query["sensor_id"] = sensor_id

    total = await db.sensor_readings.count_documents(query)
    readings = (
        await db.sensor_readings.find(query)
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    for reading in readings:
        reading["_id"] = str(reading["_id"])

    return {"readings": readings, "total": total, "skip": skip, "limit": limit}


@router.get("/sensor-data/{sensor_code}")
async def get_sensor_data(
    sensor_code: str,
    limit: int = 100,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    data = (
        await db.sensor_data.find(
            {"data.sensor_id": sensor_code, "tenant_id": str(current_user.effective_tenant_id)}
        )
        .sort("timestamp", -1)
        .limit(limit)
        .to_list(limit)
    )
    for d in data:
        d["_id"] = str(d["_id"])
    return {"sensor_code": sensor_code, "data": data, "count": len(data)}


# ---- Settings (PostgreSQL) ----


@router.get("/settings")
async def get_settings(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    # Load user_settings
    result = await session.execute(
        select(UserSetting).where(UserSetting.user_id == current_user.id)
    )
    user_setting = result.scalar_one_or_none()

    # Load fault_actions
    result = await session.execute(
        select(FaultAction).where(FaultAction.user_id == current_user.id)
    )
    fault_actions = result.scalars().all()

    if not user_setting:
        return {
            "autoRefresh": True,
            "refreshInterval": 5,
            "anomalyThreshold": 0.7,
            "enableNotifications": True,
            "faultActions": [],
        }

    return {
        "autoRefresh": user_setting.auto_refresh,
        "refreshInterval": user_setting.refresh_interval_sec,
        "anomalyThreshold": user_setting.anomaly_threshold,
        "enableNotifications": user_setting.enable_notifications,
        "faultActions": [
            {
                "type": fa.type,
                "enabled": fa.enabled,
                "config": fa.config or {},
            }
            for fa in fault_actions
        ],
    }


@router.post("/settings")
async def save_settings(
    settings_data: dict,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    # Upsert user_settings
    result = await session.execute(
        select(UserSetting).where(UserSetting.user_id == current_user.id)
    )
    user_setting = result.scalar_one_or_none()

    if user_setting:
        user_setting.auto_refresh = settings_data.get("autoRefresh", True)
        user_setting.refresh_interval_sec = settings_data.get("refreshInterval", 5)
        user_setting.anomaly_threshold = settings_data.get("anomalyThreshold", 0.7)
        user_setting.enable_notifications = settings_data.get("enableNotifications", True)
    else:
        user_setting = UserSetting(
            user_id=current_user.id,
            auto_refresh=settings_data.get("autoRefresh", True),
            refresh_interval_sec=settings_data.get("refreshInterval", 5),
            anomaly_threshold=settings_data.get("anomalyThreshold", 0.7),
            enable_notifications=settings_data.get("enableNotifications", True),
        )
        session.add(user_setting)

    # Sync fault_actions: delete old, insert new
    result = await session.execute(
        select(FaultAction).where(FaultAction.user_id == current_user.id)
    )
    old_actions = result.scalars().all()
    for old in old_actions:
        await session.delete(old)

    for action_data in settings_data.get("faultActions", []):
        fa = FaultAction(
            user_id=current_user.id,
            type=action_data.get("type", "email"),
            enabled=action_data.get("enabled", False),
            config=action_data.get("config", {}),
        )
        session.add(fa)

    logger.info(f"Settings saved for user: {current_user.email}")
    return {"status": "success", "message": "Settings saved successfully"}


# ---- Sites (PostgreSQL CRUD) ----


@router.get("/sites", response_model=list[SiteOut])
async def list_sites(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Site).where(
            Site.tenant_id == current_user.effective_tenant_id,
            Site.is_deleted == False,
        ).order_by(Site.created_at.desc())
    )
    return [SiteOut.model_validate(s) for s in result.scalars().all()]


@router.post("/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    data: SiteCreate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    # Check unique constraint
    result = await session.execute(
        select(Site).where(
            Site.tenant_id == current_user.effective_tenant_id,
            Site.site_code == data.site_code,
            Site.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail=f"Site code '{data.site_code}' already exists")

    site = Site(
        tenant_id=current_user.effective_tenant_id,
        site_code=data.site_code,
        site_name=data.site_name,
        location=data.location,
        created_by=current_user.id,
    )
    session.add(site)
    await session.flush()
    return SiteOut.model_validate(site)


@router.get("/sites/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Site).where(
            Site.id == site_id,
            Site.tenant_id == current_user.effective_tenant_id,
            Site.is_deleted == False,
        )
    )
    site = result.scalar_one_or_none()
    if not site:
        raise NotFoundError(detail="Site not found")
    return SiteOut.model_validate(site)


@router.patch("/sites/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: UUID,
    data: SiteUpdate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Site).where(
            Site.id == site_id,
            Site.tenant_id == current_user.effective_tenant_id,
            Site.is_deleted == False,
        )
    )
    site = result.scalar_one_or_none()
    if not site:
        raise NotFoundError(detail="Site not found")

    if data.site_name is not None:
        site.site_name = data.site_name
    if data.location is not None:
        site.location = data.location
    if data.is_active is not None:
        site.is_active = data.is_active
    site.updated_by = current_user.id

    return SiteOut.model_validate(site)


@router.delete("/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Site).where(
            Site.id == site_id,
            Site.tenant_id == current_user.effective_tenant_id,
            Site.is_deleted == False,
        )
    )
    site = result.scalar_one_or_none()
    if not site:
        raise NotFoundError(detail="Site not found")

    site.is_deleted = True
    site.deleted_by = current_user.id
    site.deleted_at = datetime.utcnow()


# ---- Gateways (PostgreSQL CRUD) ----


@router.get("/gateways", response_model=list[GatewayOut])
async def list_gateways(
    site_id: Optional[UUID] = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    query = select(Gateway).where(
        Gateway.tenant_id == current_user.effective_tenant_id,
        Gateway.is_deleted == False,
    )
    if site_id:
        query = query.where(Gateway.site_id == site_id)
    result = await session.execute(query.order_by(Gateway.created_at.desc()))
    return [GatewayOut.model_validate(g) for g in result.scalars().all()]


@router.post("/gateways", response_model=GatewayOut, status_code=status.HTTP_201_CREATED)
async def create_gateway(
    data: GatewayCreate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Gateway).where(
            Gateway.tenant_id == current_user.effective_tenant_id,
            Gateway.gateway_code == data.gateway_code,
            Gateway.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail=f"Gateway code '{data.gateway_code}' already exists")

    gateway = Gateway(
        tenant_id=current_user.effective_tenant_id,
        site_id=data.site_id,
        gateway_code=data.gateway_code,
        ip_address=data.ip_address,
        firmware_version=data.firmware_version,
        created_by=current_user.id,
    )
    session.add(gateway)
    await session.flush()
    return GatewayOut.model_validate(gateway)


@router.get("/gateways/{gateway_id}", response_model=GatewayOut)
async def get_gateway(
    gateway_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Gateway).where(
            Gateway.id == gateway_id,
            Gateway.tenant_id == current_user.effective_tenant_id,
            Gateway.is_deleted == False,
        )
    )
    gw = result.scalar_one_or_none()
    if not gw:
        raise NotFoundError(detail="Gateway not found")
    return GatewayOut.model_validate(gw)


@router.patch("/gateways/{gateway_id}", response_model=GatewayOut)
async def update_gateway(
    gateway_id: UUID,
    data: GatewayUpdate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Gateway).where(
            Gateway.id == gateway_id,
            Gateway.tenant_id == current_user.effective_tenant_id,
            Gateway.is_deleted == False,
        )
    )
    gw = result.scalar_one_or_none()
    if not gw:
        raise NotFoundError(detail="Gateway not found")

    if data.ip_address is not None:
        gw.ip_address = data.ip_address
    if data.firmware_version is not None:
        gw.firmware_version = data.firmware_version
    if data.is_active is not None:
        gw.is_active = data.is_active
    gw.updated_by = current_user.id

    return GatewayOut.model_validate(gw)


@router.delete("/gateways/{gateway_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gateway(
    gateway_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Gateway).where(
            Gateway.id == gateway_id,
            Gateway.tenant_id == current_user.effective_tenant_id,
            Gateway.is_deleted == False,
        )
    )
    gw = result.scalar_one_or_none()
    if not gw:
        raise NotFoundError(detail="Gateway not found")

    gw.is_deleted = True
    gw.deleted_by = current_user.id
    gw.deleted_at = datetime.utcnow()


# ---- Assets (PostgreSQL CRUD) ----


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(
    site_id: Optional[UUID] = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    query = select(Asset).where(
        Asset.tenant_id == current_user.effective_tenant_id,
        Asset.is_deleted == False,
    )
    if site_id:
        query = query.where(Asset.site_id == site_id)
    result = await session.execute(query.order_by(Asset.created_at.desc()))
    return [AssetOut.model_validate(a) for a in result.scalars().all()]


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Asset).where(
            Asset.tenant_id == current_user.effective_tenant_id,
            Asset.asset_code == data.asset_code,
            Asset.is_deleted == False,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError(detail=f"Asset code '{data.asset_code}' already exists")

    asset = Asset(
        tenant_id=current_user.effective_tenant_id,
        site_id=data.site_id,
        gateway_id=data.gateway_id,
        asset_code=data.asset_code,
        asset_name=data.asset_name,
        asset_type=data.asset_type,
        created_by=current_user.id,
    )
    session.add(asset)
    await session.flush()
    return AssetOut.model_validate(asset)


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == current_user.effective_tenant_id,
            Asset.is_deleted == False,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError(detail="Asset not found")
    return AssetOut.model_validate(asset)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: UUID,
    data: AssetUpdate,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == current_user.effective_tenant_id,
            Asset.is_deleted == False,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError(detail="Asset not found")

    if data.asset_name is not None:
        asset.asset_name = data.asset_name
    if data.asset_type is not None:
        asset.asset_type = data.asset_type
    if data.gateway_id is not None:
        asset.gateway_id = data.gateway_id
    if data.is_active is not None:
        asset.is_active = data.is_active
    asset.updated_by = current_user.id

    return AssetOut.model_validate(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == current_user.effective_tenant_id,
            Asset.is_deleted == False,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError(detail="Asset not found")

    asset.is_deleted = True
    asset.deleted_by = current_user.id
    asset.deleted_at = datetime.utcnow()
