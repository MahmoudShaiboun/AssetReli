"""
NotificationDispatcher — fires actual network calls for each queued notification.

Runs as asyncio.create_task() from router.py so it never blocks the HTTP response.
Updates notification_log rows from "queued" → "sent" | "failed" in its own session.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationType, NotificationLog, AlarmEvent
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


async def dispatch_notifications(
    tenant_id: UUID,
    asset_id: Optional[UUID],
    event: AlarmEvent,
    notification_types: list[NotificationType],
    rule_name: str,
    prediction_label: str,
    probability: float,
) -> None:
    """Dispatch all notification channels for one alarm event."""
    async with async_session_factory() as session:
        try:
            for nt in notification_types:
                data = nt.notify_type_data or {}
                channel = _channel_name(nt)
                success, error = await _dispatch_one(
                    channel=channel,
                    data=data,
                    event=event,
                    rule_name=rule_name,
                    prediction_label=prediction_label,
                    probability=probability,
                )
                await session.execute(
                    update(NotificationLog)
                    .where(
                        NotificationLog.alarm_event_id == event.id,
                        NotificationLog.notification_type_id == nt.id,
                        NotificationLog.status == "queued",
                    )
                    .values(
                        status="sent" if success else "failed",
                        sent_at=datetime.now(timezone.utc) if success else None,
                        error_message=error,
                    )
                )
            await session.commit()
        except Exception as exc:
            logger.error(
                f"dispatch_notifications failed for event {event.id}: {exc}",
                exc_info=True,
            )
            await session.rollback()


async def _dispatch_one(
    channel: str,
    data: dict,
    event: AlarmEvent,
    rule_name: str,
    prediction_label: str,
    probability: float,
) -> tuple[bool, Optional[str]]:
    try:
        if channel == "email":
            return await _send_email(data, event, rule_name, prediction_label, probability)
        elif channel == "sms":
            return await _send_sms(data, event, prediction_label, probability)
        elif channel in ("webhook", "slack"):
            return await _send_webhook(data, event, rule_name, prediction_label, probability)
        else:
            logger.warning(f"Unknown notification channel '{channel}' — skipping")
            return False, f"Unknown channel: {channel}"
    except Exception as exc:
        return False, str(exc)


async def _send_email(
    data: dict,
    event: AlarmEvent,
    rule_name: str,
    prediction_label: str,
    probability: float,
) -> tuple[bool, Optional[str]]:
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
    except ImportError:
        return False, "aiosmtplib not installed"

    to_email = data.get("email")
    if not to_email:
        return False, "No email address configured"

    smtp_host = data.get("smtp_host") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(data.get("smtp_port") or os.getenv("SMTP_PORT", "587"))
    smtp_user = data.get("smtp_username") or os.getenv("SMTP_USERNAME", "")
    smtp_pass = data.get("smtp_password") or os.getenv("SMTP_PASSWORD", "")
    from_email = data.get("from_email") or smtp_user

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not configured — skipping email")
        return False, "SMTP credentials not configured"

    body = (
        f"Alarm Rule: {rule_name}\n"
        f"Fault Detected: {prediction_label}\n"
        f"Probability: {probability * 100:.1f}%\n"
        f"Asset: {event.asset_id}\n"
        f"Triggered at: {event.triggered_at.isoformat()}\n"
    )
    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = f"[Aastreli] Alarm: {prediction_label}"
    msg.attach(MIMEText(body, "plain"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            start_tls=True,
        )
        logger.info(f"Email sent to {to_email} for event {event.id}")
        return True, None
    except Exception as exc:
        return False, str(exc)


async def _send_sms(
    data: dict,
    event: AlarmEvent,
    prediction_label: str,
    probability: float,
) -> tuple[bool, Optional[str]]:
    to_phone = data.get("phone")
    account_sid = data.get("twilio_account_sid") or os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = data.get("twilio_auth_token") or os.getenv("TWILIO_AUTH_TOKEN", "")
    from_phone = data.get("from_phone") or os.getenv("TWILIO_FROM_PHONE", "")

    if not all([to_phone, account_sid, auth_token, from_phone]):
        return False, "Twilio credentials or phone number not configured"

    body = (
        f"[Aastreli] {prediction_label} ({probability * 100:.0f}%). "
        f"Asset: {event.asset_id}. Check dashboard."
    )
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(body=body, from_=from_phone, to=to_phone)
        logger.info(f"SMS sent to {to_phone} for event {event.id}")
        return True, None
    except ImportError:
        return False, "twilio not installed"
    except Exception as exc:
        return False, str(exc)


async def _send_webhook(
    data: dict,
    event: AlarmEvent,
    rule_name: str,
    prediction_label: str,
    probability: float,
) -> tuple[bool, Optional[str]]:
    url = data.get("url") or data.get("webhook_url")
    if not url:
        return False, "No webhook URL configured"

    payload = {
        "alert_type": "alarm_event",
        "alarm_event_id": str(event.id),
        "rule_name": rule_name,
        "prediction_label": prediction_label,
        "probability": probability,
        "asset_id": str(event.asset_id) if event.asset_id else None,
        "sensor_id": str(event.sensor_id) if event.sensor_id else None,
        "triggered_at": event.triggered_at.isoformat(),
        "status": event.status,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        logger.info(f"Webhook sent to {url} for event {event.id}")
        return True, None
    except Exception as exc:
        return False, str(exc)


def _channel_name(nt: NotificationType) -> str:
    data = nt.notify_type_data or {}
    if data.get("channel") in ("email", "sms", "webhook", "slack"):
        return data["channel"]
    name = nt.notify_type_name.lower()
    for known in ("email", "sms", "slack", "webhook"):
        if known in name:
            return known
    return "webhook"
