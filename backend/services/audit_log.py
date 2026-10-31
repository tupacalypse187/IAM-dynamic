"""
JSONL audit trail — the immutable compliance record for access requests.

Every request lifecycle event (submitted, auto-approved, queued for
review, approved, denied, sent back for changes, resubmitted, activated,
discarded) is appended here as one JSON object per line, alongside the
queryable SQLite rows in request_store.py. The JSONL file is the portable
trail: admins browse it in-app via GET /api/audit, and it survives
database rebuilds.

Only metadata is recorded — request text, policy, risk, actors, and
feedback. Never pass credential material (access keys, secrets, session
tokens) to append().
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Events that must never carry credential material. append() does not
# inspect values — callers are responsible — but the allowlist documents
# the contract the audit dashboard relies on.
AUDIT_EVENTS = frozenset({
    "submitted",
    "auto_approved",
    "queued_for_review",
    "approved",
    "denied",
    "changes_requested",
    "resubmitted",
    "activated",
    "discarded",
})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    """Thread-safe append-only JSONL writer with filtered reads."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.parent != Path(".") and str(self.path.parent):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Touch the file so reads on a fresh install return [] instead of failing.
        if not self.path.exists():
            self.path.touch()

    def append(
        self,
        event: str,
        *,
        request_id: int,
        actor: str,
        actor_role: str,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        **extra,
    ) -> dict:
        """Append one audit event. Returns the recorded record."""
        if event not in AUDIT_EVENTS:
            raise ValueError(f"Unknown audit event '{event}'.")
        record = {
            "ts": _utcnow(),
            "event": event,
            "request_id": request_id,
            "actor": actor,
            "actor_role": actor_role,
            "from_status": from_status,
            "to_status": to_status,
            **extra,
        }
        line = json.dumps(record, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        logger.info("Audit: %s request=%s actor=%s", event, request_id, actor)
        return record

    def read(
        self,
        *,
        limit: int = 100,
        request_id: Optional[int] = None,
        actor: Optional[str] = None,
        event: Optional[str] = None,
    ) -> list[dict]:
        """Read matching events, newest first. Skips malformed lines."""
        if not self.path.exists():
            return []
        matches: list[dict] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed audit line")
                    continue
                if request_id is not None and record.get("request_id") != request_id:
                    continue
                if actor is not None and record.get("actor") != actor:
                    continue
                if event is not None and record.get("event") != event:
                    continue
                matches.append(record)
        matches.reverse()
        return matches[: max(limit, 1)]
