"""
Thin MQTT client — connect/disconnect/subscribe and dispatch messages to MessageHandler.
"""

import json
import logging
import asyncio
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt
from motor.motor_asyncio import AsyncIOMotorClient

from app.ingestion.message_handler import MessageHandler
from app.ingestion.sensor_registry import SensorRegistryCache
from app.prediction.model_binding import ModelBindingCache
from app.features.sliding_window import SlidingWindowManager
from app.prediction.ml_client import MLClient
from app.storage.telemetry_writer import TelemetryWriter
from app.storage.prediction_writer import PredictionWriter
from app.alerts.publisher import AlertPublisher

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, broker_host: str, broker_port: int, topics: List[str]):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topics = topics

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.latest_data: Dict = {}
        self.message_count: int = 0
        self.connected: bool = False

        self.mongo_client = None
        self.db = None
        self.loop = None

        self.handler: Optional[MessageHandler] = None
        self.ml_client_instance: Optional[MLClient] = None

    async def connect(
        self,
        sensor_registry: Optional[SensorRegistryCache] = None,
        model_binding_cache: Optional[ModelBindingCache] = None,
    ) -> None:
        from app.config import settings

        self.loop = asyncio.get_event_loop()

        # MongoDB
        self.mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.mongo_client[settings.MONGODB_DB]
        logger.info("Connected to MongoDB")

        # Build the processing pipeline
        window_manager = SlidingWindowManager(window_size=14)

        self.ml_client_instance = MLClient(
            base_url=settings.ML_SERVICE_URL,
            api_key=getattr(settings, "ML_API_KEY", ""),
        )

        telemetry_writer = TelemetryWriter(self.db)
        prediction_writer = PredictionWriter(self.db)

        alert_publisher = AlertPublisher(
            backend_api_url=settings.BACKEND_API_URL,
            api_key=settings.INTERNAL_API_KEY,
        )

        self.handler = MessageHandler(
            window_manager=window_manager,
            ml_client=self.ml_client_instance,
            telemetry_writer=telemetry_writer,
            prediction_writer=prediction_writer,
            alert_publisher=alert_publisher,
            sensor_registry=sensor_registry,
            model_binding_cache=model_binding_cache,
        )

        # MQTT
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        logger.info(f"Connected to MQTT broker: {self.broker_host}:{self.broker_port}")

    async def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        if self.ml_client_instance:
            await self.ml_client_instance.close()
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("Disconnected from MQTT broker and MongoDB")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            for topic in self.topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to: {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic

            self.latest_data[topic] = {
                "data": payload,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                "topic": topic,
            }
            self.message_count += 1

            if self.loop and self.handler:
                asyncio.run_coroutine_threadsafe(
                    self.handler.handle(topic, payload), self.loop
                )

            logger.debug(f"Received message on {topic}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning("Unexpected disconnection")

    def get_latest_data(self) -> Dict:
        return self.latest_data

    def is_connected(self) -> bool:
        return self.connected
