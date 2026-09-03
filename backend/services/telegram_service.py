"""
Telegram notification service

Sends audit notifications through a Telegram bot created via @BotFather
(https://core.telegram.org/bots#botfather). Requires the bot token and
the chat_id of the user or group that should receive the messages.
"""
import logging
from html import escape
from typing import Optional
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

# Colored circles so risk is scannable without reading (mirrors Slack)
RISK_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}


def _blockquote(text: str) -> str:
    """Render text as a Telegram <blockquote>, escaping HTML."""
    lines = [escape(line) for line in text.splitlines() if line.strip()]
    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


class TelegramService:
    """
    Telegram bot notification service

    Sends formatted notifications via the Telegram Bot API for audit and
    approval tracking — a drop-in alternative (or complement) to Slack.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram service

        Args:
            bot_token: Bot API token from @BotFather (optional)
            chat_id: Chat ID that receives the messages (optional)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        if self.enabled:
            logger.info("Telegram service initialized (chat_id=%s)", chat_id)
        else:
            logger.info("Telegram bot not configured, notifications will be skipped")

    @property
    def enabled(self) -> bool:
        """Both the bot token and the chat ID are required to send."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str) -> bool:
        """
        Send an HTML-formatted message via the Bot API

        Args:
            text: Message text (Telegram HTML markup)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram bot not configured, skipping notification")
            return False

        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def format_credential_message(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None
    ) -> str:
        """
        Format credential issuance message for Telegram

        Args:
            request_text: The user's access request
            risk_level: Risk assessment level
            duration_hours: Duration of credentials
            auto_approved: Whether auto-approved
            approver: Approver name (if manual approval)

        Returns:
            Formatted Telegram HTML message
        """
        approval = (
            "✅ Auto-approved"
            if auto_approved
            else f"✍️ Manual — {escape(approver or 'unknown')}"
        )
        risk = RISK_EMOJI.get(risk_level.lower(), "🟡")

        return (
            "🔓 <b>AWS Temporary Credentials Issued</b>\n\n"
            f"<b>Approval:</b> {approval}\n"
            f"<b>Risk Score:</b> {risk} {escape(risk_level.upper())}\n"
            f"<b>Duration:</b> {duration_hours} hour(s)\n\n"
            f"{_blockquote(request_text)}"
        )

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
        message = self.format_credential_message(
            request_text=request_text,
            risk_level=risk_level,
            duration_hours=duration_hours,
            auto_approved=auto_approved,
            approver=approver
        )
        return self.send_message(message)

    def format_error_message(
        self,
        error_type: str,
        request_text: str,
        error_details: str
    ) -> str:
        """
        Format error message for Telegram

        Args:
            error_type: Type of error (e.g., "Policy Generation", "Credential Issuance")
            request_text: The user's access request
            error_details: Error details

        Returns:
            Formatted Telegram HTML message
        """
        return (
            f"⚠️ <b>Error — {escape(error_type)}</b>\n\n"
            f"{_blockquote(request_text)}\n\n"
            f"<pre>{escape(error_details)}</pre>"
        )

    def send_error_notification(
        self,
        error_type: str,
        request_text: str,
        error_details: str
    ) -> bool:
        """
        Send error notification to Telegram

        Args:
            error_type: Type of error
            request_text: The user's access request
            error_details: Error details

        Returns:
            True if successful, False otherwise
        """
        message = self.format_error_message(
            error_type=error_type,
            request_text=request_text,
            error_details=error_details
        )
        return self.send_message(message)
