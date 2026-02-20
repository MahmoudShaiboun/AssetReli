import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MLClient:
    """HTTP client for the ML prediction service. Uses a singleton AsyncClient."""

    def __init__(self, base_url: str, api_key: str = ""):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=5.0)
        self._api_key = api_key

    async def predict(
        self,
        features: List[float],
        top_k: int = 3,
        tenant_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        model_version_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Call ML service /predict endpoint with optional tenant context."""
        try:
            headers = {}
            if self._api_key:
                headers["X-API-Key"] = self._api_key

            body: Dict = {"features": features, "top_k": top_k}
            if tenant_id:
                body["tenant_id"] = tenant_id
            if asset_id:
                body["asset_id"] = asset_id
            if model_version_id:
                body["model_version_id"] = model_version_id

            response = await self._client.post(
                "/predict",
                json=body,
                headers=headers,
            )
            if response.status_code == 200:
                return response.json()

            logger.warning(f"ML prediction failed: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return None

    async def close(self) -> None:
        await self._client.aclose()
