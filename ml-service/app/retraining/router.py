import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.common.auth import verify_internal_key
from app.config import settings
from app.retraining.schemas import RetrainRequest, RetrainResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level reference — set by main.py
_retraining_pipeline = None


def set_retraining_pipeline(pipeline):
    global _retraining_pipeline
    _retraining_pipeline = pipeline


def get_retraining_pipeline():
    if _retraining_pipeline is None:
        raise RuntimeError("RetrainingPipeline not initialized")
    return _retraining_pipeline


async def _run_retrain_background(pipeline, selected_data_ids, tenant_id, model_id):
    """Wrapper for running async retrain in a background task."""
    await pipeline.retrain_model(
        selected_data_ids=selected_data_ids,
        tenant_id=tenant_id,
        model_id=model_id,
    )


@router.post("/retrain", response_model=RetrainResponse)
async def trigger_retrain(request: RetrainRequest, background_tasks: BackgroundTasks, _key: str = Depends(verify_internal_key)):
    try:
        pipeline = get_retraining_pipeline()

        # Resolve optional tenant/model UUIDs
        tenant_uuid = UUID(request.tenant_id) if request.tenant_id else None
        model_uuid = UUID(request.model_id) if request.model_id else None

        feedback_count = await pipeline.feedback_service.get_feedback_count(
            tenant_id=tenant_uuid
        )

        if feedback_count < settings.MIN_FEEDBACK_FOR_RETRAIN:
            return RetrainResponse(
                success=False,
                message=(
                    f"Insufficient feedback. "
                    f"Need {settings.MIN_FEEDBACK_FOR_RETRAIN}, have {feedback_count}"
                ),
                feedback_count=feedback_count,
            )

        if request.async_mode:
            background_tasks.add_task(
                _run_retrain_background,
                pipeline,
                request.selected_data_ids,
                tenant_uuid,
                model_uuid,
            )
            return RetrainResponse(
                success=True,
                message="Retraining started in background",
                feedback_count=feedback_count,
                async_mode=True,
            )

        result = await pipeline.retrain_model(
            selected_data_ids=request.selected_data_ids,
            tenant_id=tenant_uuid,
            model_id=model_uuid,
        )

        return RetrainResponse(
            success=result["success"],
            message=result["message"],
            new_version=result.get("version"),
            metrics=result.get("metrics"),
            feedback_count=feedback_count,
            async_mode=False,
        )
    except Exception as e:
        logger.error(f"Retraining error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
