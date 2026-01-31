"""
Input validation utilities
"""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class InputValidator:
    """
    Validate user inputs

    Provides static methods for validating request text,
    duration, and business justification.
    """

    # Suspicious patterns that should be blocked
    SUSPICIOUS_PATTERNS = [
        r'\*:\*',  # Full wildcard
        r'AdministratorAccess',
        r'PowerUserAccess',
        r'\*:\*:\*'
    ]

    @staticmethod
    def validate_duration(duration_hours: float, risk_level: str = "medium") -> Tuple[bool, Optional[str]]:
        """
        Validate requested duration against limits

        Args:
            duration_hours: Requested duration in hours
            risk_level: Risk assessment level

        Returns:
            Tuple of (is_valid, error_message)
        """
        max_durations = {
            "low": 12,
            "medium": 4,
            "high": 2,
            "critical": 1
        }

        max_allowed = max_durations.get(risk_level.lower(), 4)

        if duration_hours <= 0:
            return False, "Duration must be greater than 0"

        if duration_hours > 12:
            return False, "Maximum duration is 12 hours"

        if duration_hours > max_allowed:
            return False, f"Duration capped at {max_allowed} hours for {risk_level} risk"

        return True, None

    @staticmethod
    def validate_request_text(text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user request text

        Args:
            text: Request text to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not text.strip():
            return False, "Request text cannot be empty"

        if len(text.strip()) < 10:
            return False, "Please provide more details about your request (min 10 characters)"

        if len(text) > 2000:
            return False, "Request too long (max 2000 characters)"

        # Check for suspicious patterns
        for pattern in InputValidator.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Request contains restricted pattern: {pattern}"

        return True, None

    @staticmethod
    def validate_business_justification(
        justification: str,
        risk_level: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate business justification for high-risk requests

        Args:
            justification: Business justification text
            risk_level: Risk assessment level

        Returns:
            Tuple of (is_valid, error_message)
        """
        if risk_level.lower() in ["high", "critical"]:
            if not justification or not justification.strip():
                return False, "Business justification required for high-risk requests"

            if len(justification.strip()) < 20:
                return False, "Justification too brief (min 20 characters)"

            if len(justification.strip()) > 500:
                return False, "Justification too long (max 500 characters)"

        return True, None

    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitize user input to prevent injection attacks

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text
        """
        # Remove any non-printable characters except newlines and tabs
        text = ''.join(
            char for char in text
            if char.isprintable() or char in ['\n', '\t']
        )

        # Limit length
        return text[:2000]

    @staticmethod
    def validate_role_arn(role_arn: str) -> Tuple[bool, Optional[str]]:
        """
        Validate AWS IAM role ARN format

        Args:
            role_arn: Role ARN to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not role_arn:
            return False, "Role ARN cannot be empty"

        # ARN format: arn:aws:iam::account-id:role/role-name
        pattern = r'^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@-_]+$'

        if not re.match(pattern, role_arn):
            return False, (
                "Invalid Role ARN format. "
                "Expected: arn:aws:iam::123456789012:role/role-name"
            )

        return True, None

    @staticmethod
    def validate_account_id(account_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate AWS account ID format

        Args:
            account_id: AWS account ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not account_id:
            return False, "Account ID cannot be empty"

        # AWS account IDs are 12 digits
        if not re.match(r'^\d{12}$', account_id):
            return False, "Invalid AWS Account ID (must be 12 digits)"

        return True, None

    @staticmethod
    def validate_api_key(api_key: str, provider: str = "gemini") -> Tuple[bool, Optional[str]]:
        """
        Validate API key format

        Args:
            api_key: API key to validate
            provider: Provider name (gemini or openai)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not api_key:
            return False, f"{provider.capitalize()} API key cannot be empty"

        if provider == "gemini":
            # Google API keys typically start with "AIza"
            if not api_key.startswith("AIza"):
                return False, "Invalid Google API key format (should start with 'AIza')"

        elif provider == "openai":
            # OpenAI API keys start with "sk-"
            if not api_key.startswith("sk-"):
                return False, "Invalid OpenAI API key format (should start with 'sk-')"

        return True, None
