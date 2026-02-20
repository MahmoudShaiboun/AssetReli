"""
Alert evaluation service — pure async functions, no FastAPI imports.

Called by router.py with an injected AsyncSession.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AlarmRule,
    AlarmNotificationType,
    AlarmEvent,
    NotificationLog,
    MaintenanceWorkOrder,
    NotificationType,
)
from app.alerts.schemas import (
    AlertEvaluateRequest,
    AlertEvaluateResponse,
    AlarmRuleOut,
    AlarmEventOut,
    NotificationLogOut,
    WorkOrderOut,
)

logger = logging.getLogger(__name__)

_OPERATORS = {
    ">":  lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
    "<":  lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    "==": lambda v, t: abs(v - t) < 1e-9,
}


# ---- Rule matching ----

async def fetch_matching_rules(
    session: AsyncSession,
    tenant_id: UUID,
    asset_id: Optional[UUID],
    sensor_id: Optional[UUID],
) -> list[AlarmRule]:
    """Return active, non-deleted AlarmRules for the given tenant that match scope."""
    result = await session.execute(
        select(AlarmRule).where(
            AlarmRule.tenant_id == tenant_id,
            AlarmRule.is_active == True,
            AlarmRule.is_deleted == False,
        )
    )
    rules = result.scalars().all()

    matched = []
    for rule in rules:
        # Tenant-wide rule
        if rule.asset_id is None and rule.sensor_id is None:
            matched.append(rule)
        # Asset-scoped rule
        elif rule.asset_id is not None and rule.asset_id == asset_id and rule.sensor_id is None:
            matched.append(rule)
        # Sensor-scoped rule
        elif rule.sensor_id is not None and rule.sensor_id == sensor_id:
            matched.append(rule)
    return matched


def evaluate_rule(rule: AlarmRule, triggered_value: float) -> bool:
    """Return True if triggered_value satisfies the rule's threshold comparison."""
    if rule.parameter_name != "probability":
        return False
    op_fn = _OPERATORS.get(rule.comparison_operator)
    if op_fn is None:
        logger.warning(f"AlarmRule {rule.id}: unknown operator '{rule.comparison_operator}'")
        return False
    return op_fn(triggered_value, rule.threshold_value)


# ---- Event / log creation ----

async def create_alarm_event(
    session: AsyncSession,
    req: AlertEvaluateRequest,
    rule: AlarmRule,
) -> AlarmEvent:
    event = AlarmEvent(
        tenant_id=req.tenant_id,
        asset_id=req.asset_id,
        sensor_id=req.sensor_id,
        alarm_rule_id=rule.id,
        prediction_id=req.prediction_id,
        model_version_id=req.model_version_id,
        triggered_value=req.probability,
        triggered_at=req.timestamp,
        status="open",
    )
    session.add(event)
    await session.flush()
    return event


async def fetch_notification_types_for_rule(
    session: AsyncSession,
    rule_id: UUID,
    tenant_id: UUID,
) -> list[NotificationType]:
    """Join AlarmNotificationType → NotificationType for a given rule."""
    result = await session.execute(
        select(NotificationType)
        .join(
            AlarmNotificationType,
            AlarmNotificationType.notification_type_id == NotificationType.id,
        )
        .where(
            AlarmNotificationType.alarm_rule_id == rule_id,
            AlarmNotificationType.tenant_id == tenant_id,
            NotificationType.is_active == True,
        )
    )
    return list(result.scalars().all())


async def write_notification_log(
    session: AsyncSession,
    tenant_id: UUID,
    asset_id: Optional[UUID],
    alarm_event_id: UUID,
    notification_type_id: Optional[UUID],
    channel: str,
    recipient: Optional[str],
    log_status: str,
    error_message: Optional[str] = None,
) -> NotificationLog:
    log = NotificationLog(
        tenant_id=tenant_id,
        asset_id=asset_id,
        alarm_event_id=alarm_event_id,
        notification_type_id=notification_type_id,
        channel=channel,
        recipient=recipient,
        status=log_status,
        sent_at=datetime.now(timezone.utc) if log_status == "sent" else None,
        error_message=error_message,
    )
    session.add(log)
    await session.flush()
    return log


async def create_work_order(
    session: AsyncSession,
    tenant_id: UUID,
    asset_id: UUID,
    alarm_event_id: UUID,
    rule: AlarmRule,
    probability: float,
) -> MaintenanceWorkOrder:
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    work_number = f"WO-{ts_ms}-{str(alarm_event_id)[:8].upper()}"

    wo = MaintenanceWorkOrder(
        tenant_id=tenant_id,
        asset_id=asset_id,
        alarm_event_id=alarm_event_id,
        work_number=work_number,
        description=(
            f"Auto-generated from alarm rule '{rule.rule_name}'. "
            f"Triggered at probability {probability:.2%}."
        ),
        priority_level="critical",
        status="open",
    )
    session.add(wo)
    await session.flush()
    return wo


