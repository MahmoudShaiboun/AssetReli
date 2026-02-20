"""Read-only asyncpg connection pool for mqtt-ingestion.

Lightweight — no ORM, just raw SQL for registry/binding lookups.
"""

import asyncio
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None

MAX_RETRIES = 10
RETRY_DELAY = 3  # seconds


async def init_pg_pool(dsn: str) -> asyncpg.Pool:
    """Create and return a read-only asyncpg connection pool with retry."""
    global _pool
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=5,
                command_timeout=10,
            )
            logger.info("PostgreSQL read pool initialized")
            return _pool
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
            if attempt == MAX_RETRIES:
                logger.error(f"Failed to connect to PostgreSQL after {MAX_RETRIES} attempts")
                raise
            logger.warning(
                f"PostgreSQL connection attempt {attempt}/{MAX_RETRIES} failed: {exc}. "
                f"Retrying in {RETRY_DELAY}s..."
            )
            await asyncio.sleep(RETRY_DELAY)


async def close_pg_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL read pool closed")


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool
