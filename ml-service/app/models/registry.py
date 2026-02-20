"""
ModelRegistry — multi-version model registry with LRU cache.

Phase 1 behavior preserved: loads a single "current" model from the filesystem.
Phase 3C: loads additional model versions by UUID from PG artifact paths,
routes predictions to the correct version per tenant/asset, and periodically refreshes
default production deployments from PG.
"""

import asyncio
import logging
import pickle
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import xgboost as xgb

from app.models.manager import ModelManager

logger = logging.getLogger(__name__)

# Module-level singleton — set by main.py during startup
_registry: Optional["ModelRegistry"] = None


def get_registry() -> "ModelRegistry":
    if _registry is None:
        raise RuntimeError("ModelRegistry not initialized. Call init_registry() first.")
    return _registry


def init_registry(model_dir: str, current_model_dir: str) -> "ModelRegistry":
    global _registry
    _registry = ModelRegistry(model_dir=model_dir, current_model_dir=current_model_dir)
    return _registry


@dataclass
class LoadedModel:
    """A loaded model version with its artifacts."""
    manager: ModelManager
    version_id: Optional[UUID] = None
    version_label: str = "default"


class ModelRegistry:
    def __init__(
        self,
        model_dir: str,
        current_model_dir: str,
        max_loaded_models: int = 10,
    ):
        self._default_manager = ModelManager(
            model_dir=model_dir, current_model_dir=current_model_dir
        )

        # LRU cache of loaded model versions (keyed by version_id UUID)
        self._loaded: OrderedDict[UUID, LoadedModel] = OrderedDict()
        self._max_loaded = max_loaded_models

        # Default model version per tenant (populated by refresh_defaults)
        # tenant_id -> model_version_id
        self._tenant_defaults: Dict[UUID, UUID] = {}

        # version_id -> artifact_path (populated by refresh_defaults)
        self._version_paths: Dict[UUID, str] = {}

        self._refresh_task: Optional[asyncio.Task] = None

    # ---- Backward-compatible API ----

    def load(self) -> None:
        """Load the filesystem-based default model."""
        self._default_manager.load_current_model()

    def predict(
        self,
        features: List[float],
        top_k: int = 3,
        model_version_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run prediction using the specified or default model version.

        Resolution order:
        1. Explicit model_version_id (from mqtt-ingestion asset binding)
        2. Tenant default (from PG ml_model_deployments WHERE is_production)
        3. Filesystem default model (fallback)
        """
        resolved_version_id = self._resolve_version_id(model_version_id, tenant_id)

        if resolved_version_id and resolved_version_id in self._loaded:
            # LRU hit — move to end
            self._loaded.move_to_end(resolved_version_id)
            loaded = self._loaded[resolved_version_id]
            result = loaded.manager.predict(features=features, top_k=top_k)
            result["model_version_id"] = str(resolved_version_id)
            result["model_version_label"] = loaded.version_label
            return result

        if resolved_version_id and resolved_version_id in self._version_paths:
            # LRU miss — try to load from artifact path
            loaded = self._load_version(resolved_version_id)
            if loaded:
                result = loaded.manager.predict(features=features, top_k=top_k)
                result["model_version_id"] = str(resolved_version_id)
                result["model_version_label"] = loaded.version_label
                return result

        # Fallback to default filesystem model
        result = self._default_manager.predict(features=features, top_k=top_k)
        result["model_version_id"] = None
        result["model_version_label"] = self._default_manager.get_current_version()
        return result

    def _resolve_version_id(
        self,
        model_version_id: Optional[str],
        tenant_id: Optional[str],
    ) -> Optional[UUID]:
        """Resolve which model version UUID to use."""
        # 1. Explicit version
        if model_version_id:
            try:
                return UUID(model_version_id)
            except (ValueError, TypeError):
                pass

        # 2. Tenant default
        if tenant_id:
            try:
                tid = UUID(tenant_id)
                return self._tenant_defaults.get(tid)
            except (ValueError, TypeError):
                pass

        return None

    def _load_version(self, version_id: UUID) -> Optional[LoadedModel]:
        """Load a model version from its artifact path into the LRU cache."""
        artifact_path = self._version_paths.get(version_id)
        if not artifact_path:
            logger.warning(f"No artifact path for version {version_id}")
            return None

        version_dir = Path(artifact_path)
        if not version_dir.is_absolute():
            # Relative paths are under MODEL_DIR
            from app.config import settings
            version_dir = Path(settings.MODEL_DIR) / artifact_path

        model_file = version_dir / "xgboost_anomaly_detector.json"
        if not model_file.exists():
            logger.warning(f"Model file not found at {model_file}")
            return None

        try:
            mgr = ModelManager(
                model_dir=str(version_dir.parent.parent),
                current_model_dir=str(version_dir),
            )
            mgr.load_current_model()

            loaded = LoadedModel(
                manager=mgr,
                version_id=version_id,
                version_label=mgr.get_current_version(),
            )

            # Evict LRU if at capacity
            if len(self._loaded) >= self._max_loaded:
                evicted_id, evicted = self._loaded.popitem(last=False)
                logger.info(f"Evicted model version {evicted_id} from cache")

            self._loaded[version_id] = loaded
            logger.info(
                f"Loaded model version {version_id} from {version_dir}"
            )
            return loaded
        except Exception:
            logger.exception(f"Failed to load model version {version_id}")
            return None

    def get_current_version(self) -> str:
        return self._default_manager.get_current_version()

    def list_versions(self) -> List[Dict[str, Any]]:
        return self._default_manager.list_versions()

    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        return self._default_manager.get_version_info(version)

    def activate_version(self, version: str) -> bool:
        return self._default_manager.activate_version(version)

    def get_metrics(self) -> Dict[str, Any]:
        return self._default_manager.get_metrics()

    @property
    def manager(self) -> ModelManager:
        """Expose the underlying default manager for retraining pipeline."""
        return self._default_manager

    # ---- Multi-version API (Phase 3C) ----

    async def refresh_defaults(self, pg_session_factory) -> None:
        """Poll PG for current production deployments and update defaults.

        Called periodically (every 60s) to pick up model activation changes.
        """
        try:
            from sqlalchemy import select
            from app.db.models import MLModelDeployment, MLModelVersion

            async with pg_session_factory() as session:
                result = await session.execute(
                    select(MLModelDeployment).where(
                        MLModelDeployment.is_production == True
                    )
                )
                deployments = result.scalars().all()

                new_defaults: Dict[UUID, UUID] = {}
                for dep in deployments:
                    new_defaults[dep.tenant_id] = dep.model_version_id

                self._tenant_defaults = new_defaults

                # Also refresh version artifact paths
                version_ids = set(new_defaults.values())
                if version_ids:
                    vresult = await session.execute(
                        select(MLModelVersion).where(
                            MLModelVersion.id.in_(version_ids)
                        )
                    )
                    for v in vresult.scalars().all():
                        self._version_paths[v.id] = v.model_artifact_path

                logger.debug(
                    f"ModelRegistry defaults refreshed: {len(new_defaults)} tenants"
                )
        except Exception:
            logger.exception("Failed to refresh model defaults")

    def start_refresh_loop(self, pg_session_factory, interval_sec: int = 60) -> None:
        """Start background task to periodically refresh defaults from PG."""
        async def _loop():
            while True:
                await self.refresh_defaults(pg_session_factory)
                await asyncio.sleep(interval_sec)

        self._refresh_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    @property
    def loaded_count(self) -> int:
        return len(self._loaded)
