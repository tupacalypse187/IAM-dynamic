"""
User store — SQLite-backed multi-user authentication.

Replaces the single-user AUTH_PASSWORD_HASH workflow with real accounts:
the first registered user becomes the administrator, subsequent users are
standard. Passwords are bcrypt-hashed; the table never stores plaintext.

Registration policy (open vs invite-only) is enforced by the caller via
`AuthConfig.allow_registration` — this module only stores and verifies.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
MIN_PASSWORD_LENGTH = 8


class RegistrationError(ValueError):
    """Machine-readable registration failure (`code` is stable API)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    """SQLite user database with versioned migrations."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()
        current = int(row["value"]) if row else 0
        for version in range(current, SCHEMA_VERSION):
            self._conn.executescript(_MIGRATIONS[version])
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                (str(version + 1),),
            )
        self._conn.commit()

    def count_users(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    def register(self, username: str, password: str) -> dict:
        """Create a user; the first user becomes administrator."""
        username = (username or "").strip()
        if not USERNAME_RE.match(username):
            raise RegistrationError(
                "invalid_username",
                "Username must be 3-32 characters: letters, numbers, _ or -.",
            )
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise RegistrationError(
                "weak_password",
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            )
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        is_admin = 1 if self.count_users() == 0 else 0
        try:
            self._conn.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at) "
                "VALUES (?, ?, ?, ?)",
                (username, password_hash, is_admin, _utcnow()),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise RegistrationError("username_taken", "That username is already registered.")
        logger.info("Registered user %s (admin=%s)", username, bool(is_admin))
        return {"username": username, "is_admin": bool(is_admin)}

    def verify(self, username: str, password: str) -> bool:
        """Check credentials without revealing whether the username exists."""
        row = self._conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            # Burn comparable work so unknown users aren't measurably faster.
            bcrypt.checkpw(b"invalid", bcrypt.gensalt())
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8"))
        except Exception:
            logger.warning("Password verification failed for user %s", username)
            return False

    def is_admin(self, username: Optional[str]) -> bool:
        if not username:
            return False
        row = self._conn.execute(
            "SELECT is_admin FROM users WHERE username = ?", (username,)
        ).fetchone()
        return bool(row and row["is_admin"])

    def list_users(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT username, is_admin, created_at FROM users ORDER BY id"
        ).fetchall()
        return [
            {"username": r["username"], "is_admin": bool(r["is_admin"]), "created_at": r["created_at"]}
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
