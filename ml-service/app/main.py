from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from .model import ModelManager
from .retrain import RetrainingPipeline
from .schemas import (
    PredictionRequest,
    PredictionResponse,
    FeedbackRequest,
    FeedbackResponse,
    RetrainRequest,
    RetrainResponse,
    ModelInfo,
    HealthResponse
)
from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
model_manager = None
retraining_pipeline = None


def convert_structured_to_features(request: PredictionRequest) -> list[float]:
    """
    Convert structured sensor data to features array (336 features).
    If features array is provided, use it directly. Otherwise, construct from structured fields.
    """
    # If features array is provided, use it
    if request.features and len(request.features) > 0:
        return request.features
    
    # Otherwise, construct from structured fields
    # Order must match the training data structure
    features = [
        # Motor DE vibration bands (4)
        request.motor_DE_vib_band_1 or 0.0,
        request.motor_DE_vib_band_2 or 0.0,
        request.motor_DE_vib_band_3 or 0.0,
        request.motor_DE_vib_band_4 or 0.0,
        
        # Motor NDE vibration bands (4)
        request.motor_NDE_vib_band_1 or 0.0,
        request.motor_NDE_vib_band_2 or 0.0,
        request.motor_NDE_vib_band_3 or 0.0,
        request.motor_NDE_vib_band_4 or 0.0,
        
        # Motor ultrasonic sensors (2)
        request.motor_DE_ultra_db or 0.0,
        request.motor_NDE_ultra_db or 0.0,
        
        # Motor temperature sensors (2)
        request.motor_DE_temp_c or 0.0,
        request.motor_NDE_temp_c or 0.0,
        
        # Pump DE vibration bands (4)
        request.pump_DE_vib_band_1 or 0.0,
        request.pump_DE_vib_band_2 or 0.0,
        request.pump_DE_vib_band_3 or 0.0,
        request.pump_DE_vib_band_4 or 0.0,
        
        # Pump NDE vibration bands (4)
        request.pump_NDE_vib_band_1 or 0.0,
        request.pump_NDE_vib_band_2 or 0.0,
        request.pump_NDE_vib_band_3 or 0.0,
        request.pump_NDE_vib_band_4 or 0.0,
        
        # Pump ultrasonic sensors (2)
        request.pump_DE_ultra_db or 0.0,
        request.pump_NDE_ultra_db or 0.0,
        
        # Pump temperature sensors (2)
        request.pump_DE_temp_c or 0.0,
        request.pump_NDE_temp_c or 0.0,
    ]
    
    # Duplicate the pattern to create 336 features (matches training structure)
    # The actual model expects this specific structure
    features = features * 14  # 24 * 14 = 336
    
    return features


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global model_manager, retraining_pipeline
    
    logger.info("🚀 Starting ML Service...")
    
    # Initialize model manager
    model_manager = ModelManager(
        model_dir=settings.MODEL_DIR,
        current_model_dir=settings.CURRENT_MODEL_DIR
    )
    
    # Load current model
    try:
        model_manager.load_current_model()
        logger.info(f"✅ Loaded model: {model_manager.get_current_version()}")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise
    
    # Initialize retraining pipeline
    retraining_pipeline = RetrainingPipeline(
        model_manager=model_manager,
        feedback_dir=settings.FEEDBACK_DIR
    )
    
    logger.info("✅ ML Service ready!")
    
    yield
    
    logger.info("👋 Shutting down ML Service...")


