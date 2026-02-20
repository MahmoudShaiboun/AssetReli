import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.ingestion.context import MessageContext

logger = logging.getLogger(__name__)


class PredictionWriter:
    """Writes structured sensor readings (with prediction) to sensor_readings collection."""

    def __init__(self, db):
        self.db = db

    def _add_context(self, doc: dict, ctx: Optional["MessageContext"]) -> dict:
        """Inject tenant context fields into a document."""
        if ctx and ctx.is_resolved:
            doc["tenant_id"] = ctx.tenant_id_str
            doc["site_id"] = ctx.site_id_str
            doc["asset_id"] = ctx.asset_id_str
            doc["sensor_uuid"] = ctx.sensor_id_str
            if ctx.model_version_id:
                doc["model_version_id"] = ctx.model_version_id_str
        return doc

    async def write_simple_reading(
        self,
        data: dict,
        topic: str,
        timestamp: datetime,
        prediction: Optional[str],
        confidence: float,
        ctx: Optional["MessageContext"] = None,
    ) -> None:
        sensor_reading = {
            "sensor_id": data.get("sensor_id", "unknown"),
            "timestamp": (
                data.get("timestamp", timestamp.isoformat())
                if isinstance(data.get("timestamp"), str)
                else timestamp
            ),
            "temperature": data.get("temperature"),
            "vibration": data.get("vibration"),
            "pressure": data.get("pressure"),
            "humidity": data.get("humidity"),
            "topic": topic,
            "has_feedback": False,
            "prediction": prediction,
            "confidence": confidence,
        }
        self._add_context(sensor_reading, ctx)
        await self.db.sensor_readings.insert_one(sensor_reading)
        logger.info(f"Stored simple sensor reading with ML prediction: {prediction}")

    async def write_complex_reading(
        self,
        data: dict,
        topic: str,
        timestamp: datetime,
        prediction: Optional[str],
        confidence: float,
        ctx: Optional["MessageContext"] = None,
    ) -> dict:
        sensor_reading = {
            "sensor_id": data.get("sensor_id", "industrial_sensor"),
            "timestamp": (
                data.get("timestamp", timestamp.isoformat())
                if isinstance(data.get("timestamp"), str)
                else timestamp
            ),
            "state": data.get("state"),
            "regime": data.get("regime"),
            "motor_data": {
                "DE_temp": data.get("motor_DE_temp_c"),
                "NDE_temp": data.get("motor_NDE_temp_c"),
                "DE_ultra": data.get("motor_DE_ultra_db"),
                "NDE_ultra": data.get("motor_NDE_ultra_db"),
                "DE_vib_band_1": data.get("motor_DE_vib_band_1"),
                "DE_vib_band_2": data.get("motor_DE_vib_band_2"),
                "DE_vib_band_3": data.get("motor_DE_vib_band_3"),
                "DE_vib_band_4": data.get("motor_DE_vib_band_4"),
            },
            "pump_data": {
                "DE_temp": data.get("pump_DE_temp_c"),
                "NDE_temp": data.get("pump_NDE_temp_c"),
                "DE_ultra": data.get("pump_DE_ultra_db"),
                "NDE_ultra": data.get("pump_NDE_ultra_db"),
            },
            "topic": topic,
            "has_feedback": False,
            "prediction": prediction,
            "confidence": confidence,
        }
        self._add_context(sensor_reading, ctx)
        await self.db.sensor_readings.insert_one(sensor_reading)
        logger.info(
            f"Stored sensor reading with ML prediction: {prediction} "
            f"(confidence: {confidence:.2f})"
        )
        return sensor_reading
