from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from datetime import datetime

from .mqtt_client import MQTTClient
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mqtt_client = None
active_websockets = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_client
    logger.info("🚀 Starting MQTT Ingestion Service...")
    
    # Initialize MQTT client
    mqtt_client = MQTTClient(
        broker_host=settings.MQTT_BROKER_HOST,
        broker_port=settings.MQTT_BROKER_PORT,
        topics=settings.MQTT_TOPICS
    )
    
    # Start MQTT client
    await mqtt_client.connect()
    logger.info("✅ MQTT Ingestion Service ready!")
    
    yield
    
    # Cleanup
    await mqtt_client.disconnect()
    logger.info("👋 MQTT Ingestion Service stopped")

app = FastAPI(
    title="Aastreli MQTT Ingestion",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "mqtt-ingestion",
        "status": "running",
        "broker": settings.MQTT_BROKER_HOST,
        "topics": settings.MQTT_TOPICS
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.is_connected() if mqtt_client else False,
        "messages_received": mqtt_client.message_count if mqtt_client else 0
    }

@app.get("/latest")
async def get_latest():
    """Get latest sensor readings"""
    if mqtt_client:
        return mqtt_client.get_latest_data()
    return {"error": "MQTT client not initialized"}

@app.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket for real-time data streaming"""
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            # Send latest data every second
            if mqtt_client:
                data = mqtt_client.get_latest_data()
                await websocket.send_json(data)
            await asyncio.sleep(1)
    
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        logger.info("WebSocket client disconnected")
