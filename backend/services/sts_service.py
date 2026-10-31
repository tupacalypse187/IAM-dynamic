"""
AWS STS service for credential issuance
"""
import json
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)


class STSServiceError(Exception):
    """Base exception for STS service errors"""
    pass


class STSAssumeRoleError(STSServiceError):
    """Raised when AssumeRole operation fails"""
    pass


# Action verbs that never mutate state. A policy is read-only only when
# EVERY allowed action starts with one of these (trailing wildcards like
# "s3:Get*" count: the verb stem still only reads).
READ_ONLY_VERBS = (
    "get", "list", "describe", "head", "batchget", "query", "scan",
    "search", "lookup", "count",
)


def select_base_role_class(policy: Dict[str, Any]) -> str:
    """Classify a session policy into a base-role class.

    Returns "readonly" when every Allow action is read-only, else
    "developer". Conservative by design: wildcards, NotAction, Deny-only
    statements, and unparseable shapes all resolve to "developer" — the
    session policy still scopes the final credentials downward, so a
    misclassification only widens the *base*, never the grant.
    """
    try:
        statements = policy.get("Statement", [])
    except AttributeError:
        return "developer"
    if not isinstance(statements, list) or not statements:
        return "developer"
    allow_actions: list = []
    for statement in statements:
        if not isinstance(statement, dict):
            return "developer"
        if statement.get("Effect") != "Allow":
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "NotAction" in statement:
            return "developer"
        if not isinstance(actions, list) or not actions:
            return "developer"
        allow_actions.extend(actions)
    if not allow_actions:
        return "developer"
    for action in allow_actions:
        if not isinstance(action, str):
            return "developer"
        verb = action.split(":")[-1].lower().rstrip("*")
        if not verb or not verb.startswith(READ_ONLY_VERBS):
            return "developer"
    return "readonly"


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
        session_name: str = "gemini-jit-session",
        role_arn: str = None
    ) -> Dict[str, Any]:
        """
        Assume role with session policy

        Args:
            policy: IAM policy document as dict
            duration_hours: Session duration in hours (max 12)
            session_name: Identifier for the session
            role_arn: Base role to assume (least-privilege match for the
                task); defaults to the service's configured role.

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

            target_arn = role_arn or self.role_arn
            logger.info(f"Assuming role {target_arn} with session policy")

            response = self.client.assume_role(
                RoleArn=target_arn,
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
