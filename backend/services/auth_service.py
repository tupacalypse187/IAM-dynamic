"""
Authentication service — JWT token creation/verification and password checking.

When auth is disabled (no AUTH_PASSWORD_HASH configured), all checks pass through
to preserve the local development workflow.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.hash import bcrypt

logger = logging.getLogger(__name__)


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
            return bcrypt.verify(password, self.password_hash)
        except Exception:
            logger.warning("Password verification failed (invalid hash?)")
            return False

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return a JWT, or None on failure."""
        if username != self.username:
            return None
        if not self.verify_password(password):
            return None
        return self.create_token(username)

    def create_token(self, username: str) -> str:
        """Create a signed JWT for the given username."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + timedelta(hours=self.jwt_expiry_hours),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

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
