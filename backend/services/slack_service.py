"""
Slack notification service
"""
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class SlackService:
    """
    Slack webhook notification service

    Sends formatted notifications to Slack for audit and approval tracking.
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

    def send_notification(self, message: str) -> bool:
        """
        Send notification to Slack

        Args:
            message: Message text to send

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.debug("Slack webhook not configured, skipping notification")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=10
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
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
        Format credential issuance message for Slack

        Args:
            request_text: The user's access request
            risk_level: Risk assessment level
            duration_hours: Duration of credentials
            auto_approved: Whether auto-approved
            approver: Approver name (if manual approval)

        Returns:
            Formatted Slack message
        """
        base = ":unlock: AWS Temporary Credentials issued for request:\n"
        approval_type = "AUTO-APPROVED" if auto_approved else f"MANUAL APPROVAL (by {approver})"

        return f"""{base}{approval_type}
`{request_text}`
Risk Score: {risk_level.upper()}
Duration: {duration_hours} hour(s)"""

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
        return self.send_notification(message)

    def format_error_message(
        self,
        error_type: str,
        request_text: str,
        error_details: str
    ) -> str:
        """
        Format error message for Slack

        Args:
            error_type: Type of error (e.g., "Policy Generation", "Credential Issuance")
            request_text: The user's access request
            error_details: Error details

        Returns:
            Formatted Slack error message
        """
        return f""":warning: IAM-Dynamic Error: {error_type}
Request: `{request_text}`
Details: {error_details}"""

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
        message = self.format_error_message(
            error_type=error_type,
            request_text=request_text,
            error_details=error_details
        )
        return self.send_notification(message)
