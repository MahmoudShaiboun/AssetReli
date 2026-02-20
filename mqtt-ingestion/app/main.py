import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.mqtt_client import MQTTClient
from app.ingestion.sensor_registry import SensorRegistryCache
from app.prediction.model_binding import ModelBindingCache
from app.db.postgres import init_pg_pool, close_pg_pool
from app.streaming.websocket import router as ws_router
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MQTT Ingestion Service...")

    # PostgreSQL read pool (for sensor registry + model bindings)
    pg_pool = await init_pg_pool(settings.POSTGRES_DSN)

    # Caches — populate once, then auto-refresh in background
    sensor_registry = SensorRegistryCache(refresh_interval_sec=60)
    await sensor_registry.refresh(pg_pool)
    sensor_registry.start_refresh_loop(pg_pool)

    model_binding_cache = ModelBindingCache(refresh_interval_sec=60)
    await model_binding_cache.refresh(pg_pool)
    model_binding_cache.start_refresh_loop(pg_pool)

    logger.info(
        f"Caches loaded: {sensor_registry.size} sensors, "
        f"{model_binding_cache.size} model bindings"
    )

    mqtt_client = MQTTClient(
        broker_host=settings.MQTT_BROKER_HOST,
        broker_port=settings.MQTT_BROKER_PORT,
        topics=settings.MQTT_TOPICS,
    )

    await mqtt_client.connect(
        sensor_registry=sensor_registry,
        model_binding_cache=model_binding_cache,
    )
    app.state.mqtt_client = mqtt_client
    app.state.sensor_registry = sensor_registry
    app.state.model_binding_cache = model_binding_cache
    logger.info("MQTT Ingestion Service ready!")

    yield

    await sensor_registry.stop()
    await model_binding_cache.stop()
    await mqtt_client.disconnect()
    await close_pg_pool()
    logger.info("MQTT Ingestion Service stopped")


app = FastAPI(title="Aastreli MQTT Ingestion", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "service": "mqtt-ingestion",
        "status": "running",
        "broker": settings.MQTT_BROKER_HOST,
        "topics": settings.MQTT_TOPICS,
    }


@app.get("/health")
async def health():
    mqtt_client = app.state.mqtt_client
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.is_connected() if mqtt_client else False,
        "messages_received": mqtt_client.message_count if mqtt_client else 0,
        "sensor_cache_size": getattr(app.state, "sensor_registry", None) and app.state.sensor_registry.size or 0,
        "model_cache_size": getattr(app.state, "model_binding_cache", None) and app.state.model_binding_cache.size or 0,
    }


@app.get("/latest")
async def get_latest():
    mqtt_client = app.state.mqtt_client
    if mqtt_client:
        return mqtt_client.get_latest_data()
    return {"error": "MQTT client not initialized"}
