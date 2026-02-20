"""MessageContext — tenant/site/asset/sensor context resolved for each MQTT message."""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class MessageContext:
    """Full multi-tenant context for a single MQTT message."""
    tenant_id: Optional[UUID] = None
    tenant_code: Optional[str] = None
    site_id: Optional[UUID] = None
    site_code: Optional[str] = None
    asset_id: Optional[UUID] = None
    sensor_id: Optional[UUID] = None
    sensor_code: Optional[str] = None
    model_version_id: Optional[UUID] = None

    @property
    def is_resolved(self) -> bool:
        """True if the context was resolved from the sensor registry."""
        return self.tenant_id is not None and self.sensor_id is not None

    @property
    def window_key(self) -> str:
        """Key for the sliding window manager."""
        if self.is_resolved:
            return f"{self.tenant_id}:{self.asset_id}:{self.sensor_id}"
        return self.sensor_code or "unknown"

    @property
    def tenant_id_str(self) -> Optional[str]:
        return str(self.tenant_id) if self.tenant_id else None

    @property
    def site_id_str(self) -> Optional[str]:
        return str(self.site_id) if self.site_id else None

    @property
    def asset_id_str(self) -> Optional[str]:
        return str(self.asset_id) if self.asset_id else None

    @property
    def sensor_id_str(self) -> Optional[str]:
        return str(self.sensor_id) if self.sensor_id else None

    @property
    def model_version_id_str(self) -> Optional[str]:
        return str(self.model_version_id) if self.model_version_id else None
