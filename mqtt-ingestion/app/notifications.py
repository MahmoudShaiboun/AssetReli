import os
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
import httpx
from twilio.rest import Client

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via email, SMS, webhook, and Slack"""
    
    def __init__(self):
        # Email configuration from environment variables
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        
        # Twilio configuration
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from_phone = os.getenv("TWILIO_FROM_PHONE", "")
        
        # Initialize Twilio client if credentials available
        self.twilio_client = None
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
                logger.info("✅ Twilio client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        
        # HTTP client for webhooks
        self.http_client = httpx.AsyncClient(timeout=10.0)
    
    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email notification via SMTP"""
        if not self.smtp_username or not self.smtp_password:
            logger.warning("⚠️ SMTP credentials not configured, email not sent")
            logger.info(f"📧 Would send email to: {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body: {body[:100]}...")
            return False
        
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.smtp_from_email
            message["To"] = to_email
            message["Subject"] = subject
            
            # Create HTML and plain text versions
            text_part = MIMEText(body, "plain")
            body_html = body.replace('\n', '<br>')
            html_body = f"""
            <html>
              <body>
                <h2 style="color: #d32f2f;">🚨 Aastreli Fault Alert</h2>
                <div style="font-family: Arial, sans-serif;">
                  {body_html}
                </div>
              </body>
            </html>
            """
            html_part = MIMEText(html_body, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                start_tls=True,
            )
            
            logger.info(f"✅ Email sent successfully to: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False
    
    async def send_sms(self, to_phone: str, message: str) -> bool:
        """Send SMS notification via Twilio"""
        if not self.twilio_client:
            logger.warning("⚠️ Twilio not configured, SMS not sent")
            logger.info(f"📱 Would send SMS to: {to_phone}")
            logger.info(f"Message: {message}")
            return False
        
        try:
            # Twilio uses synchronous API, but we can still call it
            sms = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_from_phone,
                to=to_phone
            )
            logger.info(f"✅ SMS sent successfully to: {to_phone} (SID: {sms.sid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send SMS to {to_phone}: {e}")
            return False
    
    async def send_webhook(self, url: str, data: Dict) -> bool:
        """Send webhook notification via HTTP POST"""
        try:
            response = await self.http_client.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            logger.info(f"✅ Webhook sent successfully to: {url} (status: {response.status_code})")
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to send webhook to {url}: {e}")
            return False
    
    async def send_slack(self, webhook_url: str, message: str, fault_data: Dict) -> bool:
        """Send notification to Slack via webhook"""
        try:
            # Slack webhook payload format
            payload = {
                "text": f"🚨 *Fault Alert*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 Aastreli Fault Detected"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Fault Type:*\n{fault_data.get('fault_type', 'Unknown')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Confidence:*\n{fault_data.get('confidence', 0)*100:.1f}%"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Sensor ID:*\n{fault_data.get('sensor_id', 'Unknown')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Timestamp:*\n{fault_data.get('timestamp', 'Unknown')}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    }
                ]
            }
            
            response = await self.http_client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            logger.info(f"✅ Slack notification sent successfully")
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to send Slack notification: {e}")
            return False
    
    async def send_fault_notification(self, action: Dict, fault_data: Dict) -> bool:
        """
        Send notification based on action configuration
        
        Args:
            action: Dict with keys: type, enabled, config
            fault_data: Dict with fault information
        """
        if not action.get("enabled", False):
            logger.debug(f"Action {action.get('type')} is disabled, skipping")
            return False
        
        action_type = action.get("type")
        config = action.get("config", {})
        
        # Format message
        message = f"""
🚨 FAULT DETECTED

Fault Type: {fault_data.get('fault_type', 'Unknown')}
Confidence: {fault_data.get('confidence', 0)*100:.1f}%
Sensor ID: {fault_data.get('sensor_id', 'Unknown')}
Timestamp: {fault_data.get('timestamp', 'Unknown')}

Motor Temperature: {fault_data.get('motor_temp', 'N/A')}°C
Pump Temperature: {fault_data.get('pump_temp', 'N/A')}°C

Please investigate immediately.

---
Aastreli Industrial Anomaly Detection System
"""
        
        try:
            if action_type == "email":
                email = config.get("email")
                if email:
                    subject = f"🚨 Fault Alert: {fault_data.get('fault_type', 'Unknown')}"
                    return await self.send_email(email, subject, message)
            
            elif action_type == "sms":
                phone = config.get("phone")
                if phone:
                    # SMS message should be shorter
                    sms_message = f"🚨 Fault: {fault_data.get('fault_type')} ({fault_data.get('confidence')*100:.0f}% conf) on {fault_data.get('sensor_id')}. Check Aastreli dashboard."
                    return await self.send_sms(phone, sms_message)
            
            elif action_type == "webhook":
                url = config.get("url")
                if url:
                    # Send full fault data as JSON
                    webhook_payload = {
                        "alert_type": "fault_detected",
                        "fault_data": fault_data,
                        "message": message
                    }
                    return await self.send_webhook(url, webhook_payload)
            
            elif action_type == "slack":
                channel = config.get("channel")
                # For Slack, channel is actually the webhook URL
                if channel:
                    return await self.send_slack(channel, message, fault_data)
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending {action_type} notification: {e}")
            return False
        
        return False
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
