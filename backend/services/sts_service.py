"""
AWS STS service for credential issuance
"""
import json
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class STSServiceError(Exception):
    """Base exception for STS service errors"""
    pass


class STSAssumeRoleError(STSServiceError):
    """Raised when AssumeRole operation fails"""
    pass


class STSService:
    """
    AWS STS service for issuing temporary credentials

    This service handles assuming an IAM role with a session policy
    to issue temporary AWS credentials with scoped permissions.
    """

    def __init__(self, role_arn: str):
        """
        Initialize STS service

        Args:
            role_arn: The ARN of the role to assume
        """
        self.role_arn = role_arn
        self.client = boto3.client("sts")
        logger.info(f"STS Service initialized with role: {role_arn}")

    def assume_role_with_policy(
        self,
        policy: Dict[str, Any],
        duration_hours: float,
        session_name: str = "gemini-jit-session"
    ) -> Dict[str, Any]:
        """
        Assume role with session policy

        Args:
            policy: IAM policy document as dict
            duration_hours: Session duration in hours (max 12)
            session_name: Identifier for the session

        Returns:
            Dictionary with credentials and metadata including:
            - AccessKeyId
            - SecretAccessKey
            - SessionToken
            - Expiration
            - IssuedAt
            - SessionName

        Raises:
            STSAssumeRoleError: If AssumeRole operation fails
        """
        try:
            duration_seconds = int(duration_hours * 3600)

            # Validate duration limits
            if duration_seconds < 900:
                raise ValueError("Duration must be at least 15 minutes (900 seconds)")
            if duration_seconds > 43200:
                raise ValueError("Duration cannot exceed 12 hours (43200 seconds)")

            logger.info(f"Assuming role {session_name} for {duration_hours} hours")

            response = self.client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName=session_name,
                DurationSeconds=duration_seconds,
                Policy=json.dumps(policy)
            )

            creds = response["Credentials"]

            # Ensure timezone-aware datetime
            if creds["Expiration"].tzinfo is None:
                creds["Expiration"] = creds["Expiration"].replace(tzinfo=timezone.utc)

            # Add metadata
            creds["IssuedAt"] = datetime.now(timezone.utc)
            creds["SessionName"] = session_name

            logger.info(f"Credentials issued for session {session_name}, expires at {creds['Expiration']}")

            return creds

        except ValueError as e:
            logger.error(f"Invalid duration: {e}")
            raise STSAssumeRoleError(str(e)) from e
        except Exception as e:
            logger.error(f"Failed to assume role: {e}")
            raise STSAssumeRoleError(f"Failed to issue credentials: {str(e)}") from e

    def validate_duration(self, duration_hours: float, risk_level: str) -> int:
        """
        Validate duration against risk-based limits

        Args:
            duration_hours: Requested duration
            risk_level: Risk assessment (low, medium, high, critical)

        Returns:
            Validated duration in hours (capped if necessary)
        """
        max_durations = {
            "low": 12,
            "medium": 4,
            "high": 2,
            "critical": 1
        }

        max_allowed = max_durations.get(risk_level.lower(), 2)

        if duration_hours > max_allowed:
            logger.warning(
                f"Duration {duration_hours}h exceeds limit for {risk_level} risk, capping at {max_allowed}h"
            )
            return max_allowed

        return int(duration_hours)

    def get_session_duration_remaining(self, expiration: datetime) -> tuple[int, int]:
        """
        Get remaining time until credential expiration

        Args:
            expiration: Credential expiration datetime

        Returns:
            Tuple of (hours, minutes) remaining
        """
        now = datetime.now(timezone.utc)
        remaining = expiration - now

        if remaining.total_seconds() <= 0:
            return 0, 0

        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)

        return hours, minutes
