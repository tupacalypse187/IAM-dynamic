"""
SQLite persistence layer for session history and audit trail
"""
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    SQLite database service for persistence

    Provides CRUD operations for requests, credentials, and audit logs.
    """

    def __init__(self, db_path: str = "iam_dynamic.db"):
        """
        Initialize database service

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()
        logger.info(f"Database initialized at {db_path}")

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_text TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    duration_hours REAL NOT NULL,
                    policy_json TEXT NOT NULL,
                    explanation TEXT,
                    approver_note TEXT,
                    auto_approved BOOLEAN NOT NULL,
                    approved_by TEXT,
                    business_justification TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Credentials table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    access_key_id TEXT NOT NULL,
                    secret_access_key TEXT NOT NULL,
                    session_token TEXT NOT NULL,
                    expiration TIMESTAMP NOT NULL,
                    issued_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES requests(id)
                )
            """)

            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    user_identifier TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES requests(id)
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_created_at
                ON requests(created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_risk_level
                ON requests(risk_level)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_status
                ON requests(status)
                """)

            conn.commit()

    def save_request(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: float,
        policy: Dict[str, Any],
        explanation: str,
        approver_note: str,
        auto_approved: bool
    ) -> int:
        """
        Save a new request and return its ID

        Args:
            request_text: User's access request text
            risk_level: Risk assessment level
            duration_hours: Requested duration
            policy: Generated IAM policy
            explanation: Risk explanation
            approver_note: Note from approver
            auto_approved: Whether auto-approved

        Returns:
            ID of the created request
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO requests
                (request_text, risk_level, duration_hours, policy_json, explanation,
                 approver_note, auto_approved, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                request_text,
                risk_level,
                duration_hours,
                json.dumps(policy),
                explanation,
                approver_note,
                1 if auto_approved else 0
            ))
            conn.commit()
            request_id = cursor.lastrowid
            logger.info(f"Saved request {request_id} with risk level {risk_level}")
            return request_id

    def update_request_status(
        self,
        request_id: int,
        status: str,
        approved_by: Optional[str] = None,
        business_justification: Optional[str] = None
    ):
        """
        Update request status

        Args:
            request_id: Request ID
            status: New status (approved, rejected, issued)
            approved_by: Approver name (if manual approval)
            business_justification: Business justification text
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE requests
                SET status = ?, approved_by = ?, business_justification = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, approved_by, business_justification, request_id))
            conn.commit()
            logger.info(f"Updated request {request_id} status to {status}")

    def save_credentials(
        self,
        request_id: int,
        access_key_id: str,
        secret_access_key: str,
        session_token: str,
        expiration: datetime
    ):
        """
        Save issued credentials

        Args:
            request_id: Associated request ID
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
            session_token: Session token
            expiration: Credential expiration datetime
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO credentials
                (request_id, access_key_id, secret_access_key, session_token, expiration, issued_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                request_id,
                access_key_id,
                secret_access_key,
                session_token,
                expiration.isoformat()
            ))
            conn.commit()
            logger.info(f"Saved credentials for request {request_id}")

    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent requests

        Args:
            limit: Maximum number of requests to return

        Returns:
            List of request dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, request_text, risk_level, duration_hours, status,
                       auto_approved, created_at
                FROM requests
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_request_history(
        self,
        limit: int = 50,
        risk_filter: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get request history with optional filters

        Args:
            limit: Maximum number of requests
            risk_filter: Filter by risk level
            status_filter: Filter by status

        Returns:
            List of request dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM requests WHERE 1=1"
            params = []

            if risk_filter:
                query += " AND risk_level = ?"
                params.append(risk_filter)

            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_request_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single request by ID

        Args:
            request_id: Request ID

        Returns:
            Request dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM requests WHERE id = ?
            """, (request_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_credentials_for_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get credentials for a request

        Args:
            request_id: Request ID

        Returns:
            Credentials dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM credentials WHERE request_id = ?
            """, (request_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_audit_trail(self, request_id: int) -> List[Dict[str, Any]]:
        """
        Get audit trail for a request

        Args:
            request_id: Request ID

        Returns:
            List of audit event dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event_type, event_data, user_identifier, timestamp
                FROM audit_log
                WHERE request_id = ?
                ORDER BY timestamp ASC
            """, (request_id,))

            return [dict(row) for row in cursor.fetchall()]

    def log_event(
        self,
        event_type: str,
        request_id: Optional[int] = None,
        event_data: Optional[Dict[str, Any]] = None,
        user_identifier: Optional[str] = None
    ):
        """
        Log an audit event

        Args:
            event_type: Type of event
            request_id: Associated request ID
            event_data: Event data as dictionary
            user_identifier: User identifier
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (event_type, request_id, event_data, user_identifier)
                VALUES (?, ?, ?, ?)
            """, (
                event_type,
                request_id,
                json.dumps(event_data) if event_data else None,
                user_identifier or "system"
            ))
            conn.commit()
            logger.debug(f"Logged event {event_type} for request {request_id}")

    def export_history(self, format: str = "csv") -> str:
        """
        Export history in specified format

        Args:
            format: Export format ('csv' or 'json')

        Returns:
            Exported data as string
        """
        import pandas as pd

        df = pd.read_sql_query(
            "SELECT * FROM requests ORDER BY created_at DESC",
            sqlite3.connect(self.db_path)
        )

        if format == "csv":
            return df.to_csv(index=False)
        elif format == "json":
            return df.to_json(orient="records", indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total requests
            cursor.execute("SELECT COUNT(*) FROM requests")
            total_requests = cursor.fetchone()[0]

            # Requests by risk level
            cursor.execute("""
                SELECT risk_level, COUNT(*) as count
                FROM requests
                GROUP BY risk_level
            """)
            by_risk = {row[0]: row[1] for row in cursor.fetchall()}

            # Requests by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM requests
                GROUP BY status
            """)
            by_status = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_requests": total_requests,
                "by_risk_level": by_risk,
                "by_status": by_status
            }
