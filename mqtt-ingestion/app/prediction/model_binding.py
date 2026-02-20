"""ModelBindingCache — maps asset_id → active model version.

Used by the ingestion pipeline to resolve which ML model version
should serve predictions for each asset's sensor data.
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
    amv.asset_id,
    amv.model_id,
    amv.model_version_id,
    mv.full_version_label,
    mv.model_artifact_path
FROM asset_model_versions amv
JOIN ml_model_versions mv ON mv.id = amv.model_version_id
WHERE amv.is_active = true
"""


@dataclass(frozen=True)
class ModelBinding:
    model_id: UUID
    model_version_id: UUID
    version_label: str
    artifact_path: Optional[str]


class ModelBindingCache:
    """In-memory lookup from asset_id to ModelBinding, refreshed from PG."""

    def __init__(self, refresh_interval_sec: int = 60):
        self._cache: Dict[UUID, ModelBinding] = {}
        self._refresh_interval = refresh_interval_sec
        self._refresh_task: Optional[asyncio.Task] = None

    def lookup(self, asset_id: UUID) -> Optional[ModelBinding]:
        return self._cache.get(asset_id)

    async def refresh(self, pool: asyncpg.Pool) -> None:
        try:
            rows = await pool.fetch(REFRESH_SQL)
            new_cache: Dict[UUID, ModelBinding] = {}
            for row in rows:
                binding = ModelBinding(
                    model_id=row["model_id"],
                    model_version_id=row["model_version_id"],
                    version_label=row["full_version_label"] or "",
                    artifact_path=row["model_artifact_path"],
                )
                new_cache[row["asset_id"]] = binding
            self._cache = new_cache
            logger.debug(f"ModelBindingCache refreshed: {len(new_cache)} bindings")
        except Exception:
            logger.exception("Failed to refresh ModelBindingCache")

    def start_refresh_loop(self, pool: asyncpg.Pool) -> None:
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
