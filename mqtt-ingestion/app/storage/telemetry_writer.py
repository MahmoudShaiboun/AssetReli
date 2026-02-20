import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.ingestion.context import MessageContext

logger = logging.getLogger(__name__)


class TelemetryWriter:
    """Writes raw MQTT payloads to the sensor_data MongoDB collection."""

    def __init__(self, db):
        self.db = db

    async def write(
        self,
        topic: str,
        data: dict,
        timestamp: datetime,
        ctx: Optional["MessageContext"] = None,
    ) -> None:
        document = {"topic": topic, "data": data, "timestamp": timestamp}

        # Add tenant context if available
        if ctx and ctx.is_resolved:
            document["tenant_id"] = ctx.tenant_id_str
            document["site_id"] = ctx.site_id_str
            document["asset_id"] = ctx.asset_id_str
            document["sensor_id"] = ctx.sensor_id_str

        await self.db.sensor_data.insert_one(document)
        logger.debug(f"Stored raw data for topic: {topic}")
