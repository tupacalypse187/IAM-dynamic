"""
Authentication service — JWT token creation/verification and password checking.

When auth is disabled (no AUTH_PASSWORD_HASH configured), all checks pass through
to preserve the local development workflow.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)


@dataclass
class TokenResult:
    """JWT token with its expiry timestamp."""
    token: str
    expires_at: datetime


def create_jwt(username: str, jwt_secret: str, jwt_expiry_hours: int = 8) -> TokenResult:
    """Create a signed JWT for any username (single-user or user-store)."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=jwt_expiry_hours)
    payload = {
        "sub": username,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return TokenResult(token=token, expires_at=expires_at)


def verify_jwt(token: str, jwt_secret: str) -> Optional[str]:
    """Verify a JWT and return the username, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.debug("Invalid token")
        return None


# TEMPORARY hackathon demo aid (admin view-as-user). Fifteen-minute tokens
# carrying the impersonating admin in `impersonated_from`; remove with the
# impersonate endpoint before production.
IMPERSONATION_EXPIRY_MINUTES = 15


def create_impersonation_jwt(username: str, impersonator: str, jwt_secret: str) -> TokenResult:
    """Mint a short-lived view-as token for an allowlisted demo user."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=IMPERSONATION_EXPIRY_MINUTES)
    payload = {
        "sub": username,
        "impersonated_from": impersonator,
        "iat": now,
        "exp": expires_at,
    }
    return TokenResult(token=jwt.encode(payload, jwt_secret, algorithm="HS256"), expires_at=expires_at)


class AuthService:
    def __init__(
        self,
        username: str,
        password_hash: str,
        jwt_secret: str,
        jwt_expiry_hours: int = 8,
    ):
        self.username = username
        self.password_hash = password_hash
        self.jwt_secret = jwt_secret
        self.jwt_expiry_hours = jwt_expiry_hours

    def verify_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored bcrypt hash."""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                self.password_hash.encode('utf-8')
            )
        except Exception:
            logger.warning("Password verification failed (invalid hash?)")
            return False

    def authenticate(self, username: str, password: str) -> Optional[TokenResult]:
        """Authenticate user and return a TokenResult, or None on failure.

        Always runs bcrypt verify to prevent timing-based username enumeration.
        """
        username_match = username == self.username
        password_match = self.verify_password(password)
        if not username_match or not password_match:
            return None
        return self.create_token(username)

    def create_token(self, username: str) -> TokenResult:
        """Create a signed JWT for the given username."""
        return create_jwt(username, self.jwt_secret, self.jwt_expiry_hours)

    def verify_token(self, token: str) -> Optional[str]:
        """Verify a JWT and return the username, or None if invalid/expired."""
        return verify_jwt(token, self.jwt_secret)
