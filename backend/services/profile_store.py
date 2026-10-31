"""
Per-user LLM profiles + admin-managed provider catalog.

Replaces hardcoded provider/model/API-key configuration with user-owned
named profiles: each profile pins a provider + model and carries the
user's own API key, encrypted at rest with Fernet. Keys are decrypted
only in-process to construct a provider instance — they are never
logged, never written to the audit trail, and never returned by any
read API (callers see `has_key` + a last-4 hint only).

The catalog decides which provider/model pairs exist at all; only an
administrator can enable or disable entries. Profiles that reference a
disabled pair are rejected at submit time.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS provider_catalog (
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (provider, model)
    );
    CREATE TABLE IF NOT EXISTS user_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        key_enc TEXT NOT NULL DEFAULT '',
        key_hint TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (username, name)
    );
    CREATE INDEX IF NOT EXISTS idx_user_profiles_username
        ON user_profiles (username);
    CREATE TABLE IF NOT EXISTS user_active_profile (
        username TEXT PRIMARY KEY,
        profile_id INTEGER NOT NULL
    );""",
]

PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,64}$")


class ProfileStoreError(ValueError):
    """Machine-readable store failure (`code` is stable API)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_fernet(secret: str) -> Fernet:
    """Build a Fernet instance from an arbitrary server secret.

    The secret (PROFILE_ENCRYPTION_KEY, falling back to JWT_SECRET) is
    hashed to the 32 bytes Fernet requires — operators never handle raw
    Fernet keys.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class ProfileStore:
    """SQLite profile/catalog database with versioned migrations."""

    def __init__(self, db_path: str | Path, encryption_secret: str):
        if not encryption_secret:
            raise ProfileStoreError(
                "no_encryption_secret",
                "Profile encryption requires PROFILE_ENCRYPTION_KEY or JWT_SECRET.",
            )
        self.db_path = str(db_path)
        self._fernet = derive_fernet(encryption_secret)
        self._write_lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
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

    # -- catalog ------------------------------------------------------

    def seed_catalog(self, entries: list[dict]) -> None:
        """Idempotently insert provider/model pairs (display names refresh)."""
        with self._write_lock:
            for entry in entries:
                self._conn.execute(
                    "INSERT INTO provider_catalog (provider, model, display_name, enabled)"
                    " VALUES (?, ?, ?, 1)"
                    " ON CONFLICT (provider, model) DO UPDATE SET display_name = excluded.display_name",
                    (entry["provider"], entry["model"], entry.get("display_name", "")),
                )
            self._conn.commit()

    def list_catalog(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT provider, model, display_name, enabled FROM provider_catalog"
            " ORDER BY provider, model"
        ).fetchall()
        return [
            {
                "provider": r["provider"],
                "model": r["model"],
                "display_name": r["display_name"],
                "enabled": bool(r["enabled"]),
            }
            for r in rows
        ]

    def set_catalog_enabled(self, provider: str, model: str, enabled: bool) -> dict:
        with self._write_lock:
            cursor = self._conn.execute(
                "UPDATE provider_catalog SET enabled = ? WHERE provider = ? AND model = ?",
                (1 if enabled else 0, provider, model),
            )
            self._conn.commit()
            if cursor.rowcount == 0:
                raise ProfileStoreError(
                    "unknown_model", f"Unknown catalog entry {provider}/{model}."
                )
        row = self._conn.execute(
            "SELECT provider, model, display_name, enabled FROM provider_catalog"
            " WHERE provider = ? AND model = ?",
            (provider, model),
        ).fetchone()
        return {
            "provider": row["provider"],
            "model": row["model"],
            "display_name": row["display_name"],
            "enabled": bool(row["enabled"]),
        }

    def is_enabled(self, provider: str, model: str) -> bool:
        row = self._conn.execute(
            "SELECT enabled FROM provider_catalog WHERE provider = ? AND model = ?",
            (provider, model),
        ).fetchone()
        return bool(row and row["enabled"])

    # -- profiles -----------------------------------------------------

    @staticmethod
    def _public_row(row: sqlite3.Row, active_id: Optional[int] = None) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "name": row["name"],
            "provider": row["provider"],
            "model": row["model"],
            "has_key": bool(row["key_enc"]),
            "key_hint": row["key_hint"],
            "active": active_id is not None and row["id"] == active_id,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _get_active_id(self, username: str) -> Optional[int]:
        row = self._conn.execute(
            "SELECT profile_id FROM user_active_profile WHERE username = ?", (username,)
        ).fetchone()
        return int(row["profile_id"]) if row else None

    def create_profile(
        self, *, username: str, name: str, provider: str, model: str, api_key: str
    ) -> dict:
        name = (name or "").strip()
        if not PROFILE_NAME_RE.match(name):
            raise ProfileStoreError(
                "invalid_name",
                "Profile name must be 1-64 characters: letters, numbers, space, _ or -.",
            )
        if not self.is_enabled(provider, model):
            raise ProfileStoreError(
                "model_disabled",
                f"{provider}/{model} is not enabled. Ask an administrator.",
            )
        if not (api_key or "").strip():
            raise ProfileStoreError("missing_key", "An API key is required.")
        key_enc = self._fernet.encrypt(api_key.strip().encode("utf-8")).decode("utf-8")
        key_hint = api_key.strip()[-4:]
        now = _utcnow()
        with self._write_lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO user_profiles (username, name, provider, model,"
                    " key_enc, key_hint, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, name, provider, model, key_enc, key_hint, now, now),
                )
            except sqlite3.IntegrityError:
                self._conn.rollback()
                raise ProfileStoreError(
                    "name_taken", f"You already have a profile named '{name}'."
                )
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            else:
                # First profile becomes active automatically.
                if self._get_active_id(username) is None:
                    self._conn.execute(
                        "INSERT INTO user_active_profile (username, profile_id)"
                        " VALUES (?, ?)",
                        (username, cursor.lastrowid),
                    )
                self._conn.commit()
        logger.info("Profile '%s' created for %s (%s/%s)", name, username, provider, model)
        return self.get_profile_public(username, int(cursor.lastrowid))  # type: ignore[arg-type]

    def get_profile_public(self, username: str, profile_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM user_profiles WHERE id = ? AND username = ?",
            (profile_id, username),
        ).fetchone()
        if row is None:
            return None
        return self._public_row(row, self._get_active_id(username))

    def list_profiles(self, username: str) -> list[dict]:
        active_id = self._get_active_id(username)
        rows = self._conn.execute(
            "SELECT * FROM user_profiles WHERE username = ? ORDER BY id", (username,)
        ).fetchall()
        return [self._public_row(r, active_id) for r in rows]

    def get_credentials(self, username: str, profile_id: int) -> dict:
        """Return provider/model/decrypted key for instance construction.

        Internal use only — never serialize this to an API response.
        """
        row = self._conn.execute(
            "SELECT * FROM user_profiles WHERE id = ? AND username = ?",
            (profile_id, username),
        ).fetchone()
        if row is None:
            raise ProfileStoreError("not_found", f"Profile {profile_id} not found.")
        try:
            api_key = self._fernet.decrypt(row["key_enc"].encode("utf-8")).decode("utf-8")
        except InvalidToken as e:
            raise ProfileStoreError(
                "decrypt_failed",
                "Stored key cannot be decrypted with the current server secret.",
            ) from e
        return {"provider": row["provider"], "model": row["model"], "api_key": api_key}

    def get_active_credentials(self, username: str) -> Optional[dict]:
        active_id = self._get_active_id(username)
        if active_id is None:
            return None
        try:
            creds = self.get_credentials(username, active_id)
        except ProfileStoreError:
            return None
        return {"id": active_id, **creds}

    def update_profile(
        self,
        username: str,
        profile_id: int,
        *,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict:
        row = self._conn.execute(
            "SELECT * FROM user_profiles WHERE id = ? AND username = ?",
            (profile_id, username),
        ).fetchone()
        if row is None:
            raise ProfileStoreError("not_found", f"Profile {profile_id} not found.")
        updates: list[str] = []
        params: list = []
        if name is not None:
            clean = name.strip()
            if not PROFILE_NAME_RE.match(clean):
                raise ProfileStoreError(
                    "invalid_name",
                    "Profile name must be 1-64 characters: letters, numbers, space, _ or -.",
                )
            updates.append("name = ?")
            params.append(clean)
        if api_key is not None:
            if not api_key.strip():
                raise ProfileStoreError("missing_key", "An API key is required.")
            updates.append("key_enc = ?")
            params.append(self._fernet.encrypt(api_key.strip().encode("utf-8")).decode("utf-8"))
            updates.append("key_hint = ?")
            params.append(api_key.strip()[-4:])
        if not updates:
            result = self.get_profile_public(username, profile_id)
            assert result is not None
            return result
        updates.append("updated_at = ?")
        params.append(_utcnow())
        params.extend([profile_id, username])
        with self._write_lock:
            try:
                self._conn.execute(
                    f"UPDATE user_profiles SET {', '.join(updates)} WHERE id = ? AND username = ?",
                    params,
                )
            except sqlite3.IntegrityError:
                self._conn.rollback()
                raise ProfileStoreError(
                    "name_taken", f"You already have a profile named '{name}'."
                )
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            else:
                self._conn.commit()
        result = self.get_profile_public(username, profile_id)
        assert result is not None
        return result

    def delete_profile(self, username: str, profile_id: int) -> None:
        with self._write_lock:
            cursor = self._conn.execute(
                "DELETE FROM user_profiles WHERE id = ? AND username = ?",
                (profile_id, username),
            )
            self._conn.execute(
                "DELETE FROM user_active_profile WHERE username = ? AND profile_id = ?",
                (username, profile_id),
            )
            # Promote the oldest surviving profile so one stays active.
            if self._get_active_id(username) is None:
                survivor = self._conn.execute(
                    "SELECT id FROM user_profiles WHERE username = ? ORDER BY id LIMIT 1",
                    (username,),
                ).fetchone()
                if survivor is not None:
                    self._conn.execute(
                        "INSERT INTO user_active_profile (username, profile_id)"
                        " VALUES (?, ?)",
                        (username, survivor["id"]),
                    )
            self._conn.commit()
            if cursor.rowcount == 0:
                raise ProfileStoreError("not_found", f"Profile {profile_id} not found.")

    def set_active(self, username: str, profile_id: int) -> dict:
        row = self._conn.execute(
            "SELECT id FROM user_profiles WHERE id = ? AND username = ?",
            (profile_id, username),
        ).fetchone()
        if row is None:
            raise ProfileStoreError("not_found", f"Profile {profile_id} not found.")
        with self._write_lock:
            self._conn.execute(
                "INSERT INTO user_active_profile (username, profile_id)"
                " VALUES (?, ?) ON CONFLICT (username) DO UPDATE SET profile_id = excluded.profile_id",
                (username, profile_id),
            )
            self._conn.commit()
        result = self.get_profile_public(username, profile_id)
        assert result is not None
        return result

    def close(self) -> None:
        self._conn.close()
