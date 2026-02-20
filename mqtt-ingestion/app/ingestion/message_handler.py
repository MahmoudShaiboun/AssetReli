"""
MessageHandler — the main processing pipeline for each MQTT message.

Flow:  raw payload → resolve context → store raw → feature extraction
       → ML prediction → store reading → alert
"""

import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.features.extractors import (
    extract_24_features_from_data,
    extract_statistical_features_from_window,
)
from app.features.sliding_window import SlidingWindowManager
from app.prediction.ml_client import MLClient
from app.storage.telemetry_writer import TelemetryWriter
from app.storage.prediction_writer import PredictionWriter
from app.alerts.publisher import AlertPublisher
from app.ingestion.sensor_registry import SensorRegistryCache
from app.ingestion.topic_parser import parse_topic
from app.ingestion.context import MessageContext
from app.prediction.model_binding import ModelBindingCache

logger = logging.getLogger(__name__)


class MessageHandler:
    """Processes each MQTT message through the ingestion pipeline."""

    def __init__(
        self,
        window_manager: SlidingWindowManager,
        ml_client: MLClient,
        telemetry_writer: TelemetryWriter,
        prediction_writer: PredictionWriter,
        alert_publisher: AlertPublisher,
        sensor_registry: Optional[SensorRegistryCache] = None,
        model_binding_cache: Optional[ModelBindingCache] = None,
    ):
        self.window_manager = window_manager
        self.ml_client = ml_client
        self.telemetry_writer = telemetry_writer
        self.prediction_writer = prediction_writer
        self.alert_publisher = alert_publisher
        self.sensor_registry = sensor_registry
        self.model_binding_cache = model_binding_cache

    def _resolve_context(self, topic: str, data: dict) -> MessageContext:
        """Resolve full tenant/site/asset/sensor context from topic + registry."""
        parsed = parse_topic(topic)
        if not parsed:
            return MessageContext(sensor_code=data.get("sensor_id"))

        ctx = MessageContext(
            sensor_code=parsed.sensor_code,
            tenant_code=parsed.tenant_code,
            site_code=parsed.site_code,
        )

        # Try to enrich from sensor registry
        if self.sensor_registry:
            binding = self.sensor_registry.lookup(parsed.sensor_code)
            if binding:
                ctx.tenant_id = binding.tenant_id
                ctx.tenant_code = binding.tenant_code
                ctx.site_id = binding.site_id
                ctx.site_code = binding.site_code
                ctx.asset_id = binding.asset_id
                ctx.sensor_id = binding.sensor_id

                # Resolve model version for this asset
                if self.model_binding_cache and binding.asset_id:
                    mb = self.model_binding_cache.lookup(binding.asset_id)
                    if mb:
                        ctx.model_version_id = mb.model_version_id
            else:
                logger.warning(
                    f"Sensor '{parsed.sensor_code}' not found in registry, "
                    f"processing without tenant context"
                )

        return ctx

    async def handle(self, topic: str, data: dict) -> None:
        try:
            timestamp = datetime.utcnow()

            # 0. Resolve tenant context
            ctx = self._resolve_context(topic, data)

            # 1. Store raw telemetry
            await self.telemetry_writer.write(topic, data, timestamp, ctx)

            # 2. Feature extraction + prediction
            prediction: Optional[str] = None
            confidence: float = 0.0

            if "motor_DE_vib_band_1" in data:
                prediction, confidence = await self._handle_complex_sensor(
                    data, timestamp, ctx
                )
            elif "sensor_id" in data and any(
                key in data
                for key in ("temperature", "vibration", "pressure", "humidity")
            ):
                prediction, confidence = await self._handle_simple_sensor(data, ctx)

            # 3. Store structured reading
            if "sensor_id" in data and "motor_DE_vib_band_1" not in data:
                await self.prediction_writer.write_simple_reading(
                    data, topic, timestamp, prediction, confidence, ctx
                )
            elif "motor_DE_vib_band_1" in data:
                sensor_reading = await self.prediction_writer.write_complex_reading(
                    data, topic, timestamp, prediction, confidence, ctx
                )

                # 4. Trigger alert if anomaly
                if (
                    prediction
                    and prediction.lower() != "normal"
                    and confidence > settings.ALERT_CONFIDENCE_THRESHOLD
                ):
                    _pred_id = str(sensor_reading.get("_id", "")) or None
                    await self.alert_publisher.publish(
                        prediction, confidence, sensor_reading, ctx,
                        prediction_id=_pred_id,
                    )

        except Exception as e:
            logger.error(f"Error storing data: {e}", exc_info=True)

    async def _handle_complex_sensor(
        self, data: dict, timestamp: datetime, ctx: MessageContext
    ) -> tuple[Optional[str], float]:
        sensor_key = ctx.window_key

        current_features = extract_24_features_from_data(data)
        window = self.window_manager.add_reading(sensor_key, current_features)

        if window is not None:
            features = extract_statistical_features_from_window(window)
            logger.info(
                f"Making prediction with {len(features)} statistical features "
                f"for {sensor_key}"
            )

            result = await self.ml_client.predict(
                features,
                tenant_id=ctx.tenant_id_str,
                asset_id=ctx.asset_id_str,
                model_version_id=ctx.model_version_id_str,
            )
            if result:
                prediction = result.get("prediction")
                confidence = result.get("confidence", 0.0)
                logger.info(
                    f"ML Prediction (window): {prediction} "
                    f"(confidence: {confidence:.2f})"
                )
                return prediction, confidence

        return None, 0.0

    async def _handle_simple_sensor(
        self, data: dict, ctx: MessageContext
    ) -> tuple[Optional[str], float]:
        features = [
            data.get("temperature", 0.0),
            data.get("vibration", 0.0),
            data.get("pressure", 0.0),
            data.get("humidity", 0.0),
        ]
        features.extend([0.0] * (336 - len(features)))

        result = await self.ml_client.predict(
            features,
            tenant_id=ctx.tenant_id_str,
            asset_id=ctx.asset_id_str,
            model_version_id=ctx.model_version_id_str,
        )
        if result:
            prediction = result.get("prediction")
            confidence = result.get("confidence", 0.0)
            logger.info(
                f"ML Prediction: {prediction} (confidence: {confidence:.2f})"
            )
            return prediction, confidence

        return None, 0.0
