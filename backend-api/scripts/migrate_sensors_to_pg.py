"""
One-time migration: Copy MongoDB sensors → PostgreSQL sensors table.

Sensors in MongoDB have a flat structure (sensor_id, name, type, location).
In PostgreSQL, sensors belong to an asset hierarchy (tenant → site → asset → sensor).
This script assigns all sensors to the default tenant/site/asset created by seed data.

Usage:
    cd backend-api
    python -m scripts.migrate_sensors_to_pg

Requires both MongoDB and PostgreSQL to be running.
"""

import asyncio
import logging
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB = "aastreli"
POSTGRES_URL = "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5432/aastreli"

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ASSET_ID = uuid.UUID("00000000-0000-0000-0000-000000000007")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def migrate():
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client[MONGODB_DB]

    engine = create_async_engine(POSTGRES_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    migrated = 0
    skipped = 0

    async with session_factory() as session:
        # Verify default asset exists
        result = await session.execute(
            text("SELECT id FROM assets WHERE id = :aid"),
            {"aid": str(DEFAULT_ASSET_ID)},
        )
        if not result.scalar_one_or_none():
            logger.error(
                "Default asset not found. Run 'alembic upgrade head' first."
            )
            return

        async for sensor_doc in mongo_db.sensors.find():
            sensor_id_str = sensor_doc.get("sensor_id")
            if not sensor_id_str:
                logger.warning(f"Skipping sensor without sensor_id: {sensor_doc.get('_id')}")
                skipped += 1
                continue

            # Use sensor_id as sensor_code
            sensor_code = sensor_id_str

            # Check if already exists
            result = await session.execute(
                text(
                    "SELECT id FROM sensors WHERE tenant_id = :tid AND sensor_code = :code"
                ),
                {"tid": str(DEFAULT_TENANT_ID), "code": sensor_code},
            )
            if result.scalar_one_or_none():
                logger.info(f"Sensor {sensor_code} already in PG, skipping")
                skipped += 1
                continue

            sensor_type = sensor_doc.get("type", "vibration")
            mqtt_topic = sensor_doc.get("mqtt_topic", f"sensors/{sensor_code}")

            await session.execute(
                text(
                    """
                    INSERT INTO sensors (
                        id, tenant_id, asset_id, sensor_code, sensor_type,
                        mqtt_topic, position_x, position_y,
                        is_active, is_deleted, created_by
                    ) VALUES (
                        :id, :tenant_id, :asset_id, :code, :type,
                        :mqtt_topic, 50, 50,
                        true, false, :user_id
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(DEFAULT_TENANT_ID),
                    "asset_id": str(DEFAULT_ASSET_ID),
                    "code": sensor_code,
                    "type": sensor_type,
                    "mqtt_topic": mqtt_topic,
                    "user_id": str(DEFAULT_USER_ID),
                },
            )
            migrated += 1
            logger.info(f"Migrated sensor: {sensor_code}")

        await session.commit()

    await engine.dispose()
    mongo_client.close()

    logger.info(f"Migration complete: {migrated} sensors migrated, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(migrate())
