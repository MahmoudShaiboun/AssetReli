import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.common.auth import verify_internal_key
from app.prediction.schemas import PredictionRequest, PredictionResponse
from app.prediction.feature_converter import convert_structured_to_features

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest, _key: str = Depends(verify_internal_key)):
    try:
        from app.models.registry import get_registry

        registry = get_registry()
        features = convert_structured_to_features(request)
        result = registry.predict(
            features=features,
            top_k=request.top_k or 3,
            model_version_id=request.model_version_id,
            tenant_id=request.tenant_id,
        )

        top_3_str = ", ".join(
            [
                f"{p['label']}({p['confidence']:.3f})"
                for p in result["top_predictions"][:3]
            ]
        )
        logger.info(
            f"PREDICTION: {result['prediction']} | "
            f"Confidence: {result['confidence']:.4f} | Top 3: {top_3_str}"
        )

        return PredictionResponse(
            prediction=result["prediction"],
            confidence=result["confidence"],
            top_predictions=result["top_predictions"],
            model_version=registry.get_current_version(),
            model_version_id=result.get("model_version_id"),
            timestamp=datetime.utcnow(),
            request_id=request.request_id,
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-batch")
async def predict_batch(requests: list[PredictionRequest]):
    """Batch predictions — correctly calls convert_structured_to_features."""
    try:
        from app.models.registry import get_registry

        registry = get_registry()
        results = []
        for req in requests:
            features = convert_structured_to_features(req)
            result = registry.predict(
                features=features,
                top_k=req.top_k or 3,
                model_version_id=req.model_version_id,
                tenant_id=req.tenant_id,
            )

            results.append(
                PredictionResponse(
                    prediction=result["prediction"],
                    confidence=result["confidence"],
                    top_predictions=result["top_predictions"],
                    model_version=registry.get_current_version(),
                    model_version_id=result.get("model_version_id"),
                    timestamp=datetime.utcnow(),
                    request_id=req.request_id,
                )
            )
        return results
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
