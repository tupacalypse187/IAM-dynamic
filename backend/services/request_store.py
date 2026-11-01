"""
Access request store — SQLite-backed persistence for the review workflow.

Separates *requests* (what a user asked for, plus the evaluated LLM
response) from *approvals* (what a reviewer decided). The first store of
record is this SQLite database; the immutable append-only trail lives in
the JSONL audit log (see audit_log.py) and is written alongside every
state change by the caller in main.py.

Status machine:
    pending_review -> approved | denied | changes_requested | discarded
    changes_requested -> pending_review | discarded   (resubmit bumps revision)
    approved -> activated | discarded                 (activation issues STS creds)
    denied / activated / discarded are terminal.

Concurrency follows services/user_store.py: one shared connection guarded
by a lock, BEGIN IMMEDIATE so extra uvicorn workers serialize instead of
failing with SQLITE_BUSY.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

_MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester TEXT NOT NULL,
        request_text TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT,
        duration INTEGER NOT NULL,
        policy_json TEXT NOT NULL DEFAULT '{}',
        risk TEXT NOT NULL DEFAULT 'medium',
        explanation TEXT NOT NULL DEFAULT '',
        approver_note TEXT NOT NULL DEFAULT '',
        auto_approved INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending_review',
        reviewer TEXT,
        feedback TEXT,
        revision INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        decided_at TEXT,
        credentials_expires_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_access_requests_requester
        ON access_requests (requester);
    CREATE INDEX IF NOT EXISTS idx_access_requests_status
        ON access_requests (status);""",
    """ALTER TABLE access_requests ADD COLUMN environment TEXT NOT NULL DEFAULT 'dev';
    ALTER TABLE access_requests ADD COLUMN batch_id INTEGER;
    ALTER TABLE access_requests ADD COLUMN grant_expires_at TEXT;
    UPDATE access_requests SET batch_id = id WHERE batch_id IS NULL;
    CREATE INDEX IF NOT EXISTS idx_access_requests_batch
        ON access_requests (batch_id);""",
]

STATUS_PENDING = "pending_review"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"
STATUS_CHANGES = "changes_requested"
STATUS_ACTIVATED = "activated"
STATUS_DISCARDED = "discarded"
STATUS_CANCELLED = "cancelled"

ALL_STATUSES = frozenset({
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_CHANGES,
    STATUS_ACTIVATED,
    STATUS_DISCARDED,
    STATUS_CANCELLED,
})

# Allowed transitions for set_status(). Resubmits go through resubmit(),
# activations through mark_activated() — both enforce the same map.
# Cancelled is terminal: a cancelled grant can never be re-activated, and
# already-issued sessions run to their own expiry (STS has no revocation).
_VALID_TRANSITIONS = {
    STATUS_PENDING: frozenset({STATUS_APPROVED, STATUS_DENIED, STATUS_CHANGES, STATUS_DISCARDED}),
    STATUS_CHANGES: frozenset({STATUS_PENDING, STATUS_DISCARDED}),
    STATUS_APPROVED: frozenset({STATUS_ACTIVATED, STATUS_DISCARDED, STATUS_CANCELLED}),
    STATUS_DENIED: frozenset(),
    STATUS_ACTIVATED: frozenset({STATUS_CANCELLED}),
    STATUS_DISCARDED: frozenset(),
    STATUS_CANCELLED: frozenset(),
}


