"""
Type definitions for IAM-Dynamic
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RequestData:
    """
    Typed container for request data

    Attributes:
        request_text: User's access request text
        duration_hours: Requested credential duration
        risk_level: Risk assessment level
        policy: Generated IAM policy
        explanation: Risk explanation
        approver_note: Note from approver
        auto_approved: Whether auto-approved
    """
    request_text: str
    duration_hours: float
    risk_level: str
    policy: Dict[str, Any]
    explanation: str
    approver_note: str
    auto_approved: bool


@dataclass
class CredentialData:
    """
    Typed container for credential data

    Attributes:
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key (should be treated as sensitive)
        session_token: Session token
        expiration: Credential expiration datetime
        issued_at: When credentials were issued
        session_name: Name of the STS session
    """
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: datetime
    issued_at: datetime
    session_name: str


@dataclass
class AuditEvent:
    """
    Typed container for audit events

    Attributes:
        event_type: Type of event (e.g., "request_created", "credentials_issued")
        request_id: Associated request ID
        event_data: Additional event data as dictionary
        user_identifier: User who triggered the event
        timestamp: When the event occurred
    """
    event_type: str
    request_id: Optional[int]
    event_data: Optional[Dict[str, Any]]
    user_identifier: Optional[str]
    timestamp: datetime


@dataclass
class HistoryItem:
    """
    Typed container for session history items

    Attributes:
        time: Timestamp of the request
        req: Request text
        risk: Risk level
        access_key: Access key ID (truncated for display)
        status: Request status (if available)
    """
    time: str
    req: str
    risk: str
    access_key: str
    status: Optional[str] = None


@dataclass
class PolicyStats:
    """
    Statistics about a generated policy

    Attributes:
        services: List of AWS services in the policy
        action_count: Total number of actions
        unique_actions: Number of unique actions
        has_wildcard_resource: Whether policy uses wildcard resources
        has_wildcard_action: Whether policy uses wildcard actions
    """
    services: List[str]
    action_count: int
    unique_actions: int
    has_wildcard_resource: bool
    has_wildcard_action: bool


@dataclass
class ValidationResult:
    """
    Result of a validation operation

    Attributes:
        is_valid: Whether validation passed
        errors: List of error messages
        warnings: List of warning messages
    """
    is_valid: bool
    errors: List[str]
    warnings: List[str]


# Type aliases for common patterns
RequestId = int
RiskLevel = str  # Literal["low", "medium", "high", "critical"]
DurationHours = float
PolicyJSON = Dict[str, Any]
