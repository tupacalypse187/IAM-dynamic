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
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.jwt_expiry_hours)
        payload = {
            "sub": username,
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        return TokenResult(token=token, expires_at=expires_at)

    def verify_token(self, token: str) -> Optional[str]:
        """Verify a JWT and return the username, or None if invalid/expired."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.debug("Invalid token")
            return None
