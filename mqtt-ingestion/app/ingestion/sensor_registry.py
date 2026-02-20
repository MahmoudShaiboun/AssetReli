"""SensorRegistryCache — maps sensor_code → tenant/site/asset context.

Refreshed periodically from PostgreSQL so mqtt-ingestion can resolve
MQTT topic sensor codes into full multi-tenant context without
per-message DB lookups.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

REFRESH_SQL = """
SELECT
    s.sensor_code,
    s.id        AS sensor_id,
    s.tenant_id,
    t.tenant_code,
    a.site_id,
    si.site_code,
    s.asset_id,
    s.gateway_id
FROM sensors s
JOIN tenants t  ON t.id = s.tenant_id
JOIN assets  a  ON a.id = s.asset_id
JOIN sites   si ON si.id = a.site_id
WHERE s.is_active  = true
  AND s.is_deleted = false
  AND a.is_active  = true
  AND a.is_deleted = false
  AND t.is_active  = true
  AND t.is_deleted = false
"""


@dataclass(frozen=True)
class SensorBinding:
    sensor_id: UUID
    tenant_id: UUID
    tenant_code: str
    site_id: UUID
    site_code: str
    asset_id: UUID
    gateway_id: Optional[UUID]


class SensorRegistryCache:
    """In-memory lookup from sensor_code to SensorBinding, refreshed from PG."""

    def __init__(self, refresh_interval_sec: int = 60):
        self._cache: Dict[str, SensorBinding] = {}
        self._refresh_interval = refresh_interval_sec
        self._refresh_task: Optional[asyncio.Task] = None

    def lookup(self, sensor_code: str) -> Optional[SensorBinding]:
        return self._cache.get(sensor_code)

    async def refresh(self, pool: asyncpg.Pool) -> None:
        """Reload the full sensor→context mapping from PG."""
        try:
            rows = await pool.fetch(REFRESH_SQL)
            new_cache: Dict[str, SensorBinding] = {}
            for row in rows:
                binding = SensorBinding(
                    sensor_id=row["sensor_id"],
                    tenant_id=row["tenant_id"],
                    tenant_code=row["tenant_code"],
                    site_id=row["site_id"],
                    site_code=row["site_code"],
                    asset_id=row["asset_id"],
                    gateway_id=row["gateway_id"],
                )
                new_cache[row["sensor_code"]] = binding
            self._cache = new_cache
            logger.debug(f"SensorRegistryCache refreshed: {len(new_cache)} sensors")
        except Exception:
            logger.exception("Failed to refresh SensorRegistryCache")

    def start_refresh_loop(self, pool: asyncpg.Pool) -> None:
        """Start a background task that refreshes the cache periodically."""
        async def _loop():
            while True:
                await self.refresh(pool)
                await asyncio.sleep(self._refresh_interval)

        self._refresh_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    @property
    def size(self) -> int:
        return len(self._cache)
