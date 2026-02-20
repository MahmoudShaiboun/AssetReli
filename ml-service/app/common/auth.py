"""
Internal API key validation for service-to-service calls.

Enforced when INTERNAL_API_KEY is set to a non-empty value other than 'dev_key'.
Callers must include `X-Internal-Key: <key>` header.
"""

from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_internal_key(x_internal_key: str = Header(default="")) -> str:
    """FastAPI dependency: validates X-Internal-Key header for service-to-service auth."""
    key = getattr(settings, "INTERNAL_API_KEY", "") or getattr(settings, "API_KEY", "")
    if key and key != "dev_key":
        if x_internal_key != key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing internal API key",
            )
    return x_internal_key
