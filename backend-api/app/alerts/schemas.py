from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# ---------- Evaluate endpoint ----------

class AlertEvaluateRequest(BaseModel):
    """Payload sent by mqtt-ingestion when a prediction exceeds the threshold."""
    tenant_id: UUID
    asset_id: Optional[UUID] = None
    sensor_id: Optional[UUID] = None
    prediction_label: str
    probability: float
    model_version_id: Optional[UUID] = None
    prediction_id: Optional[str] = None
    timestamp: datetime


class AlertEvaluateResponse(BaseModel):
    matched_rules: int
    alarm_events_created: int
    notifications_queued: int
    work_orders_created: int


# ---------- Output schemas ----------

class AlarmRuleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    asset_id: Optional[UUID] = None
    sensor_id: Optional[UUID] = None
    rule_name: str
    parameter_name: str
    threshold_value: float
    comparison_operator: str
    severity_level: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AlarmEventOut(BaseModel):
    id: UUID
    tenant_id: UUID
    asset_id: Optional[UUID] = None
    sensor_id: Optional[UUID] = None
    alarm_rule_id: Optional[UUID] = None
    prediction_id: Optional[str] = None
    model_version_id: Optional[UUID] = None
    triggered_value: Optional[float] = None
    triggered_at: datetime
    cleared_at: Optional[datetime] = None
    status: str
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class NotificationLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    alarm_event_id: UUID
    channel: str
    recipient: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class WorkOrderOut(BaseModel):
    id: UUID
    tenant_id: UUID
    asset_id: UUID
    alarm_event_id: Optional[UUID] = None
    work_number: str
    description: Optional[str] = None
    priority_level: str
    status: str
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
