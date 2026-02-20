import logging

from fastapi import APIRouter, Depends, HTTPException

from app.common.auth import verify_internal_key
from app.feedback.schemas import FeedbackRequest, FeedbackResponse
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level reference — set by main.py
_feedback_service = None


def set_feedback_service(service):
    global _feedback_service
    _feedback_service = service


def get_feedback_service():
    if _feedback_service is None:
        raise RuntimeError("FeedbackService not initialized")
    return _feedback_service


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest, _key: str = Depends(verify_internal_key)):
    try:
        svc = get_feedback_service()
        from uuid import UUID as _UUID

        def _to_uuid(val):
            if val:
                try:
                    return _UUID(val)
                except (ValueError, TypeError):
                    pass
            return None

        tenant_uuid = _to_uuid(feedback.tenant_id)

        feedback_id = await svc.store_feedback(
            features=feedback.features,
            original_prediction=feedback.original_prediction,
            corrected_label=feedback.corrected_label,
            feedback_type=feedback.feedback_type,
            confidence=feedback.confidence,
            notes=feedback.notes,
            tenant_id=tenant_uuid,
            asset_id=_to_uuid(feedback.asset_id),
            sensor_id=_to_uuid(feedback.sensor_id),
            prediction_id=feedback.prediction_id,
        )

        count = await svc.get_feedback_count()

        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message=f"Feedback stored. Total: {count}",
            total_feedback=count,
            ready_for_retraining=count >= settings.MIN_FEEDBACK_FOR_RETRAIN,
        )
    except Exception as e:
        logger.error(f"Feedback storage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/stats")
async def get_feedback_stats():
    try:
        return await get_feedback_service().get_feedback_stats()
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
