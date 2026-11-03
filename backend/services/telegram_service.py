"""
Telegram notification service

Sends audit notifications through a Telegram bot created via @BotFather
(https://core.telegram.org/bots#botfather). Requires the bot token and
the chat_id of the user or group that should receive the messages.
"""
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html import escape
from typing import Optional
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

# Colored circles so risk is scannable without reading (mirrors Slack)
RISK_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🟠",
    "critical": "🔴",
}

# Review-decision markers: every decision notification carries one
DECISION_EMOJI = {
    "approved": "✅",
    "denied": "❌",
    "changes_requested": "↩️",
}

DECISION_LABEL = {
    "approved": "Approved",
    "denied": "Denied",
    "changes_requested": "Changes requested",
}

# Root header emoji tracks the CURRENT status of the request.
ROOT_STATUS_EMOJI = {
    "pending_review": "🔎",
    "approved": "✅",
    "denied": "❌",
    "changes_requested": "↩️",
    "activated": "🔓",
    "discarded": "🗑️",
    "cancelled": "🗑️",
    "waiting": "⏳",
}

ROOT_STATUS_LABEL = {
    "pending_review": "pending review",
    "approved": "approved",
    "denied": "denied",
    "changes_requested": "changes requested",
    "activated": "activated",
    "discarded": "discarded",
    "cancelled": "cancelled",
    "waiting": "waiting for review",
}

# User-quoted text is truncated so Bot API message limits hold.
MAX_QUOTE_CHARS = 600

# Long quotes collapse behind a tap; short ones render inline.
EXPANDABLE_QUOTE_CHARS = 300

# Thin visual separator between the title and the labelled fields.
SEPARATOR = "────────────────────"


def root_status_emoji(status: str) -> str:
    """Emoji for a thread-root header given the request status."""
    return ROOT_STATUS_EMOJI.get((status or "").strip().lower(), "📌")


# Environment indicator: traffic-light so blast radius reads at a glance.
ENVIRONMENT_EMOJI = {
    "dev": "🟢",
    "development": "🟢",
    "stage": "🟡",
    "staging": "🟡",
    "prod": "🔴",
    "production": "🔴",
}


def environment_emoji(environment: str) -> str:
    """Colour indicator for an environment name (dev/stage/prod)."""
    return ENVIRONMENT_EMOJI.get((environment or "").strip().lower(), "⚪")


def truncate_quoted(text: str, limit: int = MAX_QUOTE_CHARS) -> str:
    """Cap user-quoted text, signalling the cut with an ellipsis."""
    text = text or ""
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "…"
    return text


def _blockquote(text: str) -> str:
    """Render text as a Telegram <pre> code block, escaping HTML.

    Owner preference: code blocks over quote blocks for every card
    section (Request / Why / feedback). User content is always
    truncated and HTML-escaped — never MarkdownV2, this service posts
    HTML.
    """
    quoted = truncate_quoted(text)
    lines = [escape(line) for line in quoted.splitlines() if line.strip()]
    body = "\n".join(lines) if lines else "(empty)"
    return f"<pre>{body}</pre>"


def _now_stamp() -> str:
    """Current timestamp in UTC and US Eastern for replies and footers."""
    now = datetime.now(timezone.utc)
    eastern = now.astimezone(ZoneInfo("America/New_York"))
    return (
        now.strftime("%Y-%m-%d %H:%M UTC")
        + " · "
        + eastern.strftime("%H:%M %Z")
    )


def _short_quote(text: str, limit: int = 200) -> str:
    """Cap feedback for terse replies, signalling the cut with an ellipsis."""
    text = " ".join((text or "").split())
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "…"
    return text


def _footer(request_ref: Optional[str] = None, environment: Optional[str] = None) -> str:
    """Shared footer line: ref + env + product + updated timestamp, italic."""
    timestamp = _now_stamp()
    crumbs = [c for c in (request_ref, environment) if c]
    crumbs += ["IAM-Dynamic", f"updated {timestamp}"]
    return f"<i>{escape(' - '.join(crumbs))}</i>"


def _scrub_token(text: str, token: Optional[str]) -> str:
    """Strip the bot token from error text before it reaches any log.

    The Bot API URL embeds the token, so a raw requests exception would
    print it in full. Logs must never carry credential material.
    """
    if token:
        return text.replace(token, "***")
    return text


