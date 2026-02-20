"""Backfill tenant_id on all MongoDB documents and create tenant-scoped indexes.

Reads the default tenant UUID from PostgreSQL, then updates every document
in sensor_data, sensor_readings, predictions, and feedback that lacks a
tenant_id field.  Also creates compound indexes for tenant-scoped queries.

Usage:
    cd backend-api
    python -m scripts.backfill_tenant_id_mongo
"""

import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECTIONS = ["sensor_data", "sensor_readings", "predictions", "feedback", "sensors"]


async def get_default_tenant_id() -> str:
    """Fetch the default tenant UUID string from PostgreSQL."""
    engine = create_async_engine(settings.POSTGRES_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM tenants WHERE tenant_code = 'default' AND is_deleted = false LIMIT 1")
        )
        row = result.first()
        if not row:
            raise RuntimeError("Default tenant not found in PostgreSQL. Run Alembic seed first.")
        tenant_id = str(row[0])

    await engine.dispose()
    return tenant_id


async def backfill_collection(db, collection_name: str, tenant_id: str) -> int:
    """Set tenant_id on all docs in a collection that lack it."""
    result = await db[collection_name].update_many(
        {"tenant_id": {"$exists": False}},
        {"$set": {"tenant_id": tenant_id}},
    )
    return result.modified_count


async def create_indexes(db):
    """Create compound indexes for tenant-scoped queries."""
    index_specs = {
        "sensor_readings": [
            [("tenant_id", 1), ("timestamp", -1)],
            [("tenant_id", 1), ("sensor_id", 1), ("timestamp", -1)],
        ],
        "predictions": [
            [("tenant_id", 1), ("timestamp", -1)],
        ],
        "sensor_data": [
            [("tenant_id", 1), ("timestamp", -1)],
        ],
        "feedback": [
            [("tenant_id", 1), ("created_at", -1)],
        ],
        "sensors": [
            [("tenant_id", 1), ("sensor_id", 1)],
        ],
    }

    for coll_name, indexes in index_specs.items():
        for index in indexes:
            await db[coll_name].create_index(index)
            logger.info(f"  Index created on {coll_name}: {index}")


async def main():
    tenant_id = await get_default_tenant_id()
    logger.info(f"Default tenant ID: {tenant_id}")

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB]

    logger.info("Backfilling tenant_id on MongoDB documents...")
    for coll_name in COLLECTIONS:
        count = await backfill_collection(db, coll_name, tenant_id)
        logger.info(f"  {coll_name}: {count} documents updated")

    logger.info("Creating compound indexes...")
    await create_indexes(db)

    client.close()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
