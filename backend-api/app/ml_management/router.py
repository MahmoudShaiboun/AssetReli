import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.auth.schemas import UserOut
from app.common.dependencies import get_current_user_with_tenant
from app.db.postgres import get_pg_session
from app.config import settings
from app.ml_management import service
from app.ml_management.schemas import (
    MLModelOut,
    MLModelVersionOut,
    DeploymentOut,
    FeedbackStatsOut,
    RetrainRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=list[MLModelOut])
async def list_models(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_models(session, current_user.effective_tenant_id)


@router.get("/models/{model_id}", response_model=MLModelOut)
async def get_model(
    model_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    model = await service.get_model(session, current_user.effective_tenant_id, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.get("/models/{model_id}/versions", response_model=list[MLModelVersionOut])
async def list_model_versions(
    model_id: UUID,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_model_versions(
        session, current_user.effective_tenant_id, model_id
    )


@router.get("/deployments", response_model=list[DeploymentOut])
async def list_deployments(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_deployments(session, current_user.effective_tenant_id)


@router.get("/feedback/stats", response_model=FeedbackStatsOut)
async def feedback_stats(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.get_feedback_stats(session, current_user.effective_tenant_id)


@router.post("/retrain")
async def trigger_retrain(
    body: RetrainRequest = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
):
    try:
        payload = {
            "tenant_id": str(current_user.effective_tenant_id),
            "async_mode": True,
        }
        if body:
            payload["async_mode"] = body.async_mode
            if body.selected_data_ids:
                payload["selected_data_ids"] = body.selected_data_ids

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/retrain",
                json=payload,
                timeout=60.0,
            )
            return response.json()
    except Exception as e:
        logger.error(f"Retrain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