# Create FastAPI app
app = FastAPI(
    title="Aastreli ML Service",
    description="Machine Learning service for industrial anomaly detection",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="ml-service",
        version="1.0.0",
        model_version=model_manager.get_current_version(),
        timestamp=datetime.utcnow()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check"""
    model_loaded = model_manager.model is not None
    
    return HealthResponse(
        status="healthy" if model_loaded else "unhealthy",
        service="ml-service",
        version="1.0.0",
        model_version=model_manager.get_current_version(),
        timestamp=datetime.utcnow(),
        details={
            "model_loaded": model_loaded,
            "num_classes": len(model_manager.label_encoder.classes_) if model_loaded else 0,
            "feedback_count": retraining_pipeline.get_feedback_count()
        }
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Predict fault type from sensor window data.
    Accepts either:
    - Structured sensor data fields (motor_DE_vib_band_1, etc.)
    - Direct features array (336 values)
    
    Args:
        request: PredictionRequest with sensor features
    
    Returns:
        PredictionResponse with prediction and confidence
    """
    try:
        # Convert structured data to features array
        features = convert_structured_to_features(request)
        
        # Make prediction
        result = model_manager.predict(
            features=features,
            top_k=request.top_k or 3
        )
        
        # Log prediction details
        top_3_str = ", ".join([f"{p['label']}({p['confidence']:.3f})" for p in result['top_predictions'][:3]])
        logger.info(f"🔮 PREDICTION: {result['prediction']} | Confidence: {result['confidence']:.4f} | Top 3: {top_3_str}")
        
        return PredictionResponse(
            prediction=result['prediction'],
            confidence=result['confidence'],
            top_predictions=result['top_predictions'],
            model_version=model_manager.get_current_version(),
            timestamp=datetime.utcnow(),
            request_id=request.request_id
        )
    
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-batch")
async def predict_batch(requests: list[PredictionRequest]):
    """
    Batch predictions for multiple sensor windows.
    
    Args:
        requests: List of PredictionRequest objects
    
    Returns:
        List of PredictionResponse objects
    """
    try:
        results = []
        for req in requests:
            result = model_manager.predict(
                features=req.features,
                top_k=req.top_k or 3
            )
            
            results.append(PredictionResponse(
                prediction=result['prediction'],
                confidence=result['confidence'],
                top_predictions=result['top_predictions'],
                model_version=model_manager.get_current_version(),
                timestamp=datetime.utcnow(),
                request_id=req.request_id
            ))
        
        return results
    
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit user feedback for model improvement.
    
    Args:
        feedback: FeedbackRequest with correction
    
    Returns:
        FeedbackResponse with confirmation
    """
    try:
        # Store feedback
        feedback_id = retraining_pipeline.store_feedback(
            features=feedback.features,
            original_prediction=feedback.original_prediction,
            corrected_label=feedback.corrected_label,
            feedback_type=feedback.feedback_type,
            confidence=feedback.confidence,
            notes=feedback.notes
        )
        
        feedback_count = retraining_pipeline.get_feedback_count()
        
        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message=f"Feedback stored. Total: {feedback_count}",
            total_feedback=feedback_count,
            ready_for_retraining=feedback_count >= settings.MIN_FEEDBACK_FOR_RETRAIN
        )
    
    except Exception as e:
        logger.error(f"Feedback storage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrain", response_model=RetrainResponse)
async def trigger_retrain(
    request: RetrainRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger model retraining with accumulated feedback.
    
    Args:
        request: RetrainRequest with options
        background_tasks: FastAPI background tasks
    
    Returns:
        RetrainResponse with status
    """
    try:
        feedback_count = retraining_pipeline.get_feedback_count()
        
        # Check minimum feedback threshold
        if feedback_count < settings.MIN_FEEDBACK_FOR_RETRAIN:
            return RetrainResponse(
                success=False,
                message=f"Insufficient feedback. Need {settings.MIN_FEEDBACK_FOR_RETRAIN}, have {feedback_count}",
                feedback_count=feedback_count
            )
        
        # Run retraining in background
        if request.async_mode:
            background_tasks.add_task(
                retraining_pipeline.retrain_model,
                request.selected_data_ids
            )
            
            return RetrainResponse(
                success=True,
                message="Retraining started in background",
                feedback_count=feedback_count,
                async_mode=True
            )
        else:
            # Synchronous retraining
            result = retraining_pipeline.retrain_model(
                selected_data_ids=request.selected_data_ids
            )
            
            return RetrainResponse(
                success=result['success'],
                message=result['message'],
                new_version=result.get('version'),
                metrics=result.get('metrics'),
                feedback_count=feedback_count,
                async_mode=False
            )
    
    except Exception as e:
        logger.error(f"Retraining error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models", response_model=list[ModelInfo])
async def list_models():
    """
    List all available model versions.
    
    Returns:
        List of ModelInfo objects
    """
    try:
        models = model_manager.list_versions()
        return models
    
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models/{version}", response_model=ModelInfo)
async def get_model_info(version: str):
    """
    Get information about a specific model version.
    
    Args:
        version: Model version identifier
    
    Returns:
        ModelInfo object
    """
    try:
        info = model_manager.get_version_info(version)
        if not info:
            raise HTTPException(status_code=404, detail=f"Model version {version} not found")
        return info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/{version}/activate")
async def activate_model(version: str):
    """
    Activate a specific model version.
    
    Args:
        version: Model version to activate
    
    Returns:
        Success message
    """
    try:
        success = model_manager.activate_version(version)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Model version {version} not found")
        
        return {
            "success": True,
            "message": f"Activated model version {version}",
            "current_version": model_manager.get_current_version()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """
    Get current model performance metrics.
    
    Returns:
        Performance metrics dictionary
    """
    try:
        metrics = model_manager.get_metrics()
        return metrics
    
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback/stats")
async def get_feedback_stats():
    """
    Get feedback statistics.
    
    Returns:
        Feedback statistics dictionary
    """
    try:
        stats = retraining_pipeline.get_feedback_stats()
        return stats
    
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
