"""
One-time migration: Copy MongoDB users + user_settings → PostgreSQL.

Usage:
    cd backend-api
    python -m scripts.migrate_users_to_pg

Requires both MongoDB and PostgreSQL to be running.
"""

import asyncio
import logging
import sys
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration — override via environment variables
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB = "aastreli"
POSTGRES_URL = "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5432/aastreli"

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def migrate():
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client[MONGODB_DB]

    # Connect to PostgreSQL
    engine = create_async_engine(POSTGRES_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    migrated_users = 0
    migrated_settings = 0
    skipped = 0

    async with session_factory() as session:
        # Verify default tenant exists
        result = await session.execute(
            text("SELECT id FROM tenants WHERE id = :tid"),
            {"tid": str(DEFAULT_TENANT_ID)},
        )
        if not result.scalar_one_or_none():
            logger.error(
                "Default tenant not found. Run 'alembic upgrade head' first "
                "to create seed data."
            )
            return

        # Migrate users
        async for user_doc in mongo_db.users.find():
            email = user_doc.get("email")
            username = user_doc.get("username")

            if not email or not username:
                logger.warning(f"Skipping user without email/username: {user_doc.get('_id')}")
                skipped += 1
                continue

            # Check if user already exists in PG
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email AND tenant_id = :tid"),
                {"email": email, "tid": str(DEFAULT_TENANT_ID)},
            )
            if result.scalar_one_or_none():
                logger.info(f"User {email} already exists in PG, skipping")
                skipped += 1
                continue

            user_id = uuid.uuid4()
            password_hash = user_doc.get("hashed_password", user_doc.get("password_hash", ""))
            if not password_hash:
                logger.warning(f"User {email} has no password hash, skipping")
                skipped += 1
                continue

            await session.execute(
                text(
                    """
                    INSERT INTO users (id, tenant_id, username, email, full_name, password_hash, role, is_active, is_deleted)
                    VALUES (:id, :tenant_id, :username, :email, :full_name, :password_hash, :role, :is_active, false)
                    """
                ),
                {
                    "id": str(user_id),
                    "tenant_id": str(DEFAULT_TENANT_ID),
                    "username": username,
                    "email": email,
                    "full_name": user_doc.get("full_name"),
                    "password_hash": password_hash,
                    "role": user_doc.get("role", "operator"),
                    "is_active": not user_doc.get("disabled", False),
                },
            )
            migrated_users += 1
            logger.info(f"Migrated user: {email} -> {user_id}")

            # Migrate user_settings for this user
            settings_doc = await mongo_db.user_settings.find_one({"user_email": email})
            if settings_doc:
                await session.execute(
                    text(
                        """
                        INSERT INTO user_settings (id, user_id, auto_refresh, refresh_interval_sec, anomaly_threshold, enable_notifications)
                        VALUES (:id, :user_id, :auto_refresh, :refresh_interval, :threshold, :notifications)
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": str(user_id),
                        "auto_refresh": settings_doc.get("autoRefresh", True),
                        "refresh_interval": settings_doc.get("refreshInterval", 5),
                        "threshold": settings_doc.get("anomalyThreshold", 0.7),
                        "notifications": settings_doc.get("enableNotifications", True),
                    },
                )
                migrated_settings += 1

                # Migrate fault_actions
                for action in settings_doc.get("faultActions", []):
                    await session.execute(
                        text(
                            """
                            INSERT INTO fault_actions (id, user_id, type, enabled, config)
                            VALUES (:id, :user_id, :type, :enabled, :config::jsonb)
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": str(user_id),
                            "type": action.get("type", "email"),
                            "enabled": action.get("enabled", False),
                            "config": str(action.get("config", {})).replace("'", '"'),
                        },
                    )

        await session.commit()

    await engine.dispose()
    mongo_client.close()

    logger.info(
        f"Migration complete: {migrated_users} users, "
        f"{migrated_settings} settings, {skipped} skipped"
    )


if __name__ == "__main__":
    asyncio.run(migrate())
