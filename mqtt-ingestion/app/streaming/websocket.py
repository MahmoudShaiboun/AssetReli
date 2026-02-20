import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Each entry: (websocket, tenant_id_str or None)
active_websockets: list[tuple[WebSocket, Optional[str]]] = []


def _extract_tenant_from_token(token: str, query_tenant_id: Optional[str] = None) -> Optional[str]:
    """Validate JWT and return tenant_id string, or None on failure.

    For platform-scoped users (super_admin), tenant_id comes from the
    query parameter instead of the JWT.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=["HS256"]
        )
        scope = payload.get("scope", "tenant")
        if scope == "platform":
            # super_admin: must provide tenant_id via query param
            return query_tenant_id or None
        return payload.get("tenant_id")
    except JWTError:
        return None


@router.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket for real-time data streaming.

    Requires a valid JWT as a query parameter: /stream?token=<jwt>
    Data is filtered to the tenant extracted from the token.
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    query_tenant_id = websocket.query_params.get("tenant_id")
    tenant_id = _extract_tenant_from_token(token, query_tenant_id)
    if not tenant_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    entry = (websocket, tenant_id)
    active_websockets.append(entry)

    try:
        while True:
            mqtt_client = websocket.app.state.mqtt_client
            if mqtt_client:
                all_data = mqtt_client.get_latest_data()
                # Filter to tenant's data only
                filtered = {
                    topic: entry_data
                    for topic, entry_data in all_data.items()
                    if _topic_matches_tenant(topic, tenant_id, websocket)
                }
                await websocket.send_json(filtered)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_websockets.remove(entry)
        logger.info("WebSocket client disconnected")
    except Exception:
        if entry in active_websockets:
            active_websockets.remove(entry)


def _topic_matches_tenant(
    topic: str, tenant_id: str, websocket: WebSocket
) -> bool:
    """Check if an MQTT topic belongs to the given tenant.

    Uses the sensor registry cache if available. For legacy topics
    (sensors/...) that can't be resolved, allow them through — the
    Batch 2 backfill ensures MongoDB docs are tenant-tagged, so the
    worst case is the frontend shows an extra reading (not a data leak).
    """
    registry = getattr(websocket.app.state, "sensor_registry", None)
    if not registry:
        return True  # No registry, allow all (backward compat)

    from app.ingestion.topic_parser import parse_topic

    parsed = parse_topic(topic)
    if not parsed:
        return True

    binding = registry.lookup(parsed.sensor_code)
    if not binding:
        return True  # Unknown sensor, allow (backward compat)

    return str(binding.tenant_id) == tenant_id
