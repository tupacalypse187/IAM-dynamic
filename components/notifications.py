"""
Enhanced notification system using Streamlit toasts
"""
import time
import streamlit as st
from typing import Optional


class NotificationManager:
    """
    Manage toast notifications in Streamlit

    Provides static methods for displaying different types of toast notifications
    with appropriate icons and durations.
    """

    @staticmethod
    def show_success(message: str, duration: int = 3):
        """
        Show success toast notification

        Args:
            message: Success message to display
            duration: Display duration in seconds
        """
        st.toast(f"✅ {message}", icon="✅")

    @staticmethod
    def show_error(message: str, duration: int = 5):
        """
        Show error toast notification

        Args:
            message: Error message to display
            duration: Display duration in seconds
        """
        st.toast(f"❌ {message}", icon="❌")

    @staticmethod
    def show_warning(message: str, duration: int = 4):
        """
        Show warning toast notification

        Args:
            message: Warning message to display
            duration: Display duration in seconds
        """
        st.toast(f"⚠️ {message}", icon="⚠️")

    @staticmethod
    def show_info(message: str, duration: int = 3):
        """
        Show info toast notification

        Args:
            message: Info message to display
            duration: Display duration in seconds
        """
        st.toast(f"ℹ️ {message}", icon="ℹ️")

    @staticmethod
    def show_credential_issued(duration_hours: int, risk_level: str):
        """
        Show credential issued notification

        Args:
            duration_hours: Duration credentials are valid
            risk_level: Risk level of the request
        """
        emoji_map = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        emoji = emoji_map.get(risk_level.lower(), "⚪")

        NotificationManager.show_success(
            f"Credentials issued! Valid for {duration_hours}h. Risk: {emoji} {risk_level.upper()}"
        )

    @staticmethod
    def show_policy_generated(risk_level: str):
        """
        Show policy generated notification

        Args:
            risk_level: Risk level of the generated policy
        """
        emoji_map = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        emoji = emoji_map.get(risk_level.lower(), "⚪")

        NotificationManager.show_success(
            f"Policy generated! Risk Level: {emoji} {risk_level.upper()}"
        )

    @staticmethod
    def show_request_approved(auto_approved: bool):
        """
        Show request approval notification

        Args:
            auto_approved: Whether request was auto-approved
        """
        if auto_approved:
            NotificationManager.show_success("Request auto-approved!")
        else:
            NotificationManager.show_info("Request approved manually")

    @staticmethod
    def show_copy_success(format_name: str):
        """
        Show copy to clipboard success notification

        Args:
            format_name: Name of the format copied (e.g., "Bash", "PowerShell")
        """
        NotificationManager.show_success(f"{format_name} script copied to clipboard!")

    @staticmethod
    def show_request_rejected(risk_level: str):
        """
        Show request rejected notification

        Args:
            risk_level: Risk level that caused rejection
        """
        emoji_map = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        emoji = emoji_map.get(risk_level.lower(), "⚪")

        NotificationManager.show_warning(
            f"Request rejected. Risk: {emoji} {risk_level.upper()}. Please revise and resubmit."
        )
