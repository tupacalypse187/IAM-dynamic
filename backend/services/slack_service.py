"""
Slack notification service

Sends audit notifications via Slack Incoming Webhooks using Block Kit
(https://api.slack.com/block-kit) — the current best practice for
formatted Slack messages — with a plain-text fallback for clients and
notification previews that don't render blocks.
"""
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Colored status circles so risk is scannable without reading
RISK_EMOJI = {
    "low": ":large_green_circle:",
    "medium": ":large_yellow_circle:",
    "high": ":large_orange_circle:",
    "critical": ":red_circle:",
}

# Headers are plain_text (shortcodes don't render there): real glyphs only
DECISION_HEADER_EMOJI = {
    "approved": "✅",
    "denied": "❌",
    "changes_requested": "↩️",
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

# Long-form status labels for root headers.
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

# User-quoted text is truncated so Block Kit section limits hold.
MAX_QUOTE_CHARS = 600


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


def _quote_mrkdwn(text: str) -> str:
    """Render user text as a fenced code block, escaped and truncated.

    Owner preference: code blocks over quote blocks for every card
    section (Request / Why / feedback). Backticks in user text are
    neutralized so the fence cannot be broken out of.
    """
    quoted = truncate_quoted(text).replace("`", "'")
    body = _escape_mrkdwn(quoted).strip()
    return f"```{body}```" if body else "```(empty)```"


def _now_stamp() -> str:
    """Current timestamp in UTC and US Eastern for replies and footers."""
    now = datetime.now(timezone.utc)
    eastern = now.astimezone(ZoneInfo("America/New_York"))
    return (
        now.strftime("%Y-%m-%d %H:%M UTC")
        + " · "
        + eastern.strftime("%H:%M %Z")
    )


def _footer(request_ref: Optional[str] = None, environment: Optional[str] = None) -> Dict[str, Any]:
    """Shared context footer: ref - env - product - updated timestamp."""
    timestamp = _now_stamp()
    crumbs = [c for c in (request_ref, environment) if c]
    crumbs += ["IAM-Dynamic", f"updated {timestamp}"]
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": " - ".join(crumbs)}],
    }

DECISION_LABEL = {
    "approved": "Approved",
    "denied": "Denied",
    "changes_requested": "Changes requested",
}


def _escape_mrkdwn(text: str) -> str:
    """
    Neutralize user-controlled text inside mrkdwn.

    Slack has no mrkdwn escape syntax; per Slack's own formatting guidance
    (https://api.slack.com/reference/surfaces/formatting#escaping), replacing
    &, <, and > with their HTML entities prevents link, mention, and
    broadcast-command injection (e.g. <http://phish|Click here> or <!channel>).
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


SLACK_API_POST_MESSAGE = "https://slack.com/api/chat.postMessage"
SLACK_API_REACTIONS_ADD = "https://slack.com/api/reactions.add"
SLACK_API_REACTIONS_REMOVE = "https://slack.com/api/reactions.remove"

# Status reaction pinned on the root post itself (in addition to the
# header emoji): swapped on every status change so the channel list
# shows state without opening the thread. Names are Slack emoji ids.
STATUS_REACTION = {
    "pending_review": "mag",
    "waiting": "hourglass_flowing_sand",
    "approved": "white_check_mark",
    "denied": "x",
    "changes_requested": "leftwards_arrow_with_hook",
    "activated": "unlock",
    "discarded": "wastebasket",
    "cancelled": "wastebasket",
}
SLACK_API_UPDATE_MESSAGE = "https://slack.com/api/chat.update"


def _scrub_secrets(text: str, *secrets) -> str:
    """Strip webhook URLs / bot tokens from error text before logging."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