# ---- Helpers ----

def _channel_from_type(nt: NotificationType) -> str:
    data = nt.notify_type_data or {}
    if data.get("channel") in ("email", "sms", "webhook", "slack"):
        return data["channel"]
    name = nt.notify_type_name.lower()
    for known in ("email", "sms", "slack", "webhook"):
        if known in name:
            return known
    return "webhook"


def _recipient_from_type(nt: NotificationType) -> Optional[str]:
    data = nt.notify_type_data or {}
    return (
        data.get("email")
        or data.get("phone")
        or data.get("url")
        or data.get("webhook_url")
        or data.get("channel")
    )


# ---- Top-level orchestration ----

class EvaluateResult:
    """Bundles the response with dispatch metadata for the router."""
    def __init__(self, response: AlertEvaluateResponse, dispatch_items: list):
        self.response = response
        self.dispatch_items = dispatch_items


async def evaluate_alert(
    session: AsyncSession,
    req: AlertEvaluateRequest,
) -> EvaluateResult:
    """
    Orchestrate rule evaluation for one prediction event.

    Returns an EvaluateResult with the response and dispatch_items for
    the router to fire as background tasks.
    """
    rules = await fetch_matching_rules(session, req.tenant_id, req.asset_id, req.sensor_id)

    events_created = 0
    notifications_queued = 0
    work_orders_created = 0
    matched_rules = 0
    dispatch_items: list[tuple[AlarmEvent, list[NotificationType], AlarmRule]] = []

    for rule in rules:
        if not evaluate_rule(rule, req.probability):
            continue
        matched_rules += 1

        event = await create_alarm_event(session, req, rule)
        events_created += 1

        notif_types = await fetch_notification_types_for_rule(session, rule.id, req.tenant_id)

        for nt in notif_types:
            await write_notification_log(
                session=session,
                tenant_id=req.tenant_id,
                asset_id=req.asset_id,
                alarm_event_id=event.id,
                notification_type_id=nt.id,
                channel=_channel_from_type(nt),
                recipient=_recipient_from_type(nt),
                log_status="queued",
            )
            notifications_queued += 1

        dispatch_items.append((event, notif_types, rule))

        if rule.severity_level == "critical" and req.asset_id is not None:
            await create_work_order(
                session, req.tenant_id, req.asset_id, event.id, rule, req.probability,
            )
            work_orders_created += 1

    resp = AlertEvaluateResponse(
        matched_rules=matched_rules,
        alarm_events_created=events_created,
        notifications_queued=notifications_queued,
        work_orders_created=work_orders_created,
    )
    return EvaluateResult(response=resp, dispatch_items=dispatch_items)


# ---- CRUD helpers for router ----

async def list_alarm_rules(session: AsyncSession, tenant_id: UUID) -> list[AlarmRuleOut]:
    result = await session.execute(
        select(AlarmRule).where(
            AlarmRule.tenant_id == tenant_id,
            AlarmRule.is_deleted == False,
        ).order_by(AlarmRule.created_at.desc())
    )
    return [AlarmRuleOut.model_validate(r) for r in result.scalars().all()]


async def list_alarm_events(
    session: AsyncSession, tenant_id: UUID, status_filter: Optional[str] = None,
) -> list[AlarmEventOut]:
    stmt = select(AlarmEvent).where(
        AlarmEvent.tenant_id == tenant_id,
        AlarmEvent.is_deleted == False,
    )
    if status_filter:
        stmt = stmt.where(AlarmEvent.status == status_filter)
    stmt = stmt.order_by(AlarmEvent.triggered_at.desc())
    result = await session.execute(stmt)
    return [AlarmEventOut.model_validate(r) for r in result.scalars().all()]


async def list_notification_logs(
    session: AsyncSession, tenant_id: UUID, alarm_event_id: Optional[UUID] = None,
) -> list[NotificationLogOut]:
    stmt = select(NotificationLog).where(NotificationLog.tenant_id == tenant_id)
    if alarm_event_id:
        stmt = stmt.where(NotificationLog.alarm_event_id == alarm_event_id)
    stmt = stmt.order_by(NotificationLog.created_at.desc())
    result = await session.execute(stmt)
    return [NotificationLogOut.model_validate(r) for r in result.scalars().all()]


async def list_work_orders(
    session: AsyncSession, tenant_id: UUID, status_filter: Optional[str] = None,
) -> list[WorkOrderOut]:
    stmt = select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.tenant_id == tenant_id,
        MaintenanceWorkOrder.is_deleted == False,
    )
    if status_filter:
        stmt = stmt.where(MaintenanceWorkOrder.status == status_filter)
    stmt = stmt.order_by(MaintenanceWorkOrder.created_at.desc())
    result = await session.execute(stmt)
    return [WorkOrderOut.model_validate(r) for r in result.scalars().all()]
