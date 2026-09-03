"""
Slack notification service

Sends audit notifications via Slack Incoming Webhooks using Block Kit
(https://api.slack.com/block-kit) — the current best practice for
formatted Slack messages — with a plain-text fallback for clients and
notification previews that don't render blocks.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Colored status circles so risk is scannable without reading
RISK_EMOJI = {
    "low": ":large_green_circle:",
    "medium": ":large_yellow_circle:",
    "high": ":large_orange_circle:",
    "critical": ":red_circle:",
}


def _escape_mrkdwn(text: str) -> str:
    """
    Neutralize user-controlled text inside mrkdwn.

    Slack has no mrkdwn escape syntax; per Slack's own formatting guidance
    (https://api.slack.com/reference/surfaces/formatting#escaping), replacing
    &, <, and > with their HTML entities prevents link, mention, and
    broadcast-command injection (e.g. <http://phish|Click here> or <!channel>).
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SlackService:
    """
    Slack webhook notification service

    Sends Block Kit formatted notifications to Slack for audit and
    approval tracking.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack service

        Args:
            webhook_url: Slack webhook URL (optional)
        """
        self.webhook_url = webhook_url
        if webhook_url:
            logger.info("Slack service initialized with webhook")
        else:
            logger.info("Slack webhook not configured, notifications will be skipped")

    def send_payload(self, payload: Dict[str, Any]) -> bool:
        """
        Send a raw webhook payload to Slack

        Args:
            payload: JSON body for the webhook (blocks and/or text)

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.debug("Slack webhook not configured, skipping notification")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def send_notification(self, message: str) -> bool:
        """
        Send a plain-text notification to Slack

        Args:
            message: Message text to send

        Returns:
            True if successful, False otherwise
        """
        return self.send_payload({"text": message})

    def format_credential_payload(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a Block Kit payload for a credential issuance notification

        Args:
            request_text: The user's access request
            risk_level: Risk assessment level
            duration_hours: Duration of credentials
            auto_approved: Whether auto-approved
            approver: Approver name (if manual approval)

        Returns:
            Webhook payload with blocks plus a plain-text fallback
        """
        approval = (
            "*Approval*\n:white_check_mark: Auto-approved"
            if auto_approved
            else f"*Approval*\n:writing_hand: Manual — {_escape_mrkdwn(approver or 'unknown')}"
        )
        risk = RISK_EMOJI.get(risk_level.lower(), ":large_yellow_circle:")
        # mrkdwn blockquotes (one ">" per line) render multi-line requests well;
        # escape user content before adding our own ">" prefixes
        quoted_request = "\n".join(
            f"> {line}"
            for line in _escape_mrkdwn(request_text).splitlines()
            if line.strip()
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        return {
            # Plain-text fallback for previews / non-Block Kit clients
            "text": f"AWS Temporary Credentials issued ({risk_level.upper()} risk, {duration_hours}h)",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔓 AWS Temporary Credentials Issued",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": approval},
                        {
                            "type": "mrkdwn",
                            "text": f"*Risk Score*\n{risk} {risk_level.upper()}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Duration*\n{duration_hours} hour(s)",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Request*\n{quoted_request}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"IAM-Dynamic • {timestamp}"},
                    ],
                },
            ],
        }

    def send_credential_notification(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None
    ) -> bool:
        """
        Send formatted credential issuance notification

        Args:
            request_text: The user's access request
            risk_level: Risk assessment level
            duration_hours: Duration of credentials
            auto_approved: Whether auto-approved
            approver: Approver name (if manual approval)

        Returns:
            True if successful, False otherwise
        """
        payload = self.format_credential_payload(
            request_text=request_text,
            risk_level=risk_level,
            duration_hours=duration_hours,
            auto_approved=auto_approved,
            approver=approver
        )
        return self.send_payload(payload)

    def format_error_payload(
        self,
        error_type: str,
        request_text: str,
        error_details: str
    ) -> Dict[str, Any]:
        """
        Build a Block Kit payload for an error notification

        Args:
            error_type: Type of error (e.g., "Policy Generation", "Credential Issuance")
            request_text: The user's access request
            error_details: Error details

        Returns:
            Webhook payload with blocks plus a plain-text fallback
        """
        quoted_request = "\n".join(
            f"> {line}"
            for line in _escape_mrkdwn(request_text).splitlines()
            if line.strip()
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        return {
            "text": f"IAM-Dynamic error: {error_type}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"⚠️ Error — {error_type}",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Request*\n{quoted_request}"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Details*\n```{_escape_mrkdwn(error_details)}```"},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"IAM-Dynamic • {timestamp}"},
                    ],
                },
            ],
        }

    def send_error_notification(
        self,
        error_type: str,
        request_text: str,
        error_details: str
    ) -> bool:
        """
        Send error notification to Slack

        Args:
            error_type: Type of error
            request_text: The user's access request
            error_details: Error details

        Returns:
            True if successful, False otherwise
        """
        payload = self.format_error_payload(
            error_type=error_type,
            request_text=request_text,
            error_details=error_details
        )
        return self.send_payload(payload)
