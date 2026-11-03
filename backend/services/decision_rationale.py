"""Deterministic decision rationale for review notifications.

Builds the "why" behind an approval/denial as a short narrative from
facts already stored at policy time — never invented. The narrative
names what the requester is doing (privilege level + top actions from
the STORED policy), which resources it touches, who decided, the grant
window, and the work item when one is referenced. Reviewer feedback is
paraphrased as a clause (the feedback section of the notification still
quotes it verbatim). Output is capped so it fits in chat notifications.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from services.policy_summary import (
    policy_actions,
    policy_resources,
    privilege_level,
    short_resource,
)

MAX_RATIONALE_CHARS = 500

# Ticket/work-item references: CHG-1234, INC12345, AB-12, ticket #42.
TICKET_RE = re.compile(
    r"(CHG-\d+|INC\d+|[A-Z]{2,}-\d+|ticket\s*#?\d+)",
    re.IGNORECASE,
)

DECISION_LABEL = {
    "approved": "Approved",
    "denied": "Denied",
    "changes_requested": "Sent back for changes",
}


def _clip(text: str, limit: int = MAX_RATIONALE_CHARS) -> str:
    text = " ".join((text or "").split())
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "…"
    return text


def _clean_evaluation_text(text: str) -> str:
    """Strip stale labelling prefixes from stored evaluation prose."""
    cleaned = " ".join((text or "").split()).strip()
    for prefix in ("Evaluation summary:", "Approver note:", "Summary:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip(" -–—:")
    return cleaned


def extract_ticket_ref(*texts: Any) -> Optional[str]:
    """First work-item reference across the given texts, if any."""
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            continue
        match = TICKET_RE.search(text)
        if match:
            return match.group(1).strip()
    return None


def _resource_phrase(resource: str) -> str:
    """Human phrasing for one resource ARN (wildcard-aware)."""
    resource = (resource or "").strip()
    if resource == "*":
        return "all AWS resources"
    if "*" in resource:
        short = short_resource(resource).replace("/*", "").rstrip("*")
        return f"all {short} resources"
    return short_resource(resource)


def _resource_clause(resources: list[str]) -> str:
    if not resources:
        return "unspecified resources"
    shown = [_resource_phrase(r) for r in resources[:4]]
    extra = len(resources) - len(shown)
    text = ", ".join(shown)
    if extra:
        text += f" (+{extra} more)"
    return text


def build_decision_rationale(
    stored: dict,
    decision: str,
    reviewer: str,
    feedback: Optional[str] = None,
) -> str:
    """Explain a review decision as a narrative built from stored facts.

    Args:
        stored: The persisted request row (requester, request_text,
            policy, risk, explanation, approver_note, narrative,
            auto_approved, duration, environment, ...). Missing keys
            are tolerated.
        decision: approved, denied, or changes_requested.
        reviewer: Admin (or system) who decided.
        feedback: Reviewer feedback, if any.

    Returns:
        A plain-text narrative of at most ~500 characters. Never
        contains the literal prefix "Evaluation summary:".
    """
    stored = stored if isinstance(stored, dict) else {}
    decision = (decision or "").strip().lower()
    label = DECISION_LABEL.get(decision, decision or "Decided")
    reviewer = (reviewer or "unknown").strip() or "unknown"
    requester = str(stored.get("requester") or "unknown").strip() or "unknown"
    feedback = (feedback or "").strip()

    policy = stored.get("policy") if isinstance(stored.get("policy"), dict) else {}
    actions = policy_actions(policy)
    resources = policy_resources(policy)
    level = privilege_level(actions)
    top_actions = ", ".join(actions[:2]) if actions else "the requested access"

    first = (
        f"{requester} is performing {level} tasks ({top_actions}) "
        f"against {_resource_clause(resources)}."
    )

    duration = stored.get("duration")
    environment = (stored.get("environment") or "").strip()
    window = ""
    if duration and environment:
        window = f" for a short {duration}h window in {environment}"
    elif duration:
        window = f" for a short {duration}h window"
    elif environment:
        window = f" in {environment}"

    narrative = stored.get("narrative") if isinstance(stored.get("narrative"), dict) else {}
    ticket = extract_ticket_ref(
        stored.get("request_text"),
        narrative.get("summary_plain") if isinstance(narrative, dict) else "",
        feedback,
    )
    second = f"{label} by {reviewer}{window}."
    if ticket:
        second += f" Based on work item {ticket}."

    tail_parts: list[str] = []
    if decision == "approved" and bool(stored.get("auto_approved")):
        tail_parts.append("Low risk auto-approved per policy.")
    if feedback:
        tail_parts.append(f"Per reviewer feedback: {_clip(feedback, 140)}")
    else:
        evaluation = _clean_evaluation_text(
            str(narrative.get("approver_plain") or "").strip()
            or str(stored.get("approver_note") or "").strip()
            or str(narrative.get("summary_plain") or "").strip()
            or str(stored.get("explanation") or "").strip()
        )
        if evaluation:
            tail_parts.append(_clip(evaluation, 200))

    text = f"{first} {second}"
    if tail_parts:
        text += " " + " ".join(tail_parts)
    return _clip(text)
