import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import httpx

from app.auth.schemas import UserOut
from app.common.database import get_mongo_db
from app.common.dependencies import get_current_user_with_tenant
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/predictions")
async def get_predictions(
    limit: int = 100,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    tenant_filter = {"tenant_id": str(current_user.effective_tenant_id)}
    predictions = (
        await db.predictions.find(tenant_filter)
        .sort("timestamp", -1)
        .limit(limit)
        .to_list(limit)
    )
    for p in predictions:
        p["_id"] = str(p["_id"])
    return {"predictions": predictions, "count": len(predictions)}


@router.post("/predictions")
async def create_prediction(
    features: list[float],
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/predict",
                json={"features": features},
                timeout=30.0,
            )
            result = response.json()

        prediction_doc = {
            **result,
            "tenant_id": str(current_user.effective_tenant_id),
            "created_at": datetime.utcnow(),
        }
        await db.predictions.insert_one(prediction_doc)

        return result
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(
    features: list[float],
    original_prediction: str,
    corrected_label: str,
    feedback_type: str,
    confidence: float = None,
    notes: str = None,
    sensor_id: str = None,
    reading_id: str = None,
    timestamp: str = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    db=Depends(get_mongo_db),
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/feedback",
                json={
                    "features": features,
                    "original_prediction": original_prediction,
                    "corrected_label": corrected_label,
                    "feedback_type": feedback_type,
                    "confidence": confidence,
                    "notes": notes,
                    "tenant_id": str(current_user.effective_tenant_id),
                },
                timeout=30.0,
            )
            result = response.json()

        feedback_doc = {
            "features": features,
            "original_prediction": original_prediction,
            "corrected_label": corrected_label,
            "feedback_type": feedback_type,
            "confidence": confidence,
            "notes": notes,
            "sensor_id": sensor_id,
            "reading_id": reading_id,
            "timestamp": timestamp,
            "tenant_id": str(current_user.effective_tenant_id),
            "feedback_id": result.get("feedback_id"),
            "created_at": datetime.utcnow(),
        }
        await db.feedback.insert_one(feedback_doc)

        if reading_id:
            from bson import ObjectId

            try:
                await db.sensor_readings.update_one(
                    {"_id": ObjectId(reading_id)},
                    {
                        "$set": {
                            "has_feedback": True,
                            "feedback_label": corrected_label,
                        }
                    },
                )
            except Exception as e:
                logger.warning(f"Could not update reading: {e}")

        return result
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
