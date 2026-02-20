import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserOut
from app.common.dependencies import (
    get_current_user_with_tenant,
    verify_api_key,
)
from app.db.postgres import get_pg_session
from app.alerts import service
from app.alerts.schemas import (
    AlertEvaluateRequest,
    AlertEvaluateResponse,
    AlarmRuleOut,
    AlarmEventOut,
    NotificationLogOut,
    WorkOrderOut,
)
from app.alerts.notifications import dispatch_notifications

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Internal endpoint (mqtt-ingestion → backend-api) ----------

@router.post(
    "/alerts/evaluate",
    response_model=AlertEvaluateResponse,
    status_code=status.HTTP_200_OK,
)
async def evaluate_alert(
    req: AlertEvaluateRequest,
    session: AsyncSession = Depends(get_pg_session),
    _key: str = Depends(verify_api_key),
):
    """Evaluate a prediction event against tenant alarm rules.

    Called by mqtt-ingestion with X-API-Key header.
    Returns synchronously with counts; notification dispatch runs in background.
    """
    try:
        result = await service.evaluate_alert(session, req)
    except Exception as exc:
        logger.error(f"Alert evaluation error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Alert evaluation failed")

    # Fire-and-forget notification dispatch for each matched event
    for event, notif_types, rule in result.dispatch_items:
        asyncio.create_task(
            dispatch_notifications(
                tenant_id=req.tenant_id,
                asset_id=req.asset_id,
                event=event,
                notification_types=notif_types,
                rule_name=rule.rule_name,
                prediction_label=req.prediction_label,
                probability=req.probability,
            )
        )

    return result.response


# ---------- User-facing endpoints (JWT auth) ----------

@router.get("/alerts/rules", response_model=list[AlarmRuleOut])
async def list_alarm_rules(
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_alarm_rules(session, current_user.effective_tenant_id)


@router.get("/alerts/events", response_model=list[AlarmEventOut])
async def list_alarm_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_alarm_events(
        session, current_user.effective_tenant_id, status_filter,
    )


@router.get("/alerts/notifications", response_model=list[NotificationLogOut])
async def list_notification_logs(
    alarm_event_id: Optional[UUID] = None,
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_notification_logs(
        session, current_user.effective_tenant_id, alarm_event_id,
    )


@router.get("/alerts/work-orders", response_model=list[WorkOrderOut])
async def list_work_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserOut = Depends(get_current_user_with_tenant),
    session: AsyncSession = Depends(get_pg_session),
):
    return await service.list_work_orders(
        session, current_user.effective_tenant_id, status_filter,
    )
