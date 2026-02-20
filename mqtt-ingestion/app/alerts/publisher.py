"""
AlertPublisher — sends fault prediction events to backend-api /alerts/evaluate.

Uses tenacity for retry with exponential backoff.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

if TYPE_CHECKING:
    from app.ingestion.context import MessageContext

logger = logging.getLogger(__name__)


class AlertPublisher:
    """Publishes fault alert events to backend-api /alerts/evaluate."""

    def __init__(self, backend_api_url: str, api_key: str = ""):
        self.backend_api_url = backend_api_url.rstrip("/")
        self._api_key = api_key

    async def publish(
        self,
        prediction: str,
        confidence: float,
        sensor_data: dict,
        ctx: Optional["MessageContext"] = None,
        prediction_id: Optional[str] = None,
    ) -> None:
        """Post a fault event to backend-api for rule-based evaluation.

        Silently returns if context is not resolved (no tenant_id).
        Retries up to 3 times on transport/timeout errors.
        """
        if ctx is None or not ctx.is_resolved:
            logger.warning(
                "AlertPublisher.publish: skipping — context not resolved "
                f"(prediction={prediction})"
            )
            return

        payload = {
            "tenant_id": ctx.tenant_id_str,
            "prediction_label": prediction,
            "probability": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if ctx.asset_id:
            payload["asset_id"] = ctx.asset_id_str
        if ctx.sensor_id:
            payload["sensor_id"] = ctx.sensor_id_str
        if ctx.model_version_id:
            payload["model_version_id"] = ctx.model_version_id_str
        if prediction_id:
            payload["prediction_id"] = prediction_id

        headers = {"X-API-Key": self._api_key} if self._api_key else {}

        try:
            await self._post_with_retry(payload, headers)
        except Exception as exc:
            logger.error(
                f"AlertPublisher: failed to post to /alerts/evaluate after retries: {exc}"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _post_with_retry(self, payload: dict, headers: dict) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self.backend_api_url}/alerts/evaluate",
                json=payload,
                headers=headers,
            )
            if response.status_code not in (200, 201, 202):
                logger.warning(
                    f"AlertPublisher: /alerts/evaluate returned "
                    f"{response.status_code}: {response.text[:200]}"
                )
            else:
                logger.info(
                    f"AlertPublisher: alert posted successfully "
                    f"(status={response.status_code})"
                )