class RequestStoreError(ValueError):
    """Machine-readable store failure (`code` is stable API)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequestStore:
    """SQLite access-request database with versioned migrations."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        data = dict(row)
        try:
            data["policy"] = json.loads(data.pop("policy_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            data["policy"] = {}
        data["auto_approved"] = bool(data["auto_approved"])
        return data

    def create(
        self,
        *,
        requester: str,
        request_text: str,
        provider: str,
        model: Optional[str],
        duration: int,
        policy: dict,
        risk: str,
        explanation: str,
        approver_note: str,
        auto_approved: bool,
        status: str,
        environment: str = "dev",
        batch_id: Optional[int] = None,
        grant_expires_at: Optional[str] = None,
    ) -> dict:
        """Persist a freshly evaluated request. Returns the stored row."""
        if status not in ALL_STATUSES:
            raise RequestStoreError("invalid_status", f"Unknown status '{status}'.")
        now = _utcnow()
        with self._write_lock:
            cursor = self._conn.execute(
                "INSERT INTO access_requests (requester, request_text, provider, model,"
                " duration, policy_json, risk, explanation, approver_note,"
                " auto_approved, status, revision, created_at, updated_at,"
                " environment, batch_id, grant_expires_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)",
                (
                    requester,
                    request_text,
                    provider,
                    model,
                    duration,
                    json.dumps(policy),
                    risk,
                    explanation,
                    approver_note,
                    1 if auto_approved else 0,
                    status,
                    now,
                    now,
                    environment,
                    batch_id,
                    grant_expires_at,
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM access_requests WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        logger.info("Access request %s created by %s (status=%s)", row["id"], requester, status)
        return self._row_to_dict(row)

    def get(self, request_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM access_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list(
        self, *, requester: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict]:
        """List requests, newest first. `requester` scopes to one user's rows."""
        query = "SELECT * FROM access_requests"
        clauses: list[str] = []
        params: list = []
        if requester is not None:
            clauses.append("requester = ?")
            params.append(requester)
        if status is not None:
            if status not in ALL_STATUSES:
                raise RequestStoreError("invalid_status", f"Unknown status '{status}'.")
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def set_status(
        self,
        request_id: int,
        to_status: str,
        *,
        reviewer: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> dict:
        """Apply a review decision or discard. Enforces the status machine."""
        if to_status not in ALL_STATUSES:
            raise RequestStoreError("invalid_status", f"Unknown status '{to_status}'.")
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM access_requests WHERE id = ?", (request_id,)
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    raise RequestStoreError("not_found", f"Request {request_id} not found.")
                from_status = row["status"]
                if to_status not in _VALID_TRANSITIONS.get(from_status, frozenset()):
                    self._conn.rollback()
                    raise RequestStoreError(
                        "invalid_transition",
                        f"Cannot move request {request_id} from {from_status} to {to_status}.",
                    )
                now = _utcnow()
                self._conn.execute(
                    "UPDATE access_requests SET status = ?, reviewer = ?, feedback = ?,"
                    " updated_at = ?, decided_at = ? WHERE id = ?",
                    (to_status, reviewer, feedback, now, now, request_id),
                )
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            else:
                self._conn.commit()
        logger.info(
            "Access request %s: %s -> %s (reviewer=%s)",
            request_id, from_status, to_status, reviewer,
        )
        return self.get(request_id)  # type: ignore[return-value]

    def resubmit(
        self,
        request_id: int,
        *,
        request_text: str,
        provider: str,
        model: Optional[str],
        duration: int,
        policy: dict,
        risk: str,
        explanation: str,
        approver_note: str,
        auto_approved: bool,
        status: str,
    ) -> dict:
        """Re-evaluate a sent-back request as a new revision. Same id, same history."""
        if status not in (STATUS_PENDING, STATUS_APPROVED):
            raise RequestStoreError(
                "invalid_status",
                "A resubmission must land in pending_review or approved.",
            )
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM access_requests WHERE id = ?", (request_id,)
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    raise RequestStoreError("not_found", f"Request {request_id} not found.")
                if row["status"] != STATUS_CHANGES:
                    self._conn.rollback()
                    raise RequestStoreError(
                        "invalid_transition",
                        f"Only requests sent back for changes can be resubmitted "
                        f"(request {request_id} is {row['status']}).",
                    )
                now = _utcnow()
                self._conn.execute(
                    "UPDATE access_requests SET request_text = ?, provider = ?, model = ?,"
                    " duration = ?, policy_json = ?, risk = ?, explanation = ?,"
                    " approver_note = ?, auto_approved = ?, status = ?, reviewer = NULL,"
                    " feedback = NULL, revision = revision + 1, updated_at = ?,"
                    " decided_at = NULL WHERE id = ?",
                    (
                        request_text, provider, model, duration, json.dumps(policy),
                        risk, explanation, approver_note, 1 if auto_approved else 0,
                        status, now, request_id,
                    ),
                )
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            else:
                self._conn.commit()
        logger.info("Access request %s resubmitted (status=%s)", request_id, status)
        return self.get(request_id)  # type: ignore[return-value]

    def set_batch_ids(self, request_ids: list[int], batch_id: int) -> None:
        """Link freshly created unit rows into one batch."""
        if not request_ids:
            return
        with self._write_lock:
            self._conn.execute(
                f"UPDATE access_requests SET batch_id = ?, updated_at = ? WHERE id IN"
                f" ({','.join('?' * len(request_ids))})",
                [batch_id, _utcnow(), *request_ids],
            )
            self._conn.commit()

    def set_grant_expires_at(self, request_id: int, grant_expires_at: str) -> None:
        """Stamp the approval window (set on every approval)."""
        with self._write_lock:
            cursor = self._conn.execute(
                "UPDATE access_requests SET grant_expires_at = ?, updated_at = ?"
                " WHERE id = ?",
                (grant_expires_at, _utcnow(), request_id),
            )
            self._conn.commit()
            if cursor.rowcount == 0:
                raise RequestStoreError("not_found", f"Request {request_id} not found.")

    def mark_activated(self, request_id: int, *, credentials_expires_at: str) -> dict:
        """Record STS issuance.

        Approved grants activate; activated dev grants re-activate (each
        issuance is a fresh ≤12h session inside the grant window). The
        endpoint enforces environment + window rules — the store only
        enforces that anything else (pending, denied, discarded,
        cancelled…) can never issue.
        """
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM access_requests WHERE id = ?", (request_id,)
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    raise RequestStoreError("not_found", f"Request {request_id} not found.")
                if row["status"] not in (STATUS_APPROVED, STATUS_ACTIVATED):
                    self._conn.rollback()
                    raise RequestStoreError(
                        "invalid_transition",
                        f"Only approved grants can be activated "
                        f"(request {request_id} is {row['status']}).",
                    )
                now = _utcnow()
                self._conn.execute(
                    "UPDATE access_requests SET status = ?, updated_at = ?,"
                    " credentials_expires_at = ? WHERE id = ?",
                    (STATUS_ACTIVATED, now, credentials_expires_at, request_id),
                )
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            else:
                self._conn.commit()
        logger.info("Access request %s activated", request_id)
        return self.get(request_id)  # type: ignore[return-value]

    def close(self) -> None:
        self._conn.close()
