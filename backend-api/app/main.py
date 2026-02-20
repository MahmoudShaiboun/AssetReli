import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import text

from app.config import settings
from app.db.postgres import engine
from app.auth.router import router as auth_router
from app.auth.tenant_router import router as tenant_router
from app.auth.user_router import router as user_router
from app.site_setup.router import router as site_setup_router
from app.predictions.router import router as predictions_router
from app.ml_management.router import router as ml_management_router
from app.alerts.router import router as alerts_router
from app.dashboard.router import router as dashboard_router

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",    
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Backend API...")

    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"PostgreSQL not available: {e}")
        raise

    # MongoDB (still used for telemetry_raw + predictions)
    try:
        app.mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL, serverSelectionTimeoutMS=5000
        )
        await app.mongodb_client.admin.command("ping")
        app.mongodb = app.mongodb_client[settings.MONGODB_DB]
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.warning(f"MongoDB not available: {e}")
        app.mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL, serverSelectionTimeoutMS=5000
        )
        app.mongodb = app.mongodb_client[settings.MONGODB_DB]

    logger.info("Backend API ready!")
    yield

    await engine.dispose()
    app.mongodb_client.close()
    logger.info("Backend API stopped")


app = FastAPI(title="Aastreli Backend API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire domain routers
# Auth endpoints keep their existing paths for backward compatibility
app.include_router(auth_router, tags=["auth"])
app.include_router(tenant_router, tags=["tenants"])
app.include_router(user_router, tags=["users"])
app.include_router(site_setup_router, tags=["site-setup"])
app.include_router(predictions_router, tags=["predictions"])
app.include_router(ml_management_router, prefix="/ml", tags=["ml-management"])
app.include_router(alerts_router, tags=["alerts"])
app.include_router(dashboard_router, tags=["dashboard"])


@app.get("/")
async def root():
    return {"service": "backend-api", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
