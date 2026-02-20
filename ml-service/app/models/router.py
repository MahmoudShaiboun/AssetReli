import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ModelInfo
from app.common.auth import verify_internal_key
from app.common.exceptions import ModelNotFoundError
from app.db.postgres import get_pg_session
from app.db.models import MLModelVersion, MLModelDeployment

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=list[ModelInfo])
async def list_models():
    try:
        from app.models.registry import get_registry

        return get_registry().list_versions()
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{version}", response_model=ModelInfo)
async def get_model_info(version: str):
    try:
        from app.models.registry import get_registry

        info = get_registry().get_version_info(version)
        if not info:
            raise ModelNotFoundError(version)
        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{version}/activate")
async def activate_model(version: str):
    """Legacy filesystem-based activation (backward compatible)."""
    try:
        from app.models.registry import get_registry

        registry = get_registry()
        success = registry.activate_version(version)

        if not success:
            raise ModelNotFoundError(version)

        return {
            "success": True,
            "message": f"Activated model version {version}",
            "current_version": registry.get_current_version(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeployRequest(BaseModel):
    is_production: bool = True


@router.post("/models/versions/{version_id}/deploy")
async def deploy_model_version(
    version_id: UUID,
    body: DeployRequest = DeployRequest(),
    session: AsyncSession = Depends(get_pg_session),
    _key: str = Depends(verify_internal_key),
):
    """Atomic model activation via PG deployment records.

    1. Validates the model version exists
    2. Ends current production deployment for the same tenant+model
    3. Creates a new deployment record
    4. Updates the registry default immediately
    """
    from app.models.registry import get_registry

    # Fetch the version
    result = await session.execute(
        select(MLModelVersion).where(
            MLModelVersion.id == version_id,
            MLModelVersion.is_deleted == False,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Model version not found")

    now = datetime.now(timezone.utc)

    if body.is_production:
        # End current production deployment for same tenant+model
        await session.execute(
            update(MLModelDeployment)
            .where(
                MLModelDeployment.tenant_id == version.tenant_id,
                MLModelDeployment.model_id == version.model_id,
                MLModelDeployment.is_production == True,
                MLModelDeployment.deployment_end == None,
            )
            .values(deployment_end=now, is_production=False)
        )

        # Promote version stage to production
        version.stage = "production"

    # Create new deployment
    deployment = MLModelDeployment(
        tenant_id=version.tenant_id,
        model_id=version.model_id,
        model_version_id=version.id,
        is_production=body.is_production,
        deployment_start=now,
    )
    session.add(deployment)
    await session.commit()

    # Immediately update registry default (no wait for 60s poll)
    registry = get_registry()
    if body.is_production:
        registry._tenant_defaults[version.tenant_id] = version.id
        registry._version_paths[version.id] = version.model_artifact_path
        logger.info(
            f"Atomically deployed version {version.full_version_label} "
            f"as production for tenant {version.tenant_id}"
        )

    return {
        "success": True,
        "message": f"Deployed {version.full_version_label}",
        "deployment_id": str(deployment.id),
        "is_production": body.is_production,
    }


@router.get("/metrics")
async def get_metrics():
    try:
        from app.models.registry import get_registry

        return get_registry().get_metrics()
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