class SlackService:
    """
    Slack notification service (webhook + Web API).

    Webhook posts (SLACK_WEBHOOK_URL) are top-level only — incoming
    webhooks cannot start or join threads. Threaded one-thread-per-request
    posts need the Web API (SLACK_BOT_TOKEN + SLACK_CHANNEL_ID,
    ``chat:write`` scope): the root post returns a ``ts`` and every later
    event for the request passes it back as ``thread_ts``. When the bot
    token is unset the service keeps the exact webhook top-level behaviour.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
    ):
        """
        Initialize Slack service

        Args:
            webhook_url: Slack webhook URL (optional)
            bot_token: Slack bot token for Web API posts (optional)
            channel_id: Channel ID for Web API posts (optional)
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = channel_id
        if webhook_url:
            logger.info("Slack service initialized with webhook")
        if self.api_enabled:
            logger.info("Slack Web API threading enabled (channel_id=%s)", channel_id)
        if not webhook_url and not self.api_enabled:
            logger.info("Slack not configured, notifications will be skipped")

    @property
    def api_enabled(self) -> bool:
        """Web API posts need both the bot token and the channel ID."""
        return bool(self.bot_token and self.channel_id)

    def _post_via_webhook(self, payload: Dict[str, Any]) -> bool:
        """Unchanged legacy path: top-level webhook post, no thread support."""
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error("Failed to send Slack notification: %s", _scrub_secrets(str(e), self.webhook_url, self.bot_token))
            return False

    def _post_via_api(
        self, payload: Dict[str, Any], thread_ts: Optional[str] = None
    ) -> tuple:
        """Post via chat.postMessage. Returns (ok, ts)."""
        body = {"channel": self.channel_id, **payload}
        if thread_ts is not None:
            body["thread_ts"] = thread_ts
        try:
            response = requests.post(
                SLACK_API_POST_MESSAGE,
                json=body,
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error("Failed to send Slack API notification: %s", _scrub_secrets(str(e), self.webhook_url, self.bot_token))
            return False, None
        if not isinstance(data, dict) or data.get("ok") is not True:
            logger.error("Slack API post failed: %s", data)
            return False, None
        ts = data.get("ts")
        return True, ts if isinstance(ts, str) else None

    def send_payload(
        self, payload: Dict[str, Any], thread_ts: Optional[str] = None
    ) -> bool:
        """
        Send a raw payload to Slack

        Args:
            payload: JSON body for the webhook (blocks and/or text)
            thread_ts: Thread to reply in (Web API only; webhooks ignore
                it and post top-level, preserving legacy behaviour)

        Returns:
            True if successful, False otherwise
        """
        if self.api_enabled:
            ok, _ = self._post_via_api(payload, thread_ts=thread_ts)
            return ok
        if not self.webhook_url:
            logger.debug("Slack not configured, skipping notification")
            return False
        return self._post_via_webhook(payload)

    def post_message(
        self, payload: Dict[str, Any], thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """Post and return the message ``ts`` (Web API only).

        Webhook posts have no timestamp — they still send top-level but
        return None, so callers store no thread root for them.
        """
        if self.api_enabled:
            ok, ts = self._post_via_api(payload, thread_ts=thread_ts)
            return ts if ok else None
        self.send_payload(payload)
        return None

    def send_notification(
        self, message: str, thread_ts: Optional[str] = None
    ) -> bool:
        """
        Send a plain-text notification to Slack

        Args:
            message: Message text to send
            thread_ts: Thread to reply in (Web API only)

        Returns:
            True if successful, False otherwise
        """
        return self.send_payload({"text": message}, thread_ts=thread_ts)

    def format_credential_reply_payload(
        self,
        requester: Optional[str] = None,
        expires_at: Optional[str] = None,
        request_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the terse threaded reply for a credential issuance event.

        The living card root carries the full details; the reply is a
        one-section event log pointing at it.
        """
        who = _escape_mrkdwn((requester or "unknown").strip() or "unknown")
        expiry = _escape_mrkdwn((expires_at or "").strip() or "session expiry")
        stamp = _now_stamp()
        return {
            "text": f"Credentials issued to {who} ({stamp})",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"🔓 *Credentials issued* to {who} - "
                            f"expires {expiry} - card above updated"
                        ),
                    },
                },
            ],
        }

    def format_credential_payload(
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
    ) -> Dict[str, Any]:
        """
        Build a Block Kit payload for a credential issuance notification.

        Terse event-log reply (kept under the legacy name for
        compatibility): the living card root holds the full details.

        Returns:
            Webhook payload with blocks plus a plain-text fallback
        """
        return self.format_credential_reply_payload(
            requester=requester,
            expires_at=expires_at,
            request_ref=request_ref,
        )

    def send_credential_notification(
        self,
        request_text: str,
        risk_level: str,
        duration_hours: int,
        auto_approved: bool,
        approver: Optional[str] = None,
        thread_ts: Optional[str] = None,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
        requester: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> bool:
        """
        Send the terse credential-issuance reply (the card root holds details)

        Returns:
            True if successful, False otherwise
        """
        payload = self.format_credential_payload(
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
        return self.send_payload(payload, thread_ts=thread_ts)

    def format_decision_reply_payload(
        self,
        request_ref: str,
        decision: str,
        reviewer: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the terse threaded reply for a review decision event.

        One section only: emoji + decision + reviewer + timestamp, with
        short reviewer feedback appended when present. The living card
        root carries the full fields, request, grants, and why.
        """
        header_emoji = DECISION_HEADER_EMOJI.get(decision, "❔")
        label = DECISION_LABEL.get(decision, decision)
        stamp = _now_stamp()
        text = (
            f"{header_emoji} *{label}* by {_escape_mrkdwn(reviewer)}"
            f" - {stamp} - card above updated"
        )
        if (feedback or "").strip():
            short = truncate_quoted((feedback or "").strip(), limit=200)
            text += f"\n```{_escape_mrkdwn(short).replace('`', chr(39))}```"
        return {
            "text": f"Request {request_ref} {label.lower()} by {reviewer}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            ],
        }

    def format_decision_payload(
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
    ) -> Dict[str, Any]:
        """
        Build a Block Kit payload for a review decision notification.

        Terse event-log reply (kept under the legacy name for
        compatibility): the living card root holds the full details.
        Extra params (requester, risk_level, request_text, why,
        environment) are accepted for compatibility and ignored.

        Returns:
            Webhook payload with blocks plus a plain-text fallback
        """
        return self.format_decision_reply_payload(
            request_ref=request_ref,
            decision=decision,
            reviewer=reviewer,
            feedback=feedback,
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
        thread_ts: Optional[str] = None,
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
            thread_ts: Thread to reply in (Web API only)
            why: Grounded rationale for the decision (Why section)
            environment: Grant environment for the footer

        Returns:
            True if successful, False otherwise
        """
        payload = self.format_decision_payload(
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
        return self.send_payload(payload, thread_ts=thread_ts)

    def format_request_root_payload(
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
    ) -> Dict[str, Any]:
        """Build the living-card thread-root payload for a request.

        The root is the single complete card, rebuilt by
        update_thread_root on every event. The header emoji tracks the
        CURRENT status (pending 🔎, approved ✅, denied ❌, sent back ↩️,
        activated 🔓, discarded 🗑️, stale-waiting ⏳), so auto-approved
        roots are ✅ from birth. Fields stay short and paired so Slack
        renders them two-per-row: Requester|Risk, Duration|Environment,
        Decided by|When (once decided).
        """
        risk = RISK_EMOJI.get(risk_level.lower(), ":large_yellow_circle:")
        emoji = root_status_emoji(status)
        label = ROOT_STATUS_LABEL.get((status or "").strip().lower(), status)

        fields: list = [
            {"type": "mrkdwn", "text": f"*Requester*\n{_escape_mrkdwn(requester)}"},
            {"type": "mrkdwn", "text": f"*Risk*\n{risk} {risk_level.upper()}"},
        ]
        if duration_hours is not None:
            fields.append(
                {"type": "mrkdwn", "text": f"*Duration*\n{duration_hours}h"}
            )
        if environment:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Environment*\n{environment_emoji(environment)} {_escape_mrkdwn(environment)}",
                }
            )
        if (decided_by or "").strip():
            fields.append(
                {"type": "mrkdwn", "text": f"*Decided by*\n{_escape_mrkdwn(decided_by or '')}"}
            )
            if (decided_at or "").strip():
                fields.append(
                    {"type": "mrkdwn", "text": f"*When*\n{_escape_mrkdwn(decided_at or '')}"}
                )

        blocks: list = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {request_ref} - {label}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {"type": "section", "fields": fields},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Request*\n{_quote_mrkdwn(request_text)}",
                },
            },
        ]
        if (unit_label or "").strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*This part*\n{_quote_mrkdwn(unit_label or '')}",
                    },
                }
            )
        if (batch_line or "").strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Split*\n{_escape_mrkdwn((batch_line or '').strip())}",
                    },
                }
            )
        if (grants_summary or "").strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*What it grants*\n```{_escape_mrkdwn((grants_summary or '').strip())}```",
                    },
                }
            )
        if (why or "").strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Why*\n{_quote_mrkdwn(why or '')}",
                    },
                }
            )
        if (feedback or "").strip():
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Reviewer feedback*\n{_quote_mrkdwn(feedback or '')}",
                    },
                }
            )
        blocks.append(_footer(request_ref, environment))

        return {
            "text": f"{request_ref} {label} ({risk_level.upper()} risk)",
            "blocks": blocks,
        }

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
    ) -> Optional[str]:
        """Post a thread root and return its ``ts`` (None when not posted).

        Falls back to a top-level webhook post (returning None, so no root
        is stored) when the Web API is not configured.
        """
        payload = self.format_request_root_payload(
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
        return self.post_message(payload)

    def update_thread_root(
        self,
        request_ref: str,
        requester: str,
        risk_level: str,
        request_text: str,
        status: str,
        thread_ts: Optional[str],
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

        Uses chat.update (Web API only — needs ``chat:write``, already
        granted). Webhook-only setups and missing roots are a no-op
        returning False. Root failures never fail the request flow.
        """
        if not self.api_enabled or not thread_ts:
            return False
        payload = self.format_request_root_payload(
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
        body = {"channel": self.channel_id, "ts": thread_ts, **payload}
        try:
            response = requests.post(
                SLACK_API_UPDATE_MESSAGE,
                json=body,
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error("Failed to update Slack thread root: %s", _scrub_secrets(str(e), self.webhook_url, self.bot_token))
            return False
        if not isinstance(data, dict) or data.get("ok") is not True:
            logger.error("Slack root update failed: %s", data)
            return False
        return True

    def _reaction_call(self, url: str, thread_ts: str, name: str) -> bool:
        """One reactions.add/remove call. Returns Slack's ok flag."""
        try:
            response = requests.post(
                url,
                json={"channel": self.channel_id, "timestamp": thread_ts, "name": name},
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error("Slack reaction call failed: %s", _scrub_secrets(str(e), self.webhook_url, self.bot_token))
            return False
        return isinstance(data, dict) and data.get("ok") is True

    def set_status_reaction(
        self, thread_ts: Optional[str], status: str
    ) -> bool:
        """Pin the status reaction on the root post, swapping out the old.

        Reactions show in the channel list without opening the thread.
        Every known status reaction is removed first (not-reacted errors
        are ignored), then the current one is added. Web API only
        (``reactions:write``); webhook mode is a no-op returning False.
        """
        if not self.api_enabled or not thread_ts:
            return False
        target = STATUS_REACTION.get((status or "").strip().lower())
        if target is None:
            return False
        for name in set(STATUS_REACTION.values()):
            if name != target:
                self._reaction_call(SLACK_API_REACTIONS_REMOVE, thread_ts, name)
        return self._reaction_call(SLACK_API_REACTIONS_ADD, thread_ts, target)

    def format_error_payload(
        self,
        error_type: str,
        request_text: str,
        error_details: str,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a Block Kit payload for an error notification

        Args:
            error_type: Type of error (e.g., "Policy Generation", "Credential Issuance")
            request_text: The user's access request
            error_details: Error details
            request_ref: Human-readable request id for the footer
            environment: Grant environment for the footer

        Returns:
            Webhook payload with blocks plus a plain-text fallback
        """
        return {
            "text": f"IAM-Dynamic error: {error_type}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"⚠️ Error — {error_type}",
                        "emoji": True,
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Request*\n{_quote_mrkdwn(request_text)}",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Details*\n```{_escape_mrkdwn(truncate_quoted(error_details))}```"},
                },
                _footer(request_ref, environment),
            ],
        }

    def send_error_notification(
        self,
        error_type: str,
        request_text: str,
        error_details: str,
        thread_ts: Optional[str] = None,
        request_ref: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> bool:
        """
        Send error notification to Slack

        Args:
            error_type: Type of error
            request_text: The user's access request
            error_details: Error details
            thread_ts: Thread to reply in (Web API only)
            request_ref: Human-readable request id for the footer
            environment: Grant environment for the footer

        Returns:
            True if successful, False otherwise
        """
        payload = self.format_error_payload(
            error_type=error_type,
            request_text=request_text,
            error_details=error_details,
            request_ref=request_ref,
            environment=environment,
        )
        return self.send_payload(payload, thread_ts=thread_ts)
