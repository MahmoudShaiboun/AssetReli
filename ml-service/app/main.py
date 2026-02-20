from contextlib import asynccontextmanager
from datetime import datetime
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db.postgres import engine, async_session_factory
from app.models.registry import init_registry, get_registry
from app.models.schemas import HealthResponse
from app.feedback.service import FeedbackService
from app.feedback.router import set_feedback_service
from app.retraining.pipeline import RetrainingPipeline
from app.retraining.router import set_retraining_pipeline

from app.prediction import router as prediction_router
from app.models import router as models_router
from app.feedback import router as feedback_router
from app.retraining import router as retraining_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ML Service...")

    # PostgreSQL connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"PostgreSQL not available: {e}")
        raise

    # Model registry (wraps ModelManager)
    registry = init_registry(
        model_dir=settings.MODEL_DIR,
        current_model_dir=settings.CURRENT_MODEL_DIR,
    )
    try:
        registry.load()
        logger.info(f"Loaded model: {registry.get_current_version()}")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

    # Feedback service (PostgreSQL-backed)
    feedback_svc = FeedbackService(session_factory=async_session_factory)
    set_feedback_service(feedback_svc)

    # Retraining pipeline
    pipeline = RetrainingPipeline(
        model_manager=registry.manager,
        feedback_service=feedback_svc,
        session_factory=async_session_factory,
    )
    set_retraining_pipeline(pipeline)

    # Start periodic refresh of default model deployments from PG
    registry.start_refresh_loop(async_session_factory, interval_sec=60)

    logger.info("ML Service ready")
    yield

    await registry.stop()
    await engine.dispose()
    logger.info("Shutting down ML Service...")


app = FastAPI(
    title="Aastreli ML Service",
    description="Machine Learning service for industrial anomaly detection",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire routers — no prefix to preserve backward-compatible paths
app.include_router(prediction_router.router)
app.include_router(models_router.router)
app.include_router(feedback_router.router)
app.include_router(retraining_router.router)


@app.get("/", response_model=HealthResponse)
async def root():
    registry = get_registry()
    return HealthResponse(
        status="healthy",
        service="ml-service",
        version="1.0.0",
        model_version=registry.get_current_version(),
        timestamp=datetime.utcnow(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    registry = get_registry()
    mgr = registry.manager
    model_loaded = mgr.model is not None

    return HealthResponse(
        status="healthy" if model_loaded else "unhealthy",
        service="ml-service",
        version="1.0.0",
        model_version=registry.get_current_version(),
        timestamp=datetime.utcnow(),
        details={
            "model_loaded": model_loaded,
            "num_classes": (
                len(mgr.label_encoder.classes_) if model_loaded else 0
            ),
            "feedback_count": await feedback_router.get_feedback_service().get_feedback_count(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