class TelegramService:
    """
    Telegram bot notification service

    Sends formatted notifications via the Telegram Bot API for audit and
    approval tracking — a drop-in alternative (or complement) to Slack.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram service

        Args:
            bot_token: Bot API token from @BotFather (optional)
            chat_id: Chat ID that receives the messages (optional)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        if self.enabled:
            logger.info("Telegram service initialized (chat_id=%s)", chat_id)
        else:
            logger.info("Telegram bot not configured, notifications will be skipped")

    @property
    def enabled(self) -> bool:
        """Both the bot token and the chat ID are required to send."""
        return bool(self.bot_token and self.chat_id)

    def _post(
        self, text: str, reply_to_message_id: Optional[int] = None
    ) -> tuple:
        """Post via sendMessage. Returns (ok, message_id).

        message_id is None when the send failed or the response carried no
        parseable id (e.g. mocked responses) — ok still reports delivery.
        """
        if not self.enabled:
            logger.debug("Telegram bot not configured, skipping notification")
            return False, None

        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        body = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_to_message_id is not None:
            body["reply_to_message_id"] = reply_to_message_id
        try:
            response = requests.post(url, json=body, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to send Telegram notification: %s", _scrub_token(str(e), self.bot_token))
            return False, None
        message_id = None
        try:
            data = response.json()
            result = (data.get("result") or {}) if isinstance(data, dict) else {}
            candidate = result.get("message_id")
            message_id = candidate if isinstance(candidate, int) else None
        except (ValueError, AttributeError):
            message_id = None
        logger.info("Telegram notification sent successfully")
        return True, message_id

    def send_message(
        self, text: str, reply_to_message_id: Optional[int] = None
    ) -> bool:
        """
        Send an HTML-formatted message via the Bot API

        Args:
            text: Message text (Telegram HTML markup)
            reply_to_message_id: Reply in the thread rooted at this message
                (plain reply, not a forum topic)

        Returns:
            True if successful, False otherwise
        """
        ok, _ = self._post(text, reply_to_message_id=reply_to_message_id)
        return ok

    def post_message(
        self, text: str, reply_to_message_id: Optional[int] = None
    ) -> Optional[int]:
        """Post and return the new ``message_id`` (None when not posted)."""
        ok, message_id = self._post(text, reply_to_message_id=reply_to_message_id)
        return message_id if ok else None

    def format_credential_reply_message(
        self,
        requester: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> str:
        """Terse threaded reply for a credential issuance event.

        The living card root carries the full details; the reply is a
        two-line event log pointing at it.
        """
        who = escape((requester or "unknown").strip() or "unknown")
        expiry = escape((expires_at or "").strip() or "session expiry")
        return (
            f"🔓 <b>Credentials issued</b> to {who} - expires {expiry}\n"
            "Card above updated."
        )

    def format_credential_message(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
        requester: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> str:
        """
        Format credential issuance message for Telegram.

        Terse event-log reply (kept under the legacy name for
        compatibility): the living card root holds the full details.

        Returns:
            Formatted Telegram HTML message
        """
        return self.format_credential_reply_message(
            requester=requester, expires_at=expires_at
        )

    def send_credential_notification(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
        requester: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> bool:
        """
        Send the terse credential-issuance reply (card root holds details)

        Returns:
            True if successful, False otherwise
        """
        message = self.format_credential_message(
            request_text=request_text,
            risk_level=risk_level,
            duration_hours=duration_hours,
            auto_approved=auto_approved,
            approver=approver,
            request_ref=request_ref,
            environment=environment,
            requester=requester,
            expires_at=expires_at,
        )
        return self.send_message(message, reply_to_message_id=reply_to_message_id)

    def format_decision_reply_message(
        self,
        decision: str,
        reviewer: str,
        feedback: Optional[str] = None,
    ) -> str:
        """Terse threaded reply for a review decision event.

        Two lines: emoji + decision + reviewer + timestamp, with short
        reviewer feedback appended when present. The living card root
        carries the full fields, request, grants, and why.
        """
        emoji = DECISION_EMOJI.get(decision, "❔")
        label = DECISION_LABEL.get(decision, decision)
        stamp = _now_stamp()
        message = (
            f"{emoji} <b>{escape(label)}</b> by {escape(reviewer)}"
            f" - {stamp} - card above updated."
        )
        if (feedback or "").strip():
            message += f"\n<pre>{escape(_short_quote(feedback or ''))}</pre>"
        return message

    def format_decision_message(
        self,
        request_ref: str,
        decision: str,
        reviewer: str,
        requester: str,
        risk_level: str,
        request_text: str,
        feedback: Optional[str] = None,
        why: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> str:
        """
        Format review decision message for Telegram.

        Terse event-log reply (kept under the legacy name for
        compatibility): the living card root holds the full details.

        Returns:
            Formatted Telegram HTML message
        """
        return self.format_decision_reply_message(
            decision=decision, reviewer=reviewer, feedback=feedback
        )

    def send_decision_notification(
        self,
        request_ref: str,
        decision: str,
        reviewer: str,
        requester: str,
        risk_level: str,
        request_text: str,
        feedback: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        why: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> bool:
        """
        Send formatted review decision notification

        Args:
            request_ref: Human-readable request id (req-00001)
            decision: approved, denied, or changes_requested
            reviewer: Admin who decided
            requester: User who asked for access
            risk_level: Risk assessment level
            request_text: The user's access request
            feedback: Reviewer feedback (required for deny/send-back)
            reply_to_message_id: Reply in the thread rooted at this message
            why: Grounded rationale for the decision (Why section)
            environment: Grant environment for the footer

        Returns:
            True if successful, False otherwise
        """
        message = self.format_decision_message(
            request_ref=request_ref,
            decision=decision,
            reviewer=reviewer,
            requester=requester,
            risk_level=risk_level,
            request_text=request_text,
            feedback=feedback,
            why=why,
            environment=environment,
        )
        return self.send_message(message, reply_to_message_id=reply_to_message_id)

    def format_request_root_message(
        self,
        request_ref: str,
        requester: str,
        risk_level: str,
        request_text: str,
        status: str,
        environment: Optional[str] = None,
        duration_hours: Optional[int] = None,
        decided_by: Optional[str] = None,
        decided_at: Optional[str] = None,
        why: Optional[str] = None,
        feedback: Optional[str] = None,
        grants_summary: Optional[str] = None,
        batch_line: Optional[str] = None,
        unit_label: Optional[str] = None,
    ) -> str:
        """Format the living-card thread-root message for a request.

        The title emoji tracks the CURRENT status (pending 🔎, approved
        ✅, denied ❌, sent back ↩️, activated 🔓, discarded 🗑️,
        stale-waiting ⏳), so auto-approved roots are ✅ from birth.
        Every later event for the request lands as a reply to it, and
        status changes rewrite this root via update_thread_root.
        Paired lines stay short: Requester|Risk, Duration|Environment,
        Decided by|When (once decided).
        """
        risk = RISK_EMOJI.get(risk_level.lower(), "🟡")
        emoji = root_status_emoji(status)
        label = ROOT_STATUS_LABEL.get((status or "").strip().lower(), status)
        lines = [
            f"{emoji} <b>{escape(request_ref)} - {escape(label)}</b>",
            SEPARATOR,
            f"<b>Requester:</b> {escape(requester)}  |  <b>Risk:</b> {risk} {escape(risk_level.upper())}",
        ]
        pair = []
        if duration_hours is not None:
            pair.append(f"<b>Duration:</b> {duration_hours}h")
        if environment:
            pair.append(f"<b>Environment:</b> {environment_emoji(environment)} {escape(environment)}")
        if pair:
            lines.append("  |  ".join(pair))
        if (decided_by or "").strip():
            decided = f"<b>Decided by:</b> {escape(decided_by or '')}"
            if (decided_at or "").strip():
                decided += f"  |  <b>When:</b> {escape(decided_at or '')}"
            lines.append(decided)
        lines.append(f"<b>Request:</b>\n{_blockquote(request_text)}")
        if (unit_label or "").strip():
            lines.append(f"<b>This part:</b>\n{_blockquote(unit_label or '')}")
        if (batch_line or "").strip():
            lines.append(f"<b>Split:</b> {escape((batch_line or '').strip())}")
        if (grants_summary or "").strip():
            lines.append(f"<b>What it grants:</b>\n<pre>{escape((grants_summary or '').strip())}</pre>")
        if (why or "").strip():
            lines.append(f"<b>Why:</b>\n{_blockquote(why or '')}")
        if (feedback or "").strip():
            lines.append(f"<b>Reviewer feedback:</b>\n{_blockquote(feedback or '')}")
        lines.append(_footer(request_ref, environment))
        return "\n\n".join(lines)

    def post_thread_root(
        self,
        request_ref: str,
        requester: str,
        risk_level: str,
        request_text: str,
        status: str,
        environment: Optional[str] = None,
        duration_hours: Optional[int] = None,
        decided_by: Optional[str] = None,
        decided_at: Optional[str] = None,
        why: Optional[str] = None,
        feedback: Optional[str] = None,
        grants_summary: Optional[str] = None,
        batch_line: Optional[str] = None,
        unit_label: Optional[str] = None,
    ) -> Optional[int]:
        """Post a thread root and return its ``message_id`` (None if unset)."""
        return self.post_message(
            self.format_request_root_message(
                request_ref=request_ref,
                requester=requester,
                risk_level=risk_level,
                request_text=request_text,
                status=status,
                environment=environment,
                duration_hours=duration_hours,
                decided_by=decided_by,
                decided_at=decided_at,
                why=why,
                feedback=feedback,
                grants_summary=grants_summary,
                batch_line=batch_line,
                unit_label=unit_label,
            )
        )

    def update_thread_root(
        self,
        request_ref: str,
        requester: str,
        risk_level: str,
        request_text: str,
        status: str,
        message_id: Optional[int],
        environment: Optional[str] = None,
        duration_hours: Optional[int] = None,
        decided_by: Optional[str] = None,
        decided_at: Optional[str] = None,
        why: Optional[str] = None,
        feedback: Optional[str] = None,
        grants_summary: Optional[str] = None,
        batch_line: Optional[str] = None,
        unit_label: Optional[str] = None,
    ) -> bool:
        """Rewrite the thread root in place to reflect the current status.

        Uses editMessageText (the bot edits its own root). When the bot
        is unconfigured or there is no root, this is a no-op returning
        False. Root failures never fail the request flow.
        """
        if not self.enabled or not message_id:
            return False
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/editMessageText"
        body = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "text": self.format_request_root_message(
                request_ref=request_ref,
                requester=requester,
                risk_level=risk_level,
                request_text=request_text,
                status=status,
                environment=environment,
                duration_hours=duration_hours,
                decided_by=decided_by,
                decided_at=decided_at,
                why=why,
                feedback=feedback,
                grants_summary=grants_summary,
                batch_line=batch_line,
                unit_label=unit_label,
            ),
            "parse_mode": "HTML",
        }
        try:
            response = requests.post(url, json=body, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to update Telegram thread root: %s", _scrub_token(str(e), self.bot_token))
            return False
        try:
            data = response.json()
        except ValueError:
            return True
        if isinstance(data, dict) and data.get("ok") is False:
            logger.error("Telegram root update failed: %s", data)
            return False
        return True

    def set_status_reaction(
        self, message_id: Optional[int], status: str
    ) -> bool:
        """Set the bot's status reaction on the root message.

        Uses setMessageReaction with the same emoji as the root header,
        replacing any previous reaction (a single bot reaction is kept).
        Best effort: many chat types restrict bot reactions, so failures
        are logged-and-False, never raised.
        """
        if not self.enabled or not message_id:
            return False
        emoji = ROOT_STATUS_EMOJI.get((status or "").strip().lower())
        if emoji is None:
            return False
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/setMessageReaction"
        body = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
        }
        try:
            response = requests.post(url, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("Telegram status reaction not set: %s", _scrub_token(str(e), self.bot_token))
            return False
        return isinstance(data, dict) and data.get("ok") is True

    def format_error_message(
        self,
        error_type: str,
        request_text: str,
        error_details: str,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> str:
        """
        Format error message for Telegram

        Args:
            error_type: Type of error (e.g., "Policy Generation", "Credential Issuance")
            request_text: The user's access request
            error_details: Error details
            request_ref: Human-readable request id for the footer
            environment: Grant environment for the footer

        Returns:
            Formatted Telegram HTML message
        """
        return (
            f"⚠️ <b>Error — {escape(error_type)}</b>\n"
            f"{SEPARATOR}\n"
            f"<b>Request:</b>\n{_blockquote(request_text)}\n\n"
            f"<b>Details:</b>\n<pre>{escape(truncate_quoted(error_details))}</pre>\n\n"
            f"{_footer(request_ref, environment)}"
        )

    def send_error_notification(
        self,
        error_type: str,
        request_text: str,
        error_details: str,
        reply_to_message_id: Optional[int] = None,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> bool:
        """
        Send error notification to Telegram

        Args:
            error_type: Type of error
            request_text: The user's access request
            error_details: Error details
            reply_to_message_id: Reply in the thread rooted at this message
            request_ref: Human-readable request id for the footer
            environment: Grant environment for the footer

        Returns:
            True if successful, False otherwise
        """
        message = self.format_error_message(
            error_type=error_type,
            request_text=request_text,
            error_details=error_details,
            request_ref=request_ref,
            environment=environment,
        )
        return self.send_message(message, reply_to_message_id=reply_to_message_id)
